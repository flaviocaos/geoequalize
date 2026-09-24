"""
Análise Multicritério (MCDA — Multi-Criteria Decision Analysis).

Responsabilidade:
- Combinar múltiplos critérios (rasters), cada um normalizado para escala
  0-1 e com um peso definido pelo usuário, em um único mapa de aptidão
  (suitability map), via combinação linear ponderada (WLC).
- Aplicar restrições booleanas (constraints) — áreas totalmente excluídas
  da análise, independente do escore (ex.: áreas de preservação).

Esta é uma implementação do método clássico de "Weighted Linear
Combination" (WLC), o núcleo da análise multicritério usada em
ferramentas como o IDRISI (módulo MCE) e o ArcGIS (Weighted Overlay).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

import numpy as np

from core.map_algebra import normalize_to_unit_scale


@dataclass
class Criterion:
    """Um critério de decisão: um raster, seu peso, e se valores altos ou
    baixos são favoráveis (benefit vs cost)."""
    name: str
    array: np.ndarray
    weight: float
    higher_is_better: bool = True
    nodata: Optional[float] = None


@dataclass
class Constraint:
    """Uma restrição booleana: máscara onde True = área excluída da análise."""
    name: str
    excluded_mask: np.ndarray


@dataclass
class MCDAResult:
    suitability: np.ndarray  # 0-1, já com restrições aplicadas (excluídas = NaN)
    raw_suitability: np.ndarray  # 0-1, sem restrições aplicadas
    criteria_weights: dict[str, float] = field(default_factory=dict)


def validate_weights(criteria: list[Criterion]) -> None:
    total = sum(c.weight for c in criteria)
    if abs(total - 1.0) > 1e-3:
        raise ValueError(f"A soma dos pesos deve ser 1.0 (soma atual: {total:.4f}).")


def run_weighted_linear_combination(
    criteria: list[Criterion],
    constraints: Optional[list[Constraint]] = None,
) -> MCDAResult:
    """Executa a combinação linear ponderada (WLC) clássica de MCDA.

    1. Cada critério é normalizado para 0-1 (invertendo a escala se
       higher_is_better=False, já que "menor é melhor" nesses casos).
    2. Os critérios normalizados são somados conforme seus pesos.
    3. As restrições (constraints) zeram/excluem áreas do resultado final.
    """
    if not criteria:
        raise ValueError("É necessário ao menos um critério.")

    validate_weights(criteria)

    normalized_layers = []
    for criterion in criteria:
        normalized = normalize_to_unit_scale(criterion.array, nodata=criterion.nodata)
        if not criterion.higher_is_better:
            normalized = 1.0 - normalized
        normalized_layers.append(normalized)

    raw_suitability = np.zeros(criteria[0].array.shape, dtype=np.float64)
    for criterion, normalized in zip(criteria, normalized_layers):
        raw_suitability += normalized * criterion.weight

    suitability = raw_suitability.copy()
    if constraints:
        combined_exclusion = np.zeros(suitability.shape, dtype=bool)
        for constraint in constraints:
            combined_exclusion |= constraint.excluded_mask
        suitability = np.where(combined_exclusion, np.nan, suitability)

    return MCDAResult(
        suitability=suitability,
        raw_suitability=raw_suitability,
        criteria_weights={c.name: c.weight for c in criteria},
    )


def suitability_to_rgb_display(suitability: np.ndarray) -> np.ndarray:
    """Converte o mapa de aptidão (0-1, com NaN nas áreas restritas) em uma
    imagem RGB: vermelho (baixa aptidão) -> amarelo -> verde (alta aptidão).
    Áreas restritas (NaN) aparecem em cinza neutro."""
    h, w = suitability.shape
    rgb = np.zeros((3, h, w), dtype=np.float64)

    valid_mask = np.isfinite(suitability)
    clipped = np.clip(np.nan_to_num(suitability, nan=0.0), 0, 1)

    stops = np.array([0.0, 0.5, 1.0])
    colors = np.array([
        [200, 40, 40],    # vermelho — baixa aptidão
        [230, 220, 80],   # amarelo — aptidão média
        [30, 140, 60],    # verde — alta aptidão
    ], dtype=np.float64)

    for c in range(3):
        rgb[c] = np.interp(clipped, stops, colors[:, c])
        rgb[c] = np.where(valid_mask, rgb[c], 160)  # cinza nas áreas restritas

    return rgb