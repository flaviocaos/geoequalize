"""
Fixtures compartilhadas pelos testes: cria rasters temporários (GeoTIFF)
sintéticos em memória/disco, para não depender de arquivos externos.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
import rasterio
from rasterio.transform import from_origin


@pytest.fixture
def sample_geotiff_path(tmp_path: Path) -> Path:
    """Cria um GeoTIFF sintético 3 bandas (RGB), 64x64, com CRS, NoData e
    transform definidos, e retorna o caminho do arquivo."""
    path = tmp_path / "sample.tif"

    width, height = 64, 64
    rng = np.random.default_rng(42)
    data = rng.integers(0, 255, size=(3, height, width), dtype=np.uint8)

    # Marca um canto como NoData para os testes que verificam preservação
    data[:, 0:5, 0:5] = 0
    nodata_value = 0

    transform = from_origin(west=500000, north=7000000, xsize=10, ysize=10)

    profile = {
        "driver": "GTiff",
        "dtype": "uint8",
        "width": width,
        "height": height,
        "count": 3,
        "crs": "EPSG:32723",
        "transform": transform,
        "nodata": nodata_value,
        "compress": "lzw",
    }

    with rasterio.open(path, "w", **profile) as dst:
        dst.write(data)

    return path


@pytest.fixture
def sample_single_band_path(tmp_path: Path) -> Path:
    """Cria um GeoTIFF sintético de 1 banda, sem NoData, para testes de
    correções de histograma em imagens de banda única."""
    path = tmp_path / "single_band.tif"

    width, height = 32, 32
    rng = np.random.default_rng(7)
    data = rng.integers(10, 245, size=(1, height, width), dtype=np.uint8)

    transform = from_origin(west=0, north=0, xsize=1, ysize=1)

    profile = {
        "driver": "GTiff", "dtype": "uint8", "width": width, "height": height,
        "count": 1, "crs": "EPSG:4326", "transform": transform,
    }

    with rasterio.open(path, "w", **profile) as dst:
        dst.write(data)

    return path