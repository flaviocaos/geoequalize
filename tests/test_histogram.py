"""
Testes do módulo core.histogram_tools: stretch, equalização, CLAHE, gamma.
"""
import numpy as np

from core import histogram_tools as ht


def _synthetic_band(low=10, high=240, size=(32, 32)):
    rng = np.random.default_rng(123)
    return rng.uniform(low, high, size=size)


def test_compute_band_statistics_basic():
    band = _synthetic_band()
    stats = ht.compute_band_statistics(band)
    assert stats["min"] is not None
    assert stats["max"] > stats["min"]
    assert stats["mean"] is not None


def test_compute_band_statistics_ignores_nodata():
    band = _synthetic_band()
    band[0, 0] = -9999
    stats = ht.compute_band_statistics(band, nodata=-9999)
    assert stats["min"] > -9999


def test_compute_histogram_shapes():
    band = _synthetic_band()
    counts, edges = ht.compute_histogram(band, bins=64)
    assert counts.shape[0] == 64
    assert edges.shape[0] == 65


def test_stretch_linear_maps_to_0_255():
    band = _synthetic_band()
    stretched = ht.stretch_linear(band, vmin=float(band.min()), vmax=float(band.max()))
    assert stretched.max() <= 255.0001
    assert stretched.min() >= -0.0001


def test_stretch_percentile_clips_extremes():
    band = _synthetic_band()
    band[0, 0] = 10000  # outlier extremo
    stretched = ht.stretch_percentile(band, low_pct=2.0, high_pct=98.0)
    assert stretched.max() <= 255.0001


def test_stretch_preserves_nodata_pixels():
    band = _synthetic_band()
    band[5, 5] = -1
    stretched = ht.stretch_linear(band, vmin=10, vmax=240, nodata=-1)
    assert stretched[5, 5] == -1


def test_equalize_histogram_changes_distribution():
    band = _synthetic_band(low=100, high=110)  # histograma estreito
    equalized = ht.equalize_histogram(band)
    assert equalized.std() >= band.std()


def test_apply_clahe_runs_without_error():
    band = _synthetic_band()
    result = ht.apply_clahe(band)
    assert result.shape == band.shape


def test_adjust_gamma_changes_values():
    band = _synthetic_band()
    result = ht.adjust_gamma(band, gamma=2.0)
    assert not np.allclose(result, band)


def test_adjust_brightness_contrast():
    band = _synthetic_band()
    result = ht.adjust_brightness_contrast(band, brightness=20.0, contrast=1.2)
    assert result.shape == band.shape
    assert result.max() <= 255.0001