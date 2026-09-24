"""
Diálogo de perfil espectral: mostra um gráfico de linha com o valor de
cada banda no pixel clicado pelo usuário.

Este é um arquivo NOVO. Crie-o em app/ui/spectral_profile_dialog.py.
"""
from __future__ import annotations

from typing import Optional

import numpy as np
import pyqtgraph as pg
from PySide6.QtWidgets import QDialog, QVBoxLayout, QLabel

pg.setConfigOption("background", "w")
pg.setConfigOption("foreground", "k")


class SpectralProfileDialog(QDialog):
    """Janela não-modal exibindo o perfil espectral de um pixel."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Perfil espectral")
        self.resize(480, 360)

        layout = QVBoxLayout(self)
        self._coord_label = QLabel("")
        layout.addWidget(self._coord_label)

        self._plot = pg.PlotWidget(title="Valor por banda")
        self._plot.setLabel("bottom", "Banda")
        self._plot.setLabel("left", "Valor do pixel")
        layout.addWidget(self._plot)

        self.setLayout(layout)

    def update_profile(self, x: int, y: int, values: np.ndarray) -> None:
        self._coord_label.setText(f"Pixel ({x}, {y}) — {len(values)} banda(s)")
        self._plot.clear()

        band_indexes = np.arange(1, len(values) + 1)
        self._plot.plot(
            band_indexes, values,
            pen=pg.mkPen("#1e3a5f", width=2),
            symbol="o", symbolBrush="#f97316", symbolSize=8,
        )
        self.show()
        self.raise_()
        self.activateWindow()