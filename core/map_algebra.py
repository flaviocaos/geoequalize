"""
Álgebra de mapas e reclassificação.

Responsabilidade:
- Reclassificar um raster contínuo em classes discretas, a partir de
  intervalos definidos pelo usuário (ex.: NDVI -> "solo", "vegetação rala",
  "vegetação densa")
- Combinar múltiplos rasters reclassificados via operações lógicas/aritméticas
  simples (E, OU, soma ponderada) — base para MCDA na próxima etapa
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

import numpy as np


@dataclass
class ReclassRule:
    """Uma regra de reclassificação: intervalo [min, max) -> novo valor de classe."""
    min_value: float
    max_value: float
    new_class: int
    label: str = ""


@dataclass
class ReclassScheme:
    """Conjunto de regras de reclassificação, aplicadas em ordem."""
    rules: list[ReclassRule] = field(default_factory=list)
    nodata_class: int = 0  # valor atribuído a pixels que não caem em nenhuma regra ou são NoData


def reclassify(
    array: np.ndarray,
    scheme: ReclassScheme,
    nodata: Optional[float] = None,
) -> np.ndarray:
    """Aplica um esquema de reclassificação a um array 2D contínuo.

    Pixels que não se encaixam em nenhuma regra recebem `scheme.nodata_class`.
    """
    result = np.full(array.shape, scheme.nodata_class, dtype=np.int32)

    valid_mask = np.isfinite(array)
    if nodata is not None:
        valid_mask &= array != nodata

    for rule in scheme.rules:
        rule_mask = valid_mask & (array >= rule.min_value) & (array < rule.max_value)
        result[rule_mask] = rule.new_class

    return result


def classes_to_rgb(
    classes: np.ndarray,
    class_colors: dict[int, tuple[int, int, int]],
    default_color: tuple[int, int, int] = (200, 200, 200),
) -> np.ndarray:
    """Converte um raster de classes inteiras em uma imagem RGB (3, H, W) para
    visualização, usando um dict {classe: (r,g,b)}."""
    h, w = classes.shape
    rgb = np.zeros((3, h, w), dtype=np.float64)

    unique_classes = np.unique(classes)
    for cls in unique_classes:
        color = class_colors.get(int(cls), default_color)
        mask = classes == cls
        for c in range(3):
            rgb[c][mask] = color[c]

    return rgb


# ----------------------------------------------------------------------
# Operações de álgebra de mapas entre múltiplos rasters reclassificados
# ----------------------------------------------------------------------
def logical_and(*class_arrays: np.ndarray, true_classes: list[set[int]]) -> np.ndarray:
    """Retorna 1 onde TODOS os rasters estão em sua respectiva lista de classes-verdadeiras, 0 caso contrário.

    true_classes[i] é o conjunto de valores de classe considerados "verdadeiro" no i-ésimo array.
    """
    if len(class_arrays) != len(true_classes):
        raise ValueError("Número de arrays e de conjuntos de classes-verdadeiras deve coincidir.")

    result = np.ones(class_arrays[0].shape, dtype=bool)
    for array, true_set in zip(class_arrays, true_classes):
        result &= np.isin(array, list(true_set))
    return result.astype(np.int32)


def logical_or(*class_arrays: np.ndarray, true_classes: list[set[int]]) -> np.ndarray:
    """Retorna 1 onde QUALQUER raster está em sua respectiva lista de classes-verdadeiras."""
    if len(class_arrays) != len(true_classes):
        raise ValueError("Número de arrays e de conjuntos de classes-verdadeiras deve coincidir.")

    result = np.zeros(class_arrays[0].shape, dtype=bool)
    for array, true_set in zip(class_arrays, true_classes):
        result |= np.isin(array, list(true_set))
    return result.astype(np.int32)


def weighted_sum(arrays: list[np.ndarray], weights: list[float]) -> np.ndarray:
    """Soma ponderada simples de N rasters (já normalizados/reclassificados
    para uma escala comparável). Usado como base para MCDA."""
    if len(arrays) != len(weights):
        raise ValueError("Número de arrays e de pesos deve coincidir.")
    if abs(sum(weights) - 1.0) > 1e-6:
        raise ValueError(f"Os pesos devem somar 1.0 (soma atual: {sum(weights):.4f}).")

    result = np.zeros(arrays[0].shape, dtype=np.float64)
    for array, weight in zip(arrays, weights):
        result += array.astype(np.float64) * weight
    return result


def normalize_to_unit_scale(array: np.ndarray, nodata: Optional[float] = None) -> np.ndarray:
    """Normaliza um raster contínuo para a escala 0-1 (min-max), usado para
    tornar critérios comparáveis antes da soma ponderada em MCDA."""
    valid_mask = np.isfinite(array)
    if nodata is not None:
        valid_mask &= array != nodata

    if not valid_mask.any():
        return np.zeros_like(array, dtype=np.float64)

    vmin = array[valid_mask].min()
    vmax = array[valid_mask].max()
    if vmax <= vmin:
        return np.zeros_like(array, dtype=np.float64)

    result = np.zeros_like(array, dtype=np.float64)
    result[valid_mask] = (array[valid_mask] - vmin) / (vmax - vmin)
    return result