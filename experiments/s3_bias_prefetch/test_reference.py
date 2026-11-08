from pathlib import Path
import random
import tempfile
import unittest

from reference import MASK40, generate, merge_bias, signed_bias, sram_words


class BiasReferenceTests(unittest.TestCase):
    def test_exhaustive_masks_preserve_each_unselected_byte(self):
        rng = random.Random(42)
        for mask in range(32):
            for old, new in [(0, MASK40), (MASK40, 0), (1 << 39, (1 << 39)-1)] + [
                    (rng.getrandbits(40), rng.getrandbits(40)) for _ in range(128)]:
                result = merge_bias(old, new, mask)
                for byte in range(5):
                    self.assertEqual((result >> (8*byte)) & 255,
                                     ((new if mask & (1 << byte) else old) >> (8*byte)) & 255)
                words = sram_words(result)
                self.assertEqual(words[0] | (words[1] << 16) | (words[2] << 32), result)
                self.assertLess(words[2], 256)
                self.assertEqual(signed_bias(result), result if result < (1 << 39) else result-(1 << 40))

    def test_stimulus_replays_old_cache_semantics_and_covers_all_addresses_masks(self):
        with tempfile.TemporaryDirectory() as tmp:
            records, final = generate(tmp)
            memory = [0]*256
            masks, writes, errors = set(), set(), 0
            for read, active, addr, mask, data, expected, error in records:
                if not read:
                    masks.add(mask); writes.add(addr)
                    self.assertEqual(error, int(bool(active)))
                    if not error:
                        memory[addr] = merge_bias(memory[addr], data, mask)
                    errors += error
                self.assertEqual(expected, memory[addr])
            self.assertEqual(memory, final)
            self.assertEqual(masks, set(range(32)))
            self.assertEqual(writes, set(range(256)))
            self.assertGreater(errors, 100)
            self.assertEqual(len((Path(tmp)/'transactions.txt').read_text().splitlines()), len(records))

    def test_invalid_raw_codes_are_rejected(self):
        for args in [(-1, 0, 0), (0, MASK40+1, 31), (0, 0, 32)]:
            with self.assertRaises(ValueError):
                merge_bias(*args)


if __name__ == '__main__':
    unittest.main()
