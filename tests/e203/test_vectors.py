from pathlib import Path
import tempfile
import unittest
from test_runner import soc


class VectorCheckTests(unittest.TestCase):
    def test_independent_signed_reference_and_corruption(self):
        # Hand-derived sparse matrix; catches sign, bias width and transposition errors.
        check = getattr(soc, 'check_vectors', None)
        self.assertIsNotNone(check, 'independent vector checker is missing')
        with tempfile.TemporaryDirectory() as tmp:
            layer = Path(tmp)/'layer_00'
            layer.mkdir()
            x, w, bias = [0]*6336, [0]*16384, [0]*256
            x[0:2], x[64] = [-32768, 32767], 3
            w[0:2], w[256:258] = [2, -32768], [-3, 32767]
            bias[0:2] = [549755813887, -549755813888]
            y = bias*99
            y[0:2] = [549755650050, -547608395775]
            y[256:258] = [549755813893, -549755912192]
            for name, values, bits in [('x',x,16), ('w',w,16), ('bias',bias,40), ('y',y,48)]:
                (layer/(name+'.mem')).write_text(''.join(f'{v&((1<<bits)-1):0{bits//4}x}\n' for v in values))
            self.assertEqual(check(Path(tmp), 1)[0]['outputs'], 25344)
            data=(layer/'y.mem').read_text()
            (layer/'y.mem').write_text('000000000000\n'+data.split('\n',1)[1])
            with self.assertRaisesRegex(ValueError, 'layer=0 row=0 col=0'):
                check(Path(tmp), 1)
            with self.assertRaises(ValueError):
                check(Path(tmp), 0)


if __name__ == '__main__':
    unittest.main()
