"""
Aba de Segmentação (clustering) dentro do diálogo de Geoprocessamento.

Permite executar K-Means sobre uma camada/imagem carregada, visualizar
o resultado, consultar o método do cotovelo para escolher k, e enviar
o resultado como nova camada (compatível com Reclassificação e MCDA).

Este é um arquivo NOVO. Crie-o em app/ui/clustering_tab.py.
"""
from __future__ import annotations

from typing import Optional, Callable

import numpy as np
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QFormLayout,
    QLabel,
    QComboBox,
    QSpinBox,
    QPushButton,
    QListWidget,
    QMessageBox,
    QGroupBox,
)
from PySide6.QtCore import Signal

from core import clustering as clust


class ClusteringTab(QWidget):
    """Aba 'Segmentação': executa K-Means sobre uma camada e gera resultado como nova camada."""

    layer_added = Signal()  # emitido após salvar uma nova camada, para os outros combos atualizarem

    def __init__(
        self,
        get_layer_names_fn: Callable[[], list[str]],
        get_layer_fn: Callable[[str], Optional[np.ndarray]],
        add_layer_fn: Callable[[str, np.ndarray], None],
        get_nodata_fn: Optional[Callable[[str], Optional[float]]] = None,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self._get_layer_names = get_layer_names_fn
        self._get_layer = get_layer_fn
        self._add_layer = add_layer_fn
        self._get_nodata = get_nodata_fn or (lambda _name: None)

        self._last_result: Optional[clust.ClusterResult] = None
        self._last_layer_name: str = ""

        layout = QVBoxLayout(self)

        layout.addWidget(QLabel(
            "Agrupa pixels por similaridade espectral (K-Means), sem depender "
            "de modelos pré-treinados ou rótulos. Útil para uma primeira "
            "exploração de padrões de uso/cobertura do solo. O resultado pode "
            "ser usado nas abas Reclassificação e MCDA."
        ))

        form = QFormLayout()
        self._layer_combo = QComboBox()
        self._k_spin = QSpinBox()
        self._k_spin.setRange(2, 15)
        self._k_spin.setValue(5)
        self._smoothing_spin = QSpinBox()
        self._smoothing_spin.setRange(1, 15)
        self._smoothing_spin.setValue(3)
        self._smoothing_spin.setToolTip(
            "Tamanho da janela de suavização espacial antes do clustering "
            "(reduz ruído 'sal e pimenta'). 1 = sem suavização."
        )
        form.addRow("Camada de entrada:", self._layer_combo)
        form.addRow("Número de clusters (k):", self._k_spin)
        form.addRow("Suavização espacial (px):", self._smoothing_spin)
        layout.addLayout(form)

        buttons_layout = QHBoxLayout()
        btn_elbow = QPushButton("Sugerir k (método do cotovelo)")
        btn_elbow.clicked.connect(self._on_estimate_k_clicked)
        btn_run = QPushButton("Executar segmentação")
        btn_run.clicked.connect(self._on_run_clustering_clicked)
        buttons_layout.addWidget(btn_elbow)
        buttons_layout.addWidget(btn_run)
        layout.addLayout(buttons_layout)

        self._elbow_label = QLabel("")
        self._elbow_label.setWordWrap(True)
        layout.addWidget(self._elbow_label)

        result_group = QGroupBox("Resultado — estatísticas por cluster")
        result_layout = QVBoxLayout()
        self._result_list = QListWidget()
        result_layout.addWidget(self._result_list)
        result_group.setLayout(result_layout)
        layout.addWidget(result_group)

        btn_save_layer = QPushButton("Salvar resultado como nova camada")
        btn_save_layer.clicked.connect(self._on_save_as_layer_clicked)
        layout.addWidget(btn_save_layer)

        layout.addStretch()
        self.setLayout(layout)

    def refresh_layers(self) -> None:
        self._layer_combo.clear()
        self._layer_combo.addItems(self._get_layer_names())

    def _current_layer_array(self) -> Optional[np.ndarray]:
        name = self._layer_combo.currentText()
        if not name:
            return None
        return self._get_layer(name)

    def _on_estimate_k_clicked(self) -> None:
        array = self._current_layer_array()
        if array is None:
            QMessageBox.information(self, "Camada inválida", "Selecione uma camada válida.")
            return

        layer_name = self._layer_combo.currentText()
        nodata = self._get_nodata(layer_name)

        try:
            inertias = clust.estimate_optimal_k(
                array if array.ndim == 3 else array[np.newaxis, ...],
                nodata=nodata,
                spatial_smoothing=self._smoothing_spin.value(),
            )
        except Exception as exc:
            QMessageBox.critical(self, "Erro ao estimar k", str(exc))
            return

        lines = ["Inércia por k (procure onde a queda desacelera — 'cotovelo'):"]
        for k, inertia in inertias.items():
            lines.append(f"  k={k}: {inertia:.1f}")
        self._elbow_label.setText("\n".join(lines))

    def _on_run_clustering_clicked(self) -> None:
        array = self._current_layer_array()
        if array is None:
            QMessageBox.information(self, "Camada inválida", "Selecione uma camada válida.")
            return

        layer_name = self._layer_combo.currentText()
        nodata = self._get_nodata(layer_name)

        try:
            result = clust.run_kmeans_clustering(
                array if array.ndim == 3 else array[np.newaxis, ...],
                n_clusters=self._k_spin.value(),
                nodata=nodata,
                spatial_smoothing=self._smoothing_spin.value(),
            )
        except Exception as exc:
            QMessageBox.critical(self, "Erro na segmentação", str(exc))
            return

        self._last_result = result
        self._last_layer_name = layer_name
        self._populate_result_list(result)

    def _populate_result_list(self, result: clust.ClusterResult) -> None:
        self._result_list.clear()
        total_pixels = sum(result.pixel_counts.values())
        for cluster_id in range(result.n_clusters):
            count = result.pixel_counts.get(cluster_id, 0)
            pct = (count / total_pixels * 100) if total_pixels else 0
            color = result.cluster_colors.get(cluster_id, (128, 128, 128))
            self._result_list.addItem(
                f"Cluster {cluster_id}: {count} px ({pct:.1f}%) — cor RGB{color}"
            )

    def _on_save_as_layer_clicked(self) -> None:
        if self._last_result is None:
            QMessageBox.information(self, "Sem resultado", "Execute a segmentação antes de salvar.")
            return

        new_name = f"{self._last_layer_name}_clusters"
        self._add_layer(new_name, self._last_result.labels.astype(np.float64))
        self.layer_added.emit()
        QMessageBox.information(self, "Camada salva", f"Nova camada criada: '{new_name}'.")