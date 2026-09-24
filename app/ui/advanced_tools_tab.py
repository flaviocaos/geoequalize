"""
Aba de ferramentas avançadas (Fase 8): filtros, correções atmosféricas
simples, harmonização de ortomosaico e matching de histograma.

Este é um arquivo NOVO desta fase. Crie-o em app/ui/advanced_tools_tab.py.

Será integrado ao ToolsPanel como uma nova aba "Avançado".
"""
from __future__ import annotations

from typing import Optional

import shiboken6
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QFormLayout,
    QLabel,
    QComboBox,
    QDoubleSpinBox,
    QSpinBox,
    QPushButton,
    QGroupBox,
)
from PySide6.QtCore import Signal


def _is_alive(qt_object) -> bool:
    return qt_object is not None and shiboken6.isValid(qt_object)


class AdvancedToolsTab(QWidget):
    """Aba 'Avançado': filtros, correções atmosféricas simples, harmonização."""

    apply_requested = Signal(str, dict)
    match_histogram_region_requested = Signal()  # inicia seleção de região de referência

    METHODS = [
        ("Sharpening", "sharpen"),
        ("Unsharp mask", "unsharp_mask"),
        ("Redução de ruído — Gaussiano", "denoise_gaussian"),
        ("Redução de ruído — Mediano", "denoise_median"),
        ("Redução de ruído — Bilateral", "denoise_bilateral"),
        ("Realce local de contraste", "local_contrast"),
        ("Detecção de bordas (diagnóstico)", "edge_detection"),
        ("Redução de haze/neblina", "reduce_haze"),
        ("Correção atmosférica simplificada (DOS)", "dos_correction"),
        ("Melhorar imagem lavada", "enhance_washed_out"),
        ("Realçar áreas escuras", "enhance_dark_areas"),
        ("Controlar altas luzes", "control_highlights"),
        ("Suavizar faixas de voo (ortomosaico)", "smooth_flight_lines"),
        ("Reduzir manchas de luminosidade", "reduce_luminosity_patches"),
    ]

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(
            "<i>Atenção: estas são correções visuais heurísticas, não "
            "correções radiométricas/atmosféricas cientificamente calibradas.</i>"
        ))

        self._method_combo = QComboBox()
        for label, _key in self.METHODS:
            self._method_combo.addItem(label)
        self._method_combo.currentIndexChanged.connect(self._on_method_changed)
        layout.addWidget(self._method_combo)

        self._params_group = QGroupBox("Parâmetros")
        self._params_form = QFormLayout()
        self._params_group.setLayout(self._params_form)
        layout.addWidget(self._params_group)

        self._spin_amount = self._make_spin(0.0, 3.0, 1.0, step=0.1)
        self._spin_radius = self._make_spin(0.5, 20.0, 2.0, step=0.5)
        self._spin_ksize = self._make_int_spin(1, 31, 5)
        self._spin_strength = self._make_spin(0.0, 1.0, 0.5, step=0.05)
        self._spin_kernel_fraction = self._make_spin(0.02, 0.3, 0.08, step=0.01)
        self._spin_dos_percentile = self._make_spin(0.1, 10.0, 1.0, step=0.1)

        self._btn_apply = QPushButton("Aplicar")
        layout.addWidget(self._btn_apply)
        self._btn_apply.clicked.connect(self._on_apply_clicked)

        layout.addWidget(QLabel("<b>Matching de histograma por região</b>"))
        layout.addWidget(QLabel(
            "1. Faça uma seleção (aba Local) na área de REFERÊNCIA e clique no botão abaixo.\n"
            "2. Depois faça uma nova seleção na área de DESTINO e aplique novamente."
        ))
        self._btn_match_region = QPushButton("Usar seleção atual como referência")
        layout.addWidget(self._btn_match_region)
        self._btn_match_region.clicked.connect(self.match_histogram_region_requested.emit)

        layout.addStretch()
        self.setLayout(layout)
        self._on_method_changed(0)

    @staticmethod
    def _make_spin(minimum: float, maximum: float, default: float, step: float = 1.0) -> QDoubleSpinBox:
        spin = QDoubleSpinBox()
        spin.setRange(minimum, maximum)
        spin.setSingleStep(step)
        spin.setValue(default)
        return spin

    @staticmethod
    def _make_int_spin(minimum: int, maximum: int, default: int) -> QSpinBox:
        spin = QSpinBox()
        spin.setRange(minimum, maximum)
        spin.setValue(default)
        return spin

    def current_method_key(self) -> str:
        return self.METHODS[self._method_combo.currentIndex()][1]

    def current_params(self) -> dict:
        if not all(_is_alive(w) for w in (
            self._spin_amount, self._spin_radius, self._spin_ksize,
            self._spin_strength, self._spin_kernel_fraction, self._spin_dos_percentile,
        )):
            return {}

        method = self.current_method_key()
        if method == "sharpen":
            return {"amount": self._spin_amount.value()}
        if method == "unsharp_mask":
            return {"radius": self._spin_radius.value(), "amount": self._spin_amount.value()}
        if method in ("denoise_gaussian", "denoise_median"):
            return {"ksize": self._spin_ksize.value()}
        if method == "denoise_bilateral":
            return {"d": self._spin_ksize.value(), "sigma_color": 75, "sigma_space": 75}
        if method == "local_contrast":
            return {"amount": self._spin_amount.value(), "radius": int(self._spin_radius.value() * 10)}
        if method in ("reduce_haze", "enhance_dark_areas", "control_highlights", "reduce_luminosity_patches"):
            return {"strength": self._spin_strength.value()}
        if method == "enhance_washed_out":
            return {"strength": self._spin_strength.value() * 5}
        if method == "smooth_flight_lines":
            return {"kernel_fraction": self._spin_kernel_fraction.value()}
        if method == "dos_correction":
            return {"percentile": self._spin_dos_percentile.value()}
        return {}

    def _on_method_changed(self, _index: int) -> None:
        if not _is_alive(self._params_form):
            return
        while self._params_form.rowCount() > 0:
            self._params_form.removeRow(0)

        method = self.current_method_key()
        if method == "sharpen":
            self._params_form.addRow("Intensidade:", self._spin_amount)
        elif method == "unsharp_mask":
            self._params_form.addRow("Raio:", self._spin_radius)
            self._params_form.addRow("Intensidade:", self._spin_amount)
        elif method in ("denoise_gaussian", "denoise_median", "denoise_bilateral"):
            self._params_form.addRow("Tamanho do kernel:", self._spin_ksize)
        elif method == "local_contrast":
            self._params_form.addRow("Intensidade:", self._spin_amount)
            self._params_form.addRow("Raio (x10 px):", self._spin_radius)
        elif method in ("reduce_haze", "enhance_dark_areas", "control_highlights", "reduce_luminosity_patches", "enhance_washed_out"):
            self._params_form.addRow("Força:", self._spin_strength)
        elif method == "smooth_flight_lines":
            self._params_form.addRow("Fração do kernel:", self._spin_kernel_fraction)
        elif method == "dos_correction":
            self._params_form.addRow("Percentil (objeto escuro):", self._spin_dos_percentile)
            self._params_form.addRow(QLabel(
                "<i>Aproximação visual (Dark Object Subtraction). Não substitui "
                "correção atmosférica calibrada (ex.: FLAASH).</i>"
            ))
        else:
            self._params_form.addRow(QLabel("Sem parâmetros adicionais."))

    def _on_apply_clicked(self) -> None:
        self.apply_requested.emit(self.current_method_key(), self.current_params())