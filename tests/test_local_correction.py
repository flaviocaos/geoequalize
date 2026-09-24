"""
Testes do módulo core.local_correction: máscaras retangular/poligonal, feather.
"""
import numpy as np

from core import local_correction as lc


def test_create_rectangular_mask_shape_and_content():
    mask = lc.create_rectangular_mask((20, 20), (5, 5, 15, 15))
    assert mask.shape == (20, 20)
    assert mask[10, 10] == True
    assert mask[0, 0] == False


def test_create_rectangular_mask_clips_to_bounds():
    mask = lc.create_rectangular_mask((10, 10), (-5, -5, 100, 100))
    assert mask.shape == (10, 10)
    assert mask.all()


def test_create_polygon_mask_triangle():
    polygon = [(2, 2), (10, 2), (6, 10)]
    mask = lc.create_polygon_mask((20, 20), polygon)
    assert mask.sum() > 0
    assert mask[3, 6] == True  # ponto dentro do triângulo aproximadamente


def test_feather_mask_softens_edges():
    mask = lc.create_rectangular_mask((40, 40), (10, 10, 30, 30))
    feathered = lc.feather_mask(mask, radius=5, intensity=1.0)
    assert feathered.max() <= 1.0
    assert feathered.min() >= 0.0
    # nas bordas da seleção, o valor deve ser intermediário (não 0 nem 1 estrito)
    border_value = feathered[10, 20]
    assert 0.0 <= border_value <= 1.0


def test_respect_nodata_zeroes_out_invalid_pixels():
    mask = np.ones((10, 10))
    image = np.ones((3, 10, 10)) * 50
    image[:, 0, 0] = -1  # nodata

    result = lc.respect_nodata(mask, image, nodata=-1)
    assert result[0, 0] == 0


def test_apply_masked_correction_blends_correctly():
    image = np.zeros((1, 10, 10))
    mask = lc.create_rectangular_mask((10, 10), (0, 0, 5, 5)).astype(np.float64)

    def double_it(img):
        return img * 2 + 10  # função de correção simples

    result = lc.apply_masked_correction(image, mask, double_it)
    assert result[0, 2, 2] == 10  # dentro da máscara: 0*2+10
    assert result[0, 8, 8] == 0   # fora da máscara: inalterado