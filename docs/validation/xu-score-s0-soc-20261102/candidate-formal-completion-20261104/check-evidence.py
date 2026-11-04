#!/usr/bin/env python3
"""xu: verify archived FM27/FM37 bytes and the exact recorded proof boundary."""
import argparse
import hashlib
import json
import lzma
from pathlib import Path, PurePosixPath
import re
import tarfile

HERE = Path(__file__).resolve().parent
BASE = "/storage2/2026contest/server4/s4_23usr/Desktop/xu-score-optimization-20261102/"
EXPORT_SHA = "13ee20401b85fd3d7d241e77fa8dca908e73b02d08c90687265ec953e6af9f05"
MANIFEST_SHA = "dd5f1135a7a593e0027f991bea82ddfbfabfc4e557c0b732543755fa1258c20f"
CONFIG = {
    "s2d": ("candidate-repaired-formality-20261103-27", "s2d-ppa-campaign-20261103-02/s2d/ppa/", "s2d-hold-gating-repair-20261103-19/", "7f1c1efaa27d9eb06a6e8a1979d43df3b7a0eaadb992c1096c4bf36f19477bab", 155, 336, [17136, 0, 0, 0, 144, 26121, 39, 43440], 11772),
    "pe32": ("candidate-repaired-formality-20261103-27", "s3-pe32-ppa-campaign-20261103-01/ppa/", "pe32-hold-gating-repair-20261103-21/", "8aa1d86f72e4752e35a117ffa5359cd4cb76f1fc11130f3f178693ed584b8bbb", 158, 352, [17952, 0, 0, 0, 144, 29623, 39, 47758], 11042),
    "pe64": ("pe64-formality-campaign-20261103-37", "s3-pe64-ppa-campaign-20261103-02/ppa/", None, "3e503963574a49d1111facf23b04877ccffed1eb317912871cbd7796593009ce", 163, 384, [19584, 0, 0, 0, 144, 35770, 39, 55537], 11431),
}


def require(ok, message):
    if not ok:
        raise ValueError(message)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def safe(path):
    p = PurePosixPath(path)
    require(path and not p.is_absolute() and ".." not in p.parts and str(p) == path, "unsafe path: " + path)
    return p


def one(pattern, text):
    found = re.findall(pattern, text, re.M)
    require(len(found) == 1, "expected one match: " + pattern)
    return found[0]


def check(source_export=None):
    manifest_bytes = (HERE / "source-export-manifest.json").read_bytes()
    require(sha(manifest_bytes) == MANIFEST_SHA, "original export manifest SHA")
    original = json.loads(manifest_bytes)
    require(len(original) == 168 and len({x["path"] for x in original}) == 168, "168 unique source payloads")
    original = {x["path"]: x for x in original}
    for path in original:
        safe(path)
    selected = json.loads((HERE / "selected-manifest.json").read_bytes())
    require(selected["schema"] == "xu-candidate-formal-completion-v1", "selected schema")
    require(selected["source_export"] == {"name": "next-results-export-53.tar.xz", "bytes": 1128868, "sha256": EXPORT_SHA, "manifest_sha256": MANIFEST_SHA, "payload_count": 168}, "source identity")
    files = selected["files"]
    require(len(files) == 31 and len({x["path"] for x in files}) == 31, "31 unique selected/context payloads")
    require(len({x["stored_path"] for x in files}) == 31, "unique stored paths")
    data = {}
    for item in files:
        path = str(safe(item["path"]))
        stored = str(safe(item["stored_path"]))
        p = HERE / stored
        require(not any(q.is_symlink() for q in [p, *p.parents]), "symlink: " + stored)
        raw = p.read_bytes()
        require(len(raw) == item["stored_bytes"] and sha(raw) == item["stored_sha256"], "stored bytes: " + path)
        require(item["compression"] in ("none", "xz"), "compression")
        expanded = lzma.decompress(raw) if item["compression"] == "xz" else raw
        require(len(expanded) == item["bytes"] and sha(expanded) == item["sha256"], "expanded bytes: " + path)
        data[path] = expanded
        if path.startswith("raw/"):
            origin = item["origin"]["export_path"]
            require(path == "raw/" + origin and {k: item[k] for k in ("bytes", "sha256")} == {k: original[origin][k] for k in ("bytes", "sha256")}, "source membership")
    actual = {str(p.relative_to(HERE)) for name in ("raw", "context") for p in (HERE / name).rglob("*") if p.is_file() or p.is_symlink()}
    require(actual == {x["stored_path"] for x in files}, "unlisted or missing payload")
    raw_expected = {"raw/" + p for p in original if p.split("/")[0] in {x[0] for x in CONFIG.values()}}
    require(len(raw_expected) == 22 and raw_expected == {p for p in data if p.startswith("raw/")}, "all 22 actual FM payloads")
    if source_export:
        archive = Path(source_export)
        require(archive.stat().st_size == 1128868 and sha(archive.read_bytes()) == EXPORT_SHA, "source tar identity")
        with tarfile.open(archive, "r:xz") as tar:
            members = tar.getmembers()
            require(len(members) == 169 and len({m.name for m in members}) == 169, "169 unique tar entries")
            require({m.name for m in members} == set(original) | {"manifest.json"}, "tar inventory")
            for member in members:
                safe(member.name)
                require(member.isfile(), "non-regular tar entry")
                content = tar.extractfile(member).read()
                if member.name == "manifest.json":
                    require(content == manifest_bytes, "tar manifest")
                else:
                    receipt = original[member.name]
                    require(len(content) == receipt["bytes"] and sha(content) == receipt["sha256"], "tar payload: " + member.name)

    summary = {"schema": "xu-candidate-formal-review-v1", "selected_actual_raw_files": 22, "context_files": 9, "expanded_bytes": sum(x["bytes"] for x in files), "qualification": "NOT_QUALIFIED", "runs": {}}
    server_hashes = {}
    for candidate, (campaign, ppa, repair, mapped_sha, source_count, macros, passing, guidance) in CONFIG.items():
        state = json.loads(data["raw/" + campaign + "/state.json"])
        require(state["status"] == "EXECUTED_REVIEW_PENDING_NOT_QUALIFIED", "campaign terminal status")
        runs = {x["candidate"]: x for x in state["runs"]}
        require(len(runs) == len(state["runs"]) and set(runs) == ({"pe64"} if candidate == "pe64" else {"s2d", "pe32"}), "campaign candidates")
        run = runs[candidate]
        require(run["status"] == "VERIFIED_REVIEW_PENDING_NOT_QUALIFIED" and run["returncode"] == 0 and run["command"] == ["fm_shell", "-f", "verify.tcl"], "actual FM execution")
        before = run["frozen_before"]
        require(before == run["frozen_after"], "before/after freeze")
        require(len(before) == source_count + (7 if repair else 6), "freeze count")
        for path, receipt in before.items():
            require(receipt["path"] == path and receipt["bytes"] > 0 and re.fullmatch(r"[0-9a-f]{64}", receipt["sha256"]), "input receipt")
            require(path not in server_hashes or server_hashes[path] == receipt["sha256"], "cross-run input conflict")
            server_hashes[path] = receipt["sha256"]
        prefix = "raw/" + campaign + "/" + candidate + "/"
        for key, filename in (("log", "fm.log"), ("script", "verify.tcl")):
            receipt = run[key]
            content = data[prefix + filename]
            require(receipt == {"path": BASE + campaign + "/" + candidate + "/" + filename, "bytes": len(content), "sha256": sha(content)}, "executed " + key + " receipt")
            if key == "script":
                server_hashes[receipt["path"]] = receipt["sha256"]
        script = data[prefix + "verify.tcl"].decode()
        log = data[prefix + "fm.log"].decode()
        commands = data[prefix + "fm_shell_command.log"].decode()
        require(script in log, "actual script echoed by FM")
        require(all("#@ " + line in commands for line in script.splitlines()), "command transcript")
        require("Version R-2020.09-SP5" in log and not re.search(r"^Error:", log, re.M), "FM version/errors")
        require(one(r"^(Verification SUCCEEDED)$", log) and one(r"^(XU_FULL_SOC_FORMALITY_PASS)$", log), "unique actual success")
        require("Thank you for using Formality (R)!" in log, "complete FM log")
        ppa = BASE + ppa
        mapped = BASE + repair + "mapped.v" if repair else ppa + "mapped.v"
        require(before[mapped]["sha256"] == mapped_sha and "read_verilog -i {" + mapped + "}" in script, "exact proven mapped netlist")
        prepared = json.loads(data["context/" + candidate + "/prepared.json"])
        rtl = data["context/" + candidate + "/rtl.f"]
        sources = rtl.decode().splitlines()
        require(len(sources) == source_count and len(set(sources)) == source_count, "exact rtl.f source count")
        require(before[ppa + "rtl.f"]["sha256"] == sha(rtl) == prepared["generated_sha256"]["rtl.f"], "rtl.f binding")
        require(set(prepared["source_files"]) == {p.removeprefix(ppa) for p in sources}, "prepared source membership")
        require(all(before[p]["sha256"] == prepared["source_files"][p.removeprefix(ppa)]["sha256"] for p in sources), "all RTL hashes match original PPA")
        require("-f " + ppa + "rtl.f}" in script and "-define {" + " ".join(prepared["implementation"]["defines"]) + "}" in script, "reference list/defines")
        libraries = prepared["implementation"]["libraries"]
        require(len(libraries) == 2 and all(before[x["path"]]["sha256"] == x["sha256"] and "read_db -technology_library {" + x["path"] + "}" in script for x in libraries), "both DBs frozen and read")
        svfs = [ppa + "default.svf"] + ([BASE + repair + "repair.svf"] if repair else [])
        require(re.findall(r"\{([^{}]+\.svf)\}", script) == svfs, "ordered complete SVF chain")
        require(all(p in before and p in log.split("SVF files read:\n", 1)[1].split("SVF files produced:", 1)[0] for p in svfs), "SVFs actually read")
        extras = set(before) - set(sources) - {ppa + "rtl.f", mapped, *svfs, *(x["path"] for x in libraries)}
        old_tcl = "s2d-formality-campaign-20261103-16/s2d/verify.tcl" if candidate == "s2d" else "pe32-formality-campaign-20261103-17/pe32/verify.tcl"
        require(extras == {BASE + old_tcl}, "one retained prior verify Tcl in freeze")
        if repair:
            prior = json.loads(data["context/" + candidate + "/repair-state.json"])
            require(prior["mapped_netlist_sha256"] == mapped_sha and prior["status"] == "EXECUTED_NOT_QUALIFIED", "repair19/21 mapped binding")
            require(all(prior["input_sha256"][x["path"]] == x["sha256"] for x in libraries), "repair/FM DB identity")
        else:
            prior = json.loads(data["context/pe64/ppa-execution.json"])
            require(prior["netlist_sha256"] == mapped_sha and prior["status"] == state["observed_ppa_status"] == "EXECUTED_NOT_QUALIFIED", "original PE64 PPA02 mapped binding")
        for setting in ("set synopsys_auto_setup true", "set hdlin_unresolved_modules black_box"):
            require(setting in script, "explicit FM setup")
        assumptions = re.findall(r"^   set (.+)$", log, re.M)
        require(assumptions == ["hdlin_ignore_parallel_case false", "hdlin_ignore_full_case false", "hdlin_error_on_mismatch_message false", "hdlin_ignore_embedded_configuration true", "verification_set_undriven_signals synthesis", "verification_verify_directly_undriven_output false"], "complete setup assumptions")
        require("Verification results may disagree with a logic simulator." in log, "RTL interpretation warning retained")
        require([int(x) for x in one(r"^Passing \(equivalent\)\s+([\d ]+)$", log).split()] == passing, "passing type/counts")
        require(int(one(r"^ (\d+) Passing compare points$", log)) == passing[-1] == sum(passing[:-1]), "passing total")
        require([int(x) for x in one(r"^Failing \(not equivalent\)\s+([\d ]+)$", log).split()] == [0] * 8, "zero failing points")
        require([int(x) for x in one(r"^  Unread\s+([\d ]+)$", log).split()] == [0, 0, 0, 0, 0, 511, 0, 511], "unread exclusion")
        require([int(x) for x in one(r"^Total\s+:\s+([\d ]+)$", log).split()] == [guidance, 0, 0, 0, guidance], "SVF guidance counts")
        unmatched = data[prefix + "unmatched.rpt"].decode()
        unmatched_count = macros - 320 + 1
        require(tuple(map(int, one(r"^(\d+) Unmatched points \((\d+) reference, (\d+) implementation\):$", unmatched))) == (unmatched_count, unmatched_count, 0), "unmatched summary")
        points = re.findall(r"^  Ref  DFF\s+(\S+)$", unmatched, re.M)
        require(len(points) == len(set(points)) == unmatched_count and sum(p.endswith("/valid_read_reg") for p in points) == macros - 320 and sum(p.endswith("/u_pmu_core/count_reg[15]") for p in points) == 1, "actual unmatched DFF scope")
        require(set(re.findall(r"^ (\d+)\(0\) Unmatched reference\(implementation\) compare points", log, re.M)) == {str(unmatched_count)}, "log/unmatched consistency")
        require(set(re.findall(r"^ (\d+)\(0\) Unmatched reference\(implementation\) unread points", log, re.M)) == {"144"}, "matching-stage unmatched unread points")
        detail = data[prefix + "formality.log"].decode()
        boxes = re.findall(r"^Warning: Cell ([ri]):/WORK/(\S+) references black-box design (\S+) \(FM-158\)$", detail, re.M)
        box_counts = {side: sum(x[0] == side for x in boxes) for side in "ri"}
        require(box_counts == {"r": 321, "i": macros} and len({x[2] for x in boxes}) == 1 and boxes[0][2].endswith("/RAMSP1024X16"), "detailed black-box warnings")
        require(f"321 ({macros}) black-box references found" in log and passing[0] == 51 * macros, "log black-box/BBPin comparison")
        undriven = {side: len(re.findall(r"^Info:  Net " + side + r":/WORK/.* is undriven\.$", detail, re.M)) for side in "ri"}
        require(undriven == {"r": 24, "i": 5166} and "24 (5166) undriven nets found" in log, "full undriven warnings")
        summary["runs"][candidate] = {"campaign": campaign, "returncode": 0, "formal_result": "CONDITIONAL_EQUIVALENCE_PASS", "source_main_commit": prepared["inventory"]["main_commit"], "source_e203_commit": prepared["inventory"]["e203_commit"], "mapped": before[mapped], "rtl_sources": source_count, "frozen_before_after_identical": len(before), "retained_prior_tcl": sorted(extras), "executed_tcl": run["script"], "libraries": [before[x["path"]] for x in libraries], "ordered_svf_inputs": [before[p] for p in svfs], "passing_BBPin_Loop_BBNet_Cut_Port_DFF_LAT_TOTAL": passing, "unread_DFF": 511, "unmatched_reference_implementation": [unmatched_count, 0], "black_box_reference_implementation_warning_counts": box_counts, "undriven_reference_implementation_warning_counts": undriven, "guidance_accepted_rejected_unsupported_unprocessed": [guidance, 0, 0, 0], "auto_setup_assumptions": assumptions}
        summary["runs"][candidate]["matching_stage_unmatched_unread_reference_implementation"] = [144, 0]
    return summary, server_hashes


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-export", help="also verify all 168 payloads in the original tar.xz")
    parser.add_argument("--server-sha256", action="store_true", help="emit sha256sum -c input for every frozen input and actual executed Tcl")
    args = parser.parse_args()
    result, hashes = check(args.source_export)
    if args.server_sha256:
        print("".join(digest + "  " + path + "\n" for path, digest in sorted(hashes.items())), end="")
    else:
        print(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2))
