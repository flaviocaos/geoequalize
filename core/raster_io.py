"""
Leitura e escrita de rasters georreferenciados.

Responsabilidade:
- Abrir arquivos GeoTIFF/TIFF/JPEG/PNG/JP2 via Rasterio
- Gerar preview reduzido para performance em arquivos grandes
- Fornecer acesso a bandas individuais sem carregar o arquivo inteiro
  na memória (leitura em blocos / janelas)
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import numpy as np
import rasterio
from rasterio.enums import Resampling
from rasterio.windows import Window

logger = logging.getLogger(__name__)


@dataclass
class RasterHandle:
    """Referência a um raster aberto, mantendo metadados básicos em memória."""
    path: Path
    width: int
    height: int
    band_count: int
    dtype: str
    crs: Optional[str]
    nodata: Optional[float]
    transform: tuple
    bounds: tuple
    driver: str
    compression: Optional[str]
    colormap: Optional[dict] = None  # {indice_pixel: (r, g, b, a)}, se a banda 1 for paletted


class RasterReader:
    """Encapsula leitura de raster via Rasterio/GDAL."""

    def open(self, path: str) -> RasterHandle:
        """Abre o arquivo e retorna um RasterHandle com metadados básicos."""
        raster_path = Path(path)
        if not raster_path.exists():
            raise FileNotFoundError(f"Arquivo não encontrado: {path}")

        with rasterio.open(raster_path) as src:
            colormap = None
            try:
                if src.colorinterp and src.colorinterp[0].name == "palette":
                    colormap = src.colormap(1)
            except (ValueError, IndexError):
                colormap = None

            handle = RasterHandle(
                path=raster_path,
                width=src.width,
                height=src.height,
                band_count=src.count,
                dtype=str(src.dtypes[0]),
                crs=str(src.crs) if src.crs else None,
                nodata=src.nodata,
                transform=tuple(src.transform)[:6],
                bounds=tuple(src.bounds),
                driver=src.driver,
                compression=src.profile.get("compress"),
                colormap=colormap,
            )

        logger.info(
            "Raster aberto: %s (%dx%d, %d bandas, dtype=%s, crs=%s, paleta=%s)",
            raster_path.name, handle.width, handle.height,
            handle.band_count, handle.dtype, handle.crs, colormap is not None,
        )
        return handle

    def read_preview(
        self,
        handle: RasterHandle,
        max_dim: int = 2048,
        band_indexes: Optional[list[int]] = None,
    ) -> np.ndarray:
        """Lê uma versão reduzida do raster para exibição rápida.

        Retorna array shape (bands, height, width).
        """
        scale = min(1.0, max_dim / max(handle.width, handle.height))
        out_height = max(1, int(handle.height * scale))
        out_width = max(1, int(handle.width * scale))

        with rasterio.open(handle.path) as src:
            indexes = band_indexes or list(range(1, min(src.count, 3) + 1))
            data = src.read(
                indexes=indexes,
                out_shape=(len(indexes), out_height, out_width),
                resampling=Resampling.bilinear,
            )

        logger.debug(
            "Preview gerado: %dx%d (escala %.4f) bandas=%s",
            out_width, out_height, scale, indexes,
        )
        return data

    def read_band(
        self,
        handle: RasterHandle,
        band_index: int,
        window: Optional[Window] = None,
    ) -> np.ndarray:
        """Lê uma banda específica, opcionalmente restrita a uma janela (bloco)."""
        with rasterio.open(handle.path) as src:
            return src.read(band_index, window=window)

    def read_full_resolution(self, handle: RasterHandle) -> np.ndarray:
        """Lê o raster em resolução total (usado na exportação, Fase 6).

        Atenção: pode consumir muita memória em arquivos grandes.
        Nas Fases 6+ isso será substituído por leitura em blocos.
        """
        with rasterio.open(handle.path) as src:
            return src.read()