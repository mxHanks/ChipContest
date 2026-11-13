"""Check exact observable states/events in windows, independent of extraction."""
from pathlib import Path
import random
import subprocess
import sys
import tempfile
import unittest

BINARY = Path(sys.argv.pop(1)).resolve()
HEADER = """$date synthetic $end
$version test $end
$timescale
1 fs
$end
$scope module dut $end
$var wire 1 ! clock $end
$var wire 4 \" data [3:0] $end
$var wire 4 \" data_alias [3:0] $end
$var real 64 ~ analog $end
$upscope $end
$enddefinitions $end
"""


def semantic_projection(vcd, windows):
    """Project raw states/events at target windows; do not implement a slicer."""
    body = vcd.split("$enddefinitions $end\n", 1)[1]
    now = 0
    events = []
    for line in body.splitlines():
        if not line or line.startswith("$"):
            continue
        if line.startswith("#"):
            now = int(line[1:])
        elif line[0] in "01xXzZ":
            events.append((now, line[1:], line[0]))
        else:
            value, identifier = line.split()
            events.append((now, identifier, value))
    result = []
    for begin, end in windows:
        state = {}
        for t, identifier, value in events:
            if t < begin:
                state[identifier] = value
        result.append((state, [(t, i, v) for t, i, v in events if begin <= t <= end]))
    return result


class WindowExtraction(unittest.TestCase):
    def run_extract(self, body, padded, observed=None, expected_exit=0):
        original = HEADER + body
        with tempfile.TemporaryDirectory(prefix="xu-vcd-test-") as temp:
            root = Path(temp)
            (root / "raw.vcd").write_text(original)
            (root / "windows.tsv").write_text("".join(f"{a}\t{b}\n" for a, b in padded))
            result = subprocess.run(
                [str(BINARY), str(root / "raw.vcd"), str(root / "windows.tsv"),
                 str(root / "sliced.vcd")], capture_output=True, text=True)
            self.assertEqual(result.returncode, expected_exit, result.stderr)
            if expected_exit:
                return result
            sliced = (root / "sliced.vcd").read_text()
            self.assertEqual(sliced.split("$enddefinitions $end\n")[0],
                             original.split("$enddefinitions $end\n")[0])
            self.assertEqual(semantic_projection(original, observed or padded),
                             semantic_projection(sliced, observed or padded))
            return result

    def test_unknown_vector_real_alias_and_gap_states(self):
        body = """#0
$dumpvars
x!
bx \"
r1.5 ~
$end
#10
1!
b0101 \"
#17
0!
b10xz \"
#25
r2.5 ~
#30
1!
b1111 \"
#40
z!
#50
0!
1!
b0 \"
#60
r0.5 ~
#100
0!
"""
        self.run_extract(body, [(15, 25), (40, 60)], [(16, 24), (41, 59)])

    def test_no_events_in_whole_window(self):
        self.run_extract("#0\n$dumpvars\n0!\nb0 \"\nr1 ~\n$end\n#100\n1!\n",
                         [(10, 20), (30, 40), (80, 90)])

    def test_delayed_initial_dump(self):
        self.run_extract("#8\n$dumpvars\n0!\nb0011 \"\nr1 ~\n$end\n#20\n1!\n#50\n",
                         [(15, 25)])

    def test_random_multiple_windows_including_boundaries(self):
        for seed in range(40):
            rng = random.Random(seed)
            lines = ["#0", "$dumpvars", "x!", "bxxxx \"", "r0 ~", "$end"]
            for t in range(1, 101):
                lines.append(f"#{t}")
                if rng.randrange(3):
                    lines.append(rng.choice("01xz") + "!")
                if rng.randrange(3):
                    lines.append("b" + "".join(rng.choice("01xz") for _ in range(4)) + ' "')
                if rng.randrange(5) == 0:
                    lines.append("r" + str(rng.randrange(8)) + " ~")
            self.run_extract("\n".join(lines) + "\n", [(10, 20), (40, 60), (80, 95)])

    def test_runtime_dumpoff_refuses_unverifiable_trace(self):
        self.run_extract("#0\n$dumpvars\n0!\nb0 \"\nr1 ~\n$end\n#30\n$dumpoff\n#100\n",
                         [(10, 20)], expected_exit=1)

    def test_missing_initial_value_refuses(self):
        self.run_extract("#0\n$dumpvars\n0!\nb0 \"\n$end\n#100\n",
                         [(10, 20)], expected_exit=1)

    def test_truncated_input_refuses(self):
        self.run_extract("#0\n$dumpvars\n0!\nb0 \"\nr1 ~\n$end\n#15\n",
                         [(10, 20)], expected_exit=1)


if __name__ == "__main__":
    unittest.main()
