from fractions import Fraction
import random
import unittest

from model import fixed16_acc48 as legacy
from model import s3_y32 as s3


class S3Y32Tests(unittest.TestCase):
    def test_extreme_and_halfway_results_match_exact_fraction(self):
        values = [s3.Y48_MIN, s3.Y48_MAX, -1, 0, 1]
        for q in range(-32, 32):
            values.extend([q*512+255, q*512+256, q*512+257])
        rng = random.Random(20261105)
        values.extend(rng.randint(s3.Y48_MIN, s3.Y48_MAX) for _ in range(1000))
        for value in values:
            result = s3.quantize_result(value)
            self.assertEqual(result, round(Fraction(value, 512)))
            self.assertLessEqual(abs(s3.decode_result(result)-Fraction(value, 1 << 27)),
                                 Fraction(1, 1 << 19))

    def test_invalid_domain_never_silently_saturates(self):
        for value in [s3.Y48_MIN-1, s3.Y48_MAX+1, -(1 << 47), (1 << 47)-1]:
            with self.assertRaises(ValueError):
                s3.quantize_result(value)
        for value in [True, 1.0, None]:
            with self.assertRaises(TypeError):
                s3.quantize_result(value)

    def test_profile_ranges_and_legacy_contract(self):
        self.assertEqual(legacy.FORMAT_ID, 'fixed16_acc48_v1')
        for packed in [False, True]:
            p = s3.profile(packed)
            intervals = [(int(p[k]['offset'], 16), int(p[k]['offset'], 16)+p[k]['bytes'])
                         for k in ['x', 'w', 'bias', 'y', 'host']]
            self.assertTrue(all(a[1] <= b[0] for a, b in zip(intervals, intervals[1:])))
            self.assertEqual(p['y']['bytes'], 25344*4)
            self.assertEqual(p['y_exp'], -18)
            self.assertEqual(p['w']['bytes'], 32768 if packed else 65536)

    def test_packed_weight_order_and_signed_boundaries(self):
        weights = [[((k*256+c)*257 % 65536)-32768 for c in range(256)] for k in range(64)]
        words = s3.pack_weight_source(weights)
        decoded = []
        for word in words:
            for field in [word & 65535, word >> 16]:
                decoded.append(field-65536 if field & 32768 else field)
        self.assertEqual(len(words), 8192)
        self.assertEqual(decoded, [v for row in weights for v in row])

    def test_full_shape_mac_then_output_quantization(self):
        x = [[0]*64 for _ in range(99)]
        w = [[0]*256 for _ in range(64)]
        bias = [256 if i % 2 else -768 for i in range(256)]
        x[0][0], w[0][0] = -32768, -32768
        expected = [[round(Fraction(v, 512)) for v in bias] for _ in range(99)]
        expected[0][0] = round(Fraction(bias[0]+(1 << 30), 512))
        self.assertEqual(s3.linear99x64x256(x, w, bias), expected)


if __name__ == '__main__':
    unittest.main()
