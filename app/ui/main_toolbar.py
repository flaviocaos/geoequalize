"""
Barra de ferramentas lateral (toolbar) com ícones para as ações mais
usadas: zoom, pan, ajustar à tela, seleção retangular/poligonal, ponto
de referência e comparar antes/depois.

Centraliza ações que antes estavam espalhadas em menus e abas, no
estilo de softwares como ENVI, ArcGIS e QGIS.

Este é um arquivo NOVO. Crie-o em app/ui/main_toolbar.py.
"""
from __future__ import annotations

from typing import Optional

from PySide6.QtWidgets import QToolBar, QWidget, QToolButton, QButtonGroup
from PySide6.QtGui import QIcon, QPainter, QPixmap, QPen, QColor, QPolygon
from PySide6.QtCore import Qt, Signal, QSize, QPoint


def _make_icon(draw_fn, size: int = 28) -> QIcon:
    """Gera um QIcon desenhando formas simples via QPainter (sem depender
    de arquivos de imagem externos — ícones vetoriais leves e nítidos)."""
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing)
    draw_fn(painter, size)
    painter.end()
    return QIcon(pixmap)


def _icon_zoom_in(size: int = 28) -> QIcon:
    def draw(p: QPainter, s: int) -> None:
        pen = QPen(QColor("#1e3a5f"), 2.2)
        p.setPen(pen)
        p.drawEllipse(4, 4, int(s * 0.55), int(s * 0.55))
        p.drawLine(int(s * 0.58), int(s * 0.58), s - 3, s - 3)
        cx, cy, r = int(s * 0.3), int(s * 0.3), int(s * 0.12)
        p.drawLine(cx - r, cy, cx + r, cy)
        p.drawLine(cx, cy - r, cx, cy + r)
    return _make_icon(draw, size)


def _icon_zoom_out(size: int = 28) -> QIcon:
    def draw(p: QPainter, s: int) -> None:
        pen = QPen(QColor("#1e3a5f"), 2.2)
        p.setPen(pen)
        p.drawEllipse(4, 4, int(s * 0.55), int(s * 0.55))
        p.drawLine(int(s * 0.58), int(s * 0.58), s - 3, s - 3)
        cx, cy, r = int(s * 0.3), int(s * 0.3), int(s * 0.12)
        p.drawLine(cx - r, cy, cx + r, cy)
    return _make_icon(draw, size)


def _icon_fit_screen(size: int = 28) -> QIcon:
    def draw(p: QPainter, s: int) -> None:
        pen = QPen(QColor("#1e3a5f"), 2.2)
        p.setPen(pen)
        m = 4
        corner = int(s * 0.22)
        # quatro cantos de mira
        p.drawLine(m, m + corner, m, m); p.drawLine(m, m, m + corner, m)
        p.drawLine(s - m - corner, m, s - m, m); p.drawLine(s - m, m, s - m, m + corner)
        p.drawLine(m, s - m - corner, m, s - m); p.drawLine(m, s - m, m + corner, s - m)
        p.drawLine(s - m - corner, s - m, s - m, s - m); p.drawLine(s - m, s - m, s - m, s - m - corner)
    return _make_icon(draw, size)


def _icon_pan(size: int = 28) -> QIcon:
    def draw(p: QPainter, s: int) -> None:
        pen = QPen(QColor("#1e3a5f"), 2.0)
        p.setPen(pen)
        cx, cy = s // 2, s // 2
        arm = int(s * 0.38)
        for dx, dy in ((0, -1), (0, 1), (-1, 0), (1, 0)):
            p.drawLine(cx, cy, cx + dx * arm, cy + dy * arm)
        head = int(s * 0.1)
        p.drawPolygon(QPolygon([
            QPoint(cx, cy - arm - head), QPoint(cx - head, cy - arm + head // 2), QPoint(cx + head, cy - arm + head // 2)
        ]))
        p.drawPolygon(QPolygon([
            QPoint(cx, cy + arm + head), QPoint(cx - head, cy + arm - head // 2), QPoint(cx + head, cy + arm - head // 2)
        ]))
        p.drawPolygon(QPolygon([
            QPoint(cx - arm - head, cy), QPoint(cx - arm + head // 2, cy - head), QPoint(cx - arm + head // 2, cy + head)
        ]))
        p.drawPolygon(QPolygon([
            QPoint(cx + arm + head, cy), QPoint(cx + arm - head // 2, cy - head), QPoint(cx + arm - head // 2, cy + head)
        ]))
    return _make_icon(draw, size)


def _icon_rectangle(size: int = 28) -> QIcon:
    def draw(p: QPainter, s: int) -> None:
        pen = QPen(QColor("#f97316"), 2.2, Qt.DashLine)
        p.setPen(pen)
        m = int(s * 0.18)
        p.drawRect(m, m, s - 2 * m, s - 2 * m)
    return _make_icon(draw, size)


def _icon_polygon(size: int = 28) -> QIcon:
    def draw(p: QPainter, s: int) -> None:
        pen = QPen(QColor("#f97316"), 2.2, Qt.DashLine)
        p.setPen(pen)
        points = QPolygon([
            QPoint(int(s * 0.5), int(s * 0.12)),
            QPoint(int(s * 0.88), int(s * 0.4)),
            QPoint(int(s * 0.72), int(s * 0.88)),
            QPoint(int(s * 0.28), int(s * 0.88)),
            QPoint(int(s * 0.12), int(s * 0.4)),
        ])
        p.drawPolygon(points)
    return _make_icon(draw, size)


def _icon_reference_point(size: int = 28) -> QIcon:
    def draw(p: QPainter, s: int) -> None:
        pen = QPen(QColor("#0f1f33"), 2.0)
        p.setPen(pen)
        cx, cy = s // 2, s // 2
        r = int(s * 0.32)
        p.drawEllipse(cx - r, cy - r, 2 * r, 2 * r)
        p.drawLine(cx, cy - r - 4, cx, cy - r + 4)
        p.drawLine(cx, cy + r - 4, cx, cy + r + 4)
        p.drawLine(cx - r - 4, cy, cx - r + 4, cy)
        p.drawLine(cx + r - 4, cy, cx + r + 4, cy)
        p.setBrush(QColor("#f97316"))
        p.drawEllipse(cx - 3, cy - 3, 6, 6)
    return _make_icon(draw, size)


def _icon_compare(size: int = 28) -> QIcon:
    def draw(p: QPainter, s: int) -> None:
        pen = QPen(QColor("#1e3a5f"), 2.0)
        p.setPen(pen)
        m = 3
        p.drawRect(m, m, s - 2 * m, s - 2 * m)
        p.drawLine(s // 2, m, s // 2, s - m)
        p.setBrush(QColor("#2dd4bf"))
        p.drawRect(s // 2, m, s // 2 - m, s - 2 * m)
    return _make_icon(draw, size)


def _icon_clear_selection(size: int = 28) -> QIcon:
    def draw(p: QPainter, s: int) -> None:
        pen = QPen(QColor("#dc2626"), 2.4)
        p.setPen(pen)
        m = int(s * 0.22)
        p.drawLine(m, m, s - m, s - m)
        p.drawLine(s - m, m, m, s - m)
    return _make_icon(draw, size)


class MainToolbar(QToolBar):
    """Barra de ferramentas lateral vertical com ações de navegação e seleção."""

    zoom_in_requested = Signal()
    zoom_out_requested = Signal()
    fit_to_window_requested = Signal()
    pan_mode_requested = Signal()
    rectangle_mode_requested = Signal()
    polygon_mode_requested = Signal()
    clear_selection_requested = Signal()
    reference_point_mode_requested = Signal()
    compare_toggled = Signal(bool)

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__("Ferramentas de navegação", parent)
        self.setOrientation(Qt.Vertical)
        self.setIconSize(QSize(26, 26))
        self.setMovable(False)
        self.setFloatable(False)

        self._mode_group = QButtonGroup(self)
        self._mode_group.setExclusive(True)

        # --- Navegação ---
        action_zoom_in = self.addAction(_icon_zoom_in(), "Zoom +")
        action_zoom_in.triggered.connect(self.zoom_in_requested.emit)
        action_zoom_in.setToolTip("Zoom + (aumentar)")

        action_zoom_out = self.addAction(_icon_zoom_out(), "Zoom -")
        action_zoom_out.triggered.connect(self.zoom_out_requested.emit)
        action_zoom_out.setToolTip("Zoom - (diminuir)")

        action_fit = self.addAction(_icon_fit_screen(), "Ajustar à tela")
        action_fit.triggered.connect(self.fit_to_window_requested.emit)
        action_fit.setToolTip("Ajustar imagem à tela")

        self.addSeparator()

        # --- Modo de interação (mutuamente exclusivos) ---
        self._btn_pan = self._add_toggle_button(_icon_pan(), "Mover (Pan)", "Mover a imagem (arrastar)")
        self._btn_pan.setChecked(True)
        self._btn_pan.toggled.connect(lambda checked: checked and self.pan_mode_requested.emit())

        self._btn_rect = self._add_toggle_button(_icon_rectangle(), "Seleção retangular", "Selecionar área retangular")
        self._btn_rect.toggled.connect(lambda checked: checked and self.rectangle_mode_requested.emit())

        self._btn_poly = self._add_toggle_button(_icon_polygon(), "Seleção poligonal", "Selecionar área poligonal (clique nos vértices, duplo-clique para fechar)")
        self._btn_poly.toggled.connect(lambda checked: checked and self.polygon_mode_requested.emit())

        self._btn_reference = self._add_toggle_button(_icon_reference_point(), "Ponto de referência", "Clique na imagem para definir ponto de referência de cor")
        self._btn_reference.toggled.connect(lambda checked: checked and self.reference_point_mode_requested.emit())

        self.addSeparator()

        action_clear = self.addAction(_icon_clear_selection(), "Apagar seleção")
        action_clear.triggered.connect(self.clear_selection_requested.emit)
        action_clear.setToolTip("Apagar seleção atual")

        self.addSeparator()

        action_compare = self.addAction(_icon_compare(), "Comparar antes/depois")
        action_compare.setCheckable(True)
        action_compare.toggled.connect(self.compare_toggled.emit)
        action_compare.setToolTip("Comparar imagem original e corrigida")

    def _add_toggle_button(self, icon: QIcon, text: str, tooltip: str) -> QToolButton:
        action = self.addAction(icon, text)
        action.setCheckable(True)
        action.setToolTip(tooltip)

        # QToolBar.addAction retorna QAction; para usar QButtonGroup,
        # recuperamos o QToolButton correspondente criado internamente.
        button = self.widgetForAction(action)
        if isinstance(button, QToolButton):
            self._mode_group.addButton(button)
        return action  # mantemos a interface simples: tratamos a QAction como "botão"

    def set_pan_checked(self) -> None:
        self._btn_pan.setChecked(True)

    def uncheck_all_modes(self) -> None:
        for action in (self._btn_pan, self._btn_rect, self._btn_poly, self._btn_reference):
            action.setChecked(False)