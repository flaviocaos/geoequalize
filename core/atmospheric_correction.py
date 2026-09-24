"""
Correção atmosférica simplificada.

IMPORTANTE — leia antes de usar:
Este módulo implementa o método Dark Object Subtraction (DOS), uma
correção atmosférica simples e amplamente usada como aproximação rápida.
NÃO é equivalente ao FLAASH do ENVI (que usa o modelo de transferência
radiativa MODTRAN, com parâmetros reais de visibilidade atmosférica,
vapor d'água, altitude do sensor, ângulo solar, etc.). O DOS assume que
deveria haver pixels com reflectância ~0% (objetos escuros, como sombras
ou água profunda) em cada banda, e usa o valor mínimo observado (ou um
percentil baixo) como estimativa do espalhamento atmosférico (path
radiance) a ser subtraído.

Use este módulo para reduzir o efeito de neblina/espalhamento atmosférico
de forma rápida e sem precisar de metadados de calibração do sensor —
mas trate o resultado como uma aproximação visual/qualitativa, não como
reflectância de superfície cientificamente calibrada.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import numpy as np


@dataclass
class DOSResult:
    corrected: np.ndarray  # shape (bands, H, W)
    path_radiance_per_band: list[float]  # valor subtraído de cada banda


def estimate_path_radiance(
    band: np.ndarray,
    percentile: float = 1.0,
    nodata: Optional[float] = None,
) -> float:
    """Estima a radiância de trajetória (path radiance) de uma banda como o
    valor no percentil baixo (`percentile`) da distribuição de pixels válidos.

    O uso de um percentil baixo (em vez do mínimo absoluto) torna a
    estimativa mais robusta a ruído/outliers únicos.
    """
    flat = band.astype(np.float64).ravel()
    mask = np.isfinite(flat)
    if nodata is not None:
        mask &= flat != nodata

    valid = flat[mask]
    if valid.size == 0:
        return 0.0

    return float(np.percentile(valid, percentile))


def apply_dark_object_subtraction(
    image: np.ndarray,
    percentile: float = 1.0,
    nodata: Optional[float] = None,
    per_band_offset: Optional[list[float]] = None,
) -> DOSResult:
    """Aplica DOS a uma imagem multibanda (shape bands, H, W).

    Para cada banda, subtrai a radiância de trajetória estimada (ou um
    valor manual, se fornecido em `per_band_offset`), e recorta o
    resultado para não gerar valores negativos.
    """
    bands = image.shape[0]
    corrected = image.astype(np.float64).copy()
    path_radiance_values: list[float] = []

    for b in range(bands):
        if per_band_offset is not None and b < len(per_band_offset):
            offset = per_band_offset[b]
        else:
            offset = estimate_path_radiance(image[b], percentile=percentile, nodata=nodata)

        path_radiance_values.append(offset)

        band_corrected = corrected[b] - offset
        if nodata is not None:
            valid_mask = (image[b] != nodata) & np.isfinite(image[b])
            corrected[b] = np.where(valid_mask, np.clip(band_corrected, 0, None), image[b])
        else:
            corrected[b] = np.clip(band_corrected, 0, None)

    return DOSResult(corrected=corrected, path_radiance_per_band=path_radiance_values)


def rescale_after_dos(corrected: np.ndarray, target_max: float = 255.0) -> np.ndarray:
    """Reescala cada banda corrigida de volta para o intervalo [0, target_max],
    útil para manter compatibilidade com o pipeline de visualização 8-bit
    existente após a subtração."""
    result = corrected.copy()
    for b in range(result.shape[0]):
        band = result[b]
        finite = band[np.isfinite(band)]
        if finite.size == 0:
            continue
        vmax = finite.max()
        if vmax <= 0:
            continue
        result[b] = np.clip(band / vmax * target_max, 0, target_max)
    return result