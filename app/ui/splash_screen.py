"""
Tela de boas-vindas (splash/welcome screen) do GeoEqualize.

Exibida ao abrir o aplicativo, antes da janela principal. Mostra o logo,
o nome do produto, e abas descrevendo as funcionalidades disponíveis
(inspirada nas telas de apresentação de ENVI, ERDAS Imagine e IDRISI).

Este é um arquivo NOVO. Crie-o em app/ui/splash_screen.py.
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
    QTabWidget,
    QWidget,
    QTextBrowser,
    QCheckBox,
)
from PySide6.QtGui import QPixmap, QFont
from PySide6.QtCore import Qt, QByteArray
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtGui import QPainter, QImage

LOGO_SVG = b"""<svg viewBox="0 0 400 400" xmlns="http://www.w3.org/2000/svg">
  <defs>
    <linearGradient id="globeGrad" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="#1e3a5f"/>
      <stop offset="100%" stop-color="#0f1f33"/>
    </linearGradient>
    <linearGradient id="barGrad" x1="0%" y1="100%" x2="0%" y2="0%">
      <stop offset="0%" stop-color="#2dd4bf"/>
      <stop offset="100%" stop-color="#22c55e"/>
    </linearGradient>
    <linearGradient id="arrowGrad" x1="0%" y1="0%" x2="100%" y2="0%">
      <stop offset="0%" stop-color="#fbbf24"/>
      <stop offset="100%" stop-color="#f97316"/>
    </linearGradient>
  </defs>
  <circle cx="200" cy="200" r="150" fill="url(#globeGrad)" stroke="#0a1622" stroke-width="3"/>
  <ellipse cx="200" cy="200" rx="60" ry="150" fill="none" stroke="#3b82f6" stroke-width="2.5" opacity="0.55"/>
  <ellipse cx="200" cy="200" rx="110" ry="150" fill="none" stroke="#3b82f6" stroke-width="2.5" opacity="0.4"/>
  <ellipse cx="200" cy="200" rx="150" ry="150" fill="none" stroke="#3b82f6" stroke-width="2.5" opacity="0.25"/>
  <ellipse cx="200" cy="200" rx="150" ry="40" fill="none" stroke="#3b82f6" stroke-width="2.5" opacity="0.55"/>
  <ellipse cx="200" cy="200" rx="150" ry="90" fill="none" stroke="#3b82f6" stroke-width="2.5" opacity="0.4"/>
  <line x1="50" y1="200" x2="350" y2="200" stroke="#3b82f6" stroke-width="2.5" opacity="0.6"/>
  <clipPath id="globeClip"><circle cx="200" cy="200" r="150"/></clipPath>
  <g clip-path="url(#globeClip)">
    <rect x="120" y="240" width="14" height="60" fill="url(#barGrad)" opacity="0.9"/>
    <rect x="140" y="210" width="14" height="90" fill="url(#barGrad)" opacity="0.9"/>
    <rect x="160" y="180" width="14" height="120" fill="url(#barGrad)" opacity="0.9"/>
    <rect x="180" y="150" width="14" height="150" fill="url(#barGrad)" opacity="0.95"/>
    <rect x="200" y="165" width="14" height="135" fill="url(#barGrad)" opacity="0.95"/>
    <rect x="220" y="195" width="14" height="105" fill="url(#barGrad)" opacity="0.9"/>
    <rect x="240" y="225" width="14" height="75" fill="url(#barGrad)" opacity="0.9"/>
    <rect x="260" y="255" width="14" height="45" fill="url(#barGrad)" opacity="0.85"/>
  </g>
  <circle cx="200" cy="200" r="150" fill="none" stroke="#2dd4bf" stroke-width="5"/>
  <circle cx="200" cy="200" r="165" fill="none" stroke="#2dd4bf" stroke-width="2" opacity="0.4"/>
  <path d="M 90 290 Q 150 290 175 230 Q 200 165 240 140 Q 280 120 320 110"
        fill="none" stroke="url(#arrowGrad)" stroke-width="9" stroke-linecap="round"/>
  <path d="M 320 110 L 300 100 M 320 110 L 308 130"
        fill="none" stroke="url(#arrowGrad)" stroke-width="9" stroke-linecap="round" stroke-linejoin="round"/>
  <circle cx="175" cy="230" r="7" fill="#ffffff" stroke="#f97316" stroke-width="3"/>
  <circle cx="240" cy="140" r="7" fill="#ffffff" stroke="#f97316" stroke-width="3"/>
</svg>"""


def render_logo_pixmap(size: int = 140) -> QPixmap:
    """Renderiza o logo SVG embutido em um QPixmap quadrado, com fundo transparente."""
    renderer = QSvgRenderer(QByteArray(LOGO_SVG))
    image = QImage(size, size, QImage.Format_ARGB32)
    image.fill(Qt.transparent)
    painter = QPainter(image)
    renderer.render(painter)
    painter.end()
    return QPixmap.fromImage(image)


_OVERVIEW_HTML = """
<h2 style="color:#0f1f33;">GeoEqualize</h2>
<p style="font-size:13px; color:#333;">
Plataforma de Processamento Digital de Imagens (PDI) e Geoprocessamento
para imagens de satélite, drones e ortofotos.
</p>
<p style="font-size:13px; color:#333;">
Combina, em uma única ferramenta:
</p>
<ul style="font-size:13px; color:#333;">
  <li><b>Correção visual e radiométrica</b> — histograma, balanceamento de
  cor, filtros e harmonização de ortomosaicos.</li>
  <li><b>Sensoriamento remoto</b> — índices espectrais (NDVI, NDWI, SAVI...),
  calculadora de bandas e perfis espectrais.</li>
  <li><b>Geoprocessamento e modelagem</b> — álgebra de mapas, análise
  multicritério (MCDA) e simulação de cenários (CA-Markov).</li>
</ul>
<p style="font-size:12px; color:#666;">
Inspirado em fluxos de trabalho de ferramentas como ENVI, ERDAS Imagine e
IDRISI, com uma interface mais simples e direta.
</p>
"""

_PDI_HTML = """
<h3 style="color:#0f1f33;">Processamento Digital de Imagens</h3>
<ul style="font-size:13px; color:#333;">
  <li>Stretch linear, por percentil, por desvio padrão, equalização, CLAHE</li>
  <li>Ajuste de gamma, brilho e contraste</li>
  <li>Balanceamento de branco (Gray World, White Patch, ponto de referência)</li>
  <li>Correção de canais RGB, temperatura, matiz e saturação</li>
  <li>Correções locais com seleção retangular/poligonal e feather de borda</li>
  <li>Sharpening, unsharp mask, redução de ruído, redução de haze</li>
  <li>Harmonização de ortomosaicos e matching de histograma</li>
</ul>
"""

_REMOTE_SENSING_HTML = """
<h3 style="color:#0f1f33;">Sensoriamento Remoto</h3>
<ul style="font-size:13px; color:#333;">
  <li>Índices espectrais: NDVI, NDWI, SAVI, EVI e outros</li>
  <li>Calculadora de bandas (band math) com expressões customizadas</li>
  <li>Perfis espectrais por pixel</li>
  <li>Composições falsa-cor e presets por sensor</li>
  <li>Estatísticas avançadas por banda</li>
</ul>
<p style="font-size:12px; color:#666;">Em expansão contínua.</p>
"""

_GEOPROCESSING_HTML = """
<h3 style="color:#0f1f33;">Geoprocessamento e Modelagem</h3>
<ul style="font-size:13px; color:#333;">
  <li>Álgebra de mapas e reclassificação</li>
  <li>Análise multicritério (MCDA) — combinação ponderada de camadas</li>
  <li>Cadeias de Markov e autômatos celulares (CA-Markov)</li>
  <li>Simulação de cenários futuros (mudança de uso do solo, desmatamento)</li>
</ul>
<p style="font-size:12px; color:#666;">Módulo em desenvolvimento.</p>
"""


class SplashScreen(QDialog):
    """Tela de boas-vindas exibida ao iniciar o GeoEqualize."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("GeoEqualize")
        self.setMinimumSize(720, 560)
        self.setModal(True)

        self._skip_next_time = False

        layout = QVBoxLayout(self)

        header_layout = QHBoxLayout()
        logo_label = QLabel()
        logo_label.setPixmap(render_logo_pixmap(96))
        header_layout.addWidget(logo_label)

        title_layout = QVBoxLayout()
        title_label = QLabel("GeoEqualize")
        title_font = QFont()
        title_font.setPointSize(26)
        title_font.setBold(True)
        title_label.setFont(title_font)

        subtitle_label = QLabel("PDI, Sensoriamento Remoto e Geoprocessamento Raster")
        subtitle_font = QFont()
        subtitle_font.setPointSize(11)
        subtitle_label.setFont(subtitle_font)
        subtitle_label.setStyleSheet("color: #555;")

        title_layout.addWidget(title_label)
        title_layout.addWidget(subtitle_label)
        title_layout.addStretch()

        header_layout.addLayout(title_layout)
        header_layout.addStretch()
        layout.addLayout(header_layout)

        tabs = QTabWidget()
        tabs.addTab(self._make_tab(_OVERVIEW_HTML), "Visão geral")
        tabs.addTab(self._make_tab(_PDI_HTML), "PDI")
        tabs.addTab(self._make_tab(_REMOTE_SENSING_HTML), "Sensoriamento Remoto")
        tabs.addTab(self._make_tab(_GEOPROCESSING_HTML), "Geoprocessamento")
        layout.addWidget(tabs)

        bottom_layout = QHBoxLayout()
        self._skip_checkbox = QCheckBox("Não mostrar esta tela novamente")
        self._skip_checkbox.toggled.connect(self._on_skip_toggled)
        bottom_layout.addWidget(self._skip_checkbox)
        bottom_layout.addStretch()

        self._btn_start = QPushButton("Começar")
        self._btn_start.setMinimumWidth(140)
        self._btn_start.clicked.connect(self.accept)
        bottom_layout.addWidget(self._btn_start)

        layout.addLayout(bottom_layout)

        self.setLayout(layout)

    @staticmethod
    def _make_tab(html: str) -> QWidget:
        browser = QTextBrowser()
        browser.setHtml(html)
        browser.setOpenExternalLinks(True)
        browser.setStyleSheet("border: none;")
        return browser

    def _on_skip_toggled(self, checked: bool) -> None:
        self._skip_next_time = checked

    def should_skip_next_time(self) -> bool:
        return self._skip_next_time