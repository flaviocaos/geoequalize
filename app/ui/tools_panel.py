"""
Painel lateral de ferramentas de correção.

Fase 8: adiciona a aba "Avançado" (filtros, correções atmosféricas
simples, harmonização de ortomosaico) às abas já existentes:
Histograma, Cor e Local.
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
    QHBoxLayout,
    QTabWidget,
)
from PySide6.QtCore import Signal

from app.ui.advanced_tools_tab import AdvancedToolsTab
from app.ui.remote_sensing_tab import RemoteSensingTab


def _is_alive(qt_object) -> bool:
    return qt_object is not None and shiboken6.isValid(qt_object)


class HistogramToolsTab(QWidget):
    """Aba de correções de histograma/contraste (igual à Fase 2)."""

    apply_requested = Signal(str, dict)
    reset_requested = Signal()

    METHODS = [
        ("Stretch linear (min/máx)", "stretch_linear"),
        ("Stretch por percentil", "stretch_percentile"),
        ("Stretch por desvio padrão", "stretch_std"),
        ("Normalização", "normalize"),
        ("Equalização de histograma", "equalize"),
        ("CLAHE (adaptativa)", "clahe"),
        ("Gamma", "gamma"),
        ("Brilho/Contraste", "brightness_contrast"),
    ]

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)

        layout = QVBoxLayout(self)
        self._method_combo = QComboBox()
        for label, _key in self.METHODS:
            self._method_combo.addItem(label)
        self._method_combo.currentIndexChanged.connect(self._on_method_changed)
        layout.addWidget(self._method_combo)

        self._params_group = QGroupBox("Parâmetros")
        self._params_form = QFormLayout()
        self._params_group.setLayout(self._params_form)
        layout.addWidget(self._params_group)

        self._spin_low = self._make_spin(0.0, 50.0, 2.0)
        self._spin_high = self._make_spin(50.0, 100.0, 98.0)
        self._spin_std = self._make_spin(0.5, 5.0, 2.0, step=0.1)
        self._spin_gamma = self._make_spin(0.1, 5.0, 1.0, step=0.05)
        self._spin_brightness = self._make_spin(-100.0, 100.0, 0.0)
        self._spin_contrast = self._make_spin(0.1, 3.0, 1.0, step=0.05)

        self._btn_apply = QPushButton("Aplicar")
        self._btn_reset = QPushButton("Resetar todas as correções")
        layout.addWidget(self._btn_apply)
        layout.addWidget(self._btn_reset)
        layout.addStretch()

        self._btn_apply.clicked.connect(self._on_apply_clicked)
        self._btn_reset.clicked.connect(self.reset_requested.emit)

        self.setLayout(layout)
        self._on_method_changed(0)

    @staticmethod
    def _make_spin(minimum: float, maximum: float, default: float, step: float = 1.0) -> QDoubleSpinBox:
        spin = QDoubleSpinBox()
        spin.setRange(minimum, maximum)
        spin.setSingleStep(step)
        spin.setValue(default)
        return spin

    def current_method_key(self) -> str:
        return self.METHODS[self._method_combo.currentIndex()][1]

    def current_params(self) -> dict:
        if not all(_is_alive(w) for w in (
            self._spin_low, self._spin_high, self._spin_std,
            self._spin_gamma, self._spin_brightness, self._spin_contrast,
        )):
            return {}
        method = self.current_method_key()
        if method == "stretch_percentile":
            return {"low_pct": self._spin_low.value(), "high_pct": self._spin_high.value()}
        if method == "stretch_std":
            return {"n_std": self._spin_std.value()}
        if method == "gamma":
            return {"gamma": self._spin_gamma.value()}
        if method == "brightness_contrast":
            return {"brightness": self._spin_brightness.value(), "contrast": self._spin_contrast.value()}
        return {}

    def _on_method_changed(self, _index: int) -> None:
        if not _is_alive(self._params_form):
            return
        while self._params_form.rowCount() > 0:
            self._params_form.removeRow(0)

        method = self.current_method_key()
        if method == "stretch_percentile":
            self._params_form.addRow("Percentil baixo (%):", self._spin_low)
            self._params_form.addRow("Percentil alto (%):", self._spin_high)
        elif method == "stretch_std":
            self._params_form.addRow("Nº de desvios padrão:", self._spin_std)
        elif method == "gamma":
            self._params_form.addRow("Gamma:", self._spin_gamma)
        elif method == "brightness_contrast":
            self._params_form.addRow("Brilho:", self._spin_brightness)
            self._params_form.addRow("Contraste:", self._spin_contrast)
        else:
            self._params_form.addRow(QLabel("Sem parâmetros adicionais."))

    def _on_apply_clicked(self) -> None:
        self.apply_requested.emit(self.current_method_key(), self.current_params())


class ColorToolsTab(QWidget):
    """Aba de correções de cor/balanceamento (igual à Fase 3)."""

    apply_requested = Signal(str, dict)
    reference_point_requested = Signal(str)

    METHODS = [
        ("Balanceamento — Gray World", "gray_world"),
        ("Balanceamento — White Patch", "white_patch"),
        ("Canais RGB (ganho)", "channels"),
        ("Temperatura de cor", "temperature"),
        ("Matiz / Saturação", "hue_saturation"),
        ("Sombras / Médios / Realces", "tonal_ranges"),
        ("Reduzir dominância azulada", "cast_blue"),
        ("Reduzir dominância esverdeada", "cast_green"),
        ("Reduzir dominância amarelada", "cast_yellow"),
        ("Reduzir dominância avermelhada", "cast_red"),
        ("Iluminação desigual (ortofoto)", "uneven_illumination"),
        ("Correção de vinheta", "vignette"),
        ("Realce — área urbana", "enhance_urban"),
        ("Realce — vegetação", "enhance_vegetation"),
        ("Realce — solo exposto", "enhance_bare_soil"),
        ("Realce — estradas/telhados", "enhance_roads_roofs"),
    ]

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)

        layout = QVBoxLayout(self)
        self._method_combo = QComboBox()
        for label, _key in self.METHODS:
            self._method_combo.addItem(label)
        self._method_combo.currentIndexChanged.connect(self._on_method_changed)
        layout.addWidget(self._method_combo)

        self._params_group = QGroupBox("Parâmetros")
        self._params_form = QFormLayout()
        self._params_group.setLayout(self._params_form)
        layout.addWidget(self._params_group)

        self._spin_intensity = self._make_spin(0.0, 2.0, 1.0, step=0.1)
        self._spin_r = self._make_spin(0.1, 3.0, 1.0, step=0.05)
        self._spin_g = self._make_spin(0.1, 3.0, 1.0, step=0.05)
        self._spin_b = self._make_spin(0.1, 3.0, 1.0, step=0.05)
        self._spin_temperature = self._make_spin(-100.0, 100.0, 0.0)
        self._spin_hue = self._make_spin(-180.0, 180.0, 0.0)
        self._spin_saturation = self._make_spin(0.0, 3.0, 1.0, step=0.05)
        self._spin_shadows = self._make_spin(-100.0, 100.0, 0.0)
        self._spin_midtones = self._make_spin(-100.0, 100.0, 0.0)
        self._spin_highlights = self._make_spin(-100.0, 100.0, 0.0)
        self._spin_vignette = self._make_spin(0.0, 2.0, 0.5, step=0.05)

        layout.addWidget(QLabel("<b>Ferramenta de ponto de referência</b>"))
        ref_layout = QHBoxLayout()
        self._btn_ref_white = QPushButton("Branco")
        self._btn_ref_gray = QPushButton("Cinza")
        self._btn_ref_black = QPushButton("Preto")
        ref_layout.addWidget(self._btn_ref_white)
        ref_layout.addWidget(self._btn_ref_gray)
        ref_layout.addWidget(self._btn_ref_black)
        layout.addLayout(ref_layout)

        self._btn_ref_white.clicked.connect(lambda: self.reference_point_requested.emit("white"))
        self._btn_ref_gray.clicked.connect(lambda: self.reference_point_requested.emit("gray"))
        self._btn_ref_black.clicked.connect(lambda: self.reference_point_requested.emit("black"))

        self._btn_apply = QPushButton("Aplicar")
        layout.addWidget(self._btn_apply)
        layout.addStretch()

        self._btn_apply.clicked.connect(self._on_apply_clicked)

        self.setLayout(layout)
        self._on_method_changed(0)

    @staticmethod
    def _make_spin(minimum: float, maximum: float, default: float, step: float = 1.0) -> QDoubleSpinBox:
        spin = QDoubleSpinBox()
        spin.setRange(minimum, maximum)
        spin.setSingleStep(step)
        spin.setValue(default)
        return spin

    def current_method_key(self) -> str:
        return self.METHODS[self._method_combo.currentIndex()][1]

    def current_params(self) -> dict:
        if not all(_is_alive(w) for w in (
            self._spin_intensity, self._spin_r, self._spin_g, self._spin_b,
            self._spin_temperature, self._spin_hue, self._spin_saturation,
            self._spin_shadows, self._spin_midtones, self._spin_highlights, self._spin_vignette,
        )):
            return {}
        method = self.current_method_key()
        if method == "channels":
            return {"r_gain": self._spin_r.value(), "g_gain": self._spin_g.value(), "b_gain": self._spin_b.value()}
        if method == "temperature":
            return {"temperature": self._spin_temperature.value()}
        if method == "hue_saturation":
            return {"hue_shift": self._spin_hue.value(), "saturation": self._spin_saturation.value()}
        if method == "tonal_ranges":
            return {
                "shadows": self._spin_shadows.value(),
                "midtones": self._spin_midtones.value(),
                "highlights": self._spin_highlights.value(),
            }
        if method.startswith("cast_"):
            return {"intensity": self._spin_intensity.value()}
        if method == "vignette":
            return {"strength": self._spin_vignette.value()}
        return {}

    def _on_method_changed(self, _index: int) -> None:
        if not _is_alive(self._params_form):
            return
        while self._params_form.rowCount() > 0:
            self._params_form.removeRow(0)

        method = self.current_method_key()
        if method == "channels":
            self._params_form.addRow("Ganho R:", self._spin_r)
            self._params_form.addRow("Ganho G:", self._spin_g)
            self._params_form.addRow("Ganho B:", self._spin_b)
        elif method == "temperature":
            self._params_form.addRow("Temperatura:", self._spin_temperature)
        elif method == "hue_saturation":
            self._params_form.addRow("Matiz (graus):", self._spin_hue)
            self._params_form.addRow("Saturação:", self._spin_saturation)
        elif method == "tonal_ranges":
            self._params_form.addRow("Sombras:", self._spin_shadows)
            self._params_form.addRow("Médios tons:", self._spin_midtones)
            self._params_form.addRow("Realces:", self._spin_highlights)
        elif method.startswith("cast_"):
            self._params_form.addRow("Intensidade:", self._spin_intensity)
        elif method == "vignette":
            self._params_form.addRow("Força:", self._spin_vignette)
        else:
            self._params_form.addRow(QLabel("Sem parâmetros adicionais."))

    def _on_apply_clicked(self) -> None:
        self.apply_requested.emit(self.current_method_key(), self.current_params())


class LocalToolsTab(QWidget):
    """Aba de correções locais (Fase 4): seleção de área + feather + aplicar."""

    selection_mode_requested = Signal(object)
    clear_selection_requested = Signal()
    apply_local_requested = Signal(str, dict)
    undo_requested = Signal()
    redo_requested = Signal()
    reset_all_requested = Signal()

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("<b>Seleção de área</b>"))

        sel_layout = QHBoxLayout()
        self._btn_rect = QPushButton("Retangular")
        self._btn_rect.setCheckable(True)
        self._btn_poly = QPushButton("Poligonal")
        self._btn_poly.setCheckable(True)
        sel_layout.addWidget(self._btn_rect)
        sel_layout.addWidget(self._btn_poly)
        layout.addLayout(sel_layout)

        self._btn_clear_selection = QPushButton("Apagar seleção")
        layout.addWidget(self._btn_clear_selection)

        layout.addWidget(QLabel(
            "Retangular: clique e arraste.\n"
            "Poligonal: clique para cada vértice, dê duplo-clique para fechar."
        ))

        layout.addWidget(QLabel("<b>Suavização de borda (feather)</b>"))
        feather_form = QFormLayout()
        self._spin_feather_radius = QSpinBox()
        self._spin_feather_radius.setRange(0, 200)
        self._spin_feather_radius.setValue(15)
        self._spin_feather_intensity = QDoubleSpinBox()
        self._spin_feather_intensity.setRange(0.0, 1.0)
        self._spin_feather_intensity.setSingleStep(0.05)
        self._spin_feather_intensity.setValue(0.6)
        feather_form.addRow("Raio (px):", self._spin_feather_radius)
        feather_form.addRow("Intensidade:", self._spin_feather_intensity)
        layout.addLayout(feather_form)

        layout.addWidget(QLabel("<b>Aplicar correção na seleção</b>"))
        self._scope_combo = QComboBox()
        self._scope_combo.addItem("Usar método de Histograma ativo", "histogram")
        self._scope_combo.addItem("Usar método de Cor ativo", "color")
        layout.addWidget(self._scope_combo)

        self._btn_apply_local = QPushButton("Aplicar correção local")
        layout.addWidget(self._btn_apply_local)

        layout.addWidget(QLabel("<b>Histórico</b>"))
        hist_layout = QHBoxLayout()
        self._btn_undo = QPushButton("Desfazer")
        self._btn_redo = QPushButton("Refazer")
        hist_layout.addWidget(self._btn_undo)
        hist_layout.addWidget(self._btn_redo)
        layout.addLayout(hist_layout)

        self._btn_reset_all = QPushButton("Resetar tudo")
        layout.addWidget(self._btn_reset_all)
        layout.addStretch()

        self.setLayout(layout)

        self._btn_rect.toggled.connect(self._on_rect_toggled)
        self._btn_poly.toggled.connect(self._on_poly_toggled)
        self._btn_clear_selection.clicked.connect(self.clear_selection_requested.emit)
        self._btn_apply_local.clicked.connect(self._on_apply_local_clicked)
        self._btn_undo.clicked.connect(self.undo_requested.emit)
        self._btn_redo.clicked.connect(self.redo_requested.emit)
        self._btn_reset_all.clicked.connect(self.reset_all_requested.emit)

    def feather_params(self) -> dict:
        return {
            "radius": self._spin_feather_radius.value(),
            "intensity": self._spin_feather_intensity.value(),
        }

    def _on_rect_toggled(self, checked: bool) -> None:
        if checked:
            self._btn_poly.setChecked(False)
            self.selection_mode_requested.emit("rectangle")
        elif not self._btn_poly.isChecked():
            self.selection_mode_requested.emit(None)

    def _on_poly_toggled(self, checked: bool) -> None:
        if checked:
            self._btn_rect.setChecked(False)
            self.selection_mode_requested.emit("polygon")
        elif not self._btn_rect.isChecked():
            self.selection_mode_requested.emit(None)

    def _on_apply_local_clicked(self) -> None:
        scope = self._scope_combo.currentData()
        self.apply_local_requested.emit(scope, self.feather_params())


class ToolsPanel(QWidget):
    """Painel com abas: Histograma, Cor, Local, Avançado e Sensoriamento Remoto."""

    apply_requested = Signal(str, dict)
    reset_requested = Signal()
    compare_toggled = Signal(bool)
    reference_point_requested = Signal(str)

    selection_mode_requested = Signal(object)
    clear_selection_requested = Signal()
    apply_local_requested = Signal(str, dict)
    undo_requested = Signal()
    redo_requested = Signal()
    reset_all_requested = Signal()

    advanced_apply_requested = Signal(str, dict)
    match_histogram_region_requested = Signal()

    index_requested = Signal(str, dict)
    band_math_requested = Signal(str)
    spectral_profile_mode_requested = Signal(bool)

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("<b>Ferramentas de correção</b>"))

        self._tabs = QTabWidget()
        self.histogram_tab = HistogramToolsTab()
        self.color_tab = ColorToolsTab()
        self.local_tab = LocalToolsTab()
        self.advanced_tab = AdvancedToolsTab()
        self.remote_sensing_tab = RemoteSensingTab()
        self._tabs.addTab(self.histogram_tab, "Histograma")
        self._tabs.addTab(self.color_tab, "Cor")
        self._tabs.addTab(self.local_tab, "Local")
        self._tabs.addTab(self.advanced_tab, "Avançado")
        self._tabs.addTab(self.remote_sensing_tab, "Sensor. Remoto")
        layout.addWidget(self._tabs)

        self._btn_compare = QPushButton("Comparar antes/depois")
        self._btn_compare.setCheckable(True)
        layout.addWidget(self._btn_compare)

        self.setLayout(layout)

        self.histogram_tab.apply_requested.connect(self.apply_requested.emit)
        self.histogram_tab.reset_requested.connect(self.reset_requested.emit)
        self.color_tab.apply_requested.connect(self.apply_requested.emit)
        self.color_tab.reference_point_requested.connect(self.reference_point_requested.emit)
        self._btn_compare.toggled.connect(self.compare_toggled.emit)

        self.local_tab.selection_mode_requested.connect(self.selection_mode_requested.emit)
        self.local_tab.clear_selection_requested.connect(self.clear_selection_requested.emit)
        self.local_tab.apply_local_requested.connect(self._on_apply_local)
        self.local_tab.undo_requested.connect(self.undo_requested.emit)
        self.local_tab.redo_requested.connect(self.redo_requested.emit)
        self.local_tab.reset_all_requested.connect(self.reset_all_requested.emit)

        self.advanced_tab.apply_requested.connect(self.advanced_apply_requested.emit)
        self.advanced_tab.match_histogram_region_requested.connect(self.match_histogram_region_requested.emit)

        self.remote_sensing_tab.index_requested.connect(self.index_requested.emit)
        self.remote_sensing_tab.band_math_requested.connect(self.band_math_requested.emit)
        self.remote_sensing_tab.spectral_profile_mode_requested.connect(self.spectral_profile_mode_requested.emit)

    def set_band_count(self, band_count: int) -> None:
        self.remote_sensing_tab.set_band_count(band_count)

    def _on_apply_local(self, scope: str, feather_params: dict) -> None:
        if scope == "histogram":
            method = self.histogram_tab.current_method_key()
            params = self.histogram_tab.current_params()
        else:
            method = self.color_tab.current_method_key()
            params = self.color_tab.current_params()

        params = dict(params)
        params["_feather"] = feather_params
        params["_scope"] = scope
        self.apply_local_requested.emit(method, params)