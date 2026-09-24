"""
Widget de visualização principal da imagem.

Responsabilidade:
- Renderizar a imagem (preview reduzido para performance)
- Controlar zoom, pan e ajuste à tela
- Exibir overlays (seleções locais, máscaras)
- Modo de seleção de área (retangular e poligonal), desenhando o contorno
  sobre a imagem e emitindo selection_changed quando a seleção é concluída
- Aplicar uma paleta de cores (colormap), quando fornecida, para
  reconstruir as cores reais de rasters "paletted" de 1 banda
"""
from __future__ import annotations

from typing import Optional

import numpy as np
import shiboken6
from PySide6.QtWidgets import QGraphicsView, QGraphicsScene, QWidget
from PySide6.QtGui import QPixmap, QImage, QMouseEvent, QPen, QColor, QPolygonF
from PySide6.QtCore import Qt, Signal, QPointF, QRectF


def _is_alive(qt_object) -> bool:
    """Verifica se o objeto C++ subjacente ainda existe (não foi destruído
    pelo Qt). Evita RuntimeError 'Internal C++ object already deleted'
    quando o Python ainda guarda uma referência antiga."""
    return qt_object is not None and shiboken6.isValid(qt_object)


class ImageViewer(QGraphicsView):
    """Área central de visualização da imagem raster (com zoom/pan e seleção de área)."""

    point_clicked = Signal(int, int)
    selection_changed = Signal(str, list)  # ('rectangle' | 'polygon', [(x,y), ...])
    selection_cleared = Signal()

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._scene = QGraphicsScene(self)
        self.setScene(self._scene)
        self._pixmap_item = None
        self._zoom_factor = 1.0

        self.setDragMode(QGraphicsView.ScrollHandDrag)
        self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
        self.setRenderHints(self.renderHints())

        # Estado de seleção
        self._selection_mode: Optional[str] = None  # None | 'rectangle' | 'polygon'
        self._rect_start: Optional[QPointF] = None
        self._rect_item = None
        self._polygon_points: list[QPointF] = []
        self._polygon_item = None

    # ------------------------------------------------------------------
    def set_image(self, pixmap: QPixmap) -> None:
        """Define a imagem exibida (chamado pelo core após leitura do raster)."""
        self._scene.clear()
        self._pixmap_item = self._scene.addPixmap(pixmap)
        self._scene.setSceneRect(self._pixmap_item.boundingRect())
        self.fit_to_window()
        self._clear_selection_items()

    def set_array_as_image(self, array: np.ndarray, colormap: Optional[dict] = None) -> None:
        """Converte um array numpy (bands, H, W) ou (H, W) em QPixmap e exibe.

        Se `colormap` for fornecido (dict {indice: (r,g,b,a)}), e o array tiver
        apenas 1 banda, a paleta é aplicada para reconstruir as cores reais
        (caso comum em ortomosaicos "paletted" exportados por softwares de
        fotogrametria, como Pix4D, Agisoft, DroneDeploy).
        """
        if colormap is not None and (array.ndim == 2 or array.shape[0] == 1):
            pixmap = self._paletted_array_to_pixmap(array, colormap)
        else:
            pixmap = self._array_to_pixmap(array)
        self.set_image(pixmap)

    @staticmethod
    def _to_uint8(band: np.ndarray) -> np.ndarray:
        """Normaliza uma banda (qualquer dtype) para 0-255 uint8, só para visualização."""
        band = band.astype(np.float32)
        finite = band[np.isfinite(band)]
        if finite.size == 0:
            return np.zeros_like(band, dtype=np.uint8)

        vmin, vmax = np.percentile(finite, [2, 98])
        if vmax <= vmin:
            vmin, vmax = finite.min(), finite.max()
        if vmax <= vmin:
            return np.zeros_like(band, dtype=np.uint8)

        stretched = np.clip((band - vmin) / (vmax - vmin), 0, 1)
        return (stretched * 255).astype(np.uint8)

    def _array_to_pixmap(self, array: np.ndarray) -> QPixmap:
        if array.ndim == 2:
            array = array[np.newaxis, ...]

        bands = array.shape[0]

        if bands == 1:
            gray = self._to_uint8(array[0])
            h, w = gray.shape
            qimage = QImage(gray.data, w, h, w, QImage.Format_Grayscale8)
            return QPixmap.fromImage(qimage.copy())

        r = self._to_uint8(array[0])
        g = self._to_uint8(array[1])
        b = self._to_uint8(array[2]) if bands >= 3 else g

        rgb = np.dstack([r, g, b])
        h, w, _ = rgb.shape
        rgb = np.ascontiguousarray(rgb)
        qimage = QImage(rgb.data, w, h, 3 * w, QImage.Format_RGB888)
        return QPixmap.fromImage(qimage.copy())

    def _paletted_array_to_pixmap(self, array: np.ndarray, colormap: dict) -> QPixmap:
        """Aplica uma paleta de cores (índice -> RGBA) a uma banda única,
        reconstruindo a imagem RGB real a partir dos índices de pixel."""
        band = array[0] if array.ndim == 3 else array
        h, w = band.shape

        max_index = int(band.max()) if band.size else 0
        lut_size = max(max_index + 1, 256)
        lut = np.zeros((lut_size, 3), dtype=np.uint8)
        for index, rgba in colormap.items():
            if 0 <= index < lut_size:
                lut[index] = rgba[:3]

        indices = np.clip(band.astype(np.int64), 0, lut_size - 1)
        rgb = lut[indices]
        rgb = np.ascontiguousarray(rgb)
        qimage = QImage(rgb.data, w, h, 3 * w, QImage.Format_RGB888)
        return QPixmap.fromImage(qimage.copy())

    def zoom_in(self) -> None:
        self._zoom_factor *= 1.25
        self.scale(1.25, 1.25)

    def zoom_out(self) -> None:
        self._zoom_factor *= 0.8
        self.scale(0.8, 0.8)

    def fit_to_window(self) -> None:
        if _is_alive(self._pixmap_item):
            self.fitInView(self._pixmap_item, Qt.KeepAspectRatio)
            self._zoom_factor = 1.0

    # ------------------------------------------------------------------
    # Modo de seleção
    # ------------------------------------------------------------------
    def set_selection_mode(self, mode: Optional[str]) -> None:
        """mode: None | 'rectangle' | 'polygon'"""
        self._selection_mode = mode
        self.setDragMode(QGraphicsView.NoDrag if mode else QGraphicsView.ScrollHandDrag)
        if mode == "polygon":
            self._polygon_points = []

    def clear_selection(self) -> None:
        self._clear_selection_items()
        self._polygon_points = []
        self.selection_cleared.emit()

    def _clear_selection_items(self) -> None:
        if _is_alive(self._rect_item):
            self._scene.removeItem(self._rect_item)
        self._rect_item = None

        if _is_alive(self._polygon_item):
            self._scene.removeItem(self._polygon_item)
        self._polygon_item = None

    def _to_image_coords(self, event_pos) -> Optional[QPointF]:
        if not _is_alive(self._pixmap_item):
            return None
        scene_pos = self.mapToScene(event_pos)
        item_pos = self._pixmap_item.mapFromScene(scene_pos)
        pixmap = self._pixmap_item.pixmap()
        if 0 <= item_pos.x() < pixmap.width() and 0 <= item_pos.y() < pixmap.height():
            return item_pos
        return None

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if self._selection_mode is None:
            super().mousePressEvent(event)
            if _is_alive(self._pixmap_item):
                pos = self._to_image_coords(event.pos())
                if pos is not None:
                    self.point_clicked.emit(int(pos.x()), int(pos.y()))
            return

        pos = self._to_image_coords(event.pos())
        if pos is None:
            return

        if self._selection_mode == "rectangle":
            self._rect_start = pos
            if _is_alive(self._rect_item):
                self._scene.removeItem(self._rect_item)
            pen = QPen(QColor(255, 215, 0), 2, Qt.DashLine)
            self._rect_item = self._scene.addRect(QRectF(pos, pos), pen)

        elif self._selection_mode == "polygon":
            self._polygon_points.append(pos)
            self._redraw_polygon()

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if self._selection_mode == "rectangle" and self._rect_start is not None:
            pos = self._to_image_coords(event.pos())
            if pos is not None and _is_alive(self._rect_item):
                rect = QRectF(self._rect_start, pos).normalized()
                self._rect_item.setRect(rect)
        else:
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if self._selection_mode == "rectangle" and self._rect_start is not None:
            pos = self._to_image_coords(event.pos())
            if pos is not None:
                rect = QRectF(self._rect_start, pos).normalized()
                x_min, y_min = int(rect.left()), int(rect.top())
                x_max, y_max = int(rect.right()), int(rect.bottom())
                self.selection_changed.emit("rectangle", [(x_min, y_min), (x_max, y_max)])
            self._rect_start = None
        else:
            super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event: QMouseEvent) -> None:
        if self._selection_mode == "polygon" and len(self._polygon_points) >= 3:
            points = [(int(p.x()), int(p.y())) for p in self._polygon_points]
            self.selection_changed.emit("polygon", points)
        else:
            super().mouseDoubleClickEvent(event)

    def _redraw_polygon(self) -> None:
        if _is_alive(self._polygon_item):
            self._scene.removeItem(self._polygon_item)
        self._polygon_item = None

        if len(self._polygon_points) < 2:
            return

        polygon = QPolygonF(self._polygon_points)
        pen = QPen(QColor(255, 215, 0), 2, Qt.DashLine)
        self._polygon_item = self._scene.addPolygon(polygon, pen)