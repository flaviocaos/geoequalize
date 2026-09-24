"""
Painel lateral de histograma — usa PyQtGraph para plotagem leve.
"""
from __future__ import annotations

from typing import Optional

import numpy as np
import pyqtgraph as pg
from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QFormLayout, QTabWidget

from core.histogram_tools import compute_histogram, compute_band_statistics

pg.setConfigOption("background", "w")
pg.setConfigOption("foreground", "k")

_BAND_COLORS = ["r", "g", "b", "k"]
_BAND_NAMES = ["Vermelho (R)", "Verde (G)", "Azul (B)", "Banda"]


class HistogramPanel(QWidget):
    """Exibe histogramas por banda e estatísticas, antes/depois da correção."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("<b>Histograma</b>"))

        self._tabs = QTabWidget()
        layout.addWidget(self._tabs)

        self._plot_before = pg.PlotWidget(title="Antes da correção")
        self._plot_after = pg.PlotWidget(title="Depois da correção")
        self._tabs.addTab(self._plot_before, "Antes")
        self._tabs.addTab(self._plot_after, "Depois")

        self._stats_form = QFormLayout()
        layout.addLayout(self._stats_form)
        layout.addStretch()

        self.setLayout(layout)
        self._placeholder = QLabel("Nenhuma imagem aberta.")
        self._stats_form.addRow(self._placeholder)

    def update_histogram(self, image: np.ndarray, nodata: float | None = None, corrected: Optional[np.ndarray] = None) -> None:
        """image/corrected têm shape (bands, H, W). Plota até 3 bandas (RGB) ou 1 (cinza)."""
        self._plot_before.clear()
        self._plot_after.clear()

        bands = image.shape[0]
        names = _BAND_NAMES if bands >= 3 else ["Banda (escala de cinza)"]

        for i in range(min(bands, 3) if bands >= 3 else 1):
            counts, edges = compute_histogram(image[i], bins=256, nodata=nodata)
            color = _BAND_COLORS[i] if bands >= 3 else "k"
            self._plot_before.plot(edges, counts, stepMode="center", fillLevel=0, brush=color, pen=color)

            if corrected is not None:
                counts_c, edges_c = compute_histogram(corrected[i], bins=256, nodata=nodata)
                self._plot_after.plot(edges_c, counts_c, stepMode="center", fillLevel=0, brush=color, pen=color)

        self._update_statistics(image, nodata, names)

    def _update_statistics(self, image: np.ndarray, nodata: float | None, names: list[str]) -> None:
        while self._stats_form.rowCount() > 0:
            self._stats_form.removeRow(0)

        bands = min(image.shape[0], 3) if image.shape[0] >= 3 else 1
        for i in range(bands):
            stats = compute_band_statistics(image[i], nodata=nodata)
            label_name = names[i] if i < len(names) else f"Banda {i + 1}"
            summary = (
                f"min={stats['min']:.1f}  max={stats['max']:.1f}  "
                f"média={stats['mean']:.1f}  std={stats['std']:.1f}  "
                f"p2={stats['p2']:.1f}  p98={stats['p98']:.1f}"
                if stats["min"] is not None else "sem dados válidos"
            )
            self._stats_form.addRow(f"{label_name}:", QLabel(summary))

    def clear(self) -> None:
        self._plot_before.clear()
        self._plot_after.clear()
        while self._stats_form.rowCount() > 0:
            self._stats_form.removeRow(0)
        self._stats_form.addRow(QLabel("Nenhuma imagem aberta."))