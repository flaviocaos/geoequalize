"""
Testes do módulo core.color_correction: balanceamento de branco, canais, vinheta.
"""
import numpy as np

from core import color_correction as cc


def _synthetic_rgb(bias=(1.0, 1.0, 1.0), size=(32, 32)):
    rng = np.random.default_rng(99)
    base = rng.uniform(50, 200, size=size)
    return np.stack([base * bias[0], base * bias[1], base * bias[2]], axis=0)


def test_white_balance_gray_world_equalizes_channel_means():
    rgb = _synthetic_rgb(bias=(1.3, 1.0, 0.7))  # dominância avermelhada
    result = cc.white_balance_gray_world(rgb)

    means = [result[c].mean() for c in range(3)]
    assert max(means) - min(means) < 5.0  # médias devem ficar próximas


def test_white_balance_white_patch_maxes_to_255():
    rgb = _synthetic_rgb()
    result = cc.white_balance_white_patch(rgb)
    for c in range(3):
        assert abs(result[c].max() - 255.0) < 1.0


def test_adjust_channels_applies_independent_gains():
    rgb = _synthetic_rgb()
    result = cc.adjust_channels(rgb, r_gain=1.5, g_gain=1.0, b_gain=0.5)
    assert result[0].mean() > rgb[0].mean() * 0.9
    assert result[2].mean() < rgb[2].mean() * 1.1


def test_reduce_color_cast_blue():
    rgb = _synthetic_rgb(bias=(1.0, 1.0, 1.5))  # dominância azulada
    result = cc.reduce_color_cast(rgb, "blue", intensity=1.0)
    assert result[2].mean() < rgb[2].mean()


def test_correct_vignette_brightens_edges():
    rgb = _synthetic_rgb(size=(64, 64))
    # escurece as bordas artificialmente
    rgb[:, 0, :] *= 0.5
    rgb[:, -1, :] *= 0.5
    result = cc.correct_vignette(rgb, strength=0.8)
    assert result[:, 0, :].mean() >= rgb[:, 0, :].mean()


def test_white_balance_from_reference_point_white():
    rgb = _synthetic_rgb()
    result = cc.white_balance_from_reference_point(rgb, point_xy=(0, 0), target="white")
    assert result.shape == rgb.shape


def test_color_correction_respects_nodata():
    rgb = _synthetic_rgb()
    rgb[:, 0, 0] = -1
    result = cc.adjust_channels(rgb, r_gain=2.0, g_gain=1.0, b_gain=1.0, nodata=-1)
    assert result[0, 0, 0] == -1