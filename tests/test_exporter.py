"""
Testes do módulo core.exporter: exportação GeoTIFF preservando metadados,
e validação de caminho de saída (overwrite).
"""
from pathlib import Path

import numpy as np
import pytest
import rasterio

from core.raster_io import RasterReader
from core import exporter as exp


def _identity_corrector(block: np.ndarray, window) -> np.ndarray:
    return block


def test_export_geotiff_preserves_crs_and_transform(sample_geotiff_path, tmp_path):
    reader = RasterReader()
    handle = reader.open(str(sample_geotiff_path))

    output_path = tmp_path / "output.tif"
    options = exp.ExportOptions(output_path=output_path, file_format="GTiff", overwrite=False)

    exp.export_geotiff(handle, apply_corrections_fn=_identity_corrector, options=options)

    assert output_path.exists()
    with rasterio.open(output_path) as src:
        assert src.crs is not None
        assert src.width == handle.width
        assert src.height == handle.height


def test_export_geotiff_raises_if_file_exists_without_overwrite(sample_geotiff_path, tmp_path):
    reader = RasterReader()
    handle = reader.open(str(sample_geotiff_path))

    output_path = tmp_path / "output.tif"
    output_path.write_text("conteudo qualquer")  # simula arquivo já existente

    options = exp.ExportOptions(output_path=output_path, file_format="GTiff", overwrite=False)

    with pytest.raises(FileExistsError):
        exp.export_geotiff(handle, apply_corrections_fn=_identity_corrector, options=options)


def test_export_geotiff_overwrite_true_succeeds(sample_geotiff_path, tmp_path):
    reader = RasterReader()
    handle = reader.open(str(sample_geotiff_path))

    output_path = tmp_path / "output.tif"
    output_path.write_text("conteudo antigo")

    options = exp.ExportOptions(output_path=output_path, file_format="GTiff", overwrite=True)
    exp.export_geotiff(handle, apply_corrections_fn=_identity_corrector, options=options)

    assert output_path.exists()
    with rasterio.open(output_path) as src:
        assert src.width == handle.width


def test_export_report_creates_readable_txt(sample_geotiff_path, tmp_path):
    reader = RasterReader()
    handle = reader.open(str(sample_geotiff_path))

    report_path = tmp_path / "report.txt"
    exp.export_report(handle, operations_summary=["Stretch linear", "Gray World"], output_path=report_path)

    assert report_path.exists()
    content = report_path.read_text(encoding="utf-8")
    assert "Stretch linear" in content
    assert "Gray World" in content
    assert handle.path.name in content