"""
Janela principal da aplicação.

Integra todos os painéis (Metadados, Bandas, Histograma, Ferramentas,
Projeto), o viewer central, o histórico de operações (com undo/redo),
exportação, projeto (salvar/abrir), presets, batch processing e filtros
avançados. Também aplica a paleta de cores (colormap) do raster, quando
existir, para exibir corretamente ortomosaicos "paletted" de 1 banda.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Literal

import numpy as np
from PySide6.QtWidgets import (
    QMainWindow,
    QWidget,
    QDockWidget,
    QStatusBar,
    QMenuBar,
    QFileDialog,
    QMessageBox,
)
from PySide6.QtCore import Qt
from rasterio.windows import Window

from app.ui.viewer import ImageViewer
from app.ui.histogram_panel import HistogramPanel
from app.ui.tools_panel import ToolsPanel
from app.ui.metadata_panel import MetadataPanel
from app.ui.bands_panel import BandsPanel
from app.ui.export_dialog import ExportDialog
from app.ui.project_panel import ProjectPanel
from app.ui.batch_dialog import BatchDialog
from app.ui.main_toolbar import MainToolbar
from app.ui.spectral_profile_dialog import SpectralProfileDialog
from app.ui.geoprocessing_dialog import GeoprocessingDialog
from app.ui.agent_dialog import AgentDialog
from utils.config import AppConfig
from utils.validators import (
    is_supported_raster,
    check_image_size_warning,
    friendly_error_message,
)
from core.raster_io import RasterReader, RasterHandle
from core.metadata import extract_metadata, metadata_to_display_dict
from core import histogram_tools as ht
from core import color_correction as cc
from core import local_correction as lc
from core import band_tools as bt
from core import exporter as exp
from core import project_file as pf
from core import batch_processor as bp
from core import filters as filt
from core import spectral_indices as si
from core import atmospheric_correction as atmo
from core import pdf_report as pdfr
from core.local_agent import AgentContext

logger = logging.getLogger(__name__)

# ----------------------------------------------------------------------
# Métodos de histograma — operam banda a banda (np.ndarray 2D)
# ----------------------------------------------------------------------
_HISTOGRAM_METHOD_FUNCS = {
    "stretch_linear": lambda band, p: ht.stretch_linear(
        band, float(np.nanmin(band)), float(np.nanmax(band)), nodata=p.get("nodata")
    ),
    "stretch_percentile": lambda band, p: ht.stretch_percentile(
        band, p.get("low_pct", 2.0), p.get("high_pct", 98.0), nodata=p.get("nodata")
    ),
    "stretch_std": lambda band, p: ht.stretch_std(band, p.get("n_std", 2.0), nodata=p.get("nodata")),
    "normalize": lambda band, p: ht.normalize_band(band, nodata=p.get("nodata")),
    "equalize": lambda band, p: ht.equalize_histogram(band, nodata=p.get("nodata")),
    "clahe": lambda band, p: ht.apply_clahe(band, nodata=p.get("nodata")),
    "gamma": lambda band, p: ht.adjust_gamma(band, p.get("gamma", 1.0), nodata=p.get("nodata")),
    "brightness_contrast": lambda band, p: ht.adjust_brightness_contrast(
        band, p.get("brightness", 0.0), p.get("contrast", 1.0), nodata=p.get("nodata")
    ),
}
_HISTOGRAM_METHOD_LABELS = {
    "stretch_linear": "Stretch linear", "stretch_percentile": "Stretch por percentil",
    "stretch_std": "Stretch por desvio padrão", "normalize": "Normalização",
    "equalize": "Equalização de histograma", "clahe": "CLAHE", "gamma": "Gamma",
    "brightness_contrast": "Brilho/Contraste",
}

# ----------------------------------------------------------------------
# Métodos de cor — operam na composição RGB completa (3, H, W)
# ----------------------------------------------------------------------
_COLOR_METHOD_FUNCS = {
    "gray_world": lambda rgb, p: cc.white_balance_gray_world(rgb, nodata=p.get("nodata")),
    "white_patch": lambda rgb, p: cc.white_balance_white_patch(rgb, nodata=p.get("nodata")),
    "channels": lambda rgb, p: cc.adjust_channels(
        rgb, p.get("r_gain", 1.0), p.get("g_gain", 1.0), p.get("b_gain", 1.0), nodata=p.get("nodata")
    ),
    "temperature": lambda rgb, p: cc.adjust_temperature(rgb, p.get("temperature", 0.0), nodata=p.get("nodata")),
    "hue_saturation": lambda rgb, p: cc.adjust_hue_saturation(
        rgb, p.get("hue_shift", 0.0), p.get("saturation", 1.0), nodata=p.get("nodata")
    ),
    "tonal_ranges": lambda rgb, p: cc.adjust_tonal_ranges(
        rgb, p.get("shadows", 0.0), p.get("midtones", 0.0), p.get("highlights", 0.0), nodata=p.get("nodata")
    ),
    "cast_blue": lambda rgb, p: cc.reduce_color_cast(rgb, "blue", p.get("intensity", 1.0), nodata=p.get("nodata")),
    "cast_green": lambda rgb, p: cc.reduce_color_cast(rgb, "green", p.get("intensity", 1.0), nodata=p.get("nodata")),
    "cast_yellow": lambda rgb, p: cc.reduce_color_cast(rgb, "yellow", p.get("intensity", 1.0), nodata=p.get("nodata")),
    "cast_red": lambda rgb, p: cc.reduce_color_cast(rgb, "red", p.get("intensity", 1.0), nodata=p.get("nodata")),
    "uneven_illumination": lambda rgb, p: cc.correct_uneven_illumination(rgb, nodata=p.get("nodata")),
    "vignette": lambda rgb, p: cc.correct_vignette(rgb, p.get("strength", 0.5), nodata=p.get("nodata")),
    "enhance_urban": lambda rgb, p: cc.enhance_for_class(rgb, "urban", nodata=p.get("nodata")),
    "enhance_vegetation": lambda rgb, p: cc.enhance_for_class(rgb, "vegetation", nodata=p.get("nodata")),
    "enhance_bare_soil": lambda rgb, p: cc.enhance_for_class(rgb, "bare_soil", nodata=p.get("nodata")),
    "enhance_roads_roofs": lambda rgb, p: cc.enhance_for_class(rgb, "roads_roofs", nodata=p.get("nodata")),
}
_COLOR_METHOD_LABELS = {
    "gray_world": "Balanceamento Gray World", "white_patch": "Balanceamento White Patch",
    "channels": "Ajuste de canais RGB", "temperature": "Temperatura de cor",
    "hue_saturation": "Matiz/Saturação", "tonal_ranges": "Sombras/Médios/Realces",
    "cast_blue": "Redução de dominância azulada", "cast_green": "Redução de dominância esverdeada",
    "cast_yellow": "Redução de dominância amarelada", "cast_red": "Redução de dominância avermelhada",
    "uneven_illumination": "Correção de iluminação desigual", "vignette": "Correção de vinheta",
    "enhance_urban": "Realce — área urbana", "enhance_vegetation": "Realce — vegetação",
    "enhance_bare_soil": "Realce — solo exposto", "enhance_roads_roofs": "Realce — estradas/telhados",
}
_COLOR_METHODS = set(_COLOR_METHOD_FUNCS.keys())

# ----------------------------------------------------------------------
# Filtros avançados — operam na composição RGB completa (3, H, W)
# ----------------------------------------------------------------------
_ADVANCED_METHOD_FUNCS = {
    "sharpen": lambda rgb, p: filt.sharpen(rgb, p.get("amount", 1.0), nodata=p.get("nodata")),
    "unsharp_mask": lambda rgb, p: filt.unsharp_mask(rgb, p.get("radius", 2.0), p.get("amount", 1.0), nodata=p.get("nodata")),
    "denoise_gaussian": lambda rgb, p: filt.denoise(rgb, "gaussian", nodata=p.get("nodata"), ksize=p.get("ksize", 5)),
    "denoise_median": lambda rgb, p: filt.denoise(rgb, "median", nodata=p.get("nodata"), ksize=p.get("ksize", 5)),
    "denoise_bilateral": lambda rgb, p: filt.denoise(
        rgb, "bilateral", nodata=p.get("nodata"), d=p.get("d", 9), sigma_color=p.get("sigma_color", 75), sigma_space=p.get("sigma_space", 75)
    ),
    "local_contrast": lambda rgb, p: filt.local_contrast_enhancement(rgb, p.get("amount", 1.0), p.get("radius", 30), nodata=p.get("nodata")),
    "edge_detection": lambda rgb, p: filt.edge_detection(rgb, nodata=p.get("nodata")),
    "reduce_haze": lambda rgb, p: filt.reduce_haze(rgb, p.get("strength", 0.5), nodata=p.get("nodata")),
    "dos_correction": lambda rgb, p: atmo.rescale_after_dos(
        atmo.apply_dark_object_subtraction(rgb, percentile=p.get("percentile", 1.0), nodata=p.get("nodata")).corrected
    ),
    "enhance_washed_out": lambda rgb, p: filt.enhance_washed_out(rgb, p.get("strength", 1.0), nodata=p.get("nodata")),
    "enhance_dark_areas": lambda rgb, p: filt.enhance_dark_areas(rgb, p.get("strength", 0.5), nodata=p.get("nodata")),
    "control_highlights": lambda rgb, p: filt.control_highlights(rgb, p.get("strength", 0.5), nodata=p.get("nodata")),
    "smooth_flight_lines": lambda rgb, p: filt.smooth_flight_line_differences(rgb, p.get("kernel_fraction", 0.08), nodata=p.get("nodata")),
    "reduce_luminosity_patches": lambda rgb, p: filt.reduce_luminosity_patches(rgb, p.get("strength", 0.5), nodata=p.get("nodata")),
}
_ADVANCED_METHOD_LABELS = {
    "sharpen": "Sharpening", "unsharp_mask": "Unsharp mask",
    "denoise_gaussian": "Redução de ruído (Gaussiano)", "denoise_median": "Redução de ruído (Mediano)",
    "denoise_bilateral": "Redução de ruído (Bilateral)", "local_contrast": "Realce local de contraste",
    "edge_detection": "Detecção de bordas", "reduce_haze": "Redução de haze/neblina",
    "dos_correction": "Correção atmosférica simplificada (DOS)",
    "enhance_washed_out": "Melhoria de imagem lavada", "enhance_dark_areas": "Realce de áreas escuras",
    "control_highlights": "Controle de altas luzes", "smooth_flight_lines": "Suavização de faixas de voo",
    "reduce_luminosity_patches": "Redução de manchas de luminosidade",
}
_ADVANCED_METHODS = set(_ADVANCED_METHOD_FUNCS.keys())

_PRESETS_DIR = Path.home() / ".satellite_image_corrector" / "presets"


@dataclass
class HistoryEntry:
    kind: Literal["histogram", "color", "advanced", "reference", "match_histogram_region"]
    method: str
    params: dict
    label: str
    scope: Literal["global", "local"] = "global"
    mask: Optional[np.ndarray] = None
    enabled: bool = True


class MainWindow(QMainWindow):
    """Janela principal: integra todos os painéis, histórico, exportação, projeto, batch e filtros avançados."""

    def __init__(self, config: AppConfig, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._config = config
        self._current_handle: Optional[RasterHandle] = None
        self._reader = RasterReader()

        self._history: list[HistoryEntry] = []
        self._redo_stack: list[HistoryEntry] = []

        self._preview_full: Optional[np.ndarray] = None
        self._band_composition: tuple[int, int, int] = (1, 1, 1)
        self._preview_corrected: Optional[np.ndarray] = None
        self._showing_original = False
        self._picking_reference: Optional[str] = None
        self._current_selection_mask: Optional[np.ndarray] = None

        # Estado do fluxo de matching de histograma por região
        self._match_reference_mask: Optional[np.ndarray] = None
        self._awaiting_match_reference = False

        # Estado do modo de perfil espectral (Fase 12)
        self._spectral_profile_mode = False
        self._spectral_profile_dialog: Optional[SpectralProfileDialog] = None

        # Estatísticas de bandas já consultadas pelo usuário (para o agente local, Fase 16)
        self._queried_band_statistics: dict[int, dict] = {}
        self._agent_dialog: Optional[AgentDialog] = None

        self.setWindowTitle("GeoEqualize")
        self.resize(1400, 900)

        self._build_central_widget()
        self._build_toolbar()
        self._build_docks()
        self._build_menu()
        self._build_status_bar()
        self._connect_tools_panel()
        self._connect_bands_panel()
        self._connect_project_panel()
        self._refresh_history_panel()

    # ------------------------------------------------------------------
    def _build_central_widget(self) -> None:
        self.viewer = ImageViewer(parent=self)
        self.viewer.point_clicked.connect(self._on_viewer_clicked)
        self.viewer.selection_changed.connect(self._on_selection_changed)
        self.viewer.selection_cleared.connect(self._on_selection_cleared)
        self.setCentralWidget(self.viewer)

    def _build_toolbar(self) -> None:
        """Barra de ferramentas lateral com zoom, pan, seleção e comparação."""
        self.main_toolbar = MainToolbar(parent=self)
        self.addToolBar(Qt.LeftToolBarArea, self.main_toolbar)

        self.main_toolbar.zoom_in_requested.connect(self.viewer.zoom_in)
        self.main_toolbar.zoom_out_requested.connect(self.viewer.zoom_out)
        self.main_toolbar.fit_to_window_requested.connect(self.viewer.fit_to_window)

        self.main_toolbar.pan_mode_requested.connect(lambda: self.viewer.set_selection_mode(None))
        self.main_toolbar.rectangle_mode_requested.connect(lambda: self.viewer.set_selection_mode("rectangle"))
        self.main_toolbar.polygon_mode_requested.connect(lambda: self.viewer.set_selection_mode("polygon"))
        self.main_toolbar.reference_point_mode_requested.connect(self._on_toolbar_reference_point_mode)

        self.main_toolbar.clear_selection_requested.connect(self.viewer.clear_selection)
        self.main_toolbar.compare_toggled.connect(self._on_compare_toggled)

    def _on_toolbar_reference_point_mode(self) -> None:
        """Atalho rápido da toolbar: ativa a captura de ponto de referência branco.

        Para escolher cinza/preto especificamente, o usuário pode usar os
        botões dedicados na aba Cor do painel Ferramentas.
        """
        self.viewer.set_selection_mode(None)
        self._on_reference_point_requested("white")

    def _build_docks(self) -> None:
        self.metadata_panel = MetadataPanel(parent=self)
        self.histogram_panel = HistogramPanel(parent=self)
        self.tools_panel = ToolsPanel(parent=self)
        self.bands_panel = BandsPanel(parent=self)
        self.project_panel = ProjectPanel(parent=self)

        self._add_dock("Metadados", self.metadata_panel, Qt.RightDockWidgetArea)
        self._add_dock("Bandas", self.bands_panel, Qt.RightDockWidgetArea)
        self._add_dock("Histograma", self.histogram_panel, Qt.RightDockWidgetArea)
        self._add_dock("Ferramentas", self.tools_panel, Qt.LeftDockWidgetArea)
        self._add_dock("Projeto", self.project_panel, Qt.LeftDockWidgetArea)

        all_presets = [(k, pf.BUILTIN_PRESET_LABELS.get(k, k)) for k in pf.BUILTIN_PRESETS.keys()]
        user_presets = pf.list_user_presets(_PRESETS_DIR)
        all_presets += [(name, f"(usuário) {name}") for name in user_presets]
        self.project_panel.populate_presets(all_presets)

    def _add_dock(self, title: str, widget: QWidget, area: Qt.DockWidgetArea) -> QDockWidget:
        dock = QDockWidget(title, self)
        dock.setWidget(widget)
        self.addDockWidget(area, dock)
        return dock

    def _build_menu(self) -> None:
        menu_bar: QMenuBar = self.menuBar()

        file_menu = menu_bar.addMenu("&Arquivo")
        action_open = file_menu.addAction("Abrir imagem...")
        action_open.triggered.connect(self._on_open_image)

        action_export = file_menu.addAction("Exportar...")
        action_export.triggered.connect(self._on_export_clicked)
        action_export.setEnabled(False)
        self._action_export = action_export

        action_export_pdf = file_menu.addAction("Exportar relatório PDF (PT + EN)...")
        action_export_pdf.triggered.connect(self._on_export_pdf_clicked)
        action_export_pdf.setEnabled(False)
        self._action_export_pdf = action_export_pdf

        file_menu.addSeparator()
        action_exit = file_menu.addAction("Sair")
        action_exit.triggered.connect(self.close)

        view_menu = menu_bar.addMenu("&Visualizar")
        view_menu.addAction("Zoom +", self.viewer.zoom_in)
        view_menu.addAction("Zoom -", self.viewer.zoom_out)
        view_menu.addAction("Ajustar à tela", self.viewer.fit_to_window)

        help_menu = menu_bar.addMenu("Aj&uda")
        help_menu.addAction("Sobre", self._on_about)

        geoprocessing_menu = menu_bar.addMenu("&Geoprocessamento")
        action_geoprocessing = geoprocessing_menu.addAction("Reclassificação, MCDA e CA-Markov...")
        action_geoprocessing.triggered.connect(self._on_open_geoprocessing)

        agent_menu = menu_bar.addMenu("&Assistente")
        action_agent = agent_menu.addAction("Abrir assistente local...")
        action_agent.triggered.connect(self._on_open_agent)

    def _build_status_bar(self) -> None:
        self.setStatusBar(QStatusBar(self))
        self.statusBar().showMessage("Pronto.")

    def _connect_tools_panel(self) -> None:
        self.tools_panel.apply_requested.connect(self._on_apply_global_correction)
        self.tools_panel.reset_requested.connect(self._on_reset_all)
        self.tools_panel.compare_toggled.connect(self._on_compare_toggled)
        self.tools_panel.reference_point_requested.connect(self._on_reference_point_requested)

        self.tools_panel.selection_mode_requested.connect(self.viewer.set_selection_mode)
        self.tools_panel.clear_selection_requested.connect(self.viewer.clear_selection)
        self.tools_panel.apply_local_requested.connect(self._on_apply_local_correction)
        self.tools_panel.undo_requested.connect(self._on_undo)
        self.tools_panel.redo_requested.connect(self._on_redo)
        self.tools_panel.reset_all_requested.connect(self._on_reset_all)

        self.tools_panel.advanced_apply_requested.connect(self._on_apply_advanced)
        self.tools_panel.match_histogram_region_requested.connect(self._on_match_histogram_region_requested)

        self.tools_panel.index_requested.connect(self._on_index_requested)
        self.tools_panel.band_math_requested.connect(self._on_band_math_requested)
        self.tools_panel.spectral_profile_mode_requested.connect(self._on_spectral_profile_mode_requested)

    def _connect_bands_panel(self) -> None:
        self.bands_panel.composition_changed.connect(self._on_composition_changed)
        self.bands_panel.preset_apply_requested.connect(self._on_preset_requested)
        self.bands_panel.band_selected_for_stats.connect(self._on_band_selected_for_stats)

    def _connect_project_panel(self) -> None:
        self.project_panel.save_project_requested.connect(self._on_save_project)
        self.project_panel.open_project_requested.connect(self._on_open_project)
        self.project_panel.toggle_operation_requested.connect(self._on_toggle_operation)
        self.project_panel.remove_operation_requested.connect(self._on_remove_operation)
        self.project_panel.move_operation_requested.connect(self._on_move_operation)
        self.project_panel.save_preset_requested.connect(self._on_save_preset)
        self.project_panel.load_preset_requested.connect(self._on_load_preset)
        self.project_panel.open_batch_dialog_requested.connect(self._on_open_batch_dialog)

    # ------------------------------------------------------------------
    def _on_open_image(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Abrir imagem", "",
            "Imagens raster (*.tif *.tiff *.jp2 *.jpg *.jpeg *.png);;Todos os arquivos (*)",
        )
        if not path:
            return
        self._load_image(path)

    def _load_image(self, path: str) -> None:
        if not is_supported_raster(path):
            QMessageBox.warning(
                self, "Formato não suportado",
                f"O arquivo selecionado não é suportado:\n{path}\n\n"
                f"Formatos aceitos: GeoTIFF, TIFF, JPEG, PNG, JP2.",
            )
            return

        try:
            handle = self._reader.open(path)
        except Exception as exc:
            logger.exception("Erro ao abrir imagem")
            QMessageBox.critical(self, "Erro ao abrir imagem", friendly_error_message(exc))
            return

        size_warning = check_image_size_warning(handle.width, handle.height)
        if size_warning:
            self.statusBar().showMessage(size_warning)

        if handle.crs is None:
            QMessageBox.warning(
                self, "CRS ausente",
                "Esta imagem não possui um sistema de referência de coordenadas (CRS) definido.\n"
                "A imagem ainda pode ser aberta e corrigida normalmente, mas o "
                "georreferenciamento da exportação pode não ser válido.",
            )

        try:
            all_indexes = list(range(1, handle.band_count + 1))
            preview = self._reader.read_preview(
                handle, max_dim=self._config.preview_max_dim, band_indexes=all_indexes
            )
        except MemoryError as exc:
            logger.exception("Memória insuficiente ao gerar preview")
            QMessageBox.critical(self, "Memória insuficiente", friendly_error_message(exc))
            return
        except Exception as exc:
            logger.exception("Erro ao gerar preview da imagem")
            QMessageBox.critical(self, "Erro ao processar imagem", friendly_error_message(exc))
            return

        self._current_handle = handle
        self._preview_full = preview.astype(np.float64)
        self._history.clear()
        self._redo_stack.clear()
        self._current_selection_mask = None
        self._match_reference_mask = None
        self._awaiting_match_reference = False

        try:
            default_b = 3 if handle.band_count >= 3 else handle.band_count
            self._band_composition = (1, min(2, handle.band_count), default_b)
            self.bands_panel.set_composition_spins(*self._band_composition)

            band_infos = bt.list_bands(handle, sample=self._preview_full)
            self.bands_panel.populate_bands(band_infos)
            self.tools_panel.set_band_count(handle.band_count)

            metadata = extract_metadata(handle)
            self.metadata_panel.update_metadata(metadata_to_display_dict(metadata))

            self._recompute_preview()
        except Exception as exc:
            logger.exception("Erro ao inicializar painéis após abrir imagem")
            QMessageBox.critical(self, "Erro ao processar imagem", friendly_error_message(exc))
            return

        self._action_export.setEnabled(True)
        self._action_export_pdf.setEnabled(True)

        self.statusBar().showMessage(
            f"Aberto: {handle.path.name} | {handle.width}x{handle.height} | "
            f"{handle.band_count} banda(s) | {handle.dtype}"
        )

    # ------------------------------------------------------------------
    # Bandas e composição
    # ------------------------------------------------------------------
    def _on_composition_changed(self, r_index: int, g_index: int, b_index: int) -> None:
        if self._preview_full is None or self._current_handle is None:
            return
        max_band = self._current_handle.band_count
        if not all(1 <= idx <= max_band for idx in (r_index, g_index, b_index)):
            QMessageBox.warning(self, "Índice inválido", f"Os índices devem estar entre 1 e {max_band}.")
            return
        self._band_composition = (r_index, g_index, b_index)
        self._recompute_preview()
        self.statusBar().showMessage(f"Composição RGB: R={r_index} G={g_index} B={b_index}")

    def _on_preset_requested(self, preset_key: str) -> None:
        if self._current_handle is None:
            return
        preset = bt.COMPOSITION_PRESETS.get(preset_key)
        if preset is None:
            return
        max_band = self._current_handle.band_count
        r, g, b = preset["R"], preset["G"], preset["B"]
        if max(r, g, b) > max_band:
            QMessageBox.information(self, "Preset incompatível", f"Este preset assume ao menos {max(r, g, b)} bandas.")
            return
        self._band_composition = (r, g, b)
        self.bands_panel.set_composition_spins(r, g, b)
        self._recompute_preview()

    def _on_band_selected_for_stats(self, band_index: int) -> None:
        if self._preview_full is None or self._current_handle is None:
            return
        if not (1 <= band_index <= self._preview_full.shape[0]):
            return
        band = self._preview_full[band_index - 1]
        stats = bt.compute_advanced_statistics(band, nodata=self._current_handle.nodata)
        self.bands_panel.update_band_statistics(band_index, stats)
        self.histogram_panel.update_histogram(band[np.newaxis, ...], nodata=self._current_handle.nodata)
        self._queried_band_statistics[band_index] = stats

    # ------------------------------------------------------------------
    # Sensoriamento remoto: índices, band math, perfil espectral (Fase 12)
    # ------------------------------------------------------------------
    def _on_index_requested(self, index_key: str, band_assignment: dict) -> None:
        if self._preview_full is None or self._current_handle is None:
            QMessageBox.information(self, "Nenhuma imagem", "Abra uma imagem antes de calcular um índice.")
            return

        try:
            bands_for_calc = {
                name: self._preview_full[idx - 1]
                for name, idx in band_assignment.items()
            }
            index_array = si.compute_index(index_key, bands_for_calc)
        except Exception as exc:
            QMessageBox.critical(self, "Erro ao calcular índice", str(exc))
            return

        definition = si.INDEX_DEFINITIONS.get(index_key)
        value_range = definition.value_range if definition else (-1.0, 1.0)

        nodata_mask = None
        if self._current_handle.nodata is not None:
            nodata_mask = self._preview_full[0] == self._current_handle.nodata

        rgb_display = si.index_to_rgb_display(index_array, value_range=value_range, nodata_mask=nodata_mask)

        self._preview_corrected = rgb_display
        self.viewer.set_array_as_image(rgb_display)
        self.histogram_panel.update_histogram(index_array[np.newaxis, ...], nodata=None)

        label = definition.label if definition else index_key
        self.statusBar().showMessage(f"Índice calculado e exibido: {label} (faixa esperada {value_range})")

    def _on_band_math_requested(self, expression: str) -> None:
        if self._preview_full is None or self._current_handle is None:
            QMessageBox.information(self, "Nenhuma imagem", "Abra uma imagem antes de usar a calculadora de bandas.")
            return

        try:
            result_array = si.evaluate_band_math(expression, self._preview_full)
        except si.BandMathError as exc:
            QMessageBox.warning(self, "Expressão inválida", str(exc))
            return
        except Exception as exc:
            QMessageBox.critical(self, "Erro ao calcular expressão", str(exc))
            return

        finite_values = result_array[np.isfinite(result_array)]
        if finite_values.size == 0:
            QMessageBox.warning(self, "Resultado vazio", "A expressão não produziu valores válidos.")
            return

        vmin, vmax = float(finite_values.min()), float(finite_values.max())
        rgb_display = si.index_to_rgb_display(result_array, value_range=(vmin, vmax))

        self._preview_corrected = rgb_display
        self.viewer.set_array_as_image(rgb_display)
        self.histogram_panel.update_histogram(result_array[np.newaxis, ...], nodata=None)

        self.statusBar().showMessage(f"Expressão calculada: {expression} (faixa: {vmin:.3f} a {vmax:.3f})")

    def _on_spectral_profile_mode_requested(self, enabled: bool) -> None:
        self._spectral_profile_mode = enabled
        if enabled:
            self.viewer.set_selection_mode(None)
            self.statusBar().showMessage("Modo de perfil espectral ativo: clique em um pixel da imagem.")
        else:
            self.statusBar().showMessage("Modo de perfil espectral desativado.")

    def _show_spectral_profile(self, x: int, y: int) -> None:
        if self._preview_full is None:
            return
        if not (0 <= y < self._preview_full.shape[1] and 0 <= x < self._preview_full.shape[2]):
            return

        values = self._preview_full[:, y, x]

        if self._spectral_profile_dialog is None:
            self._spectral_profile_dialog = SpectralProfileDialog(parent=self)
        self._spectral_profile_dialog.update_profile(x, y, values)

    # ------------------------------------------------------------------
    # Seleção de área
    # ------------------------------------------------------------------
    def _on_selection_changed(self, kind: str, points: list[tuple[int, int]]) -> None:
        if self._preview_full is None:
            return
        h, w = self._preview_full.shape[1], self._preview_full.shape[2]

        if kind == "rectangle":
            (x_min, y_min), (x_max, y_max) = points
            mask = lc.create_rectangular_mask((h, w), (x_min, y_min, x_max, y_max))
        else:
            mask = lc.create_polygon_mask((h, w), points)

        if self._awaiting_match_reference:
            self._match_reference_mask = mask
            self._awaiting_match_reference = False
            self.statusBar().showMessage(
                f"Região de referência definida ({mask.sum()} pixels). "
                "Agora selecione a região de DESTINO e aplique 'Matching de histograma' novamente."
            )
            return

        self._current_selection_mask = mask
        self.statusBar().showMessage(f"Seleção {kind} definida ({mask.sum()} pixels).")

    def _on_selection_cleared(self) -> None:
        self._current_selection_mask = None
        self.statusBar().showMessage("Seleção removida.")

    # ------------------------------------------------------------------
    # Correções globais
    # ------------------------------------------------------------------
    def _on_apply_global_correction(self, method: str, params: dict) -> None:
        if self._preview_full is None or self._current_handle is None:
            QMessageBox.information(self, "Nenhuma imagem", "Abra uma imagem antes de aplicar correções.")
            return

        if method in _COLOR_METHODS:
            entry = HistoryEntry(kind="color", method=method, params=params, label=_COLOR_METHOD_LABELS.get(method, method))
        else:
            if method not in _HISTOGRAM_METHOD_FUNCS:
                QMessageBox.warning(self, "Método não implementado", f"Método desconhecido: {method}")
                return
            entry = HistoryEntry(kind="histogram", method=method, params=params, label=_HISTOGRAM_METHOD_LABELS.get(method, method))

        self._push_history(entry)

    def _on_apply_advanced(self, method: str, params: dict) -> None:
        if self._preview_full is None or self._current_handle is None:
            QMessageBox.information(self, "Nenhuma imagem", "Abra uma imagem antes de aplicar filtros.")
            return
        if method not in _ADVANCED_METHOD_FUNCS:
            QMessageBox.warning(self, "Método não implementado", f"Método desconhecido: {method}")
            return

        entry = HistoryEntry(kind="advanced", method=method, params=params, label=_ADVANCED_METHOD_LABELS.get(method, method))
        self._push_history(entry)

    def _on_reference_point_requested(self, target: str) -> None:
        self._picking_reference = target
        self.statusBar().showMessage(f"Clique na imagem para definir o ponto de referência ({target}).")

    def _on_viewer_clicked(self, x: int, y: int) -> None:
        if self._spectral_profile_mode:
            self._show_spectral_profile(x, y)
            return

        if self._picking_reference is None or self._preview_full is None:
            return
        target = self._picking_reference
        self._picking_reference = None
        entry = HistoryEntry(
            kind="reference", method="reference",
            params={"point_xy": (x, y), "target": target},
            label=f"Ponto de referência ({target}) em ({x},{y})",
        )
        self._push_history(entry)

    # ------------------------------------------------------------------
    # Matching de histograma por região
    # ------------------------------------------------------------------
    def _on_match_histogram_region_requested(self) -> None:
        if self._current_selection_mask is None and self._match_reference_mask is None:
            self._awaiting_match_reference = True
            self.statusBar().showMessage("Faça uma seleção na imagem para usar como REFERÊNCIA.")
            return

        if self._match_reference_mask is None:
            self._match_reference_mask = self._current_selection_mask
            self._current_selection_mask = None
            self.statusBar().showMessage(
                "Região de referência definida. Agora selecione a região de DESTINO "
                "e clique em 'Usar seleção atual como referência' novamente para aplicar."
            )
            return

        if self._current_selection_mask is None:
            QMessageBox.information(self, "Sem seleção de destino", "Selecione a região de destino antes de aplicar.")
            return

        entry = HistoryEntry(
            kind="match_histogram_region",
            method="match_histogram_region",
            params={},
            label="Matching de histograma por região",
            scope="global",
            mask=None,
        )
        entry.params = {"reference_mask": self._match_reference_mask, "target_mask": self._current_selection_mask}

        self._push_history(entry)
        self._match_reference_mask = None
        self._current_selection_mask = None
        self.viewer.clear_selection()

    # ------------------------------------------------------------------
    # Correções locais
    # ------------------------------------------------------------------
    def _on_apply_local_correction(self, method: str, params: dict) -> None:
        if self._preview_full is None or self._current_handle is None:
            QMessageBox.information(self, "Nenhuma imagem", "Abra uma imagem antes de aplicar correções.")
            return
        if self._current_selection_mask is None:
            QMessageBox.information(self, "Sem seleção", "Faça uma seleção retangular ou poligonal antes.")
            return

        feather_params = params.pop("_feather", {"radius": 0, "intensity": 0.0})
        scope_kind = params.pop("_scope", "histogram")

        feathered_mask = lc.feather_mask(
            self._current_selection_mask,
            radius=feather_params.get("radius", 0),
            intensity=feather_params.get("intensity", 0.0),
        )
        feathered_mask = lc.respect_nodata(feathered_mask, self._preview_full, self._current_handle.nodata)

        kind = "color" if scope_kind == "color" else "histogram"
        label_map = _COLOR_METHOD_LABELS if kind == "color" else _HISTOGRAM_METHOD_LABELS
        entry = HistoryEntry(
            kind=kind, method=method, params=params,
            label=f"{label_map.get(method, method)} (local)",
            scope="local", mask=feathered_mask,
        )
        self._push_history(entry)

    # ------------------------------------------------------------------
    # Histórico
    # ------------------------------------------------------------------
    def _push_history(self, entry: HistoryEntry) -> None:
        self._history.append(entry)
        self._redo_stack.clear()
        self._recompute_preview()
        self._refresh_history_panel()
        self.statusBar().showMessage(f"Correção aplicada: {entry.label}")

    def _on_undo(self) -> None:
        if not self._history:
            self.statusBar().showMessage("Nada para desfazer.")
            return
        entry = self._history.pop()
        self._redo_stack.append(entry)
        self._recompute_preview()
        self._refresh_history_panel()

    def _on_redo(self) -> None:
        if not self._redo_stack:
            self.statusBar().showMessage("Nada para refazer.")
            return
        entry = self._redo_stack.pop()
        self._history.append(entry)
        self._recompute_preview()
        self._refresh_history_panel()

    def _on_reset_all(self) -> None:
        self._history.clear()
        self._redo_stack.clear()
        self._recompute_preview()
        self._refresh_history_panel()

    def _on_toggle_operation(self, index: int, enabled: bool) -> None:
        if 0 <= index < len(self._history):
            self._history[index].enabled = enabled
            self._recompute_preview()

    def _on_remove_operation(self, index: int) -> None:
        if 0 <= index < len(self._history):
            self._history.pop(index)
            self._recompute_preview()
            self._refresh_history_panel()

    def _on_move_operation(self, old_index: int, new_index: int) -> None:
        if 0 <= old_index < len(self._history) and 0 <= new_index < len(self._history):
            entry = self._history.pop(old_index)
            self._history.insert(new_index, entry)
            self._recompute_preview()
            self._refresh_history_panel()

    def _refresh_history_panel(self) -> None:
        labels = [entry.label for entry in self._history]
        enabled_flags = [entry.enabled for entry in self._history]
        self.project_panel.update_history(labels, enabled_flags)

    def _on_compare_toggled(self, show_original: bool) -> None:
        self._showing_original = show_original
        self._refresh_viewer()

    # ------------------------------------------------------------------
    # Pipeline de recálculo
    # ------------------------------------------------------------------
    def _apply_entry(self, image_rgb: np.ndarray, entry: HistoryEntry, nodata: float | None) -> np.ndarray:
        result = image_rgb.copy()

        if entry.kind == "histogram":
            func = _HISTOGRAM_METHOD_FUNCS.get(entry.method)
            if func is None:
                return result
            corrected = result.copy()
            for b in range(corrected.shape[0]):
                params = dict(entry.params)
                params["nodata"] = nodata
                corrected[b] = func(result[b], params)

        elif entry.kind == "color":
            func = _COLOR_METHOD_FUNCS.get(entry.method)
            if func is None:
                return result
            params = dict(entry.params)
            params["nodata"] = nodata
            corrected = func(result, params)

        elif entry.kind == "advanced":
            func = _ADVANCED_METHOD_FUNCS.get(entry.method)
            if func is None:
                return result
            params = dict(entry.params)
            params["nodata"] = nodata
            corrected = func(result, params)

        elif entry.kind == "reference":
            point_xy = entry.params["point_xy"]
            target = entry.params["target"]
            corrected = cc.white_balance_from_reference_point(result, point_xy=point_xy, target=target, nodata=nodata)

        elif entry.kind == "match_histogram_region":
            ref_mask = entry.params["reference_mask"]
            target_mask = entry.params["target_mask"]
            if ref_mask.shape != result.shape[1:]:
                import cv2
                ref_mask = cv2.resize(ref_mask.astype(np.float64), (result.shape[2], result.shape[1])) > 0.5
                target_mask = cv2.resize(target_mask.astype(np.float64), (result.shape[2], result.shape[1])) > 0.5
            corrected = filt.match_histogram_from_region(result, ref_mask.astype(bool), target_mask.astype(bool), nodata=nodata)
        else:
            return result

        if entry.scope == "local" and entry.mask is not None:
            blended = result.copy()
            for b in range(blended.shape[0]):
                blended[b] = result[b] * (1 - entry.mask) + corrected[b] * entry.mask
            return blended

        return corrected

    def _recompute_preview(self) -> None:
        if self._preview_full is None or self._current_handle is None:
            return

        nodata = self._current_handle.nodata
        colormap = self._current_handle.colormap

        # Caso especial: raster "paletted" (1 banda com índices de cor).
        # Não faz sentido aplicar composição RGB nem a maioria das correções
        # de histograma/cor sobre índices de paleta — exibimos direto.
        if colormap is not None and self._preview_full.shape[0] == 1:
            original_rgb = self._preview_full.copy()
            self._preview_corrected = original_rgb.copy()
            self.histogram_panel.update_histogram(original_rgb, nodata=nodata, corrected=original_rgb)
            self._refresh_viewer(original_rgb)
            return

        r_idx, g_idx, b_idx = self._band_composition

        try:
            rgb_view = bt.apply_band_composition(self._preview_full, r_idx, g_idx, b_idx)
        except ValueError as exc:
            logger.warning("Composição inválida: %s", exc)
            return

        original_rgb = rgb_view.copy()
        result = rgb_view.copy()

        for entry in self._history:
            if not entry.enabled:
                continue
            result = self._apply_entry(result, entry, nodata)

        self._preview_corrected = result
        self.histogram_panel.update_histogram(original_rgb, nodata=nodata, corrected=result)
        self._refresh_viewer(original_rgb)

    def _refresh_viewer(self, original_rgb: Optional[np.ndarray] = None) -> None:
        """Atualiza a imagem exibida no viewer central.

        Se o raster aberto tiver uma paleta de cores (colormap) associada
        — comum em ortomosaicos "paletted" de 1 banda exportados por
        softwares de fotogrametria — ela é passada ao viewer para que as
        cores reais sejam reconstruídas em vez de mostrar tons de cinza.
        """
        if self._preview_corrected is None:
            return

        colormap = self._current_handle.colormap if self._current_handle else None

        if self._showing_original and original_rgb is not None:
            self.viewer.set_array_as_image(original_rgb, colormap=colormap)
        else:
            self.viewer.set_array_as_image(self._preview_corrected, colormap=colormap)

    # ------------------------------------------------------------------
    # Exportação
    # ------------------------------------------------------------------
    def _resize_mask_to_window(self, mask: np.ndarray, window: Window, full_width: int, full_height: int) -> np.ndarray:
        import cv2
        mask_full_size = cv2.resize(mask.astype(np.float64), (full_width, full_height), interpolation=cv2.INTER_LINEAR)
        row0, col0 = int(window.row_off), int(window.col_off)
        row1, col1 = row0 + int(window.height), col0 + int(window.width)
        return mask_full_size[row0:row1, col0:col1]

    def _build_full_res_corrector(self, handle: RasterHandle, band_composition: tuple[int, int, int]):
        nodata = handle.nodata

        def corrector(block: np.ndarray, window: Window) -> np.ndarray:
            result = block.copy()
            for entry in self._history:
                if not entry.enabled:
                    continue
                if entry.scope == "global":
                    result = self._apply_entry(result, entry, nodata)
                else:
                    mask_window = self._resize_mask_to_window(entry.mask, window, handle.width, handle.height)
                    corrected_full = self._apply_entry(result, entry, nodata)
                    blended = result.copy()
                    for b in range(blended.shape[0]):
                        blended[b] = result[b] * (1 - mask_window) + corrected_full[b] * mask_window
                    result = blended
            return result

        return corrector

    def _on_export_clicked(self) -> None:
        if self._current_handle is None:
            QMessageBox.information(self, "Nenhuma imagem", "Abra uma imagem antes de exportar.")
            return

        dialog = ExportDialog(default_dir=str(self._current_handle.path.parent), band_count=self._current_handle.band_count, parent=self)
        if dialog.exec() != ExportDialog.Accepted:
            return

        output_path = dialog.output_path()
        driver = dialog.selected_driver()
        only_rgb = dialog.export_only_rgb()

        try:
            corrector = self._build_full_res_corrector(self._current_handle, self._band_composition)
            options = exp.ExportOptions(
                output_path=output_path, file_format=driver, overwrite=False,
                only_rgb_composition=only_rgb, band_composition=self._band_composition if only_rgb else None,
            )

            def on_progress(progress: exp.ExportProgress) -> None:
                dialog.update_progress(progress.current_block, progress.total_blocks)

            exp.export_geotiff(self._current_handle, apply_corrections_fn=corrector, options=options, progress_callback=on_progress)

            if dialog.generate_report():
                report_path = output_path.with_suffix(".txt")
                operations_summary = [entry.label for entry in self._history]
                exp.export_report(self._current_handle, operations_summary=operations_summary, output_path=report_path)

            dialog.set_finished(True, f"Exportação concluída: {output_path}")
        except FileExistsError:
            resp = QMessageBox.question(self, "Arquivo já existe", f"O arquivo {output_path} já existe. Sobrescrever?", QMessageBox.Yes | QMessageBox.No)
            if resp == QMessageBox.Yes:
                try:
                    corrector = self._build_full_res_corrector(self._current_handle, self._band_composition)
                    options = exp.ExportOptions(
                        output_path=output_path, file_format=driver, overwrite=True,
                        only_rgb_composition=only_rgb, band_composition=self._band_composition if only_rgb else None,
                    )
                    exp.export_geotiff(self._current_handle, apply_corrections_fn=corrector, options=options)
                    dialog.set_finished(True, f"Exportação concluída (sobrescrito): {output_path}")
                except Exception as exc:
                    dialog.set_finished(False, f"Erro ao exportar: {exc}")
        except Exception as exc:
            logger.exception("Erro ao exportar")
            dialog.set_finished(False, f"Erro ao exportar: {exc}")

    # ------------------------------------------------------------------
    # Projeto
    # ------------------------------------------------------------------
    def _on_save_project(self) -> None:
        if self._current_handle is None:
            QMessageBox.information(self, "Nenhuma imagem", "Abra uma imagem antes de salvar o projeto.")
            return
        path, _ = QFileDialog.getSaveFileName(self, "Salvar projeto", str(self._current_handle.path.with_suffix(".sicproj.json")), "Projeto (*.json)")
        if not path:
            return
        try:
            pf.save_project(Path(path), self._current_handle.path, self._band_composition, self._history, self._current_selection_mask)
            QMessageBox.information(self, "Projeto salvo", f"Projeto salvo em:\n{path}")
        except Exception as exc:
            QMessageBox.critical(self, "Erro ao salvar projeto", str(exc))

    def _on_open_project(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Abrir projeto", "", "Projeto (*.json)")
        if not path:
            return
        try:
            state = pf.load_project(Path(path), history_entry_cls=HistoryEntry)
        except Exception as exc:
            QMessageBox.critical(self, "Erro ao abrir projeto", str(exc))
            return

        image_path = state["image_path"]
        if not Path(image_path).exists():
            QMessageBox.warning(self, "Imagem não encontrada", f"Imagem original não encontrada:\n{image_path}")
            return

        self._load_image(image_path)
        self._band_composition = state["band_composition"]
        self.bands_panel.set_composition_spins(*self._band_composition)
        self._history = state["history"]
        self._redo_stack.clear()
        self._current_selection_mask = state["selection_mask"]
        self._recompute_preview()
        self._refresh_history_panel()

    # ------------------------------------------------------------------
    # Presets
    # ------------------------------------------------------------------
    def _on_save_preset(self, name: str) -> None:
        operations = [
            {"kind": e.kind, "method": e.method, "params": e.params, "label": e.label}
            for e in self._history if e.scope == "global" and e.kind != "match_histogram_region"
        ]
        if not operations:
            QMessageBox.information(self, "Nada para salvar", "Não há operações globais compatíveis no histórico.")
            return
        try:
            pf.save_user_preset(_PRESETS_DIR, name, operations)
            all_presets = [(k, pf.BUILTIN_PRESET_LABELS.get(k, k)) for k in pf.BUILTIN_PRESETS.keys()]
            user_presets = pf.list_user_presets(_PRESETS_DIR)
            all_presets += [(n, f"(usuário) {n}") for n in user_presets]
            self.project_panel.populate_presets(all_presets)
            QMessageBox.information(self, "Preset salvo", f"Preset '{name}' salvo com sucesso.")
        except Exception as exc:
            QMessageBox.critical(self, "Erro ao salvar preset", str(exc))

    def _on_load_preset(self, preset_key: str) -> None:
        if self._preview_full is None:
            QMessageBox.information(self, "Nenhuma imagem", "Abra uma imagem antes de carregar um preset.")
            return
        try:
            operations = pf.get_preset_operations(preset_key, presets_dir=_PRESETS_DIR)
        except Exception as exc:
            QMessageBox.critical(self, "Erro ao carregar preset", str(exc))
            return

        self._history = [
            HistoryEntry(kind=op["kind"], method=op["method"], params=op.get("params", {}), label=op.get("label", op["method"]))
            for op in operations
        ]
        self._redo_stack.clear()
        self._recompute_preview()
        self._refresh_history_panel()

    # ------------------------------------------------------------------
    # Batch processing
    # ------------------------------------------------------------------
    def _on_open_batch_dialog(self) -> None:
        dialog = BatchDialog(parent=self)
        if dialog.exec() != BatchDialog.Accepted:
            return
        if not dialog.validate():
            return

        input_paths = dialog.input_paths()
        output_dir = dialog.output_dir()

        def build_corrector(handle: RasterHandle):
            return self._build_full_res_corrector(handle, self._band_composition)

        def on_progress(current: int, total: int, filename: str) -> None:
            dialog.update_progress(current, total, filename)

        try:
            result = bp.run_batch(
                input_paths=input_paths, output_dir=output_dir, build_corrector_fn=build_corrector,
                band_composition=self._band_composition, only_rgb=False, progress_callback=on_progress, generate_reports=True,
            )
            dialog.show_results(result)
        except Exception as exc:
            QMessageBox.critical(self, "Erro no lote", str(exc))

    def _on_about(self) -> None:
        QMessageBox.about(
            self, "Sobre",
            "Satellite Image Corrector\nFerramenta de correção visual e radiométrica "
            "de imagens de satélite, drones e ortofotos.",
        )

    def _on_open_geoprocessing(self) -> None:
        """Abre o módulo de Geoprocessamento (reclassificação, MCDA, CA-Markov).

        Se houver uma imagem aberta com 1 banda, ela é oferecida como
        camada inicial 'imagem_atual' dentro do diálogo.
        """
        initial_array = None
        initial_nodata = None
        if self._preview_full is not None and self._preview_full.shape[0] == 1:
            initial_array = self._preview_full[0]
            initial_nodata = self._current_handle.nodata if self._current_handle else None

        dialog = GeoprocessingDialog(initial_array=initial_array, initial_nodata=initial_nodata, parent=self)
        dialog.exec()
        """Abre o módulo de Geoprocessamento (reclassificação, MCDA, CA-Markov).

        Se houver uma imagem aberta com 1 banda, ela é oferecida como
        camada inicial 'imagem_atual' dentro do diálogo.
        """
        initial_array = None
        initial_nodata = None
        if self._preview_full is not None and self._preview_full.shape[0] == 1:
            initial_array = self._preview_full[0]
            initial_nodata = self._current_handle.nodata if self._current_handle else None

        dialog = GeoprocessingDialog(initial_array=initial_array, initial_nodata=initial_nodata, parent=self)
        dialog.exec()

    def _build_agent_context(self) -> AgentContext:
        """Monta um snapshot do estado atual do app para o agente local responder."""
        if self._current_handle is None or self._preview_full is None:
            return AgentContext(has_image=False)

        return AgentContext(
            has_image=True,
            image_name=self._current_handle.path.name,
            width=self._current_handle.width,
            height=self._current_handle.height,
            band_count=self._current_handle.band_count,
            dtype=self._current_handle.dtype,
            crs=self._current_handle.crs,
            nodata=self._current_handle.nodata,
            driver=self._current_handle.driver,
            compression=self._current_handle.compression,
            band_composition=self._band_composition,
            operation_labels=[entry.label for entry in self._history],
            band_statistics=dict(self._queried_band_statistics),
        )

    def _on_open_agent(self) -> None:
        if self._agent_dialog is None:
            self._agent_dialog = AgentDialog(get_context_fn=self._build_agent_context, parent=self)
        self._agent_dialog.show()
        self._agent_dialog.raise_()
        self._agent_dialog.activateWindow()

    def _on_export_pdf_clicked(self) -> None:
        """Gera dois relatórios PDF (português e inglês) com metadados,
        histórico de operações e gráfico comparativo de histograma."""
        if self._current_handle is None or self._preview_full is None:
            QMessageBox.information(self, "Nenhuma imagem", "Abra uma imagem antes de exportar o relatório.")
            return

        default_dir = str(self._current_handle.path.parent)
        output_dir_str = QFileDialog.getExistingDirectory(self, "Escolher pasta para salvar os relatórios", default_dir)
        if not output_dir_str:
            return

        output_dir = Path(output_dir_str)
        base_name = self._current_handle.path.stem

        try:
            r_idx, g_idx, b_idx = self._band_composition
            original_rgb = bt.apply_band_composition(self._preview_full, r_idx, g_idx, b_idx) \
                if self._preview_full.shape[0] >= max(r_idx, g_idx, b_idx) else self._preview_full

            report_data = pdfr.ReportData(
                image_name=self._current_handle.path.name,
                image_path=str(self._current_handle.path),
                width=self._current_handle.width,
                height=self._current_handle.height,
                band_count=self._current_handle.band_count,
                dtype=self._current_handle.dtype,
                crs=self._current_handle.crs,
                nodata=self._current_handle.nodata,
                driver=self._current_handle.driver,
                compression=self._current_handle.compression,
                operations=[entry.label for entry in self._history],
                histogram_original=original_rgb,
                histogram_corrected=self._preview_corrected,
                band_composition=self._band_composition,
            )

            pt_path, en_path = pdfr.generate_bilingual_reports(report_data, output_dir, base_name=base_name)

            QMessageBox.information(
                self, "Relatórios gerados",
                f"Relatórios PDF gerados com sucesso:\n\n{pt_path}\n{en_path}",
            )
            self.statusBar().showMessage(f"Relatórios PDF gerados em: {output_dir}")

        except Exception as exc:
            logger.exception("Erro ao gerar relatório PDF")
            QMessageBox.critical(self, "Erro ao gerar relatório", str(exc))