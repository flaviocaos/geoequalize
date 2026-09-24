"""
Cálculo de histogramas, estatísticas e correções de contraste/histograma.
Todas as funções operam em uma única banda (np.ndarray 2D) e ignoram NoData.
"""
from __future__ import annotations

import numpy as np
from skimage import exposure


def _valid_pixels(band: np.ndarray, nodata: float | None) -> np.ndarray:
    """Retorna array 1D apenas com os pixels válidos (não-NoData, finitos)."""
    flat = band.astype(np.float64).ravel()
    mask = np.isfinite(flat)
    if nodata is not None:
        mask &= flat != nodata
    return flat[mask]


def compute_band_statistics(band: np.ndarray, nodata: float | None = None) -> dict:
    """Retorna min, max, média, mediana, desvio padrão e percentis-chave da banda."""
    valid = _valid_pixels(band, nodata)
    if valid.size == 0:
        return {k: None for k in (
            "min", "max", "mean", "median", "std",
            "p1", "p2", "p5", "p95", "p98", "p99",
        )}

    percentiles = np.percentile(valid, [1, 2, 5, 95, 98, 99])
    return {
        "min": float(valid.min()),
        "max": float(valid.max()),
        "mean": float(valid.mean()),
        "median": float(np.median(valid)),
        "std": float(valid.std()),
        "p1": float(percentiles[0]),
        "p2": float(percentiles[1]),
        "p5": float(percentiles[2]),
        "p95": float(percentiles[3]),
        "p98": float(percentiles[4]),
        "p99": float(percentiles[5]),
    }


def compute_histogram(band: np.ndarray, bins: int = 256, nodata: float | None = None) -> tuple[np.ndarray, np.ndarray]:
    """Retorna (contagens, bordas_dos_bins) ignorando pixels NoData."""
    valid = _valid_pixels(band, nodata)
    if valid.size == 0:
        return np.zeros(bins), np.linspace(0, 1, bins + 1)
    counts, edges = np.histogram(valid, bins=bins)
    return counts, edges


def _apply_only_valid(band: np.ndarray, nodata: float | None, transform_fn) -> np.ndarray:
    """Aplica transform_fn apenas nos pixels válidos, preservando NoData inalterado."""
    result = band.astype(np.float64).copy()
    if nodata is not None:
        valid_mask = (result != nodata) & np.isfinite(result)
    else:
        valid_mask = np.isfinite(result)

    if valid_mask.any():
        result[valid_mask] = transform_fn(result[valid_mask])
    return result


def stretch_linear(band: np.ndarray, vmin: float, vmax: float, nodata: float | None = None) -> np.ndarray:
    """Stretch linear mínimo/máximo, mapeando [vmin, vmax] para [0, 255]."""
    def _fn(values: np.ndarray) -> np.ndarray:
        if vmax <= vmin:
            return np.zeros_like(values)
        stretched = np.clip((values - vmin) / (vmax - vmin), 0, 1)
        return stretched * 255.0

    return _apply_only_valid(band, nodata, _fn)


def stretch_percentile(band: np.ndarray, low_pct: float = 2.0, high_pct: float = 98.0, nodata: float | None = None) -> np.ndarray:
    """Stretch por percentil (padrão 2%-98%)."""
    valid = _valid_pixels(band, nodata)
    if valid.size == 0:
        return band.astype(np.float64)
    vmin, vmax = np.percentile(valid, [low_pct, high_pct])
    return stretch_linear(band, vmin, vmax, nodata=nodata)


def stretch_std(band: np.ndarray, n_std: float = 2.0, nodata: float | None = None) -> np.ndarray:
    """Stretch por desvio padrão: usa [média - n*std, média + n*std] como limites."""
    valid = _valid_pixels(band, nodata)
    if valid.size == 0:
        return band.astype(np.float64)
    mean, std = valid.mean(), valid.std()
    vmin, vmax = mean - n_std * std, mean + n_std * std
    return stretch_linear(band, vmin, vmax, nodata=nodata)


def normalize_band(band: np.ndarray, nodata: float | None = None) -> np.ndarray:
    """Normaliza a banda para o intervalo [0, 255] usando min/max reais."""
    valid = _valid_pixels(band, nodata)
    if valid.size == 0:
        return band.astype(np.float64)
    return stretch_linear(band, float(valid.min()), float(valid.max()), nodata=nodata)


def equalize_histogram(band: np.ndarray, nodata: float | None = None) -> np.ndarray:
    """Equalização de histograma clássica (skimage), retornando em escala 0-255."""
    def _fn(values: np.ndarray) -> np.ndarray:
        vmin, vmax = values.min(), values.max()
        if vmax <= vmin:
            return np.zeros_like(values)
        norm = (values - vmin) / (vmax - vmin)
        equalized = exposure.equalize_hist(norm)
        return equalized * 255.0

    return _apply_only_valid(band, nodata, _fn)


def apply_clahe(band: np.ndarray, clip_limit: float = 0.01, nodata: float | None = None) -> np.ndarray:
    """CLAHE (equalização adaptativa). clip_limit no padrão do skimage (0-1)."""
    return apply_clahe_2d(band, clip_limit=clip_limit, nodata=nodata)


def apply_clahe_2d(band: np.ndarray, clip_limit: float = 0.01, nodata: float | None = None) -> np.ndarray:
    """Implementação real do CLAHE preservando a estrutura 2D da imagem."""
    band_f = band.astype(np.float64).copy()

    if nodata is not None:
        mask = (band_f != nodata) & np.isfinite(band_f)
    else:
        mask = np.isfinite(band_f)

    if not mask.any():
        return band_f

    vmin, vmax = band_f[mask].min(), band_f[mask].max()
    if vmax <= vmin:
        return band_f

    norm = np.zeros_like(band_f)
    norm[mask] = (band_f[mask] - vmin) / (vmax - vmin)

    # Preenche áreas inválidas com a média para não distorcer o CLAHE local
    fill_value = norm[mask].mean()
    norm_filled = np.where(mask, norm, fill_value)

    equalized = exposure.equalize_adapthist(norm_filled, clip_limit=clip_limit)

    result = band_f.copy()
    result[mask] = equalized[mask] * 255.0
    return result


def adjust_gamma(band: np.ndarray, gamma: float = 1.0, nodata: float | None = None) -> np.ndarray:
    """Ajuste de gamma. gamma < 1 clareia, gamma > 1 escurece."""
    def _fn(values: np.ndarray) -> np.ndarray:
        vmin, vmax = values.min(), values.max()
        if vmax <= vmin:
            return np.zeros_like(values)
        norm = np.clip((values - vmin) / (vmax - vmin), 0, 1)
        corrected = np.power(norm, gamma)
        return corrected * 255.0

    return _apply_only_valid(band, nodata, _fn)


def adjust_brightness_contrast(band: np.ndarray, brightness: float = 0.0, contrast: float = 1.0, nodata: float | None = None) -> np.ndarray:
    """brightness: deslocamento aditivo (-100 a 100). contrast: fator multiplicativo (0.1 a 3.0)."""
    def _fn(values: np.ndarray) -> np.ndarray:
        vmin, vmax = values.min(), values.max()
        if vmax <= vmin:
            return np.zeros_like(values)
        norm = (values - vmin) / (vmax - vmin) * 255.0
        adjusted = (norm - 127.5) * contrast + 127.5 + brightness
        return np.clip(adjusted, 0, 255)

    return _apply_only_valid(band, nodata, _fn)