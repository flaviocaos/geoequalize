"""
Validações reutilizáveis: formato de arquivo, integridade de raster,
permissões de escrita, etc.

Fase 9: adiciona exceções específicas e mensagens mais claras para os
principais cenários de erro do app (arquivo inválido, CRS ausente,
imagem muito grande, erro de permissão, etc.).
"""
from __future__ import annotations

import os
from pathlib import Path

SUPPORTED_EXTENSIONS = {".tif", ".tiff", ".jp2", ".jpg", ".jpeg", ".png"}

# Acima deste número de pixels totais (largura x altura), o app avisa o
# usuário que a imagem é grande e o preview pode demorar para gerar.
LARGE_IMAGE_PIXEL_THRESHOLD = 50_000_000  # ~50 megapixels


class InvalidRasterError(Exception):
    """Levantada quando o arquivo não é um raster válido ou está corrompido."""


class MissingCRSWarning(Warning):
    """Aviso (não bloqueia) quando o raster não tem CRS definido."""


class InsufficientBandsError(Exception):
    """Levantada quando uma operação exige mais bandas do que a imagem possui."""


def is_supported_raster(path: str) -> bool:
    return Path(path).suffix.lower() in SUPPORTED_EXTENSIONS


def validate_output_path(path: Path, overwrite: bool = False) -> None:
    """Levanta exceção se o arquivo de saída já existir e overwrite=False,
    ou se não houver permissão de escrita no diretório."""
    if path.exists() and not overwrite:
        raise FileExistsError(f"O arquivo de saída já existe: {path}")

    parent = path.parent
    if not parent.exists():
        raise FileNotFoundError(f"Diretório de saída não existe: {parent}")

    if not os.access(parent, os.W_OK):
        raise PermissionError(f"Sem permissão de escrita no diretório: {parent}")


def validate_band_count(available_bands: int, required_bands: int, operation_name: str = "") -> None:
    """Levanta InsufficientBandsError com mensagem clara se a imagem não
    tiver bandas suficientes para a operação solicitada."""
    if available_bands < required_bands:
        suffix = f" para {operation_name}" if operation_name else ""
        raise InsufficientBandsError(
            f"A operação{suffix} exige ao menos {required_bands} banda(s), "
            f"mas a imagem possui apenas {available_bands}."
        )


def check_image_size_warning(width: int, height: int) -> str | None:
    """Retorna uma mensagem de aviso se a imagem for muito grande, ou None
    se o tamanho for considerado normal."""
    total_pixels = width * height
    if total_pixels > LARGE_IMAGE_PIXEL_THRESHOLD:
        megapixels = total_pixels / 1_000_000
        return (
            f"Esta imagem é grande ({megapixels:.0f} megapixels). "
            "O preview pode demorar para carregar e a exportação em "
            "resolução total pode levar vários minutos."
        )
    return None


def friendly_error_message(exc: Exception) -> str:
    """Converte exceções comuns (incluindo as do rasterio/GDAL) em mensagens
    mais amigáveis para exibir ao usuário em QMessageBox."""
    exc_str = str(exc)
    exc_type = type(exc).__name__

    if isinstance(exc, FileNotFoundError):
        return f"Arquivo não encontrado:\n{exc_str}"

    if isinstance(exc, PermissionError):
        return f"Permissão negada. Verifique se você tem acesso de escrita à pasta:\n{exc_str}"

    if isinstance(exc, FileExistsError):
        return f"O arquivo de saída já existe:\n{exc_str}"

    if isinstance(exc, InsufficientBandsError):
        return str(exc)

    if isinstance(exc, MemoryError):
        return (
            "A imagem é muito grande para ser processada com a memória "
            "disponível. Tente reduzir o tamanho do preview nas configurações "
            "ou processe a imagem em um computador com mais memória RAM."
        )

    # Erros típicos do GDAL/rasterio costumam conter palavras-chave identificáveis
    lower = exc_str.lower()
    if "not recognized as a supported file format" in lower or "unable to open" in lower:
        return (
            f"O arquivo não pôde ser aberto. Ele pode estar corrompido, "
            f"ou não ser um formato raster válido suportado pelo GDAL.\n\nDetalhe técnico: {exc_str}"
        )
    if "no such file or directory" in lower:
        return f"Arquivo ou diretório não encontrado:\n{exc_str}"
    if "permission denied" in lower:
        return f"Permissão negada ao acessar o arquivo:\n{exc_str}"

    return f"Ocorreu um erro inesperado ({exc_type}):\n{exc_str}"