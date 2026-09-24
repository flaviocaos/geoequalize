"""
Diálogo de exportação: escolhe formato, caminho de saída, escopo de bandas,
mostra barra de progresso e permite cancelar.

Este é um arquivo NOVO desta fase. Crie-o em app/ui/export_dialog.py.
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional

from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QFormLayout,
    QLabel,
    QComboBox,
    QLineEdit,
    QPushButton,
    QHBoxLayout,
    QProgressBar,
    QCheckBox,
    QFileDialog,
    QMessageBox,
)
from PySide6.QtCore import Qt


class ExportDialog(QDialog):
    """Diálogo modal para configurar e executar a exportação."""

    FORMAT_OPTIONS = [
        ("GeoTIFF corrigido (.tif)", "GTiff", ".tif"),
        ("TIFF comum (.tif)", "GTiff", ".tif"),
        ("PNG para visualização (.png)", "PNG", ".png"),
        ("JPEG para visualização (.jpg)", "JPEG", ".jpg"),
    ]

    def __init__(self, default_dir: str = "", band_count: int = 3, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Exportar imagem corrigida")
        self.setMinimumWidth(480)

        self._default_dir = default_dir
        self._band_count = band_count
        self._cancelled = False

        layout = QVBoxLayout(self)

        form = QFormLayout()
        self._format_combo = QComboBox()
        for label, _driver, _ext in self.FORMAT_OPTIONS:
            self._format_combo.addItem(label)
        self._format_combo.currentIndexChanged.connect(self._on_format_changed)
        form.addRow("Formato:", self._format_combo)

        path_layout = QHBoxLayout()
        self._path_edit = QLineEdit()
        self._btn_browse = QPushButton("Escolher...")
        path_layout.addWidget(self._path_edit)
        path_layout.addWidget(self._btn_browse)
        form.addRow("Salvar em:", path_layout)

        self._only_rgb_checkbox = QCheckBox("Exportar apenas a composição RGB visualizada")
        self._only_rgb_checkbox.setEnabled(band_count > 3)
        if band_count <= 3:
            self._only_rgb_checkbox.setChecked(True)
            self._only_rgb_checkbox.setText("Exportar composição RGB (imagem tem 3 bandas ou menos)")
        form.addRow(self._only_rgb_checkbox)

        self._report_checkbox = QCheckBox("Gerar relatório de processamento (.txt)")
        self._report_checkbox.setChecked(True)
        form.addRow(self._report_checkbox)

        layout.addLayout(form)

        self._progress_bar = QProgressBar()
        self._progress_bar.setRange(0, 100)
        self._progress_bar.setValue(0)
        layout.addWidget(self._progress_bar)

        self._status_label = QLabel("")
        layout.addWidget(self._status_label)

        buttons_layout = QHBoxLayout()
        self._btn_export = QPushButton("Exportar")
        self._btn_cancel = QPushButton("Cancelar")
        buttons_layout.addWidget(self._btn_export)
        buttons_layout.addWidget(self._btn_cancel)
        layout.addLayout(buttons_layout)

        self._btn_browse.clicked.connect(self._on_browse_clicked)
        self._btn_cancel.clicked.connect(self._on_cancel_clicked)
        self._btn_export.clicked.connect(self.accept)

        self._on_format_changed(0)

    # ------------------------------------------------------------------
    def _current_format(self) -> tuple[str, str]:
        """Retorna (driver_rasterio, extensão)."""
        _label, driver, ext = self.FORMAT_OPTIONS[self._format_combo.currentIndex()]
        return driver, ext

    def _on_format_changed(self, _index: int) -> None:
        _driver, ext = self._current_format()
        current = self._path_edit.text()
        if current:
            base = str(Path(current).with_suffix(""))
            self._path_edit.setText(base + ext)
        else:
            self._path_edit.setText(str(Path(self._default_dir) / f"imagem_corrigida{ext}"))

    def _on_browse_clicked(self) -> None:
        _driver, ext = self._current_format()
        path, _ = QFileDialog.getSaveFileName(
            self, "Salvar como", self._path_edit.text(), f"Arquivo (*{ext})"
        )
        if path:
            if not path.endswith(ext):
                path += ext
            self._path_edit.setText(path)

    def _on_cancel_clicked(self) -> None:
        self._cancelled = True
        self.reject()

    # ------------------------------------------------------------------
    def output_path(self) -> Path:
        return Path(self._path_edit.text())

    def selected_driver(self) -> str:
        driver, _ext = self._current_format()
        return driver

    def export_only_rgb(self) -> bool:
        return self._only_rgb_checkbox.isChecked()

    def generate_report(self) -> bool:
        return self._report_checkbox.isChecked()

    def is_cancelled(self) -> bool:
        return self._cancelled

    # ------------------------------------------------------------------
    def update_progress(self, current: int, total: int) -> None:
        pct = int(current / total * 100) if total else 0
        self._progress_bar.setValue(pct)
        self._status_label.setText(f"Processando bloco {current} de {total}...")

    def set_finished(self, success: bool, message: str) -> None:
        self._progress_bar.setValue(100 if success else self._progress_bar.value())
        self._status_label.setText(message)
        if success:
            QMessageBox.information(self, "Exportação concluída", message)
        else:
            QMessageBox.critical(self, "Erro na exportação", message)