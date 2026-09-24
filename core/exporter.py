"""
Exportação de resultados processados.

Responsabilidade:
- Aplicar o histórico de correções em resolução total (não no preview)
- Escrever GeoTIFF/TIFF/PNG/JPEG preservando CRS, transform, NoData e metadados
- Suportar leitura/escrita em blocos para arquivos grandes
- Gerar relatório de processamento (TXT)
- Validar permissões e evitar sobrescrever arquivos sem confirmação
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Callable, Optional

import numpy as np
import rasterio
from rasterio.windows import Window

from core.raster_io import RasterHandle
from utils.validators import validate_output_path

logger = logging.getLogger(__name__)

# Tamanho de bloco padrão para leitura/escrita (em pixels), usado quando o
# arquivo é grande e processado por janelas em vez de carregado inteiro.
DEFAULT_BLOCK_SIZE = 1024


@dataclass
class ExportOptions:
    output_path: Path
    file_format: str = "GTiff"  # 'GTiff' | 'PNG' | 'JPEG'
    overwrite: bool = False
    only_rgb_composition: bool = False  # se True, exporta só as 3 bandas compostas
    band_composition: Optional[tuple[int, int, int]] = None  # 1-based, usado se only_rgb_composition


@dataclass
class ExportProgress:
    current_block: int
    total_blocks: int
    cancelled: bool = False


ProgressCallback = Callable[[ExportProgress], None]


class ExportCancelled(Exception):
    """Levantada internamente quando o usuário cancela a exportação."""


def _iter_blocks(width: int, height: int, block_size: int = DEFAULT_BLOCK_SIZE):
    """Gera janelas (Window) cobrindo todo o raster em blocos quadrados."""
    for row_off in range(0, height, block_size):
        row_size = min(block_size, height - row_off)
        for col_off in range(0, width, block_size):
            col_size = min(block_size, width - col_off)
            yield Window(col_off=col_off, row_off=row_off, width=col_size, height=row_size)


def export_geotiff(
    handle: RasterHandle,
    apply_corrections_fn: Callable[[np.ndarray, Window], np.ndarray],
    options: ExportOptions,
    progress_callback: Optional[ProgressCallback] = None,
    should_cancel: Optional[Callable[[], bool]] = None,
) -> None:
    """Exporta o raster em resolução total, aplicando `apply_corrections_fn`
    bloco a bloco, preservando georreferenciamento e NoData.

    apply_corrections_fn(block_array, window) -> block_array corrigido
    block_array tem shape (bands, h, w) já recortado pela janela.
    """
    validate_output_path(options.output_path, overwrite=options.overwrite)

    with rasterio.open(handle.path) as src:
        profile = src.profile.copy()

        band_indexes = list(range(1, src.count + 1))
        if options.only_rgb_composition and options.band_composition:
            band_indexes = list(options.band_composition)
            profile.update(count=3)

        profile.update(driver=options.file_format)

        blocks = list(_iter_blocks(src.width, src.height))
        total_blocks = len(blocks)

        options.output_path.parent.mkdir(parents=True, exist_ok=True)

        with rasterio.open(options.output_path, "w", **profile) as dst:
            for i, window in enumerate(blocks):
                if should_cancel is not None and should_cancel():
                    logger.info("Exportação cancelada pelo usuário no bloco %d/%d", i + 1, total_blocks)
                    raise ExportCancelled()

                block = src.read(indexes=band_indexes, window=window)
                corrected_block = apply_corrections_fn(block.astype(np.float64), window)

                out_dtype = profile["dtype"]
                corrected_block = _cast_preserving_nodata(corrected_block, src.nodata, out_dtype)

                dst.write(corrected_block, window=window)

                if progress_callback is not None:
                    progress_callback(ExportProgress(current_block=i + 1, total_blocks=total_blocks))

    logger.info("Exportação concluída: %s", options.output_path)


def _cast_preserving_nodata(block: np.ndarray, nodata: Optional[float], target_dtype: str) -> np.ndarray:
    """Converte o bloco para o dtype de saída, preservando os pixels NoData exatamente."""
    if nodata is not None:
        nodata_mask = np.any(block == nodata, axis=0) if block.ndim == 3 else (block == nodata)

    np_dtype = np.dtype(target_dtype)
    if np.issubdtype(np_dtype, np.integer):
        info = np.iinfo(np_dtype)
        clipped = np.clip(block, info.min, info.max)
        result = clipped.astype(np_dtype)
    else:
        result = block.astype(np_dtype)

    if nodata is not None:
        if result.ndim == 3:
            for b in range(result.shape[0]):
                result[b][nodata_mask] = nodata
        else:
            result[nodata_mask] = nodata

    return result


def export_report(
    handle: RasterHandle,
    operations_summary: list[str],
    output_path: Path,
    extra_info: Optional[dict] = None,
) -> None:
    """Exporta um relatório TXT simples descrevendo o processamento realizado."""
    output_path.parent.mkdir(parents=True, exist_ok=True)

    lines = [
        "=" * 60,
        "RELATÓRIO DE PROCESSAMENTO — Satellite Image Corrector",
        "=" * 60,
        f"Data do processamento: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "",
        "--- Arquivo original ---",
        f"Nome: {handle.path.name}",
        f"Caminho: {handle.path}",
        f"Dimensões: {handle.width} x {handle.height} px",
        f"Bandas: {handle.band_count}",
        f"Tipo de dado: {handle.dtype}",
        f"CRS: {handle.crs or 'Ausente'}",
        f"NoData: {handle.nodata if handle.nodata is not None else 'Ausente'}",
        f"Driver: {handle.driver}",
        f"Compressão: {handle.compression or 'Nenhuma'}",
        "",
        "--- Correções aplicadas (em ordem) ---",
    ]

    if operations_summary:
        for i, summary in enumerate(operations_summary, start=1):
            lines.append(f"{i}. {summary}")
    else:
        lines.append("Nenhuma correção aplicada.")

    if extra_info:
        lines.append("")
        lines.append("--- Informações adicionais ---")
        for key, value in extra_info.items():
            lines.append(f"{key}: {value}")

    lines.append("")
    lines.append("=" * 60)

    output_path.write_text("\n".join(lines), encoding="utf-8")
    logger.info("Relatório exportado: %s", output_path)