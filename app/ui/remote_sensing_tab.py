"""
Aba de Sensoriamento Remoto: índices espectrais pré-definidos (NDVI, NDWI,
SAVI, EVI...), calculadora de bandas (band math) e ativação do modo de
perfil espectral (clique na imagem para ver valores de todas as bandas).

Este é um arquivo NOVO. Crie-o em app/ui/remote_sensing_tab.py.
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
    QTextEdit,
    QMessageBox,
)
from PySide6.QtCore import Signal

from core.spectral_indices import INDEX_DEFINITIONS


class RemoteSensingTab(QWidget):
    """Aba 'Sensoriamento Remoto': índices, band math e perfil espectral."""

    index_requested = Signal(str, dict)         # (index_key, {nome_logico: indice_banda})
    band_math_requested = Signal(str)            # expressão
    spectral_profile_mode_requested = Signal(bool)  # True = ativar modo de clique

    _LOGICAL_BAND_NAMES = {
        "red": "Vermelho", "green": "Verde", "blue": "Azul",
        "nir": "Infravermelho próximo (NIR)", "swir": "Infravermelho de onda curta (SWIR)",
    }

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._band_count = 1
        self._band_spins: dict[str, QSpinBox] = {}

        layout = QVBoxLayout(self)

        index_group = QGroupBox("Índices espectrais")
        index_layout = QVBoxLayout()

        self._index_combo = QComboBox()
        for key, definition in INDEX_DEFINITIONS.items():
            self._index_combo.addItem(definition.label, key)
        self._index_combo.currentIndexChanged.connect(self._on_index_changed)
        index_layout.addWidget(self._index_combo)

        self._description_label = QLabel("")
        self._description_label.setWordWrap(True)
        self._description_label.setStyleSheet("color: #555; font-size: 11px;")
        index_layout.addWidget(self._description_label)

        self._bands_form = QFormLayout()
        index_layout.addLayout(self._bands_form)

        self._btn_compute_index = QPushButton("Calcular e exibir índice")
        self._btn_compute_index.clicked.connect(self._on_compute_index_clicked)
        index_layout.addWidget(self._btn_compute_index)

        index_group.setLayout(index_layout)
        layout.addWidget(index_group)

        math_group = QGroupBox("Calculadora de bandas (band math)")
        math_layout = QVBoxLayout()
        math_layout.addWidget(QLabel(
            "Use B1, B2, B3... para referenciar bandas (1-based).\n"
            "Exemplo: (B4 - B3) / (B4 + B3)"
        ))
        self._expression_edit = QTextEdit()
        self._expression_edit.setPlaceholderText("(B4 - B3) / (B4 + B3)")
        self._expression_edit.setMaximumHeight(60)
        math_layout.addWidget(self._expression_edit)

        self._btn_compute_math = QPushButton("Calcular expressão")
        self._btn_compute_math.clicked.connect(self._on_compute_math_clicked)
        math_layout.addWidget(self._btn_compute_math)

        math_group.setLayout(math_layout)
        layout.addWidget(math_group)

        profile_group = QGroupBox("Perfil espectral")
        profile_layout = QVBoxLayout()
        profile_layout.addWidget(QLabel(
            "Ative e clique em um pixel da imagem para ver os valores de "
            "todas as bandas naquele ponto."
        ))
        self._btn_profile_mode = QPushButton("Ativar modo de perfil espectral")
        self._btn_profile_mode.setCheckable(True)
        self._btn_profile_mode.toggled.connect(self._on_profile_mode_toggled)
        profile_layout.addWidget(self._btn_profile_mode)
        profile_group.setLayout(profile_layout)
        layout.addWidget(profile_group)

        layout.addStretch()
        self.setLayout(layout)

        self._on_index_changed(0)

    # ------------------------------------------------------------------
    def set_band_count(self, band_count: int) -> None:
        self._band_count = max(1, band_count)
        self._on_index_changed(self._index_combo.currentIndex())

    def current_index_key(self) -> str:
        return self._index_combo.currentData()

    def _on_index_changed(self, _idx: int) -> None:
        key = self.current_index_key()
        definition = INDEX_DEFINITIONS.get(key)
        if definition is None:
            return

        self._description_label.setText(definition.description)

        while self._bands_form.rowCount() > 0:
            self._bands_form.removeRow(0)
        self._band_spins.clear()

        for logical_name in definition.required_bands:
            spin = QSpinBox()
            spin.setRange(1, self._band_count)
            spin.setValue(min(1, self._band_count))
            label = self._LOGICAL_BAND_NAMES.get(logical_name, logical_name)
            self._bands_form.addRow(f"Banda {label}:", spin)
            self._band_spins[logical_name] = spin

    def _on_compute_index_clicked(self) -> None:
        key = self.current_index_key()
        assignment = {name: spin.value() for name, spin in self._band_spins.items()}
        self.index_requested.emit(key, assignment)

    def _on_compute_math_clicked(self) -> None:
        expression = self._expression_edit.toPlainText().strip()
        if not expression:
            QMessageBox.information(self, "Expressão vazia", "Digite uma expressão antes de calcular.")
            return
        self.band_math_requested.emit(expression)

    def _on_profile_mode_toggled(self, checked: bool) -> None:
        self._btn_profile_mode.setText(
            "Desativar modo de perfil espectral" if checked else "Ativar modo de perfil espectral"
        )
        self.spectral_profile_mode_requested.emit(checked)