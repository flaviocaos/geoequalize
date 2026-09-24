"""
Índices espectrais e calculadora de bandas (band math).

Responsabilidade:
- Calcular índices de vegetação/água clássicos (NDVI, NDWI, SAVI, EVI, etc.)
- Avaliar expressões customizadas de álgebra de bandas (ex.: "(B4-B3)/(B4+B3)")
- Gerar visualização colorida (colormap) para o resultado de um índice

Convenção de nomenclatura de bandas na calculadora: B1, B2, B3, ... (1-based,
na ordem em que aparecem no arquivo). O usuário escolhe manualmente qual
banda corresponde a qual região espectral (vermelho, NIR, etc.), já que
isso varia por sensor.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional

import numpy as np


def _safe_divide(numerator: np.ndarray, denominator: np.ndarray) -> np.ndarray:
    """Divisão que evita erros de divisão por zero, retornando NaN nesses casos."""
    with np.errstate(divide="ignore", invalid="ignore"):
        result = np.where(denominator != 0, numerator / denominator, np.nan)
    return result


@dataclass
class IndexDefinition:
    key: str
    label: str
    description: str
    required_bands: list[str]  # nomes lógicos, ex.: ["red", "nir"]
    value_range: tuple[float, float]  # faixa típica de valores, p/ colormap


INDEX_DEFINITIONS: dict[str, IndexDefinition] = {
    "ndvi": IndexDefinition(
        key="ndvi", label="NDVI (vegetação)",
        description="Índice de Vegetação por Diferença Normalizada. "
                     "Realça vegetação saudável (valores altos) vs solo/água (valores baixos).",
        required_bands=["red", "nir"], value_range=(-1.0, 1.0),
    ),
    "ndwi": IndexDefinition(
        key="ndwi", label="NDWI (água)",
        description="Índice de Água por Diferença Normalizada. "
                     "Realça corpos de água (valores altos).",
        required_bands=["green", "nir"], value_range=(-1.0, 1.0),
    ),
    "savi": IndexDefinition(
        key="savi", label="SAVI (vegetação ajustado ao solo)",
        description="Soil Adjusted Vegetation Index. Como o NDVI, mas reduz "
                     "a influência do solo exposto em áreas de vegetação esparsa.",
        required_bands=["red", "nir"], value_range=(-1.0, 1.0),
    ),
    "evi": IndexDefinition(
        key="evi", label="EVI (vegetação melhorado)",
        description="Enhanced Vegetation Index. Reduz influências atmosféricas "
                     "e de solo, útil em áreas de vegetação densa.",
        required_bands=["blue", "red", "nir"], value_range=(-1.0, 1.0),
    ),
    "ndbi": IndexDefinition(
        key="ndbi", label="NDBI (área construída)",
        description="Índice de Área Construída por Diferença Normalizada. "
                     "Realça áreas urbanas/construídas.",
        required_bands=["nir", "swir"], value_range=(-1.0, 1.0),
    ),
    "gndvi": IndexDefinition(
        key="gndvi", label="GNDVI (vegetação, banda verde)",
        description="Variante do NDVI usando a banda verde em vez da vermelha; "
                     "sensível à clorofila e ao estresse de nitrogênio.",
        required_bands=["green", "nir"], value_range=(-1.0, 1.0),
    ),
}


def compute_ndvi(red: np.ndarray, nir: np.ndarray) -> np.ndarray:
    return _safe_divide(nir - red, nir + red)


def compute_ndwi(green: np.ndarray, nir: np.ndarray) -> np.ndarray:
    return _safe_divide(green - nir, green + nir)


def compute_savi(red: np.ndarray, nir: np.ndarray, L: float = 0.5) -> np.ndarray:
    return _safe_divide((nir - red) * (1 + L), nir + red + L)


def compute_evi(blue: np.ndarray, red: np.ndarray, nir: np.ndarray) -> np.ndarray:
    numerator = nir - red
    denominator = nir + 6.0 * red - 7.5 * blue + 1.0
    return _safe_divide(2.5 * numerator, denominator)


def compute_ndbi(nir: np.ndarray, swir: np.ndarray) -> np.ndarray:
    return _safe_divide(swir - nir, swir + nir)


def compute_gndvi(green: np.ndarray, nir: np.ndarray) -> np.ndarray:
    return _safe_divide(nir - green, nir + green)


_INDEX_FUNCS = {
    "ndvi": lambda bands: compute_ndvi(bands["red"], bands["nir"]),
    "ndwi": lambda bands: compute_ndwi(bands["green"], bands["nir"]),
    "savi": lambda bands: compute_savi(bands["red"], bands["nir"]),
    "evi": lambda bands: compute_evi(bands["blue"], bands["red"], bands["nir"]),
    "ndbi": lambda bands: compute_ndbi(bands["nir"], bands["swir"]),
    "gndvi": lambda bands: compute_gndvi(bands["green"], bands["nir"]),
}


def compute_index(index_key: str, band_assignment: dict[str, np.ndarray]) -> np.ndarray:
    """Calcula um índice pré-definido.

    band_assignment: dict mapeando nome lógico (ex. "red", "nir") para o
    array 2D da banda correspondente, já escolhido pelo usuário.
    """
    if index_key not in INDEX_DEFINITIONS:
        raise ValueError(f"Índice desconhecido: {index_key}")

    definition = INDEX_DEFINITIONS[index_key]
    missing = [b for b in definition.required_bands if b not in band_assignment]
    if missing:
        raise ValueError(f"Bandas faltando para {definition.label}: {missing}")

    func = _INDEX_FUNCS[index_key]
    return func(band_assignment).astype(np.float64)


# ----------------------------------------------------------------------
# Calculadora de bandas (band math) — expressões customizadas
# ----------------------------------------------------------------------
_ALLOWED_NAMES = {"np": np, "abs": abs, "min": min, "max": max}
_BAND_TOKEN_PATTERN = re.compile(r"\bB(\d+)\b")


class BandMathError(Exception):
    """Erro ao validar ou avaliar uma expressão de álgebra de bandas."""


def validate_band_math_expression(expression: str, band_count: int) -> list[int]:
    """Verifica se a expressão só referencia tokens Bn válidos (1 <= n <= band_count)
    e não contém nada fora da lista de caracteres/nomes permitidos.
    Retorna a lista de índices de banda (1-based) usados na expressão.
    """
    if not expression.strip():
        raise BandMathError("Expressão vazia.")

    tokens = [int(m.group(1)) for m in _BAND_TOKEN_PATTERN.finditer(expression)]
    if not tokens:
        raise BandMathError("Nenhuma banda (ex.: B1, B2...) referenciada na expressão.")

    invalid = [t for t in tokens if not (1 <= t <= band_count)]
    if invalid:
        raise BandMathError(f"Índice(s) de banda fora do intervalo (1-{band_count}): {invalid}")

    # Caracteres permitidos: letras/dígitos (para Bn, np., funções), operadores
    # aritméticos básicos, parênteses, ponto, vírgula e espaços.
    allowed_pattern = re.compile(r"^[\w\s\.\,\+\-\*\/\(\)<>=!]+$")
    if not allowed_pattern.match(expression):
        raise BandMathError("A expressão contém caracteres não permitidos.")

    return sorted(set(tokens))


def evaluate_band_math(expression: str, image: np.ndarray) -> np.ndarray:
    """Avalia uma expressão de álgebra de bandas sobre `image` (shape bands,H,W).

    A expressão usa tokens B1, B2, ... (1-based) para referenciar bandas.
    Exemplo: "(B4 - B3) / (B4 + B3)" calcula um NDVI genérico se B4=NIR, B3=Red.

    Por segurança, a expressão é validada antes de ser avaliada com eval(),
    restringindo o namespace disponível e os caracteres permitidos.
    """
    band_count = image.shape[0]
    used_bands = validate_band_math_expression(expression, band_count)

    namespace = dict(_ALLOWED_NAMES)
    python_expr = expression
    for band_index in used_bands:
        token = f"B{band_index}"
        var_name = f"_band_{band_index}"
        python_expr = re.sub(rf"\b{token}\b", var_name, python_expr)
        namespace[var_name] = image[band_index - 1].astype(np.float64)

    try:
        with np.errstate(divide="ignore", invalid="ignore"):
            result = eval(python_expr, {"__builtins__": {}}, namespace)  # noqa: S307
    except Exception as exc:
        raise BandMathError(f"Erro ao avaliar a expressão: {exc}") from exc

    if not isinstance(result, np.ndarray):
        raise BandMathError("A expressão não retornou um array válido (verifique se referencia bandas).")

    return result.astype(np.float64)


# ----------------------------------------------------------------------
# Colormap para visualização de índices (verde-amarelo-vermelho, tipo NDVI)
# ----------------------------------------------------------------------
def index_to_rgb_display(
    index_array: np.ndarray,
    value_range: tuple[float, float] = (-1.0, 1.0),
    nodata_mask: Optional[np.ndarray] = None,
) -> np.ndarray:
    """Converte um array de índice (ex.: NDVI) em uma imagem RGB (3, H, W) para
    visualização, usando uma rampa de cores marrom -> amarelo -> verde escuro
    (convenção comum para índices de vegetação)."""
    vmin, vmax = value_range
    normalized = np.clip((index_array - vmin) / (vmax - vmin), 0, 1)
    normalized = np.nan_to_num(normalized, nan=0.0)

    # Rampa de cores simples por interpolação em 3 pontos:
    # 0.0 -> marrom (solo), 0.5 -> amarelo, 1.0 -> verde escuro (vegetação densa)
    stops = np.array([0.0, 0.5, 1.0])
    colors = np.array([
        [120, 80, 40],   # marrom
        [230, 220, 80],  # amarelo
        [20, 110, 40],   # verde escuro
    ], dtype=np.float64)

    r = np.interp(normalized, stops, colors[:, 0])
    g = np.interp(normalized, stops, colors[:, 1])
    b = np.interp(normalized, stops, colors[:, 2])

    rgb = np.stack([r, g, b], axis=0)

    if nodata_mask is not None:
        for c in range(3):
            rgb[c] = np.where(nodata_mask, 0, rgb[c])

    return rgb