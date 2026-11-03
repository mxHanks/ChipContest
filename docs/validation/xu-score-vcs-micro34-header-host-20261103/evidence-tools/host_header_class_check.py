"""xu regression: classify vendor VPI headers, retain own -Werror diagnostics."""
from pathlib import Path
import ast
import hashlib
import json
import shutil
import subprocess
import tempfile

HERE = Path(__file__).resolve().parent
HELPER = HERE / "xu_joint_micro34.py"
source = HELPER.read_text()
tree = ast.parse(source)
base_nodes = [node.value for node in ast.walk(tree) if isinstance(node, ast.Assign)
              and any(isinstance(target, ast.Name) and target.id == "base" for target in node.targets)]
assert len(base_nodes) == 1
actual = eval(compile(ast.Expression(base_nodes[0]), "<xu frozen compile flags>", "eval"),
              {"INCLUDE": Path("/xu-vendor-include"), "str": str})
expected = ["gcc", "-std=c99", "-D_POSIX_C_SOURCE=200809L", "-fPIC", "-Wall", "-Wextra",
            "-Wshadow", "-Wstrict-prototypes", "-Werror", "-O2", "-isystem", "/xu-vendor-include"]
assert actual == expected, actual
assert source.count("'-M','-MF'") == 1  # -M retains system-header dependency identity.
assert "EXPECTED_C='cbeadf216665fc0b212ab3e239f299f4c83a64f59df561d8715414e854ed8cb1'" in source
assert "for mode in range(4):" in source
assert '20261103-34' in source and '20261103-23' not in source
cases = []
gcc = shutil.which("gcc")
assert gcc
with tempfile.TemporaryDirectory(prefix="xu-vpi-header-class-") as temporary:
    root = Path(temporary)
    vendor = root / "vendor"
    vendor.mkdir()
    # Synthetic reproducer of the old-style prototype class, not a copy of the vendor header.
    header = vendor / "vpi_user.h"
    header.write_text("extern void (*vlog_startup_routines[])();\n")
    clean = root / "xu_clean.c"
    clean.write_text("#include <vpi_user.h>\nint xu_clean(void) { return 0; }\n")
    bad = root / "xu_bad.c"
    bad.write_text("#include <vpi_user.h>\nint xu_own_old_style() { return 0; }\n")
    flags = actual[:-2]
    for label, include, unit, succeeds in [
        ("vendor-user-header-rejected", ["-I", str(vendor)], clean, False),
        ("vendor-system-header-accepted", ["-isystem", str(vendor)], clean, True),
        ("own-source-warning-retained", ["-isystem", str(vendor)], bad, False),
    ]:
        result = subprocess.run(flags + include + ["-fsyntax-only", str(unit)],
                                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, universal_newlines=True)
        text = result.stdout.replace(str(root), "<xu temporary>")
        (HERE / (label + ".log")).write_text(text)
        assert (result.returncode == 0) == succeeds, (label, result.returncode, text)
        if not succeeds:
            assert "-Werror=strict-prototypes" in text, (label, text)
        cases.append(dict(case=label, returncode=result.returncode, expected_success=succeeds,
                          diagnostics=text))
    dependency = root / "xu.d"
    result = subprocess.run(flags + ["-isystem", str(vendor), "-M", "-MF", str(dependency), str(clean)],
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, universal_newlines=True)
    assert result.returncode == 0 and str(header) in dependency.read_text()
    cases.append(dict(case="system-vendor-header-retained-in-M-dependencies", returncode=0,
                      contains_vendor_header=True))
receipt = dict(status="HOST_HEADER_CLASS_CHECK_PASS_NOT_SERVER_EXECUTION", helper_sha256=hashlib.sha256(HELPER.read_bytes()).hexdigest(),
               gcc_path=gcc, gcc_version=subprocess.check_output([gcc, "--version"], universal_newlines=True).splitlines()[0],
               cases=cases, limitations=["Synthetic header exercises warning class only; actual VCS header is not available locally.",
                                         "No VCS simulation, native SAIF equivalence, power or energy qualification."])
(HERE / "host-header-class-receipt.json").write_text(json.dumps(receipt, sort_keys=True, indent=2)+"\n")
print(json.dumps(dict(status=receipt["status"], cases=len(cases), helper_sha256=receipt["helper_sha256"]), sort_keys=True))
