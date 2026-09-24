"""
Painel de projeto: salvar/abrir projeto, histórico visual de operações,
presets e acesso ao processamento em lote.

Este é um arquivo NOVO desta fase. Crie-o em app/ui/project_panel.py.
"""
from __future__ import annotations

from typing import Optional

from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QListWidget,
    QListWidgetItem,
    QComboBox,
    QGroupBox,
    QLineEdit,
    QMessageBox,
)
from PySide6.QtCore import Signal, Qt


class ProjectPanel(QWidget):
    """Painel lateral: projeto (salvar/abrir), histórico, presets e batch."""

    save_project_requested = Signal()
    open_project_requested = Signal()

    toggle_operation_requested = Signal(int, bool)  # (índice, novo_estado_enabled)
    remove_operation_requested = Signal(int)
    move_operation_requested = Signal(int, int)  # (old_index, new_index)

    save_preset_requested = Signal(str)
    load_preset_requested = Signal(str)

    open_batch_dialog_requested = Signal()

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)

        layout = QVBoxLayout(self)

        project_group = QGroupBox("Projeto")
        project_layout = QHBoxLayout()
        self._btn_save_project = QPushButton("Salvar projeto")
        self._btn_open_project = QPushButton("Abrir projeto")
        project_layout.addWidget(self._btn_save_project)
        project_layout.addWidget(self._btn_open_project)
        project_group.setLayout(project_layout)
        layout.addWidget(project_group)

        history_group = QGroupBox("Histórico de operações")
        history_layout = QVBoxLayout()
        self._history_list = QListWidget()
        self._history_list.itemChanged.connect(self._on_item_changed)
        history_layout.addWidget(self._history_list)

        history_buttons = QHBoxLayout()
        self._btn_remove_op = QPushButton("Remover selecionada")
        self._btn_move_up = QPushButton("▲")
        self._btn_move_down = QPushButton("▼")
        history_buttons.addWidget(self._btn_remove_op)
        history_buttons.addWidget(self._btn_move_up)
        history_buttons.addWidget(self._btn_move_down)
        history_layout.addLayout(history_buttons)

        history_group.setLayout(history_layout)
        layout.addWidget(history_group)

        preset_group = QGroupBox("Presets")
        preset_layout = QVBoxLayout()

        self._preset_combo = QComboBox()
        preset_layout.addWidget(self._preset_combo)

        self._btn_load_preset = QPushButton("Carregar preset (substitui histórico)")
        preset_layout.addWidget(self._btn_load_preset)

        save_preset_layout = QHBoxLayout()
        self._preset_name_edit = QLineEdit()
        self._preset_name_edit.setPlaceholderText("Nome do novo preset...")
        self._btn_save_preset = QPushButton("Salvar como preset")
        save_preset_layout.addWidget(self._preset_name_edit)
        save_preset_layout.addWidget(self._btn_save_preset)
        preset_layout.addLayout(save_preset_layout)

        preset_group.setLayout(preset_layout)
        layout.addWidget(preset_group)

        batch_group = QGroupBox("Processamento em lote")
        batch_layout = QVBoxLayout()
        self._btn_open_batch = QPushButton("Processar várias imagens...")
        batch_layout.addWidget(self._btn_open_batch)
        batch_group.setLayout(batch_layout)
        layout.addWidget(batch_group)

        layout.addStretch()
        self.setLayout(layout)

        self._btn_save_project.clicked.connect(self.save_project_requested.emit)
        self._btn_open_project.clicked.connect(self.open_project_requested.emit)
        self._btn_remove_op.clicked.connect(self._on_remove_clicked)
        self._btn_move_up.clicked.connect(lambda: self._on_move_clicked(-1))
        self._btn_move_down.clicked.connect(lambda: self._on_move_clicked(1))
        self._btn_load_preset.clicked.connect(self._on_load_preset_clicked)
        self._btn_save_preset.clicked.connect(self._on_save_preset_clicked)
        self._btn_open_batch.clicked.connect(self.open_batch_dialog_requested.emit)

    # ------------------------------------------------------------------
    def populate_presets(self, preset_keys_labels: list[tuple[str, str]]) -> None:
        self._preset_combo.clear()
        for key, label in preset_keys_labels:
            self._preset_combo.addItem(label, key)

    def update_history(self, labels: list[str], enabled_flags: list[bool]) -> None:
        self._history_list.blockSignals(True)
        self._history_list.clear()
        for label, enabled in zip(labels, enabled_flags):
            item = QListWidgetItem(label)
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            item.setCheckState(Qt.Checked if enabled else Qt.Unchecked)
            self._history_list.addItem(item)
        self._history_list.blockSignals(False)

    def _on_item_changed(self, item: QListWidgetItem) -> None:
        index = self._history_list.row(item)
        enabled = item.checkState() == Qt.Checked
        self.toggle_operation_requested.emit(index, enabled)

    def _on_remove_clicked(self) -> None:
        index = self._history_list.currentRow()
        if index >= 0:
            self.remove_operation_requested.emit(index)

    def _on_move_clicked(self, direction: int) -> None:
        index = self._history_list.currentRow()
        if index < 0:
            return
        new_index = index + direction
        if 0 <= new_index < self._history_list.count():
            self.move_operation_requested.emit(index, new_index)

    def _on_load_preset_clicked(self) -> None:
        key = self._preset_combo.currentData()
        if key:
            self.load_preset_requested.emit(key)

    def _on_save_preset_clicked(self) -> None:
        name = self._preset_name_edit.text().strip()
        if not name:
            QMessageBox.information(self, "Nome necessário", "Digite um nome para o preset.")
            return
        self.save_preset_requested.emit(name)
        self._preset_name_edit.clear()