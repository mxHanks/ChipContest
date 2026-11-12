"""S3-Y32 output and transport profile; the legacy MAC is unchanged."""
from fractions import Fraction

from . import fixed16_acc48 as legacy

FORMAT_ID = 'fixed16_acc48_y32_rne9_v1'
OUTPUT_BITS, OUTPUT_EXP, RIGHT_SHIFT = 32, -18, 9
Y48_MIN = -(1 << 39) - 64 * ((1 << 30) - (1 << 15))
Y48_MAX = (1 << 39) - 1 + 64 * (1 << 30)


def quantize_result(value):
    """Round a reachable old integer result to signed32, nearest ties-even."""
    value = legacy.checked_signed(value, 48, 'y48')
    if not Y48_MIN <= value <= Y48_MAX:
        raise ValueError('y48 outside the fixed64 signed16/signed40 MAC domain')
    quotient, remainder = divmod(value, 1 << RIGHT_SHIFT)
    quotient += int(remainder > 256 or (remainder == 256 and quotient & 1))
    return legacy.checked_signed(quotient, OUTPUT_BITS, 'y32')


def decode_result(value):
    return Fraction(legacy.checked_signed(value, OUTPUT_BITS, 'y32'), 1 << 18)


def quantize_output(y48):
    if len(y48) != legacy.ROWS or any(len(row) != legacy.COLS for row in y48):
        raise ValueError('Y must have shape [99,256]')
    return [[quantize_result(value) for value in row] for row in y48]


def linear99x64x256(x, w, bias):
    return quantize_output(legacy.linear99x64x256(x, w, bias))


def pack_weight_source(weights):
    """Row-major W: consecutive signed16 values become low/high16 of a word."""
    if len(weights) != legacy.INNER or any(len(row) != legacy.COLS for row in weights):
        raise ValueError('W must have shape [64,256]')
    flat = [legacy.checked_signed(v, 16, 'weight') for row in weights for v in row]
    return [(flat[i] & 0xffff) | ((flat[i+1] & 0xffff) << 16)
            for i in range(0, len(flat), 2)]


def profile(shared_w_packed=False, output_y32=True):
    """Explicit metadata for a versioned output and shared-source layout."""
    if type(shared_w_packed) is not bool or type(output_y32) is not bool:
        raise TypeError('layout selectors must be bool')
    if not output_y32 and not shared_w_packed:
        raise ValueError('legacy output transport is only an independent packed-W ablation')
    return dict(format=FORMAT_ID if output_y32 else 'fixed16_acc48_wpacked16_v1',
                rows=99, inner=64, cols=256,
                x_bits=16, w_bits=16, bias_bits=40, accumulator_bits=48,
                y_bits=OUTPUT_BITS if output_y32 else 48,
                y_exp=OUTPUT_EXP if output_y32 else -27,
                output_right_shift=RIGHT_SHIFT if output_y32 else 0,
                rounding='nearest_ties_even' if output_y32 else 'exact', saturation=False,
                shared_base='0xa0000000',
                x=dict(offset='0x00000', bytes=25344, layout='signed16_in_32bit_slot'),
                w=dict(offset='0x08000', bytes=32768 if shared_w_packed else 65536,
                       layout='row_major_two_signed16_per_word' if shared_w_packed
                       else 'row_major_signed16_in_32bit_slot'),
                bias=dict(offset='0x18000', bytes=2048, layout='signed40_in_64bit_slot'),
                y=dict(offset='0x20000', bytes=101376 if output_y32 else 202752,
                       layout='row_major_signed32' if output_y32 else 'row_major_signed48_in_64bit_slot'),
                host=dict(offset='0x7f000', bytes=4096))
