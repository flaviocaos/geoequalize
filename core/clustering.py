"""
Segmentação não-supervisionada (clustering espectral) para análise
exploratória de uso/cobertura do solo, sem depender de modelos
pré-treinados ou rótulos.

Responsabilidade:
- Agrupar pixels por similaridade espectral (cor) usando K-Means
- Opcionalmente, considerar contexto espacial simples (média local) para
  reduzir ruído "sal e pimenta" típico de clustering pixel a pixel
- Gerar paleta de cores automática para visualizar os clusters
- Calcular estatísticas básicas por cluster (área, cor média) para apoiar
  a interpretação manual ("cluster 2 parece ser vegetação")

O resultado (raster de classes inteiras) é compatível com o módulo de
Geoprocessamento já existente (core.map_algebra, core.mcda) — pode ser
usado diretamente como camada de entrada para reclassificação ou MCDA.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from sklearn.cluster import KMeans
from scipy.ndimage import uniform_filter


@dataclass
class ClusterResult:
    labels: np.ndarray  # shape (H, W), valores 0..n_clusters-1
    cluster_centers: np.ndarray  # shape (n_clusters, n_features), centróides no espaço espectral
    cluster_colors: dict[int, tuple[int, int, int]]  # cor representativa de cada cluster (RGB 0-255)
    pixel_counts: dict[int, int]  # quantidade de pixels por cluster
    n_clusters: int


def _build_feature_matrix(
    image: np.ndarray,
    nodata: float | None,
    spatial_smoothing: int,
) -> tuple[np.ndarray, np.ndarray]:
    """Monta a matriz de features (pixels x bandas) para o K-Means.

    image: shape (bands, H, W).
    Retorna (features, valid_mask) onde valid_mask é shape (H, W).
    """
    bands, h, w = image.shape

    if spatial_smoothing > 1:
        smoothed = np.empty_like(image, dtype=np.float64)
        for b in range(bands):
            smoothed[b] = uniform_filter(image[b].astype(np.float64), size=spatial_smoothing)
        working = smoothed
    else:
        working = image.astype(np.float64)

    valid_mask = np.all(np.isfinite(working), axis=0)
    if nodata is not None:
        valid_mask &= np.all(working != nodata, axis=0)

    features = working[:, valid_mask].T  # shape (n_valid_pixels, bands)
    return features, valid_mask


def run_kmeans_clustering(
    image: np.ndarray,
    n_clusters: int = 5,
    nodata: float | None = None,
    spatial_smoothing: int = 3,
    random_state: int = 42,
    sample_size: int | None = 200_000,
) -> ClusterResult:
    """Executa K-Means sobre as bandas da imagem.

    image: shape (bands, H, W). Funciona com qualquer número de bandas
    (1 banda = clustering por intensidade; 3+ = clustering espectral real).

    sample_size: se a imagem tiver mais pixels válidos que isso, o K-Means
    é ajustado (fit) em uma amostra aleatória para manter a performance,
    e depois aplicado (predict) em todos os pixels.
    """
    if image.ndim == 2:
        image = image[np.newaxis, ...]

    features, valid_mask = _build_feature_matrix(image, nodata, spatial_smoothing)

    if features.shape[0] == 0:
        raise ValueError("Nenhum pixel válido encontrado para clustering.")

    rng = np.random.default_rng(random_state)
    if sample_size is not None and features.shape[0] > sample_size:
        sample_idx = rng.choice(features.shape[0], size=sample_size, replace=False)
        fit_features = features[sample_idx]
    else:
        fit_features = features

    kmeans = KMeans(n_clusters=n_clusters, random_state=random_state, n_init=10)
    kmeans.fit(fit_features)

    all_labels = kmeans.predict(features)

    h, w = image.shape[1], image.shape[2]
    labels_full = np.full((h, w), -1, dtype=np.int32)
    labels_full[valid_mask] = all_labels

    pixel_counts = {int(c): int(np.sum(all_labels == c)) for c in range(n_clusters)}

    cluster_colors = _generate_cluster_colors(kmeans.cluster_centers_, image.shape[0])

    return ClusterResult(
        labels=labels_full,
        cluster_centers=kmeans.cluster_centers_,
        cluster_colors=cluster_colors,
        pixel_counts=pixel_counts,
        n_clusters=n_clusters,
    )


def _generate_cluster_colors(centers: np.ndarray, band_count: int) -> dict[int, tuple[int, int, int]]:
    """Gera uma cor RGB representativa para cada cluster a partir dos
    centróides. Se houver 3+ bandas, usa as 3 primeiras como RGB direto
    (normalizado); se houver menos, usa uma paleta categórica fixa."""
    n_clusters = centers.shape[0]
    colors: dict[int, tuple[int, int, int]] = {}

    if band_count >= 3:
        rgb_part = centers[:, :3]
        vmin, vmax = rgb_part.min(), rgb_part.max()
        if vmax > vmin:
            normalized = (rgb_part - vmin) / (vmax - vmin) * 255
        else:
            normalized = np.zeros_like(rgb_part)
        for i in range(n_clusters):
            colors[i] = tuple(int(v) for v in normalized[i])
    else:
        palette = [
            (230, 25, 75), (60, 180, 75), (255, 225, 25), (0, 130, 200),
            (245, 130, 48), (145, 30, 180), (70, 240, 240), (240, 50, 230),
            (210, 245, 60), (250, 190, 212),
        ]
        for i in range(n_clusters):
            colors[i] = palette[i % len(palette)]

    return colors


def clusters_to_rgb_display(result: ClusterResult) -> np.ndarray:
    """Converte o raster de labels em uma imagem RGB (3, H, W) para visualização."""
    h, w = result.labels.shape
    rgb = np.zeros((3, h, w), dtype=np.float64)

    for cluster_id, color in result.cluster_colors.items():
        mask = result.labels == cluster_id
        for c in range(3):
            rgb[c][mask] = color[c]

    return rgb


def estimate_optimal_k(
    image: np.ndarray,
    k_range: range = range(2, 9),
    nodata: float | None = None,
    spatial_smoothing: int = 3,
    sample_size: int = 50_000,
) -> dict[int, float]:
    """Calcula a inércia (within-cluster sum of squares) para cada k no
    intervalo, útil para o usuário escolher um bom número de clusters
    via 'método do cotovelo' (elbow method)."""
    if image.ndim == 2:
        image = image[np.newaxis, ...]

    features, _ = _build_feature_matrix(image, nodata, spatial_smoothing)
    if features.shape[0] == 0:
        raise ValueError("Nenhum pixel válido encontrado.")

    rng = np.random.default_rng(42)
    if features.shape[0] > sample_size:
        sample_idx = rng.choice(features.shape[0], size=sample_size, replace=False)
        features = features[sample_idx]

    inertias: dict[int, float] = {}
    for k in k_range:
        kmeans = KMeans(n_clusters=k, random_state=42, n_init=5)
        kmeans.fit(features)
        inertias[k] = float(kmeans.inertia_)

    return inertias