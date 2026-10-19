"""Check the simulation-only FP32 model against exact rational arithmetic."""
import argparse
from fractions import Fraction
from pathlib import Path
import random
import subprocess

def power2(e):
    return Fraction(2**e) if e >= 0 else Fraction(1, 2**(-e))

def decode(bits):
    exponent = (bits >> 23) & 255
    significand = bits & 0x7fffff
    if exponent:
        significand |= 1 << 23
    value = significand * power2((exponent - 127 if exponent else -126) - 23)
    return -value if bits >> 31 else value

def encode(value, zero_sign=0):
    if not value:
        return zero_sign << 31
    sign = int(value < 0)
    value = abs(value)
    exponent = value.numerator.bit_length() - value.denominator.bit_length()
    if value < power2(exponent):
        exponent -= 1
    quantum = max(exponent - 23, -149)
    scaled = value / power2(quantum)
    q, rem = divmod(scaled.numerator, scaled.denominator)
    q += (2*rem > scaled.denominator or
          (2*rem == scaled.denominator and q % 2 == 1))
    if exponent < -126:
        return (sign << 31) | q
    if q == 1 << 24:
        exponent += 1
        q >>= 1
    if exponent > 127:
        return (sign << 31) | 0x7f800000
    return (sign << 31) | ((exponent+127) << 23) | (q & 0x7fffff)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--icarus-root", type=Path, default=Path("C:/iverilog"))
    args = parser.parse_args()
    out = args.output_root.resolve()
    out.mkdir(parents=True, exist_ok=False)
    root = Path(__file__).resolve().parent.parent
    directed = [0,0x80000000,1,0x007fffff,0x00800000,0x00800001,
                0x3f800000,0x3f800001,0xbf800000,0x40400000,
                0x3eaaaaab,0x3eaaaaaa,0x33800000,0x33800001,
                0x3f7fffff,0x7f7fffff,0xff7fffff]
    pairs = [(a,b) for a in directed for b in directed]
    rng = random.Random(20260913)
    for _ in range(12000):
        a,b = rng.getrandbits(32),rng.getrandbits(32)
        if ((a>>23)&255) != 255 and ((b>>23)&255) != 255:
            pairs.append((a,b))
    # Exercise cancellation and halfway cases beyond uniform random coverage.
    for _ in range(4000):
        a = rng.randrange(0x00800000,0x7f7ffff0)
        pairs.append((a, (a+rng.randrange(-4,5)) | 0x80000000))
    with (out/"vectors.hex").open("w", encoding="ascii") as f:
        for a,b in pairs:
            av,bv=decode(a),decode(b)
            m=encode(av*bv,(a^b)>>31)
            s=encode(av+bv,(a&b)>>31)
            f.write(f"{a:08x} {b:08x} {m:08x} {s:08x}\n")
    snapshot=out/"reference.vvp"
    sources=[root/"tb/tb_cats_r4_b3_fp32_mocks.sv",
             root/"tb/tb_cats_r4_b3_fp32_reference.sv"]
    with (out/"compile.log").open("w") as log:
        subprocess.run([str(args.icarus_root/"bin/iverilog.exe"),"-g2012",
                        "-s","tb_cats_r4_b3_fp32_reference","-o",str(snapshot),
                        *map(str,sources)],stdout=log,stderr=subprocess.STDOUT,check=True)
    result=subprocess.run([str(args.icarus_root/"bin/vvp.exe"),str(snapshot),
                           f"+VECTORS={out/'vectors.hex'}"],
                          text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
    (out/"run.log").write_text(result.stdout,encoding="utf8")
    print(result.stdout)
    if result.returncode or "PASS FP32 reference" not in result.stdout:
        raise SystemExit("FP32 reference failed; inspect preserved logs")
if __name__ == "__main__":
    main()
