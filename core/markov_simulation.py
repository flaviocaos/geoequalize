"""
Cadeias de Markov e simulação CA-Markov (Cellular Automata + Markov Chain).

Responsabilidade:
- Calcular a matriz de transição de probabilidades entre duas classificações
  de uso do solo em datas diferentes (T1 -> T2)
- Projetar a quantidade de pixels esperada por classe em uma data futura,
  a partir da matriz de transição (cadeia de Markov pura)
- Simular a alocação espacial dessas mudanças usando autômatos celulares
  (CA), guiados por um mapa de aptidão (ex.: resultado do MCDA) — esta é a
  combinação CA-Markov clássica usada no módulo "Land Change Modeler" do
  IDRISI / TerrSet.

Limitações desta implementação:
- O CA usa uma regra de vizinhança simples (contagem de vizinhos da
  classe-alvo em uma janela 3x3) combinada ao mapa de aptidão, não as
  regras completas e calibráveis do IDRISI — mas captura a lógica central:
  "células mudam de classe preferencialmente onde há alta aptidão E
  proximidade de células já daquela classe".
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy.ndimage import uniform_filter


@dataclass
class TransitionMatrix:
    classes: list[int]
    matrix: np.ndarray  # shape (n_classes, n_classes), matrix[i,j] = P(classe_i -> classe_j)
    pixel_counts_t1: dict[int, int]
    pixel_counts_t2: dict[int, int]


def compute_transition_matrix(classes_t1: np.ndarray, classes_t2: np.ndarray) -> TransitionMatrix:
    """Calcula a matriz de transição de probabilidades entre dois rasters de
    classificação categórica (mesma forma, mesmas classes possíveis)."""
    if classes_t1.shape != classes_t2.shape:
        raise ValueError("classes_t1 e classes_t2 devem ter a mesma forma (mesma extensão espacial).")

    all_classes = sorted(set(np.unique(classes_t1).tolist()) | set(np.unique(classes_t2).tolist()))
    n = len(all_classes)
    class_to_idx = {c: i for i, c in enumerate(all_classes)}

    matrix = np.zeros((n, n), dtype=np.float64)
    pixel_counts_t1 = {c: int(np.sum(classes_t1 == c)) for c in all_classes}
    pixel_counts_t2 = {c: int(np.sum(classes_t2 == c)) for c in all_classes}

    for c1 in all_classes:
        mask_t1 = classes_t1 == c1
        total_t1 = pixel_counts_t1[c1]
        if total_t1 == 0:
            continue
        for c2 in all_classes:
            count_transition = int(np.sum(mask_t1 & (classes_t2 == c2)))
            matrix[class_to_idx[c1], class_to_idx[c2]] = count_transition / total_t1

    return TransitionMatrix(
        classes=all_classes, matrix=matrix,
        pixel_counts_t1=pixel_counts_t1, pixel_counts_t2=pixel_counts_t2,
    )


def project_class_quantities(transition: TransitionMatrix, n_steps: int = 1) -> dict[int, int]:
    """Projeta a quantidade de pixels por classe após `n_steps` períodos de
    transição (cadeia de Markov pura, sem alocação espacial)."""
    classes = transition.classes
    current_counts = np.array([transition.pixel_counts_t2[c] for c in classes], dtype=np.float64)
    total_pixels = current_counts.sum()

    current_proportions = current_counts / total_pixels if total_pixels > 0 else current_counts

    matrix_power = np.linalg.matrix_power(transition.matrix, n_steps) if n_steps > 1 else transition.matrix
    projected_proportions = current_proportions @ matrix_power

    projected_counts = {
        c: int(round(projected_proportions[i] * total_pixels))
        for i, c in enumerate(classes)
    }
    return projected_counts


def run_ca_markov_simulation(
    current_classes: np.ndarray,
    suitability_per_class: dict[int, np.ndarray],
    target_quantities: dict[int, int],
    neighborhood_size: int = 3,
    neighborhood_weight: float = 0.5,
) -> np.ndarray:
    """Simula a alocação espacial de mudanças de uso do solo (CA-Markov).

    current_classes: raster de classes na data atual.
    suitability_per_class: dict {classe: raster de aptidão 0-1 para essa classe}
        (tipicamente o resultado de uma análise MCDA por classe-alvo).
    target_quantities: dict {classe: número de pixels desejado no resultado},
        geralmente vindo de project_class_quantities().
    neighborhood_size: tamanho da janela de vizinhança (deve ser ímpar).
    neighborhood_weight: peso (0-1) dado à influência da vizinhança vs. aptidão pura.

    Retorna um novo raster de classes simulado, com a contagem de pixels por
    classe aproximando os valores em target_quantities.
    """
    result = current_classes.copy()
    all_classes = list(target_quantities.keys())

    # Calcula um score combinado (aptidão + vizinhança) por classe-candidata.
    combined_scores: dict[int, np.ndarray] = {}
    for cls in all_classes:
        suitability = suitability_per_class.get(cls)
        if suitability is None:
            suitability = np.zeros(current_classes.shape, dtype=np.float64)

        is_class_mask = (current_classes == cls).astype(np.float64)
        neighborhood_density = uniform_filter(is_class_mask, size=neighborhood_size)

        combined = (1 - neighborhood_weight) * suitability + neighborhood_weight * neighborhood_density
        combined_scores[cls] = combined

    current_counts = {cls: int(np.sum(current_classes == cls)) for cls in all_classes}

    for cls in all_classes:
        target = target_quantities.get(cls, current_counts.get(cls, 0))
        current = current_counts.get(cls, 0)
        cells_to_add = target - current

        if cells_to_add <= 0:
            continue

        score = combined_scores[cls]
        candidate_mask = current_classes != cls
        candidate_scores = np.where(candidate_mask, score, -np.inf)

        flat_indices = np.argsort(candidate_scores.ravel())[::-1]
        flat_indices = flat_indices[:cells_to_add]

        rows, cols = np.unravel_index(flat_indices, current_classes.shape)
        result[rows, cols] = cls

    return result


def classes_array_to_palette(classes: np.ndarray, class_colors: dict[int, tuple[int, int, int]]) -> np.ndarray:
    """Reaproveita a lógica de visualização de classes (RGB), útil para
    exibir tanto o estado atual quanto o simulado lado a lado."""
    from core.map_algebra import classes_to_rgb
    return classes_to_rgb(classes, class_colors)