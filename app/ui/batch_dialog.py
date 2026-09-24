"""
Diálogo de processamento em lote: seleciona várias imagens, pasta de saída,
mostra progresso geral e relatório final (sucessos/erros por imagem).

Este é um arquivo NOVO desta fase. Crie-o em app/ui/batch_dialog.py.
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional

from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QListWidget,
    QFileDialog,
    QProgressBar,
    QLineEdit,
    QMessageBox,
)


class BatchDialog(QDialog):
    """Diálogo modal para configurar e acompanhar o processamento em lote."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Processamento em lote")
        self.setMinimumWidth(520)

        self._input_paths: list[Path] = []
        self._cancelled = False

        layout = QVBoxLayout(self)

        layout.addWidget(QLabel("<b>Imagens selecionadas</b>"))
        self._file_list = QListWidget()
        layout.addWidget(self._file_list)

        files_buttons = QHBoxLayout()
        self._btn_add_files = QPushButton("Adicionar imagens...")
        self._btn_clear_files = QPushButton("Limpar lista")
        files_buttons.addWidget(self._btn_add_files)
        files_buttons.addWidget(self._btn_clear_files)
        layout.addLayout(files_buttons)

        layout.addWidget(QLabel("<b>Pasta de saída</b>"))
        output_layout = QHBoxLayout()
        self._output_edit = QLineEdit()
        self._btn_browse_output = QPushButton("Escolher...")
        output_layout.addWidget(self._output_edit)
        output_layout.addWidget(self._btn_browse_output)
        layout.addLayout(output_layout)

        self._progress_bar = QProgressBar()
        self._progress_bar.setRange(0, 100)
        layout.addWidget(self._progress_bar)

        self._status_label = QLabel("")
        layout.addWidget(self._status_label)

        self._results_list = QListWidget()
        self._results_list.setVisible(False)
        layout.addWidget(self._results_list)

        buttons_layout = QHBoxLayout()
        self._btn_start = QPushButton("Processar lote")
        self._btn_cancel = QPushButton("Cancelar")
        buttons_layout.addWidget(self._btn_start)
        buttons_layout.addWidget(self._btn_cancel)
        layout.addLayout(buttons_layout)

        self._btn_add_files.clicked.connect(self._on_add_files)
        self._btn_clear_files.clicked.connect(self._on_clear_files)
        self._btn_browse_output.clicked.connect(self._on_browse_output)
        self._btn_cancel.clicked.connect(self._on_cancel_clicked)
        self._btn_start.clicked.connect(self.accept)

    # ------------------------------------------------------------------
    def _on_add_files(self) -> None:
        paths, _ = QFileDialog.getOpenFileNames(
            self, "Selecionar imagens",
            "", "Imagens raster (*.tif *.tiff *.jp2 *.jpg *.jpeg *.png)",
        )
        for p in paths:
            path_obj = Path(p)
            if path_obj not in self._input_paths:
                self._input_paths.append(path_obj)
                self._file_list.addItem(path_obj.name)

    def _on_clear_files(self) -> None:
        self._input_paths.clear()
        self._file_list.clear()

    def _on_browse_output(self) -> None:
        directory = QFileDialog.getExistingDirectory(self, "Escolher pasta de saída")
        if directory:
            self._output_edit.setText(directory)

    def _on_cancel_clicked(self) -> None:
        self._cancelled = True
        self.reject()

    # ------------------------------------------------------------------
    def input_paths(self) -> list[Path]:
        return list(self._input_paths)

    def output_dir(self) -> Optional[Path]:
        text = self._output_edit.text().strip()
        return Path(text) if text else None

    def validate(self) -> bool:
        if not self._input_paths:
            QMessageBox.warning(self, "Sem imagens", "Adicione ao menos uma imagem.")
            return False
        if not self._output_edit.text().strip():
            QMessageBox.warning(self, "Sem pasta de saída", "Escolha uma pasta de saída.")
            return False
        return True

    def is_cancelled(self) -> bool:
        return self._cancelled

    # ------------------------------------------------------------------
    def update_progress(self, current: int, total: int, filename: str) -> None:
        pct = int(current / total * 100) if total else 0
        self._progress_bar.setValue(pct)
        self._status_label.setText(f"Processando {current}/{total}: {filename}")

    def show_results(self, results) -> None:
        self._results_list.setVisible(True)
        self._results_list.clear()
        for item in results.items:
            if item.success:
                self._results_list.addItem(f"✔ {item.input_path.name} → {item.output_path.name}")
            else:
                self._results_list.addItem(f"✘ {item.input_path.name}: {item.error_message}")

        self._status_label.setText(
            f"Concluído: {results.success_count} com sucesso, {results.failure_count} com erro."
        )