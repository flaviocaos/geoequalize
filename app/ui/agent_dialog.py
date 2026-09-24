"""
Diálogo do Agente Local: interface tipo chat para consultar informações
sobre a imagem aberta e as operações aplicadas, usando core.local_agent.

Este é um arquivo NOVO. Crie-o em app/ui/agent_dialog.py.
"""
from __future__ import annotations

from typing import Optional

from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QTextEdit,
    QLineEdit,
    QPushButton,
    QLabel,
)
from PySide6.QtCore import Qt

from core.local_agent import AgentContext, respond


class AgentDialog(QDialog):
    """Janela de chat simples com o agente local (offline, baseado em dados reais)."""

    def __init__(self, get_context_fn, parent=None) -> None:
        """
        get_context_fn: função sem argumentos que retorna um AgentContext
        atualizado com o estado atual do app (chamada a cada mensagem,
        para sempre refletir o estado mais recente).
        """
        super().__init__(parent)
        self.setWindowTitle("Assistente GeoEqualize")
        self.setMinimumSize(480, 560)
        self._get_context_fn = get_context_fn

        layout = QVBoxLayout(self)

        layout.addWidget(QLabel(
            "<b>Assistente local</b> — responde apenas com dados reais desta "
            "sessão (sem internet, sem custo)."
        ))

        self._chat_view = QTextEdit()
        self._chat_view.setReadOnly(True)
        layout.addWidget(self._chat_view)

        input_layout = QHBoxLayout()
        self._input_edit = QLineEdit()
        self._input_edit.setPlaceholderText("Pergunte sobre a imagem ou as correções...")
        self._input_edit.returnPressed.connect(self._on_send_clicked)
        self._btn_send = QPushButton("Enviar")
        self._btn_send.clicked.connect(self._on_send_clicked)
        input_layout.addWidget(self._input_edit)
        input_layout.addWidget(self._btn_send)
        layout.addLayout(input_layout)

        self.setLayout(layout)

        self._append_agent_message(
            "Olá! Pergunte sobre a imagem aberta, as correções aplicadas, "
            "estatísticas de bandas, ou digite 'ajuda' para ver exemplos."
        )

    def _append_user_message(self, text: str) -> None:
        self._chat_view.append(f"<p style='color:#1e3a5f;'><b>Você:</b> {text}</p>")

    def _append_agent_message(self, text: str) -> None:
        formatted = text.replace("\n", "<br>")
        self._chat_view.append(f"<p style='color:#0f1f33;'><b>Assistente:</b> {formatted}</p>")

    def _on_send_clicked(self) -> None:
        message = self._input_edit.text().strip()
        if not message:
            return

        self._append_user_message(message)
        self._input_edit.clear()

        context: AgentContext = self._get_context_fn()
        reply = respond(message, context)
        self._append_agent_message(reply)