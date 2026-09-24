"""
Processamento em lote: aplica um preset/pipeline a várias imagens de uma vez.

Este é um arquivo NOVO desta fase. Crie-o em core/batch_processor.py.
"""
from __future__ import annotations

import logging
import traceback
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional

from core.raster_io import RasterReader
from core import exporter as exp

logger = logging.getLogger(__name__)


@dataclass
class BatchItemResult:
    input_path: Path
    output_path: Optional[Path] = None
    success: bool = False
    error_message: Optional[str] = None


@dataclass
class BatchResult:
    items: list[BatchItemResult] = field(default_factory=list)

    @property
    def success_count(self) -> int:
        return sum(1 for item in self.items if item.success)

    @property
    def failure_count(self) -> int:
        return sum(1 for item in self.items if not item.success)


ProgressCallback = Callable[[int, int, str], None]  # (current, total, current_filename)


def run_batch(
    input_paths: list[Path],
    output_dir: Path,
    build_corrector_fn: Callable[[object], Callable],
    band_composition: tuple[int, int, int],
    only_rgb: bool = False,
    progress_callback: Optional[ProgressCallback] = None,
    should_cancel: Optional[Callable[[], bool]] = None,
    generate_reports: bool = True,
) -> BatchResult:
    """Processa múltiplas imagens com o mesmo pipeline de correções.

    build_corrector_fn(handle) -> função (block, window) -> block_corrigido,
    permitindo que o pipeline de correções (definido na MainWindow) seja
    reaplicado a cada imagem do lote, sem depender da UI.
    """
    reader = RasterReader()
    result = BatchResult()
    output_dir.mkdir(parents=True, exist_ok=True)

    total = len(input_paths)
    for i, input_path in enumerate(input_paths):
        if should_cancel is not None and should_cancel():
            logger.info("Lote cancelado pelo usuário em %d/%d", i, total)
            break

        if progress_callback is not None:
            progress_callback(i + 1, total, input_path.name)

        item_result = BatchItemResult(input_path=input_path)
        try:
            handle = reader.open(str(input_path))
            output_path = output_dir / f"{input_path.stem}_corrigido{input_path.suffix}"

            corrector = build_corrector_fn(handle)
            options = exp.ExportOptions(
                output_path=output_path,
                file_format="GTiff",
                overwrite=True,
                only_rgb_composition=only_rgb,
                band_composition=band_composition if only_rgb else None,
            )
            exp.export_geotiff(handle, apply_corrections_fn=corrector, options=options)

            item_result.output_path = output_path
            item_result.success = True

            if generate_reports:
                report_path = output_path.with_suffix(".txt")
                exp.export_report(handle, operations_summary=["Pipeline em lote aplicado"], output_path=report_path)

        except Exception as exc:
            logger.error("Erro processando %s: %s", input_path, exc)
            logger.debug(traceback.format_exc())
            item_result.success = False
            item_result.error_message = str(exc)

        result.items.append(item_result)

    return result