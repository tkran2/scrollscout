import numpy as np

from scrollscout.score import combined_score
from scrollscout.stats import auc, bootstrap_ci, spearman
from scrollscout.survey import BAD, GOOD, MOSTLY, PARTIAL, label_from_verdict


def test_auc_extremes_and_ties():
    y = np.array([0, 0, 1, 1], bool)
    assert auc(np.array([1, 2, 3, 4]), y) == 1.0
    assert auc(np.array([4, 3, 2, 1]), y) == 0.0
    assert auc(np.array([1, 1, 1, 1]), y) == 0.5
    assert np.isnan(auc(np.array([1, 2]), np.array([1, 1], bool)))


def test_auc_ignores_nan_scores():
    assert auc(np.array([np.nan, 1, 2, 3]), np.array([1, 0, 0, 1], bool)) == 1.0


def test_bootstrap_ci_brackets_estimate():
    rng = np.random.default_rng(0)
    y = rng.random(80) > 0.5
    s = y + rng.normal(0, 0.8, 80)
    lo, hi = bootstrap_ci(auc, s, y, n=500)
    assert lo < auc(s, y) < hi


def test_spearman_monotone():
    assert spearman([1, 2, 3, 4, 5], [2, 4, 6, 8, 10]) > 0.99


def test_survey_label_mapping():
    assert label_from_verdict("follows the sheet throughout (crosshatch)") == GOOD
    assert label_from_verdict("follows the sheet over most of the patch, diagonal cracks") == MOSTLY
    assert label_from_verdict("follows the sheet on the right two-thirds (crosshatch), swirls on the left") == MOSTLY
    assert label_from_verdict("partly on the sheet, swirls") == PARTIAL
    assert label_from_verdict("on-sheet band across the middle, swirls elsewhere") == PARTIAL
    assert label_from_verdict("radial layer-crossing swirls (compressed region)") == BAD
    # "over most of the patch" describes the failure here, not the sheet
    assert label_from_verdict("escapes the papyrus into uniform material over most of the patch") == BAD


def test_combined_score_orders_clean_above_crushed():
    clean = {"pred_planarity": 0.95, "pred_dispersion": 0.02, "pred_thick": 0.001, "pred_ncomp_per_kvox": 0.4,
             "ct_dispersion": 0.05}
    crushed = {"pred_planarity": 0.6, "pred_dispersion": 0.3, "pred_thick": 0.2, "pred_ncomp_per_kvox": 1.1,
               "ct_dispersion": 0.4}
    s = combined_score([clean, crushed])
    assert s[0] > s[1]
