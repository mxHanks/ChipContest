"""Semantic failures in multi-sample precision evidence; no inference libraries."""
import copy
import math
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools/model'))
import verify_kwt_evaluation as verifier


def fixture():
    samples = []
    for index, energy in enumerate([100., 10000.]):
        samples.append(dict(sample_index=index, label_index=index,
            waveform_float32_sha256=str(index) * 64,
            layers=[dict(layer_id=layer, sse=.0001, reference_energy=energy,
                         nrmse=math.sqrt(.0001 / energy), peak_absolute_error=.01,
                         peak_reference=1.) for layer in range(12)]))
    aggregate = math.sqrt(.0002 / 10100.)
    layers = [dict(layer_id=layer, samples=2, count=2 * 99 * 256,
                   sum_error_sq=.0002, sum_reference_sq=10100., nrmse=aggregate,
                   max_sample_nrmse=.001, worst_sample_index=0, x_clips=0,
                   weight_clips=0, bias_clips=0, scales=dict(x_exp=-11, w_exp=-16, y_exp=-27))
              for layer in range(12)]
    result = dict(status='PASS', exit_code=0, evaluation_completed=True,
        dataset=dict(evaluated_samples=2, full_validation_samples=2, label_counts={'0': 1, '1': 1}),
        layers=layers, max_layer_nrmse=aggregate, max_sample_layer_nrmse=.001,
        development_3_percent_gate='PASS', official_600_task_acceptance='NOT_RUN',
        rtl_full_validation='NOT_RUN', soc_ppa='NOT_RUN')
    sampling = dict(validation=[dict(index=index, label_index=index) for index in range(2)])
    return result, sampling, samples


class EvaluationEvidenceTests(unittest.TestCase):
    def test_recomputes_aggregate_energy_instead_of_averaging_sample_errors(self):
        result, sampling, rows = fixture()
        actual = verifier.validate(result, sampling, rows)
        self.assertEqual(actual['status'], 'PASS')
        self.assertAlmostEqual(actual['max_layer_nrmse_ratio'], math.sqrt(.0002 / 10100.))
        self.assertGreater(abs(actual['max_layer_nrmse_ratio'] - (.001 + .0001) / 2), .0003)

    def test_missing_sample_is_not_a_complete_population(self):
        result, sampling, rows = fixture()
        with self.assertRaisesRegex(ValueError, 'complete multi-sample'):
            verifier.validate(result, sampling, rows[:-1])

    def test_duplicate_or_missing_layer_cannot_be_hidden_by_summary(self):
        result, sampling, rows = fixture()
        rows[1]['layers'][-1] = copy.deepcopy(rows[1]['layers'][0])
        with self.assertRaisesRegex(ValueError, 'sample has missing/duplicate'):
            verifier.validate(result, sampling, rows)

    def test_swapped_sample_identity_is_rejected(self):
        result, sampling, rows = fixture()
        with self.assertRaisesRegex(ValueError, 'sample index/label'):
            verifier.validate(result, sampling, list(reversed(rows)))

    def test_nonfinite_error_is_rejected(self):
        result, sampling, rows = fixture()
        rows[0]['layers'][0]['sse'] = float('nan')
        with self.assertRaisesRegex(ValueError, 'finite nonnegative'):
            verifier.validate(result, sampling, rows)

    def test_wrong_aggregate_summary_is_rejected(self):
        result, sampling, rows = fixture()
        result['layers'][0]['sum_error_sq'] = 0
        with self.assertRaisesRegex(ValueError, 'calculated value differs'):
            verifier.validate(result, sampling, rows)

    def test_changed_static_scales_are_rejected(self):
        result, sampling, rows = fixture()
        result['layers'][0]['scales']['x_exp'] = -10
        with self.assertRaisesRegex(ValueError, 'fixed numerical scales changed'):
            verifier.validate(result, sampling, rows)

    def test_development_output_cannot_claim_official_acceptance(self):
        result, sampling, rows = fixture()
        result['official_600_task_acceptance'] = 'PASS'
        with self.assertRaisesRegex(ValueError, 'overclaimed'):
            verifier.validate(result, sampling, rows)


if __name__ == '__main__':
    unittest.main()
