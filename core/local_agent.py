"""
Agente local de IA: responde perguntas sobre a imagem aberta e as
operações aplicadas, usando exclusivamente dados reais do app — sem
LLM externo, sem internet, sem custo, sem risco de "inventar" informação.

Funciona por reconhecimento de intenção simples (palavras-chave em
português e inglês) + templates de resposta preenchidos com os dados
reais (metadados, histórico, estatísticas). É um "agente" no sentido de
responder perguntas em linguagem natural sobre o estado do app, não um
modelo de linguagem treinado.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional, Callable

import numpy as np


@dataclass
class AgentContext:
    """Snapshot do estado atual do app, usado pelo agente para responder."""
    image_name: Optional[str] = None
    width: Optional[int] = None
    height: Optional[int] = None
    band_count: Optional[int] = None
    dtype: Optional[str] = None
    crs: Optional[str] = None
    nodata: Optional[float] = None
    driver: Optional[str] = None
    compression: Optional[str] = None
    band_composition: tuple[int, int, int] = (1, 1, 1)
    operation_labels: list[str] = field(default_factory=list)
    band_statistics: dict[int, dict] = field(default_factory=dict)  # {banda: stats dict}
    has_image: bool = False


# ----------------------------------------------------------------------
# Reconhecimento de intenção: cada intenção tem palavras-chave PT/EN e
# uma função que gera a resposta a partir do contexto.
# ----------------------------------------------------------------------
@dataclass
class Intent:
    name: str
    keywords: list[str]
    handler: Callable[[AgentContext], str]


def _no_image_response() -> str:
    return (
        "Nenhuma imagem está aberta no momento. Abra uma imagem em "
        "Arquivo → Abrir imagem... para que eu possa te ajudar.\n"
        "(No image is currently open. Open one via File → Open image... "
        "so I can help.)"
    )


def _handle_metadata(ctx: AgentContext) -> str:
    if not ctx.has_image:
        return _no_image_response()

    lines = [
        f"A imagem aberta é '{ctx.image_name}', com {ctx.width}x{ctx.height} pixels e {ctx.band_count} banda(s).",
        f"Tipo de dado: {ctx.dtype}.",
    ]
    if ctx.crs:
        lines.append(f"Sistema de referência (CRS): {ctx.crs}.")
    else:
        lines.append("Esta imagem não possui CRS definido (não está georreferenciada).")

    if ctx.nodata is not None:
        lines.append(f"Valor de NoData: {ctx.nodata}.")

    if ctx.driver:
        lines.append(f"Formato/driver: {ctx.driver}" + (f", compressão: {ctx.compression}." if ctx.compression else "."))

    return "\n".join(lines)


def _handle_operations(ctx: AgentContext) -> str:
    if not ctx.has_image:
        return _no_image_response()

    if not ctx.operation_labels:
        return "Nenhuma correção foi aplicada a esta imagem ainda."

    lines = [f"Foram aplicadas {len(ctx.operation_labels)} operação(ões), nesta ordem:"]
    for i, label in enumerate(ctx.operation_labels, start=1):
        lines.append(f"  {i}. {label}")
    return "\n".join(lines)


def _handle_statistics(ctx: AgentContext) -> str:
    if not ctx.has_image:
        return _no_image_response()

    if not ctx.band_statistics:
        return (
            "Ainda não há estatísticas calculadas. Selecione uma banda no "
            "painel 'Bandas' para que eu possa te dizer mínimo, máximo, "
            "média e desvio padrão."
        )

    lines = ["Estatísticas das bandas consultadas:"]
    for band_idx, stats in sorted(ctx.band_statistics.items()):
        if stats.get("min") is None:
            lines.append(f"  Banda {band_idx}: sem dados válidos.")
            continue
        lines.append(
            f"  Banda {band_idx}: min={stats['min']:.1f}, max={stats['max']:.1f}, "
            f"média={stats['mean']:.1f}, desvio padrão={stats['std']:.1f}"
        )
    return "\n".join(lines)


def _handle_composition(ctx: AgentContext) -> str:
    if not ctx.has_image:
        return _no_image_response()
    r, g, b = ctx.band_composition
    return f"A composição RGB exibida atualmente usa: banda {r} no vermelho, banda {g} no verde e banda {b} no azul."


def _handle_summary(ctx: AgentContext) -> str:
    if not ctx.has_image:
        return _no_image_response()

    parts = [_handle_metadata(ctx), "", _handle_operations(ctx)]
    return "\n".join(parts)


def _handle_help(_ctx: AgentContext) -> str:
    return (
        "Posso te ajudar com perguntas sobre:\n"
        "  • Metadados da imagem (dimensões, CRS, bandas, tipo de dado)\n"
        "  • Operações/correções já aplicadas\n"
        "  • Estatísticas de uma banda (se você já a selecionou no painel Bandas)\n"
        "  • Composição RGB atual\n"
        "  • Um resumo geral\n\n"
        "Exemplos: 'quais correções foram feitas?', 'qual o CRS da imagem?', "
        "'me dá um resumo'."
    )


def _handle_greeting(_ctx: AgentContext) -> str:
    return "Olá! Sou o assistente do GeoEqualize. Pergunte sobre a imagem aberta ou as correções já aplicadas."


INTENTS: list[Intent] = [
    Intent("greeting", ["olá", "oi", "hello", "hi"], _handle_greeting),
    Intent("help", ["ajuda", "help", "o que você faz", "what can you do"], _handle_help),
    Intent(
        "metadata",
        ["metadado", "metadata", "crs", "dimensão", "dimension", "tamanho", "size",
         "resolução", "resolution", "tipo de dado", "data type", "nodata"],
        _handle_metadata,
    ),
    Intent(
        "operations",
        ["correção", "correções", "correction", "corrections", "operação", "operações",
         "operation", "operations", "histórico", "history", "o que foi feito", "what was done"],
        _handle_operations,
    ),
    Intent(
        "statistics",
        ["estatística", "statistics", "média", "mean", "desvio", "deviation",
         "mínimo", "minimum", "máximo", "maximum", "histograma", "histogram"],
        _handle_statistics,
    ),
    Intent(
        "composition",
        ["composição", "composition", "rgb", "banda r", "banda g", "banda b"],
        _handle_composition,
    ),
    Intent(
        "summary",
        ["resumo", "summary", "resumir", "summarize", "me conta", "tell me about"],
        _handle_summary,
    ),
]


def _match_intent(message: str) -> Optional[Intent]:
    """Encontra a primeira intenção cujas palavras-chave aparecem na mensagem."""
    lower = message.lower()
    for intent in INTENTS:
        for keyword in intent.keywords:
            if keyword in lower:
                return intent
    return None


def respond(message: str, context: AgentContext) -> str:
    """Gera uma resposta para `message`, usando apenas dados reais de `context`.

    Se nenhuma intenção for reconhecida, retorna uma resposta de fallback
    sugerindo o comando de ajuda.
    """
    if not message.strip():
        return _handle_help(context)

    intent = _match_intent(message)
    if intent is None:
        return (
            "Não entendi exatamente sua pergunta. Digite 'ajuda' para ver "
            "o que posso responder sobre a imagem atual."
        )

    return intent.handler(context)