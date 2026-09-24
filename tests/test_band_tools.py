"""
Testes do módulo core.band_tools: composição de bandas e estatísticas avançadas.
"""
import numpy as np
import pytest

from core import band_tools as bt


def test_apply_band_composition_selects_correct_bands():
    full_data = np.stack([
        np.ones((5, 5)) * 1,
        np.ones((5, 5)) * 2,
        np.ones((5, 5)) * 3,
        np.ones((5, 5)) * 4,
    ], axis=0)

    composed = bt.apply_band_composition(full_data, r_index=4, g_index=1, b_index=2)
    assert composed.shape == (3, 5, 5)
    assert composed[0, 0, 0] == 4
    assert composed[1, 0, 0] == 1
    assert composed[2, 0, 0] == 2


def test_apply_band_composition_invalid_index_raises():
    full_data = np.ones((3, 5, 5))
    with pytest.raises(ValueError):
        bt.apply_band_composition(full_data, r_index=10, g_index=1, b_index=2)


def test_compute_advanced_statistics_counts_nodata():
    band = np.ones((10, 10)) * 50
    band[0, 0] = -1
    band[0, 1] = -1

    stats = bt.compute_advanced_statistics(band, nodata=-1)
    assert stats["nodata_pixel_count"] == 2
    assert stats["valid_pixel_count"] == 98
    assert stats["total_pixel_count"] == 100


def test_stretch_per_band_independent():
    image = np.stack([
        np.random.uniform(0, 100, size=(10, 10)),
        np.random.uniform(100, 200, size=(10, 10)),
    ], axis=0)

    result = bt.stretch_per_band(image, low_pct=2.0, high_pct=98.0)
    assert result.shape == image.shape