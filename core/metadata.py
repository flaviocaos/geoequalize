"""
Extração e formatação de metadados geoespaciais.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from core.raster_io import RasterHandle


@dataclass
class RasterMetadata:
    crs: Optional[str]
    transform: Optional[tuple]
    width: int
    height: int
    band_count: int
    dtype: str
    nodata: Optional[float]
    bounds: Optional[tuple]
    driver: Optional[str]
    compression: Optional[str]


def extract_metadata(handle: RasterHandle) -> RasterMetadata:
    """Extrai metadados completos de um RasterHandle."""
    return RasterMetadata(
        crs=handle.crs,
        transform=handle.transform,
        width=handle.width,
        height=handle.height,
        band_count=handle.band_count,
        dtype=handle.dtype,
        nodata=handle.nodata,
        bounds=handle.bounds,
        driver=handle.driver,
        compression=handle.compression,
    )


def metadata_to_display_dict(metadata: RasterMetadata) -> dict:
    """Converte RasterMetadata em dict pronto para exibição no painel lateral."""

    def fmt_transform(t: Optional[tuple]) -> str:
        if not t:
            return "—"
        return f"({t[0]:.6f}, {t[1]:.6f}, {t[2]:.2f}, {t[3]:.6f}, {t[4]:.6f}, {t[5]:.2f})"

    def fmt_bounds(b: Optional[tuple]) -> str:
        if not b:
            return "—"
        return f"({b[0]:.4f}, {b[1]:.4f}, {b[2]:.4f}, {b[3]:.4f})"

    return {
        "CRS": metadata.crs or "Ausente",
        "Dimensões (px)": f"{metadata.width} x {metadata.height}",
        "Bandas": str(metadata.band_count),
        "Tipo de dado": metadata.dtype,
        "NoData": str(metadata.nodata) if metadata.nodata is not None else "Ausente",
        "Transform": fmt_transform(metadata.transform),
        "Extensão (bounds)": fmt_bounds(metadata.bounds),
        "Driver": metadata.driver or "—",
        "Compressão": metadata.compression or "Nenhuma",
    }