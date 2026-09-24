"""
Gerenciamento de bandas, composições RGB/falsa-cor e estatísticas avançadas.

Este é um arquivo NOVO desta fase. Crie-o em core/band_tools.py.

Responsabilidade:
- Listar bandas disponíveis e seus metadados básicos
- Aplicar composições predefinidas (cor natural, falsa-cor IR, vegetação, etc.)
- Calcular estatísticas avançadas por banda (incluindo contagem de NoData)
- Stretch independente por banda, com percentis/gamma diferentes por canal
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import numpy as np

from core import histogram_tools as ht


@dataclass
class BandInfo:
    index: int  # 1-based, como no rasterio
    dtype: str
    min_value: Optional[float] = None
    max_value: Optional[float] = None
    description: Optional[str] = None


def list_bands(handle, sample: Optional[np.ndarray] = None) -> list[BandInfo]:
    """Lista as bandas de um RasterHandle. Se `sample` (array bands,H,W) for
    fornecido, calcula min/max reais a partir dele (mais rápido que reabrir o arquivo)."""
    infos: list[BandInfo] = []
    for i in range(handle.band_count):
        band_index = i + 1
        min_value = max_value = None
        if sample is not None and i < sample.shape[0]:
            valid = sample[i]
            finite = valid[np.isfinite(valid)]
            if handle.nodata is not None:
                finite = finite[finite != handle.nodata]
            if finite.size > 0:
                min_value = float(finite.min())
                max_value = float(finite.max())

        infos.append(BandInfo(index=band_index, dtype=handle.dtype, min_value=min_value, max_value=max_value))
    return infos


# Presets de composição: nomes de canais lógicos -> índice de banda (1-based).
# Como a ordem de bandas varia por satélite, estes são apenas SUGESTÕES
# para sensores comuns (ex.: Sentinel-2, Landsat 8). O usuário pode sempre
# sobrescrever manualmente os índices na interface.
COMPOSITION_PRESETS: dict[str, dict[str, int]] = {
    "cor_natural": {"R": 1, "G": 2, "B": 3},
    "falsa_cor_ir": {"R": 4, "G": 1, "B": 2},
    "vegetacao": {"R": 4, "G": 3, "B": 2},
    "urbano": {"R": 5, "G": 4, "B": 3},
    "solo_exposto": {"R": 3, "G": 4, "B": 1},
    "agua": {"R": 1, "G": 2, "B": 4},
}

COMPOSITION_LABELS = {
    "cor_natural": "Cor natural",
    "falsa_cor_ir": "Falsa-cor infravermelho próximo",
    "vegetacao": "Vegetação",
    "urbano": "Urbano",
    "solo_exposto": "Solo exposto",
    "agua": "Água",
}


def apply_band_composition(full_data: np.ndarray, r_index: int, g_index: int, b_index: int) -> np.ndarray:
    """full_data: shape (bands, H, W), índices 1-based. Retorna shape (3, H, W)."""
    bands = full_data.shape[0]
    for idx, name in ((r_index, "R"), (g_index, "G"), (b_index, "B")):
        if not (1 <= idx <= bands):
            raise ValueError(f"Índice de banda inválido para {name}: {idx} (disponíveis: 1-{bands})")

    return np.stack([
        full_data[r_index - 1],
        full_data[g_index - 1],
        full_data[b_index - 1],
    ], axis=0)


def compute_advanced_statistics(band: np.ndarray, nodata: float | None = None) -> dict:
    """Estatísticas avançadas: básicas (min/max/média/...) + variância + contagem de válidos/NoData."""
    basic = ht.compute_band_statistics(band, nodata=nodata)

    flat = band.astype(np.float64).ravel()
    total = flat.size
    if nodata is not None:
        valid_count = int(np.sum((flat != nodata) & np.isfinite(flat)))
    else:
        valid_count = int(np.sum(np.isfinite(flat)))
    nodata_count = total - valid_count

    variance = (basic["std"] ** 2) if basic["std"] is not None else None

    return {
        **basic,
        "variance": variance,
        "valid_pixel_count": valid_count,
        "nodata_pixel_count": nodata_count,
        "total_pixel_count": total,
    }


def stretch_per_band(
    image: np.ndarray,
    nodata: float | None = None,
    low_pct: float = 2.0,
    high_pct: float = 98.0,
    gamma_per_band: Optional[list[float]] = None,
) -> np.ndarray:
    """Aplica stretch por percentil de forma independente em cada banda, com
    gamma opcional independente por banda. image: shape (bands, H, W)."""
    result = image.astype(np.float64).copy()
    bands = result.shape[0]
    gammas = gamma_per_band or [1.0] * bands

    for b in range(bands):
        stretched = ht.stretch_percentile(result[b], low_pct=low_pct, high_pct=high_pct, nodata=nodata)
        if gammas[b] != 1.0:
            stretched = ht.adjust_gamma(stretched, gamma=gammas[b], nodata=nodata)
        result[b] = stretched

    return result


def normalize_per_band(image: np.ndarray, nodata: float | None = None) -> np.ndarray:
    """Normaliza cada banda independentemente para 0-255."""
    result = image.astype(np.float64).copy()
    for b in range(result.shape[0]):
        result[b] = ht.normalize_band(result[b], nodata=nodata)
    return result