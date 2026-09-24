"""
Correções de cor e balanceamento (Gray World, White Patch, canais RGB,
temperatura, matiz, saturação, sombras/médios/realces, correção de
dominância de cor, ferramentas específicas para ortofotos de drone).

Todas as funções trabalham com imagem RGB no formato (3, H, W), valores
em float64 na escala 0-255. NoData é preservado quando informado.
"""
from __future__ import annotations

import numpy as np
import cv2


def _valid_mask(image_rgb: np.ndarray, nodata: float | None) -> np.ndarray:
    """Máscara 2D (H, W) de pixels válidos, considerando todas as bandas."""
    if nodata is not None:
        mask = np.all(image_rgb != nodata, axis=0)
    else:
        mask = np.ones(image_rgb.shape[1:], dtype=bool)
    mask &= np.all(np.isfinite(image_rgb), axis=0)
    return mask


def white_balance_gray_world(image_rgb: np.ndarray, nodata: float | None = None) -> np.ndarray:
    """Assume que a média da cena deveria ser cinza neutro; corrige os ganhos por canal."""
    result = image_rgb.astype(np.float64).copy()
    mask = _valid_mask(result, nodata)
    if not mask.any():
        return result

    means = np.array([result[c][mask].mean() for c in range(3)])
    gray_mean = means.mean()
    gains = np.divide(gray_mean, means, out=np.ones_like(means), where=means != 0)

    for c in range(3):
        result[c][mask] = np.clip(result[c][mask] * gains[c], 0, 255)
    return result


def white_balance_white_patch(image_rgb: np.ndarray, nodata: float | None = None) -> np.ndarray:
    """Assume que o pixel mais claro de cada canal deveria ser branco puro (255)."""
    result = image_rgb.astype(np.float64).copy()
    mask = _valid_mask(result, nodata)
    if not mask.any():
        return result

    maxes = np.array([result[c][mask].max() for c in range(3)])
    gains = np.divide(255.0, maxes, out=np.ones_like(maxes), where=maxes != 0)

    for c in range(3):
        result[c][mask] = np.clip(result[c][mask] * gains[c], 0, 255)
    return result


def white_balance_from_reference_point(
    image_rgb: np.ndarray,
    point_xy: tuple[int, int],
    target: str = "white",
    nodata: float | None = None,
) -> np.ndarray:
    """Usa o pixel em point_xy=(x, y) como referência de branco/cinza/preto.

    target: 'white' (255,255,255) | 'gray' (128,128,128) | 'black' (0,0,0)
    """
    targets = {"white": 255.0, "gray": 128.0, "black": 0.0}
    if target not in targets:
        raise ValueError(f"target inválido: {target}")
    target_value = targets[target]

    result = image_rgb.astype(np.float64).copy()
    x, y = point_xy
    h, w = result.shape[1], result.shape[2]
    if not (0 <= y < h and 0 <= x < w):
        raise ValueError(f"Ponto de referência fora dos limites da imagem: {point_xy}")

    ref_values = result[:, y, x]
    mask = _valid_mask(result, nodata)

    for c in range(3):
        if ref_values[c] == 0:
            continue
        gain = target_value / ref_values[c]
        result[c][mask] = np.clip(result[c][mask] * gain, 0, 255)
    return result


def adjust_channels(
    image_rgb: np.ndarray,
    r_gain: float = 1.0,
    g_gain: float = 1.0,
    b_gain: float = 1.0,
    nodata: float | None = None,
) -> np.ndarray:
    """Aplica ganho multiplicativo independente por canal RGB."""
    result = image_rgb.astype(np.float64).copy()
    mask = _valid_mask(result, nodata)
    gains = [r_gain, g_gain, b_gain]

    for c in range(3):
        result[c][mask] = np.clip(result[c][mask] * gains[c], 0, 255)
    return result


def adjust_temperature(image_rgb: np.ndarray, temperature: float = 0.0, nodata: float | None = None) -> np.ndarray:
    """temperature: -100 (mais frio/azulado) a +100 (mais quente/alaranjado)."""
    result = image_rgb.astype(np.float64).copy()
    mask = _valid_mask(result, nodata)

    factor = temperature / 100.0
    r_shift = 1.0 + 0.3 * factor
    b_shift = 1.0 - 0.3 * factor

    result[0][mask] = np.clip(result[0][mask] * r_shift, 0, 255)
    result[2][mask] = np.clip(result[2][mask] * b_shift, 0, 255)
    return result


def adjust_hue_saturation(
    image_rgb: np.ndarray,
    hue_shift: float = 0.0,
    saturation: float = 1.0,
    nodata: float | None = None,
) -> np.ndarray:
    """hue_shift em graus (-180 a 180). saturation: fator multiplicativo (0 a 3)."""
    result = image_rgb.astype(np.float64).copy()
    mask = _valid_mask(result, nodata)

    rgb_uint8 = np.clip(result, 0, 255).astype(np.uint8)
    rgb_hwc = np.transpose(rgb_uint8, (1, 2, 0))
    hsv = cv2.cvtColor(rgb_hwc, cv2.COLOR_RGB2HSV).astype(np.float64)

    hsv[..., 0] = (hsv[..., 0] + hue_shift / 2.0) % 180
    hsv[..., 1] = np.clip(hsv[..., 1] * saturation, 0, 255)

    hsv_uint8 = hsv.astype(np.uint8)
    rgb_back = cv2.cvtColor(hsv_uint8, cv2.COLOR_HSV2RGB).astype(np.float64)
    rgb_back_chw = np.transpose(rgb_back, (2, 0, 1))

    for c in range(3):
        result[c][mask] = rgb_back_chw[c][mask]
    return result


def adjust_tonal_ranges(
    image_rgb: np.ndarray,
    shadows: float = 0.0,
    midtones: float = 0.0,
    highlights: float = 0.0,
    nodata: float | None = None,
) -> np.ndarray:
    """Ajusta sombras (~0-85), médios tons (~85-170) e realces (~170-255) separadamente.

    Cada parâmetro: -100 a 100 (deslocamento aditivo ponderado pela região tonal).
    """
    result = image_rgb.astype(np.float64).copy()
    mask = _valid_mask(result, nodata)

    for c in range(3):
        channel = result[c]
        norm = channel / 255.0

        shadow_weight = np.clip(1.0 - norm * 3.0, 0, 1)
        highlight_weight = np.clip((norm - 0.66) * 3.0, 0, 1)
        midtone_weight = np.clip(1.0 - shadow_weight - highlight_weight, 0, 1)

        delta = (
            shadow_weight * (shadows / 100.0 * 50.0)
            + midtone_weight * (midtones / 100.0 * 50.0)
            + highlight_weight * (highlights / 100.0 * 50.0)
        )

        adjusted = np.clip(channel + delta, 0, 255)
        result[c] = np.where(mask, adjusted, channel)
    return result


_CAST_REDUCTION_CHANNELS = {
    "blue": 2,
    "green": 1,
    "yellow": None,  # reduz amarelo = reduz R e G simultaneamente
    "red": 0,
}


def reduce_color_cast(image_rgb: np.ndarray, cast: str, intensity: float = 1.0, nodata: float | None = None) -> np.ndarray:
    """Reduz dominância de cor. cast: 'blue' | 'green' | 'yellow' | 'red'. intensity: 0-2."""
    if cast not in _CAST_REDUCTION_CHANNELS:
        raise ValueError(f"cast inválido: {cast}")

    result = image_rgb.astype(np.float64).copy()
    mask = _valid_mask(result, nodata)
    factor = 1.0 - 0.3 * intensity

    if cast == "yellow":
        for c in (0, 1):
            result[c][mask] = np.clip(result[c][mask] * factor, 0, 255)
    else:
        c = _CAST_REDUCTION_CHANNELS[cast]
        result[c][mask] = np.clip(result[c][mask] * factor, 0, 255)

    return result


def correct_uneven_illumination(image_rgb: np.ndarray, kernel_fraction: float = 0.1, nodata: float | None = None) -> np.ndarray:
    """Suaviza diferenças de iluminação (comum em ortomosaicos de drone) via
    divisão pela versão borrada (homomorphic-like flattening)."""
    result = image_rgb.astype(np.float64).copy()
    h, w = result.shape[1], result.shape[2]
    ksize = max(3, int(min(h, w) * kernel_fraction) | 1)  # garante ímpar

    for c in range(3):
        channel = result[c]
        blurred = cv2.GaussianBlur(channel, (ksize, ksize), 0)
        blurred = np.where(blurred == 0, 1.0, blurred)
        flattened = channel / blurred * blurred.mean()
        result[c] = np.clip(flattened, 0, 255)

    return result


def correct_vignette(image_rgb: np.ndarray, strength: float = 0.5, nodata: float | None = None) -> np.ndarray:
    """Correção simples de vinheta: compensa o escurecimento radial das bordas."""
    result = image_rgb.astype(np.float64).copy()
    h, w = result.shape[1], result.shape[2]

    y, x = np.indices((h, w))
    cx, cy = w / 2.0, h / 2.0
    max_dist = np.sqrt(cx ** 2 + cy ** 2)
    dist = np.sqrt((x - cx) ** 2 + (y - cy) ** 2) / max_dist

    correction = 1.0 + strength * (dist ** 2)

    for c in range(3):
        result[c] = np.clip(result[c] * correction, 0, 255)

    return result


def enhance_for_class(image_rgb: np.ndarray, target_class: str, nodata: float | None = None) -> np.ndarray:
    """Realces simples voltados a classes de cobertura, via ganho seletivo de canais.

    target_class: 'urban' | 'vegetation' | 'bare_soil' | 'roads_roofs'
    Estas são heurísticas visuais simples, não classificação científica.
    """
    presets = {
        "urban": (1.05, 1.0, 1.1),
        "vegetation": (0.95, 1.15, 0.95),
        "bare_soil": (1.1, 1.0, 0.9),
        "roads_roofs": (1.05, 1.05, 1.05),
    }
    if target_class not in presets:
        raise ValueError(f"target_class inválido: {target_class}")

    r_gain, g_gain, b_gain = presets[target_class]
    return adjust_channels(image_rgb, r_gain=r_gain, g_gain=g_gain, b_gain=b_gain, nodata=nodata)