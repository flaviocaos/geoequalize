"""
Diálogo de Geoprocessamento e Modelagem: reclassificação, análise
multicritério (MCDA) e simulação CA-Markov.

Este é um arquivo NOVO. Crie-o em app/ui/geoprocessing_dialog.py.

Diferente das correções de imagem (que operam sobre a imagem aberta),
este módulo trabalha com camadas raster carregadas independentemente
(podem ser a imagem atual ou outros arquivos), refletindo o fluxo de
trabalho real de ferramentas como IDRISI/TerrSet.
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional

import numpy as np
from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QFormLayout,
    QLabel,
    QPushButton,
    QTabWidget,
    QWidget,
    QListWidget,
    QListWidgetItem,
    QDoubleSpinBox,
    QSpinBox,
    QFileDialog,
    QMessageBox,
    QCheckBox,
    QGroupBox,
)
from PySide6.QtCore import Qt

import rasterio

from core import map_algebra as ma
from core import mcda
from core import markov_simulation as markov
from app.ui.clustering_tab import ClusteringTab


class _LayerStore:
    """Mantém as camadas raster carregadas para uso no módulo de geoprocessamento."""

    def __init__(self) -> None:
        self.layers: dict[str, np.ndarray] = {}
        self.nodata: dict[str, Optional[float]] = {}

    def load_from_file(self, path: Path) -> str:
        with rasterio.open(path) as src:
            array = src.read(1).astype(np.float64)
            nodata = src.nodata
        name = path.stem
        self.layers[name] = array
        self.nodata[name] = nodata
        return name

    def add_array(self, name: str, array: np.ndarray, nodata: Optional[float] = None) -> None:
        self.layers[name] = array
        self.nodata[name] = nodata

    def names(self) -> list[str]:
        return list(self.layers.keys())


class GeoprocessingDialog(QDialog):
    """Diálogo com abas: Camadas, Reclassificação, MCDA, CA-Markov."""

    def __init__(self, initial_array: Optional[np.ndarray] = None, initial_nodata: Optional[float] = None, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Geoprocessamento e Modelagem")
        self.setMinimumSize(820, 600)

        self._store = _LayerStore()
        if initial_array is not None:
            self._store.add_array("imagem_atual", initial_array, initial_nodata)

        self._result_preview: Optional[np.ndarray] = None
        self._combo_refreshers: list = []

        layout = QVBoxLayout(self)
        self._tabs = QTabWidget()
        layout.addWidget(self._tabs)

        self._tabs.addTab(self._build_layers_tab(), "Camadas")
        self._tabs.addTab(self._build_clustering_tab(), "Segmentação")
        self._tabs.addTab(self._build_reclass_tab(), "Reclassificação")
        self._tabs.addTab(self._build_mcda_tab(), "MCDA")
        self._tabs.addTab(self._build_markov_tab(), "CA-Markov")

        bottom = QHBoxLayout()
        self._status_label = QLabel("")
        bottom.addWidget(self._status_label)
        bottom.addStretch()
        self._btn_close = QPushButton("Fechar")
        self._btn_close.clicked.connect(self.accept)
        bottom.addWidget(self._btn_close)
        layout.addLayout(bottom)

        self.setLayout(layout)
        self._refresh_layer_lists()

    # ------------------------------------------------------------------
    # Aba: Camadas
    # ------------------------------------------------------------------
    def _build_layers_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)

        layout.addWidget(QLabel(
            "Carregue rasters de 1 banda para usar como critérios, classes "
            "ou aptidões nas demais abas. A imagem atualmente aberta no "
            "GeoEqualize já está disponível como 'imagem_atual', se houver."
        ))

        self._layer_list = QListWidget()
        layout.addWidget(self._layer_list)

        buttons = QHBoxLayout()
        btn_load = QPushButton("Carregar arquivo raster...")
        btn_load.clicked.connect(self._on_load_layer_clicked)
        buttons.addWidget(btn_load)
        layout.addLayout(buttons)

        return widget

    def _on_load_layer_clicked(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Carregar raster", "", "Raster (*.tif *.tiff)")
        if not path:
            return
        try:
            name = self._store.load_from_file(Path(path))
        except Exception as exc:
            QMessageBox.critical(self, "Erro ao carregar", str(exc))
            return
        self._refresh_layer_lists()
        self._status_label.setText(f"Camada carregada: {name}")

    def _refresh_layer_lists(self) -> None:
        self._layer_list.clear()
        for name in self._store.names():
            shape = self._store.layers[name].shape
            self._layer_list.addItem(f"{name}  [{shape[0]}x{shape[1]}]")

        for combo_refresh_fn in self._combo_refreshers:
            combo_refresh_fn()

        if hasattr(self, "_clustering_tab"):
            self._clustering_tab.refresh_layers()

    # ------------------------------------------------------------------
    # Aba: Segmentação (clustering)
    # ------------------------------------------------------------------
    def _build_clustering_tab(self) -> QWidget:
        self._clustering_tab = ClusteringTab(
            get_layer_names_fn=self._store.names,
            get_layer_fn=lambda name: self._store.layers.get(name),
            add_layer_fn=self._store.add_array,
            get_nodata_fn=lambda name: self._store.nodata.get(name),
            parent=self,
        )
        self._clustering_tab.layer_added.connect(self._refresh_layer_lists)
        return self._clustering_tab

    # ------------------------------------------------------------------
    # Aba: Reclassificação
    # ------------------------------------------------------------------
    def _build_reclass_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)

        form = QFormLayout()
        from PySide6.QtWidgets import QComboBox
        self._reclass_layer_combo = QComboBox()
        form.addRow("Camada de entrada:", self._reclass_layer_combo)
        layout.addLayout(form)

        layout.addWidget(QLabel(
            "Defina intervalos [mín, máx) e a classe correspondente. "
            "Use o botão 'Adicionar regra' para cada faixa."
        ))

        self._reclass_rules_list = QListWidget()
        layout.addWidget(self._reclass_rules_list)

        rule_form = QFormLayout()
        self._spin_reclass_min = QDoubleSpinBox()
        self._spin_reclass_min.setRange(-1e9, 1e9)
        self._spin_reclass_max = QDoubleSpinBox()
        self._spin_reclass_max.setRange(-1e9, 1e9)
        self._spin_reclass_class = QSpinBox()
        self._spin_reclass_class.setRange(0, 999)
        rule_form.addRow("Mínimo:", self._spin_reclass_min)
        rule_form.addRow("Máximo (exclusivo):", self._spin_reclass_max)
        rule_form.addRow("Classe:", self._spin_reclass_class)
        layout.addLayout(rule_form)

        rule_buttons = QHBoxLayout()
        btn_add_rule = QPushButton("Adicionar regra")
        btn_add_rule.clicked.connect(self._on_add_reclass_rule)
        btn_clear_rules = QPushButton("Limpar regras")
        btn_clear_rules.clicked.connect(lambda: (self._reclass_rules.clear(), self._reclass_rules_list.clear()))
        rule_buttons.addWidget(btn_add_rule)
        rule_buttons.addWidget(btn_clear_rules)
        layout.addLayout(rule_buttons)

        btn_run_reclass = QPushButton("Executar reclassificação -> nova camada")
        btn_run_reclass.clicked.connect(self._on_run_reclass)
        layout.addWidget(btn_run_reclass)

        self._reclass_rules: list[ma.ReclassRule] = []

        def refresh_combo():
            self._reclass_layer_combo.clear()
            self._reclass_layer_combo.addItems(self._store.names())

        self._combo_refreshers.append(refresh_combo)

        return widget

    def _on_add_reclass_rule(self) -> None:
        rule = ma.ReclassRule(
            min_value=self._spin_reclass_min.value(),
            max_value=self._spin_reclass_max.value(),
            new_class=self._spin_reclass_class.value(),
        )
        self._reclass_rules.append(rule)
        self._reclass_rules_list.addItem(f"[{rule.min_value}, {rule.max_value}) -> classe {rule.new_class}")

    def _on_run_reclass(self) -> None:
        layer_name = self._reclass_layer_combo.currentText()
        if not layer_name or layer_name not in self._store.layers:
            QMessageBox.information(self, "Camada inválida", "Selecione uma camada válida.")
            return
        if not self._reclass_rules:
            QMessageBox.information(self, "Sem regras", "Adicione ao menos uma regra de reclassificação.")
            return

        array = self._store.layers[layer_name]
        nodata = self._store.nodata[layer_name]
        scheme = ma.ReclassScheme(rules=self._reclass_rules)
        result = ma.reclassify(array, scheme, nodata=nodata)

        new_name = f"{layer_name}_reclass"
        self._store.add_array(new_name, result.astype(np.float64))
        self._refresh_layer_lists()
        self._status_label.setText(f"Reclassificação concluída: nova camada '{new_name}'.")

    # ------------------------------------------------------------------
    # Aba: MCDA
    # ------------------------------------------------------------------
    def _build_mcda_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)

        layout.addWidget(QLabel(
            "Adicione critérios (camadas) com seus pesos. A soma dos pesos "
            "deve ser 1.0. Marque 'menor é melhor' para critérios de custo "
            "(ex.: distância a vias, onde menor distância é mais favorável)."
        ))

        self._mcda_criteria_list = QListWidget()
        layout.addWidget(self._mcda_criteria_list)

        from PySide6.QtWidgets import QComboBox
        form = QFormLayout()
        self._mcda_layer_combo = QComboBox()
        self._mcda_weight_spin = QDoubleSpinBox()
        self._mcda_weight_spin.setRange(0.0, 1.0)
        self._mcda_weight_spin.setSingleStep(0.05)
        self._mcda_weight_spin.setValue(0.2)
        self._mcda_higher_better_checkbox = QCheckBox("Maior valor é mais favorável (benefício)")
        self._mcda_higher_better_checkbox.setChecked(True)
        form.addRow("Camada (critério):", self._mcda_layer_combo)
        form.addRow("Peso:", self._mcda_weight_spin)
        form.addRow(self._mcda_higher_better_checkbox)
        layout.addLayout(form)

        criteria_buttons = QHBoxLayout()
        btn_add_criterion = QPushButton("Adicionar critério")
        btn_add_criterion.clicked.connect(self._on_add_mcda_criterion)
        btn_clear_criteria = QPushButton("Limpar critérios")
        btn_clear_criteria.clicked.connect(self._on_clear_mcda_criteria)
        criteria_buttons.addWidget(btn_add_criterion)
        criteria_buttons.addWidget(btn_clear_criteria)
        layout.addLayout(criteria_buttons)

        btn_run_mcda = QPushButton("Executar MCDA (combinação linear ponderada) -> nova camada")
        btn_run_mcda.clicked.connect(self._on_run_mcda)
        layout.addWidget(btn_run_mcda)

        self._mcda_criteria: list[mcda.Criterion] = []

        def refresh_combo():
            self._mcda_layer_combo.clear()
            self._mcda_layer_combo.addItems(self._store.names())

        self._combo_refreshers.append(refresh_combo)

        return widget

    def _on_add_mcda_criterion(self) -> None:
        layer_name = self._mcda_layer_combo.currentText()
        if not layer_name or layer_name not in self._store.layers:
            QMessageBox.information(self, "Camada inválida", "Selecione uma camada válida.")
            return

        criterion = mcda.Criterion(
            name=layer_name,
            array=self._store.layers[layer_name],
            weight=self._mcda_weight_spin.value(),
            higher_is_better=self._mcda_higher_better_checkbox.isChecked(),
            nodata=self._store.nodata.get(layer_name),
        )
        self._mcda_criteria.append(criterion)
        direction = "benefício" if criterion.higher_is_better else "custo"
        self._mcda_criteria_list.addItem(f"{criterion.name} — peso {criterion.weight:.2f} ({direction})")

    def _on_clear_mcda_criteria(self) -> None:
        self._mcda_criteria.clear()
        self._mcda_criteria_list.clear()

    def _on_run_mcda(self) -> None:
        if not self._mcda_criteria:
            QMessageBox.information(self, "Sem critérios", "Adicione ao menos um critério.")
            return

        try:
            result = mcda.run_weighted_linear_combination(self._mcda_criteria)
        except ValueError as exc:
            QMessageBox.warning(self, "Erro de validação", str(exc))
            return

        self._store.add_array("mcda_aptidao", result.suitability)
        self._refresh_layer_lists()
        self._result_preview = mcda.suitability_to_rgb_display(result.suitability)
        self._status_label.setText("MCDA concluído: nova camada 'mcda_aptidao' (0=baixa aptidão, 1=alta aptidão).")

    # ------------------------------------------------------------------
    # Aba: CA-Markov
    # ------------------------------------------------------------------
    def _build_markov_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)

        layout.addWidget(QLabel(
            "Carregue duas camadas de classificação categórica (uso do solo) "
            "em datas diferentes (T1 e T2) para calcular a matriz de transição, "
            "projetar quantidades futuras e simular a alocação espacial via "
            "autômatos celulares guiados por um mapa de aptidão (ex.: do MCDA)."
        ))

        from PySide6.QtWidgets import QComboBox
        form = QFormLayout()
        self._markov_t1_combo = QComboBox()
        self._markov_t2_combo = QComboBox()
        self._markov_suitability_combo = QComboBox()
        self._markov_steps_spin = QSpinBox()
        self._markov_steps_spin.setRange(1, 20)
        self._markov_steps_spin.setValue(1)
        form.addRow("Camada T1 (uso do solo, data inicial):", self._markov_t1_combo)
        form.addRow("Camada T2 (uso do solo, data final):", self._markov_t2_combo)
        form.addRow("Camada de aptidão (para alocação):", self._markov_suitability_combo)
        form.addRow("Nº de períodos a projetar:", self._markov_steps_spin)
        layout.addLayout(form)

        btn_compute_transition = QPushButton("1. Calcular matriz de transição e projetar quantidades")
        btn_compute_transition.clicked.connect(self._on_compute_transition)
        layout.addWidget(btn_compute_transition)

        self._transition_summary = QLabel("")
        self._transition_summary.setWordWrap(True)
        layout.addWidget(self._transition_summary)

        btn_run_simulation = QPushButton("2. Executar simulação CA-Markov -> nova camada")
        btn_run_simulation.clicked.connect(self._on_run_ca_markov)
        layout.addWidget(btn_run_simulation)

        self._transition: Optional[markov.TransitionMatrix] = None
        self._projected_quantities: Optional[dict[int, int]] = None

        def refresh_combo():
            for combo in (self._markov_t1_combo, self._markov_t2_combo, self._markov_suitability_combo):
                combo.clear()
                combo.addItems(self._store.names())

        self._combo_refreshers.append(refresh_combo)

        return widget

    def _on_compute_transition(self) -> None:
        t1_name = self._markov_t1_combo.currentText()
        t2_name = self._markov_t2_combo.currentText()
        if t1_name not in self._store.layers or t2_name not in self._store.layers:
            QMessageBox.information(self, "Camadas inválidas", "Selecione camadas T1 e T2 válidas.")
            return

        classes_t1 = self._store.layers[t1_name].astype(np.int32)
        classes_t2 = self._store.layers[t2_name].astype(np.int32)

        try:
            self._transition = markov.compute_transition_matrix(classes_t1, classes_t2)
            self._projected_quantities = markov.project_class_quantities(
                self._transition, n_steps=self._markov_steps_spin.value()
            )
        except Exception as exc:
            QMessageBox.critical(self, "Erro ao calcular transição", str(exc))
            return

        lines = ["Quantidades projetadas por classe:"]
        for cls, qty in self._projected_quantities.items():
            current = self._transition.pixel_counts_t2.get(cls, 0)
            delta = qty - current
            lines.append(f"  Classe {cls}: {current} -> {qty} ({'+' if delta >= 0 else ''}{delta})")
        self._transition_summary.setText("\n".join(lines))

    def _on_run_ca_markov(self) -> None:
        if self._transition is None or self._projected_quantities is None:
            QMessageBox.information(self, "Calcule a transição primeiro", "Execute o passo 1 antes de simular.")
            return

        t2_name = self._markov_t2_combo.currentText()
        suitability_name = self._markov_suitability_combo.currentText()

        if t2_name not in self._store.layers:
            QMessageBox.information(self, "Camada inválida", "Selecione a camada T2.")
            return

        current_classes = self._store.layers[t2_name].astype(np.int32)

        suitability_per_class = {}
        if suitability_name in self._store.layers:
            base_suitability = self._store.layers[suitability_name]
            for cls in self._projected_quantities.keys():
                suitability_per_class[cls] = base_suitability
        else:
            for cls in self._projected_quantities.keys():
                suitability_per_class[cls] = np.ones(current_classes.shape, dtype=np.float64) * 0.5

        try:
            simulated = markov.run_ca_markov_simulation(
                current_classes=current_classes,
                suitability_per_class=suitability_per_class,
                target_quantities=self._projected_quantities,
            )
        except Exception as exc:
            QMessageBox.critical(self, "Erro na simulação", str(exc))
            return

        new_name = f"{t2_name}_simulado"
        self._store.add_array(new_name, simulated.astype(np.float64))
        self._refresh_layer_lists()
        self._status_label.setText(f"Simulação CA-Markov concluída: nova camada '{new_name}'.")

    # ------------------------------------------------------------------
    def get_layer(self, name: str) -> Optional[np.ndarray]:
        return self._store.layers.get(name)

    def layer_names(self) -> list[str]:
        return self._store.names()