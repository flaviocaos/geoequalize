"""
Painel lateral de metadados geoespaciais.
"""
from __future__ import annotations

from typing import Optional

from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QFormLayout


class MetadataPanel(QWidget):
    """Painel que exibe os metadados do raster aberto."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._form = QFormLayout()
        self._labels: dict[str, QLabel] = {}

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("<b>Metadados</b>"))
        layout.addLayout(self._form)
        layout.addStretch()
        self.setLayout(layout)

        self._placeholder = QLabel("Nenhuma imagem aberta.")
        self._form.addRow(self._placeholder)

    def update_metadata(self, metadata: dict) -> None:
        """Popula o formulário com os metadados do raster."""
        # limpa linhas anteriores
        while self._form.rowCount() > 0:
            self._form.removeRow(0)
        self._labels.clear()

        for key, value in metadata.items():
            value_label = QLabel(str(value))
            value_label.setWordWrap(True)
            self._form.addRow(f"{key}:", value_label)
            self._labels[key] = value_label

    def clear(self) -> None:
        while self._form.rowCount() > 0:
            self._form.removeRow(0)
        self._form.addRow(QLabel("Nenhuma imagem aberta."))