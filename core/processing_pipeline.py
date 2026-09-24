"""
Pipeline de operações de processamento (não destrutivo).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Optional
import numpy as np


@dataclass
class Operation:
    """Uma única operação no pipeline (ex.: stretch linear, gamma, balanceamento)."""
    name: str
    func: Callable[[np.ndarray, dict], np.ndarray]
    params: dict = field(default_factory=dict)
    enabled: bool = True
    mask: Optional[np.ndarray] = None  # usado para correções locais (Fase 4)


class ProcessingPipeline:
    """Mantém e aplica uma sequência de operações sobre uma imagem (todas as bandas)."""

    def __init__(self) -> None:
        self._operations: list[Operation] = []

    def add_operation(self, operation: Operation) -> None:
        self._operations.append(operation)

    def remove_operation(self, index: int) -> None:
        del self._operations[index]

    def reorder(self, old_index: int, new_index: int) -> None:
        op = self._operations.pop(old_index)
        self._operations.insert(new_index, op)

    def reset(self) -> None:
        self._operations.clear()

    def apply(self, image: np.ndarray, nodata: float | None = None) -> np.ndarray:
        """Aplica todas as operações habilitadas, em ordem, sobre uma cópia da imagem.

        `image` tem shape (bands, H, W). Cada operação é aplicada banda a banda.
        """
        result = image.astype(np.float64).copy()
        for op in self._operations:
            if not op.enabled:
                continue
            params = dict(op.params)
            params["nodata"] = nodata
            for b in range(result.shape[0]):
                corrected = op.func(result[b], params)
                if op.mask is not None:
                    result[b] = np.where(op.mask, corrected, result[b])
                else:
                    result[b] = corrected
        return result

    @property
    def operations(self) -> list[Operation]:
        return list(self._operations)