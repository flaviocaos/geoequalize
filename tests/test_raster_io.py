"""
Testes do módulo core.raster_io: abertura de GeoTIFF e leitura de metadados.
"""
import numpy as np
import pytest

from core.raster_io import RasterReader


def test_raster_reader_instantiates():
    reader = RasterReader()
    assert reader is not None


def test_open_geotiff_reads_basic_metadata(sample_geotiff_path):
    reader = RasterReader()
    handle = reader.open(str(sample_geotiff_path))

    assert handle.width == 64
    assert handle.height == 64
    assert handle.band_count == 3
    assert handle.dtype == "uint8"


def test_open_geotiff_preserves_crs(sample_geotiff_path):
    reader = RasterReader()
    handle = reader.open(str(sample_geotiff_path))
    assert handle.crs is not None
    assert "32723" in handle.crs


def test_open_geotiff_preserves_transform(sample_geotiff_path):
    reader = RasterReader()
    handle = reader.open(str(sample_geotiff_path))
    assert handle.transform is not None
    assert len(handle.transform) == 6
    # pixel size em x deve ser 10 (definido na fixture)
    assert abs(handle.transform[0] - 10) < 1e-6


def test_open_geotiff_preserves_nodata(sample_geotiff_path):
    reader = RasterReader()
    handle = reader.open(str(sample_geotiff_path))
    assert handle.nodata == 0


def test_open_nonexistent_file_raises():
    reader = RasterReader()
    with pytest.raises(FileNotFoundError):
        reader.open("arquivo_que_nao_existe_12345.tif")


def test_read_preview_returns_correct_shape(sample_geotiff_path):
    reader = RasterReader()
    handle = reader.open(str(sample_geotiff_path))
    preview = reader.read_preview(handle, max_dim=32, band_indexes=[1, 2, 3])

    assert preview.shape[0] == 3
    assert max(preview.shape[1], preview.shape[2]) <= 32