"""
Painel de gerenciamento de bandas, composições e estatísticas avançadas.

Este é um arquivo NOVO desta fase. Crie-o em app/ui/bands_panel.py.
"""
from __future__ import annotations

from typing import Optional

from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QFormLayout,
    QLabel,
    QComboBox,
    QSpinBox,
    QPushButton,
    QGroupBox,
    QHBoxLayout,
    QListWidget,
    QListWidgetItem,
)
from PySide6.QtCore import Signal

from core.band_tools import BandInfo, COMPOSITION_PRESETS, COMPOSITION_LABELS


class BandsPanel(QWidget):
    """Painel lateral para seleção de bandas, composições e estatísticas avançadas."""

    composition_changed = Signal(int, int, int)  # (r_index, g_index, b_index) 1-based
    preset_apply_requested = Signal(str)          # chave do preset
    band_selected_for_stats = Signal(int)          # índice 1-based, para estatísticas/histograma

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("<b>Bandas</b>"))

        self._band_list = QListWidget()
        self._band_list.currentRowChanged.connect(self._on_band_row_changed)
        layout.addWidget(self._band_list)

        composition_group = QGroupBox("Composição RGB")
        composition_form = QFormLayout()
        composition_group.setLayout(composition_form)

        self._spin_r = QSpinBox()
        self._spin_g = QSpinBox()
        self._spin_b = QSpinBox()
        for spin in (self._spin_r, self._spin_g, self._spin_b):
            spin.setMinimum(1)
            spin.setMaximum(1)

        composition_form.addRow("Banda R:", self._spin_r)
        composition_form.addRow("Banda G:", self._spin_g)
        composition_form.addRow("Banda B:", self._spin_b)

        self._btn_apply_composition = QPushButton("Aplicar composição")
        composition_form.addRow(self._btn_apply_composition)

        layout.addWidget(composition_group)

        preset_group = QGroupBox("Composições predefinidas")
        preset_layout = QVBoxLayout()
        preset_group.setLayout(preset_layout)

        self._preset_combo = QComboBox()
        for key, label in COMPOSITION_LABELS.items():
            self._preset_combo.addItem(label, key)
        preset_layout.addWidget(self._preset_combo)

        self._btn_apply_preset = QPushButton("Aplicar preset")
        preset_layout.addWidget(self._btn_apply_preset)
        preset_layout.addWidget(QLabel(
            "Nota: os índices de banda dos presets são sugestões genéricas.\n"
            "Ajuste manualmente acima conforme a ordem real do seu sensor."
        ))

        layout.addWidget(preset_group)

        self._stats_form = QFormLayout()
        stats_group = QGroupBox("Estatísticas avançadas da banda selecionada")
        stats_group.setLayout(self._stats_form)
        layout.addWidget(stats_group)
        self._stats_form.addRow(QLabel("Selecione uma banda na lista acima."))

        layout.addStretch()
        self.setLayout(layout)

        self._btn_apply_composition.clicked.connect(self._on_apply_composition_clicked)
        self._btn_apply_preset.clicked.connect(self._on_apply_preset_clicked)

    # ------------------------------------------------------------------
    def populate_bands(self, band_infos: list[BandInfo]) -> None:
        self._band_list.clear()
        for info in band_infos:
            range_str = (
                f"[{info.min_value:.1f} .. {info.max_value:.1f}]"
                if info.min_value is not None else "[sem dados]"
            )
            item = QListWidgetItem(f"Banda {info.index} ({info.dtype}) {range_str}")
            self._band_list.addItem(item)

        max_band = max((info.index for info in band_infos), default=1)
        for spin in (self._spin_r, self._spin_g, self._spin_b):
            spin.setMaximum(max_band)

        self._spin_r.setValue(min(1, max_band))
        self._spin_g.setValue(min(2, max_band))
        self._spin_b.setValue(min(3, max_band))

    def update_band_statistics(self, band_index: int, stats: dict) -> None:
        while self._stats_form.rowCount() > 0:
            self._stats_form.removeRow(0)

        if stats.get("min") is None:
            self._stats_form.addRow(QLabel(f"Banda {band_index}: sem dados válidos."))
            return

        rows = [
            ("Mínimo", f"{stats['min']:.2f}"),
            ("Máximo", f"{stats['max']:.2f}"),
            ("Média", f"{stats['mean']:.2f}"),
            ("Mediana", f"{stats['median']:.2f}"),
            ("Desvio padrão", f"{stats['std']:.2f}"),
            ("Variância", f"{stats['variance']:.2f}" if stats.get("variance") is not None else "—"),
            ("Percentil 2%", f"{stats['p2']:.2f}"),
            ("Percentil 98%", f"{stats['p98']:.2f}"),
            ("Pixels válidos", str(stats.get("valid_pixel_count", "—"))),
            ("Pixels NoData", str(stats.get("nodata_pixel_count", "—"))),
        ]
        for label, value in rows:
            self._stats_form.addRow(f"{label}:", QLabel(value))

    # ------------------------------------------------------------------
    def _on_band_row_changed(self, row: int) -> None:
        if row < 0:
            return
        self.band_selected_for_stats.emit(row + 1)  # 1-based

    def _on_apply_composition_clicked(self) -> None:
        self.composition_changed.emit(self._spin_r.value(), self._spin_g.value(), self._spin_b.value())

    def _on_apply_preset_clicked(self) -> None:
        key = self._preset_combo.currentData()
        self.preset_apply_requested.emit(key)

    def set_composition_spins(self, r_index: int, g_index: int, b_index: int) -> None:
        self._spin_r.setValue(r_index)
        self._spin_g.setValue(g_index)
        self._spin_b.setValue(b_index)

    def clear(self) -> None:
        self._band_list.clear()
        while self._stats_form.rowCount() > 0:
            self._stats_form.removeRow(0)
        self._stats_form.addRow(QLabel("Nenhuma imagem aberta."))