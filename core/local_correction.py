"""
Correções aplicadas apenas em trechos selecionados da imagem (máscaras).

Responsabilidade:
- Gerar máscaras a partir de seleções retangulares/poligonais
- Aplicar feather/suavização de borda na máscara
- Garantir que a máscara respeite pixels NoData
- Permitir aplicar qualquer correção (histograma/cor) restrita à máscara
"""
from __future__ import annotations

from typing import Callable

import numpy as np
import cv2


def create_rectangular_mask(shape: tuple[int, int], rect: tuple[int, int, int, int]) -> np.ndarray:
    """rect = (x_min, y_min, x_max, y_max). shape = (height, width). Retorna máscara bool 2D."""
    h, w = shape
    x_min, y_min, x_max, y_max = rect

    x_min = max(0, min(x_min, w))
    x_max = max(0, min(x_max, w))
    y_min = max(0, min(y_min, h))
    y_max = max(0, min(y_max, h))

    mask = np.zeros((h, w), dtype=bool)
    mask[y_min:y_max, x_min:x_max] = True
    return mask


def create_polygon_mask(shape: tuple[int, int], polygon_points: list[tuple[int, int]]) -> np.ndarray:
    """polygon_points: lista de (x, y). shape = (height, width). Retorna máscara bool 2D."""
    h, w = shape
    if len(polygon_points) < 3:
        return np.zeros((h, w), dtype=bool)

    mask_uint8 = np.zeros((h, w), dtype=np.uint8)
    points_array = np.array(polygon_points, dtype=np.int32).reshape((-1, 1, 2))
    cv2.fillPoly(mask_uint8, [points_array], color=1)
    return mask_uint8.astype(bool)


def feather_mask(mask: np.ndarray, radius: int = 10, intensity: float = 1.0) -> np.ndarray:
    """Suaviza as bordas de uma máscara booleana, retornando uma máscara float (0.0-1.0).

    radius: raio do desfoque em pixels.
    intensity: 0 (sem suavização) a 1 (suavização máxima).
    """
    if radius <= 0 or intensity <= 0:
        return mask.astype(np.float64)

    mask_float = mask.astype(np.float64)
    ksize = max(1, int(radius) | 1)  # garante ímpar
    blurred = cv2.GaussianBlur(mask_float, (ksize, ksize), 0)

    result = mask_float * (1 - intensity) + blurred * intensity
    return np.clip(result, 0, 1)


def respect_nodata(mask: np.ndarray, image: np.ndarray, nodata: float | None) -> np.ndarray:
    """Zera a máscara em pixels NoData (considera todas as bandas de `image`, shape (bands, H, W))."""
    if nodata is None:
        return mask

    valid = np.all(image != nodata, axis=0) & np.all(np.isfinite(image), axis=0)
    if mask.dtype == bool:
        return mask & valid
    return mask * valid.astype(mask.dtype)


def apply_masked_correction(
    image: np.ndarray,
    mask: np.ndarray,
    correction_func: Callable[[np.ndarray], np.ndarray],
    nodata: float | None = None,
) -> np.ndarray:
    """Aplica `correction_func` (recebe e retorna imagem completa shape (bands,H,W))
    e mistura o resultado com a imagem original ponderado pela máscara (0.0-1.0 ou bool).

    A máscara já deve respeitar NoData (ver respect_nodata) antes de chegar aqui.
    """
    corrected = correction_func(image)
    mask_float = mask.astype(np.float64)

    result = image.astype(np.float64).copy()
    for b in range(result.shape[0]):
        result[b] = image[b] * (1 - mask_float) + corrected[b] * mask_float

    return result