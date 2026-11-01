import numpy as np
from scipy import ndimage as ndi

from scrollscout.features import ct_features, planarity, prediction_features


def sheets(shape=(96, 96, 96), spacing=8, thickness=2, tilt=0.15):
    z, y, x = np.indices(shape)
    t = z + tilt * y
    return ((t % spacing) < thickness).astype(np.uint8) * 255


def blobs(shape=(96, 96, 96), seed=0):
    rng = np.random.default_rng(seed)
    n = ndi.gaussian_filter(rng.normal(size=shape), 3)
    return (n > np.percentile(n, 70)).astype(np.uint8) * 255


def test_planarity_flat_sheets_is_high():
    p, normal = planarity(ndi.gaussian_filter(sheets().astype(float), 1))
    assert p > 0.9
    assert abs(normal[0]) > 0.9  # sheets stack along z


def test_prediction_features_separate_sheets_from_blobs():
    good = prediction_features(sheets())
    bad = prediction_features(blobs())
    assert good["pred_planarity"] > bad["pred_planarity"] + 0.2
    assert good["pred_thick"] < bad["pred_thick"]
    assert good["pred_dispersion"] < bad["pred_dispersion"]


def test_ct_features_layered_vs_noise():
    rng = np.random.default_rng(1)
    layered = (sheets(thickness=4).astype(float) * 0.5 + 60 + rng.normal(0, 10, (96, 96, 96))).clip(1, 255)
    noise = (128 + rng.normal(0, 30, (96, 96, 96))).clip(1, 255)
    a = ct_features(layered.astype(np.uint8))
    b = ct_features(noise.astype(np.uint8))
    assert a["ct_planarity"] > b["ct_planarity"]
    assert a["ct_contrast"] > b["ct_contrast"]


def test_empty_cube_gives_nan_not_crash():
    f = prediction_features(np.zeros((64, 64, 64), np.uint8))
    assert np.isnan(f["pred_planarity"])
    g = ct_features(np.zeros((64, 64, 64), np.uint8))
    assert np.isnan(g["ct_planarity"])
