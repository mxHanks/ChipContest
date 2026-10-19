"""Exact integer reference for the candidate ``fixed16_acc48_v1`` contract.

This is a functional prototype, not evidence of KWT accuracy or silicon PPA.
Only the Python standard library is required. All MAC operations are integers.
"""

from dataclasses import dataclass, field
from fractions import Fraction
import hashlib
import json
import math
from numbers import Integral, Real
from pathlib import Path
import re

FORMAT_ID = "fixed16_acc48_v1"
ROWS, INNER, COLS, LAYERS = 99, 64, 256, 12
X_BITS = W_BITS = 16
BIAS_BITS, Y_BITS = 40, 48
NRMSE_FLOOR = 1e-8


def _integer(value, name):
    if isinstance(value, bool) or not isinstance(value, Integral):
        raise TypeError(f"{name} must be an integer (not bool)")
    return int(value)


def signed_bounds(bits):
    bits = _integer(bits, "bits")
    if bits < 2:
        raise ValueError("bits must be at least 2")
    return -(1 << (bits - 1)), (1 << (bits - 1)) - 1


def checked_signed(value, bits, name="value"):
    value = _integer(value, name)
    lo, hi = signed_bounds(bits)
    if not lo <= value <= hi:
        raise ValueError(f"{name}={value} outside signed {bits}-bit range")
    return value


def _scale(exp):
    exp = _integer(exp, "scale_exp")
    return Fraction(1 << exp, 1) if exp >= 0 else Fraction(1, 1 << -exp)


def _fraction(value):
    if isinstance(value, bool):
        raise TypeError("numeric value must not be bool")
    if isinstance(value, (Integral, Fraction)):
        return Fraction(value)
    if not isinstance(value, Real):
        raise TypeError("numeric value must be a real number or Fraction")
    if not math.isfinite(value):
        raise ValueError("NaN and infinity are not encodable")
    # Preserve the exact represented binary float for deterministic half ties.
    numerator, denominator = value.as_integer_ratio()
    return Fraction(numerator, denominator)


def encode_scalar(value, bits, scale_exp):
    """RNE then signed saturation; real = integer_code * 2**scale_exp."""
    lo, hi = signed_bounds(bits)
    scaled = _fraction(value) / _scale(scale_exp)
    # Fraction.__round__ implements exact round-to-nearest, ties-to-even.
    return min(hi, max(lo, round(scaled)))


def decode_exact(code, bits, scale_exp):
    """Decode to an exact Fraction, with no float conversion or rounding."""
    return checked_signed(code, bits) * _scale(scale_exp)


def decode_scalar(code, bits, scale_exp):
    """Decode to finite binary64; reject overflow and nonzero underflow."""
    exact = decode_exact(code, bits, scale_exp)
    try:
        result = float(exact)
    except OverflowError as exc:
        raise ValueError("decoded value does not fit finite binary64") from exc
    if not math.isfinite(result) or (exact and result == 0.0):
        raise ValueError("decoded value does not fit finite non-underflowed binary64")
    return result


@dataclass(frozen=True)
class Fixed16Scales:
    """Explicit per-layer tensor scales; no implicit or calibrated defaults."""

    x_exp: int
    w_exp: int

    def __post_init__(self):
        object.__setattr__(self, "x_exp", _integer(self.x_exp, "x_exp"))
        object.__setattr__(self, "w_exp", _integer(self.w_exp, "w_exp"))

    @property
    def y_exp(self):
        return self.x_exp + self.w_exp


def _vector(values, length, name):
    try:
        result = tuple(values)
    except TypeError as exc:
        raise TypeError(f"{name} must be a sequence") from exc
    if isinstance(values, (str, bytes)) or len(result) != length:
        raise ValueError(f"{name} must have length {length}")
    return result


def _matrix(values, rows, cols, name):
    return tuple(_vector(row, cols, f"{name}[{r}]")
                 for r, row in enumerate(_vector(values, rows, name)))


def _signed_vector(values, length, bits, name):
    return tuple(checked_signed(v, bits, f"{name}[{i}]")
                 for i, v in enumerate(_vector(values, length, name)))


def _signed_matrix(values, rows, cols, bits, name):
    return tuple(_signed_vector(row, cols, bits, f"{name}[{r}]")
                 for r, row in enumerate(_vector(values, rows, name)))


def dot64(x, w, bias):
    """Exact ordered dot product plus signed40 bias, returned as signed48 int."""
    x = _signed_vector(x, INNER, X_BITS, "x")
    w = _signed_vector(w, INNER, W_BITS, "w")
    accumulator = checked_signed(bias, BIAS_BITS, "bias")
    for k in range(INNER):
        accumulator += x[k] * w[k]
    # The input range proof guarantees this; check protects contract changes.
    return checked_signed(accumulator, Y_BITS, "accumulator")


def linear99x64x256(x, w, bias):
    """Y[r][c]=bias[c]+sum_k X[r][k]*W[k][c], exact Python integers.

    Shapes are fixed to the competition first linear layer. W is not transposed.
    There is no hidden state; each call receives all layer-specific parameters.
    """
    x = _signed_matrix(x, ROWS, INNER, X_BITS, "x")
    w = _signed_matrix(w, INNER, COLS, W_BITS, "w")
    bias = _signed_vector(bias, COLS, BIAS_BITS, "bias")
    result = []
    for row in x:
        out = list(bias)
        for k in range(INNER):
            xv = row[k]
            for c in range(COLS):
                out[c] += xv * w[k][c]
        result.append([checked_signed(v, Y_BITS, "output") for v in out])
    return result


def quantize_linear_inputs(x, w, bias, scales):
    """Encode real-valued full-shape inputs; explicit scales are mandatory."""
    if not isinstance(scales, Fixed16Scales):
        raise TypeError("scales must be Fixed16Scales")
    x = _matrix(x, ROWS, INNER, "x")
    w = _matrix(w, INNER, COLS, "w")
    bias = _vector(bias, COLS, "bias")
    return (
        [[encode_scalar(v, X_BITS, scales.x_exp) for v in row] for row in x],
        [[encode_scalar(v, W_BITS, scales.w_exp) for v in row] for row in w],
        [encode_scalar(v, BIAS_BITS, scales.y_exp) for v in bias],
    )


def decode_output(y, scales):
    if not isinstance(scales, Fixed16Scales):
        raise TypeError("scales must be Fixed16Scales")
    y = _signed_matrix(y, ROWS, COLS, Y_BITS, "y")
    return [[decode_scalar(v, Y_BITS, scales.y_exp) for v in row] for row in y]


@dataclass(frozen=True)
class LayerParameters:
    """Immutable, copied layer parameters; layer IDs are zero-based 0..11."""

    layer_id: int
    weights: tuple
    bias: tuple
    scales: Fixed16Scales

    def __post_init__(self):
        layer = _integer(self.layer_id, "layer_id")
        if not 0 <= layer < LAYERS:
            raise ValueError("layer_id must be in 0..11")
        if not isinstance(self.scales, Fixed16Scales):
            raise TypeError("scales must be Fixed16Scales")
        object.__setattr__(self, "layer_id", layer)
        object.__setattr__(self, "weights", _signed_matrix(
            self.weights, INNER, COLS, W_BITS, "weights"))
        object.__setattr__(self, "bias", _signed_vector(
            self.bias, COLS, BIAS_BITS, "bias"))

    def compute(self, x):
        return linear99x64x256(x, self.weights, self.bias)


def validate_layer_set(parameters):
    """Return parameters ordered by layer ID; require exactly one of each."""
    parameters = _vector(parameters, LAYERS, "parameters")
    if any(not isinstance(p, LayerParameters) for p in parameters):
        raise TypeError("each layer must be LayerParameters")
    if {p.layer_id for p in parameters} != set(range(LAYERS)):
        raise ValueError("parameters must contain each layer_id 0..11 exactly once")
    return tuple(sorted(parameters, key=lambda p: p.layer_id))


def _finite_float(value, name):
    if isinstance(value, bool) or not isinstance(value, (Real, Fraction)):
        raise TypeError(f"{name} must be real")
    try:
        result = float(value)
    except (OverflowError, ValueError) as exc:
        raise ValueError(f"{name} is not representable as finite binary64") from exc
    if not math.isfinite(result):
        raise ValueError(f"{name} must be finite")
    return result


@dataclass
class ErrorSums:
    """Across-sample SSE/reference energy/count, never mean(sample NRMSE)."""

    sum_error_sq: float = field(default=0.0, init=False)
    sum_reference_sq: float = field(default=0.0, init=False)
    count: int = field(default=0, init=False)
    samples: int = field(default=0, init=False)

    def update(self, decoded, reference):
        decoded, reference = tuple(decoded), tuple(reference)
        if not decoded or len(decoded) != len(reference):
            raise ValueError("sample vectors must be nonempty and equal length")
        errors, energies = [], []
        for i, (actual, expected) in enumerate(zip(decoded, reference)):
            actual = _finite_float(actual, f"decoded[{i}]")
            expected = _finite_float(expected, f"reference[{i}]")
            errors.append((actual - expected) * (actual - expected))
            energies.append(expected * expected)
        try:
            sse = math.fsum(errors)
            energy = math.fsum(energies)
            total_sse = math.fsum((self.sum_error_sq, sse))
            total_energy = math.fsum((self.sum_reference_sq, energy))
        except (OverflowError, ValueError) as exc:
            raise ValueError("error statistic overflow") from exc
        if not all(map(math.isfinite, (sse, energy, total_sse, total_energy))):
            raise ValueError("error statistic overflow")
        # Commit only after the entire sample passed validation.
        self.sum_error_sq, self.sum_reference_sq = total_sse, total_energy
        self.count += len(decoded)
        self.samples += 1

    def report(self):
        if self.count == 0:
            raise ValueError("cannot report an empty accumulator")
        error_rms = math.sqrt(self.sum_error_sq / self.count)
        reference_rms = math.sqrt(self.sum_reference_sq / self.count)
        nrmse = error_rms / max(reference_rms, NRMSE_FLOOR)
        if not math.isfinite(nrmse):
            raise ValueError("NRMSE is not finite")
        return {"sum_error_sq": self.sum_error_sq,
                "sum_reference_sq": self.sum_reference_sq,
                "count": self.count, "samples": self.samples,
                "error_rms": error_rms, "reference_rms": reference_rms,
                "nrmse": nrmse}


class LayerNRMSE:
    """Accumulate full 99x256 outputs independently for all twelve layers."""

    def __init__(self):
        self._layers = {}

    def update(self, layer_id, decoded, reference):
        layer_id = _integer(layer_id, "layer_id")
        if not 0 <= layer_id < LAYERS:
            raise ValueError("layer_id must be in 0..11")
        actual = _matrix(decoded, ROWS, COLS, "decoded")
        expected = _matrix(reference, ROWS, COLS, "reference")
        accumulator = self._layers.get(layer_id, ErrorSums())
        accumulator.update((v for row in actual for v in row),
                           (v for row in expected for v in row))
        self._layers[layer_id] = accumulator

    def report(self, require_all_layers=True):
        if not self._layers:
            raise ValueError("no samples have been recorded")
        missing = sorted(set(range(LAYERS)) - self._layers.keys())
        if require_all_layers and missing:
            raise ValueError(f"missing layers: {missing}")
        results = {str(k): v.report() for k, v in sorted(self._layers.items())}
        maximum = max(v["nrmse"] for v in results.values())
        return {"layers": results, "missing_layers": missing,
                "complete_layers": not missing, "max_layer_nrmse": maximum,
                "threshold": 0.03,
                "within_3pct_for_recorded_samples": not missing and maximum <= 0.03,
                "scope": "supplied samples only; not official competition acceptance"}


def write_hex_mem(path, values, bits):
    """One fixed-width two's-complement hex word per line, no address records."""
    signed_bounds(bits)
    values = tuple(checked_signed(v, bits) for v in values)
    if not values:
        raise ValueError("memory image cannot be empty")
    width, mask = (bits + 3) // 4, (1 << bits) - 1
    payload = "".join(f"{v & mask:0{width}x}\n" for v in values)
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(payload, encoding="ascii")
    return {"path": str(path), "bits": bits, "count": len(values),
            "sha256": hashlib.sha256(payload.encode("ascii")).hexdigest()}


def read_hex_mem(path, bits, expected_count=None):
    signed_bounds(bits)
    width, mask = (bits + 3) // 4, (1 << bits) - 1
    lines = Path(path).read_text(encoding="ascii").splitlines()
    if not lines:
        raise ValueError("memory image cannot be empty")
    if expected_count is not None and len(lines) != _integer(expected_count, "expected_count"):
        raise ValueError("memory image has wrong word count")
    result = []
    for line in lines:
        if not re.fullmatch(rf"[0-9a-fA-F]{{{width}}}", line):
            raise ValueError("memory image must contain fixed-width known hex words")
        word = int(line, 16)
        if word > mask:
            raise ValueError("nonzero padding bits in memory image")
        result.append(word - (1 << bits) if word & (1 << (bits - 1)) else word)
    return result


def write_linear_mem_vectors(directory, x, w, bias, scales=None):
    """Validate and export full row-major inputs plus exact expected Y and hashes."""
    x = _signed_matrix(x, ROWS, INNER, X_BITS, "x")
    w = _signed_matrix(w, INNER, COLS, W_BITS, "w")
    bias = _signed_vector(bias, COLS, BIAS_BITS, "bias")
    y = linear99x64x256(x, w, bias)
    if scales is not None and not isinstance(scales, Fixed16Scales):
        raise TypeError("scales must be Fixed16Scales or None for integer-only vectors")
    directory = Path(directory)
    arrays = {"x": (x, X_BITS), "w": (w, W_BITS), "y": (y, Y_BITS)}
    files = {name: write_hex_mem(directory / f"{name}.mem", (v for row in rows for v in row), bits)
             for name, (rows, bits) in arrays.items()}
    files["bias"] = write_hex_mem(directory / "bias.mem", bias, BIAS_BITS)
    manifest = {"format": FORMAT_ID, "scope": "synthetic/function vectors; not KWT accuracy",
                "shape": {"x": [ROWS, INNER], "w": [INNER, COLS], "bias": [COLS], "y": [ROWS, COLS]},
                "layout": "row-major; W[k][column]; bias[column]", "files": files,
                "scales": None if scales is None else {"x_exp": scales.x_exp, "w_exp": scales.w_exp,
                                                       "bias_exp": scales.y_exp, "y_exp": scales.y_exp}}
    (directory / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest
