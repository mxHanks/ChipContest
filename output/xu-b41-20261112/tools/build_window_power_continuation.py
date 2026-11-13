"""Prepare a minimal server-local adaptation of the existing power controller.

No EDA launch. Keeps the original script, raw wave, failed native receipt and
gate binding; records every replacement and verifies both calls are lock scoped.
"""
from pathlib import Path
import ast
import hashlib
import json

R = Path(__file__).resolve().parent


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def main():
    assert str(R) == '/tmp/xu-b41-close-20261111-r1'
    parent = R / 'xu-b41-power-r1.py'
    source = parent.read_text()
    assert len(source.splitlines()) == 62
    history = []

    def replace(old, new):
        nonlocal source
        assert source.count(old) == 1, old
        source = source.replace(old, new)
        history.append({'before': old, 'after': new})

    def replace_line(old, new):
        matches = [line for line in source.splitlines() if line.lstrip() == old]
        assert len(matches) == 1, old
        line = matches[0]
        indent = line[:len(line) - len(line.lstrip())]
        replace(line, '\n'.join(indent + part for part in new))

    replace("O=R/'xu-power-20261112-r1'", "O=R/'xu-power-windowed-20261113-r1'")
    replace("if '--launch' in sys.argv:",
            "import xu_window_power_helpers_r2 as h\n"
            "h.guard_original_terminal()\n"
            "if '--launch' in sys.argv:")
    replace("xu-b41-power-r1.log", "xu-b41-power-windowed-r1.log")
    replace("[sys.executable,str(Path(__file__).resolve())]",
            "[sys.executable,'-B',str(Path(__file__).resolve())]")
    replace("N=R/'xu-closure-20261112-r4/dc/mapped.v';",
            "with (R/'xu-b41-power-windowed-r1.pid.json').open('x') as _pid:\n"
            " json.dump({'pid':h.os.getpid(),'start':Path('/proc/self/stat').read_text().split()[21]},_pid)\n"
            "N=R/'xu-closure-20261112-r4/dc/mapped.v';")
    replace("heavy=runpy.run_path(str(f.SOURCE/'run_once.py'))['heavy_jobs']", "heavy=h.heavy_jobs")
    replace_line("manifest.append(entry);(O/'windows.json').write_text(json.dumps(manifest,indent=2))",
                 ["manifest.append(entry);(O/'windows.json').write_text(json.dumps(manifest,indent=2))",
                  "vcd=h.prepare(variant,entry,O)"])
    replace_line("with (R/'eda.lock').open('a') as lock:",
                 ["body+=h.additional_reports()", "with (R/'eda.lock').open('a') as lock:"])
    replace_line("run=f.execute(O,variant+'-ss',f.PT,body,heavy,2400)",
                 ["run=f.execute(O,variant+'-ss',f.PT,body,heavy,2400)",
                  "entry['payload']=h.payload_case(variant,entry,body,O,f,heavy)"])
    replace_line("print('POWER_NATIVE_COMPLETE',variant,str(run),flush=True)",
                 ["h.publish(entry,O)", "(O/'windows.json').write_text(json.dumps(manifest,indent=2))",
                  "print('POWER_NATIVE_COMPLETE',variant,str(run),flush=True)"])
    tree = ast.parse(source)
    with_nodes = [n for n in ast.walk(tree) if isinstance(n, ast.With)]

    def called(node, owner, method):
        return isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and \
            isinstance(node.func.value, ast.Name) and node.func.value.id == owner and node.func.attr == method

    direct = [n for n in ast.walk(tree) if called(n, 'f', 'execute')]
    payload = [n for n in ast.walk(tree) if called(n, 'h', 'payload_case')]
    assert len(direct) == len(payload) == 1
    assert any(direct[0] in list(ast.walk(w)) and payload[0] in list(ast.walk(w)) for w in with_nodes)
    target = R / 'xu-b41-power-windowed-r1.py'
    with target.open('x') as f:
        f.write(source)
    record = {'status': 'PREPARED_NOT_LAUNCHED', 'parent': str(parent),
              'parent_sha256': sha(parent), 'controller': str(target),
              'controller_sha256': sha(target), 'replacements': history,
              'helper_sha256': sha(R / 'xu_window_power_helpers_r2.py'),
              'principal_and_payload_calls_within_same_lock': True}
    with (R / 'xu-b41-power-windowed-r1.adaptation.json').open('x') as f:
        json.dump(record, f, indent=2)
        f.write('\n')
    print('POWER_CONTINUATION_PREPARED', target.stat().st_size, sha(target))
    print('AST_LOCK_SCOPED', direct[0].lineno, payload[0].lineno)


if __name__ == '__main__':
    main()
