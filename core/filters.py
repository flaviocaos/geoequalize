"""
Filtros de realce e correções visuais avançadas.

IMPORTANTE: todas as correções deste módulo são heurísticas VISUAIS,
não correções radiométricas cientificamente calibradas (não substituem
correção atmosférica real, p.ex. usando coeficientes de reflectância).
Isso é informado claramente na interface (Fase 8).

Funções trabalham em imagem RGB (3, H, W) ou banda única (H, W), float64,
preservando NoData quando informado.
"""
from __future__ import annotations

import numpy as np
import cv2
from skimage import exposure


def _valid_mask_nd(image: np.ndarray, nodata: float | None) -> np.ndarray:
    """Máscara 2D de pixels válidos, considerando todas as bandas se image for 3D."""
    if image.ndim == 3:
        if nodata is not None:
            mask = np.all(image != nodata, axis=0)
        else:
            mask = np.ones(image.shape[1:], dtype=bool)
        mask &= np.all(np.isfinite(image), axis=0)
    else:
        if nodata is not None:
            mask = image != nodata
        else:
            mask = np.ones(image.shape, dtype=bool)
        mask &= np.isfinite(image)
    return mask


# ----------------------------------------------------------------------
# Filtros de realce
# ----------------------------------------------------------------------
def sharpen(image: np.ndarray, amount: float = 1.0, nodata: float | None = None) -> np.ndarray:
    """Sharpening simples via kernel de convolução. amount: 0 (sem efeito) a 3 (forte)."""
    result = image.astype(np.float64).copy()
    kernel = np.array([[0, -1, 0], [-1, 5, -1], [0, -1, 0]], dtype=np.float64)
    kernel = kernel * amount + np.eye(3, dtype=np.float64) * 0  # placeholder p/ clareza
    # Kernel ponderado pelo amount: mistura identidade e sharpen
    identity = np.zeros((3, 3))
    identity[1, 1] = 1.0
    blended_kernel = identity * (1 - amount) + kernel * amount if amount <= 1 else kernel * amount

    bands = result.shape[0] if result.ndim == 3 else 1
    arr3d = result if result.ndim == 3 else result[np.newaxis, ...]

    for b in range(bands):
        arr3d[b] = cv2.filter2D(arr3d[b], -1, blended_kernel)

    return np.clip(arr3d if result.ndim == 3 else arr3d[0], 0, 255)


def unsharp_mask(image: np.ndarray, radius: float = 2.0, amount: float = 1.0, nodata: float | None = None) -> np.ndarray:
    """Unsharp mask clássico: original + amount * (original - blur(original))."""
    result = image.astype(np.float64).copy()
    bands = result.shape[0] if result.ndim == 3 else 1
    arr3d = result if result.ndim == 3 else result[np.newaxis, ...]

    ksize = max(1, int(radius * 2) | 1)
    for b in range(bands):
        blurred = cv2.GaussianBlur(arr3d[b], (ksize, ksize), radius)
        sharpened = arr3d[b] + amount * (arr3d[b] - blurred)
        arr3d[b] = np.clip(sharpened, 0, 255)

    return arr3d if result.ndim == 3 else arr3d[0]


def denoise(image: np.ndarray, method: str = "gaussian", nodata: float | None = None, **kwargs) -> np.ndarray:
    """method: 'gaussian' | 'median' | 'bilateral'."""
    result = image.astype(np.float64).copy()
    bands = result.shape[0] if result.ndim == 3 else 1
    arr3d = result if result.ndim == 3 else result[np.newaxis, ...]

    for b in range(bands):
        channel = arr3d[b].astype(np.float32)
        if method == "gaussian":
            ksize = max(1, int(kwargs.get("ksize", 5)) | 1)
            arr3d[b] = cv2.GaussianBlur(channel, (ksize, ksize), 0)
        elif method == "median":
            ksize = max(1, int(kwargs.get("ksize", 5)) | 1)
            arr3d[b] = cv2.medianBlur(channel.astype(np.uint8), ksize).astype(np.float64)
        elif method == "bilateral":
            d = kwargs.get("d", 9)
            sigma_color = kwargs.get("sigma_color", 75)
            sigma_space = kwargs.get("sigma_space", 75)
            arr3d[b] = cv2.bilateralFilter(channel, d, sigma_color, sigma_space)
        else:
            raise ValueError(f"método de denoise inválido: {method}")

    return arr3d if result.ndim == 3 else arr3d[0]


def local_contrast_enhancement(image: np.ndarray, amount: float = 1.0, radius: int = 30, nodata: float | None = None) -> np.ndarray:
    """Realce local de contraste via unsharp mask de grande raio (efeito 'clarity')."""
    return unsharp_mask(image, radius=radius, amount=amount, nodata=nodata)


def edge_detection(image: np.ndarray, nodata: float | None = None) -> np.ndarray:
    """Detecção simples de bordas (Sobel), apenas para apoio visual/diagnóstico."""
    result = image.astype(np.float64).copy()
    bands = result.shape[0] if result.ndim == 3 else 1
    arr3d = result if result.ndim == 3 else result[np.newaxis, ...]

    output = np.zeros_like(arr3d)
    for b in range(bands):
        channel = arr3d[b].astype(np.float32)
        sobel_x = cv2.Sobel(channel, cv2.CV_64F, 1, 0, ksize=3)
        sobel_y = cv2.Sobel(channel, cv2.CV_64F, 0, 1, ksize=3)
        magnitude = np.sqrt(sobel_x ** 2 + sobel_y ** 2)
        output[b] = np.clip(magnitude, 0, 255)

    return output if result.ndim == 3 else output[0]


# ----------------------------------------------------------------------
# Correções atmosféricas/visuais simples (NÃO científicas)
# ----------------------------------------------------------------------
def reduce_haze(image_rgb: np.ndarray, strength: float = 0.5, nodata: float | None = None) -> np.ndarray:
    """Redução simples de neblina/haze via subtração do valor mínimo local (dark channel
    simplificado). Heurística visual, não correção atmosférica científica."""
    result = image_rgb.astype(np.float64).copy()
    dark_channel = np.min(result, axis=0)

    ksize = max(3, int(min(result.shape[1], result.shape[2]) * 0.02) | 1)
    atmospheric_light = cv2.GaussianBlur(dark_channel, (ksize, ksize), 0)

    for c in range(result.shape[0]):
        transmission = 1.0 - strength * (atmospheric_light / 255.0)
        transmission = np.clip(transmission, 0.2, 1.0)
        result[c] = np.clip((result[c] - atmospheric_light * strength) / transmission, 0, 255)

    return result


def enhance_washed_out(image_rgb: np.ndarray, strength: float = 1.0, nodata: float | None = None) -> np.ndarray:
    """Melhora contraste em imagens 'lavadas' (baixo contraste, histograma estreito)."""
    result = image_rgb.astype(np.float64).copy()
    mask = _valid_mask_nd(result, nodata)

    for c in range(result.shape[0]):
        channel = result[c]
        valid = channel[mask]
        if valid.size == 0:
            continue
        p_low, p_high = np.percentile(valid, [5 - strength, 95 + strength])
        p_low, p_high = max(0, p_low), min(255, p_high)
        if p_high <= p_low:
            continue
        stretched = np.clip((channel - p_low) / (p_high - p_low) * 255, 0, 255)
        result[c] = np.where(mask, stretched, channel)

    return result


def enhance_dark_areas(image_rgb: np.ndarray, strength: float = 0.5, nodata: float | None = None) -> np.ndarray:
    """Realça áreas escuras (sombras) sem afetar muito os realces."""
    result = image_rgb.astype(np.float64).copy()
    for c in range(result.shape[0]):
        norm = result[c] / 255.0
        shadow_weight = np.clip(1.0 - norm * 2.0, 0, 1)
        boosted = norm + shadow_weight * strength * 0.3
        result[c] = np.clip(boosted * 255.0, 0, 255)
    return result


def control_highlights(image_rgb: np.ndarray, strength: float = 0.5, nodata: float | None = None) -> np.ndarray:
    """Reduz estouro de luz em altas luzes (highlights), preservando detalhes."""
    result = image_rgb.astype(np.float64).copy()
    for c in range(result.shape[0]):
        norm = result[c] / 255.0
        highlight_weight = np.clip((norm - 0.7) * 3.3, 0, 1)
        reduced = norm - highlight_weight * strength * 0.3
        result[c] = np.clip(reduced * 255.0, 0, 255)
    return result


def mask_saturated_pixels(image_rgb: np.ndarray, threshold: float = 250.0, nodata: float | None = None) -> np.ndarray:
    """Retorna uma máscara binária (H, W) marcando pixels saturados (próximos de 255) em qualquer canal."""
    return np.any(image_rgb >= threshold, axis=0).astype(np.float64)


def mask_dark_pixels(image_rgb: np.ndarray, threshold: float = 5.0, nodata: float | None = None) -> np.ndarray:
    """Retorna uma máscara binária (H, W) marcando pixels muito escuros (próximos de 0) em todos os canais."""
    return np.all(image_rgb <= threshold, axis=0).astype(np.float64)


# ----------------------------------------------------------------------
# Harmonização de ortomosaico
# ----------------------------------------------------------------------
def smooth_flight_line_differences(image_rgb: np.ndarray, kernel_fraction: float = 0.08, nodata: float | None = None) -> np.ndarray:
    """Suaviza diferenças de iluminação entre faixas de voo de um ortomosaico,
    via normalização local (flattening), similar à correção de iluminação desigual."""
    result = image_rgb.astype(np.float64).copy()
    h, w = result.shape[1], result.shape[2]
    ksize = max(3, int(min(h, w) * kernel_fraction) | 1)

    for c in range(result.shape[0]):
        channel = result[c]
        local_mean = cv2.GaussianBlur(channel, (ksize, ksize), 0)
        local_mean = np.where(local_mean == 0, 1.0, local_mean)
        global_mean = channel.mean()
        flattened = channel / local_mean * global_mean
        result[c] = np.clip(flattened, 0, 255)

    return result


def reduce_luminosity_patches(image_rgb: np.ndarray, strength: float = 0.5, nodata: float | None = None) -> np.ndarray:
    """Reduz manchas de luminosidade (variações suaves e localizadas de brilho)."""
    result = image_rgb.astype(np.float64).copy()
    h, w = result.shape[1], result.shape[2]
    ksize = max(3, int(min(h, w) * 0.15) | 1)

    for c in range(result.shape[0]):
        channel = result[c]
        large_scale_variation = cv2.GaussianBlur(channel, (ksize, ksize), 0)
        correction = channel.mean() - large_scale_variation
        result[c] = np.clip(channel + correction * strength, 0, 255)

    return result


def match_histogram(source: np.ndarray, reference: np.ndarray, nodata: float | None = None) -> np.ndarray:
    """Aplica histogram matching: ajusta `source` para ter a mesma distribuição
    de `reference`. Ambos shape (bands, H, W) com o mesmo número de bandas."""
    if source.shape[0] != reference.shape[0]:
        raise ValueError("source e reference devem ter o mesmo número de bandas.")

    result = np.zeros_like(source, dtype=np.float64)
    for b in range(source.shape[0]):
        matched = exposure.match_histograms(source[b].astype(np.float64), reference[b].astype(np.float64))
        result[b] = matched

    return result


def match_histogram_from_region(
    image: np.ndarray,
    reference_region_mask: np.ndarray,
    target_region_mask: np.ndarray,
    nodata: float | None = None,
) -> np.ndarray:
    """Usa uma região da própria imagem como referência de histograma e aplica
    o padrão resultante em outra região (útil para harmonizar blocos de uma ortofoto).

    reference_region_mask / target_region_mask: bool 2D (H, W).
    """
    result = image.astype(np.float64).copy()
    bands = result.shape[0]

    for b in range(bands):
        channel = result[b]
        ref_values = channel[reference_region_mask]
        target_values = channel[target_region_mask]

        if ref_values.size == 0 or target_values.size == 0:
            continue

        ref_sorted = np.sort(ref_values)
        target_sorted_idx = np.argsort(target_values)
        n_ref, n_target = ref_sorted.size, target_values.size

        interpolated = np.interp(
            np.linspace(0, n_ref - 1, n_target),
            np.arange(n_ref),
            ref_sorted,
        )

        matched_target = np.empty_like(target_values)
        matched_target[target_sorted_idx] = interpolated

        new_channel = channel.copy()
        new_channel[target_region_mask] = matched_target
        result[b] = new_channel

    return result