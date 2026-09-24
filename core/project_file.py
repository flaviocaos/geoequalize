"""
Persistência de projeto (salvar/carregar estado do trabalho) e presets.

Responsabilidade:
- Serializar: caminho da imagem original, composição de bandas,
  histórico de operações (com parâmetros e máscaras locais),
  em formato JSON
- Carregar esse estado de volta
- Salvar/carregar presets de correção reutilizáveis

Como o histórico (HistoryEntry) contém arrays numpy (máscaras locais),
estes são convertidos para listas aninhadas na serialização e de volta
para np.ndarray na desserialização.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Optional

import numpy as np

logger = logging.getLogger(__name__)

PROJECT_FILE_VERSION = 1
PRESETS_DIR_NAME = "presets"


def _mask_to_list(mask: Optional[np.ndarray]) -> Optional[list]:
    if mask is None:
        return None
    # Reduz precisão para float16 antes de serializar, para diminuir tamanho do JSON.
    return mask.astype(np.float16).tolist()


def _list_to_mask(data: Optional[list]) -> Optional[np.ndarray]:
    if data is None:
        return None
    return np.array(data, dtype=np.float64)


def serialize_history_entry(entry) -> dict:
    """Converte um HistoryEntry (definido em main_window.py) para dict serializável."""
    return {
        "kind": entry.kind,
        "method": entry.method,
        "params": entry.params,
        "label": entry.label,
        "scope": entry.scope,
        "mask": _mask_to_list(entry.mask),
        "enabled": entry.enabled,
    }


def deserialize_history_entry(data: dict, history_entry_cls):
    """Reconstrói um HistoryEntry a partir do dict salvo. `history_entry_cls`
    é passado pelo chamador para evitar import circular com main_window.py."""
    return history_entry_cls(
        kind=data["kind"],
        method=data["method"],
        params=data.get("params", {}),
        label=data.get("label", data["method"]),
        scope=data.get("scope", "global"),
        mask=_list_to_mask(data.get("mask")),
        enabled=data.get("enabled", True),
    )


def save_project(
    output_path: Path,
    image_path: Path,
    band_composition: tuple[int, int, int],
    history: list,
    selection_mask: Optional[np.ndarray] = None,
) -> None:
    """Salva o estado completo do projeto em um arquivo JSON."""
    output_path.parent.mkdir(parents=True, exist_ok=True)

    payload: dict[str, Any] = {
        "version": PROJECT_FILE_VERSION,
        "image_path": str(image_path),
        "band_composition": list(band_composition),
        "history": [serialize_history_entry(entry) for entry in history],
        "selection_mask": _mask_to_list(selection_mask) if selection_mask is not None else None,
    }

    output_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    logger.info("Projeto salvo: %s (%d operações)", output_path, len(history))


def load_project(input_path: Path, history_entry_cls) -> dict:
    """Carrega o projeto e retorna um dict com:
    image_path (str), band_composition (tuple), history (list[HistoryEntry]),
    selection_mask (np.ndarray | None)
    """
    if not input_path.exists():
        raise FileNotFoundError(f"Arquivo de projeto não encontrado: {input_path}")

    payload = json.loads(input_path.read_text(encoding="utf-8"))

    version = payload.get("version", 1)
    if version != PROJECT_FILE_VERSION:
        logger.warning("Versão do arquivo de projeto (%s) difere da atual (%s).", version, PROJECT_FILE_VERSION)

    history = [deserialize_history_entry(entry, history_entry_cls) for entry in payload.get("history", [])]

    return {
        "image_path": payload["image_path"],
        "band_composition": tuple(payload.get("band_composition", [1, 2, 3])),
        "history": history,
        "selection_mask": _list_to_mask(payload.get("selection_mask")),
    }


# ----------------------------------------------------------------------
# Presets de correção
# ----------------------------------------------------------------------
BUILTIN_PRESETS: dict[str, list[dict]] = {
    "ortofoto_urbana": [
        {"kind": "histogram", "method": "stretch_percentile", "params": {"low_pct": 2.0, "high_pct": 98.0}, "label": "Stretch por percentil"},
        {"kind": "color", "method": "enhance_urban", "params": {}, "label": "Realce — área urbana"},
    ],
    "vegetacao": [
        {"kind": "histogram", "method": "clahe", "params": {}, "label": "CLAHE"},
        {"kind": "color", "method": "enhance_vegetation", "params": {}, "label": "Realce — vegetação"},
    ],
    "solo_exposto": [
        {"kind": "histogram", "method": "stretch_percentile", "params": {"low_pct": 2.0, "high_pct": 98.0}, "label": "Stretch por percentil"},
        {"kind": "color", "method": "enhance_bare_soil", "params": {}, "label": "Realce — solo exposto"},
    ],
    "imagem_escura": [
        {"kind": "histogram", "method": "gamma", "params": {"gamma": 0.6}, "label": "Gamma"},
        {"kind": "histogram", "method": "stretch_std", "params": {"n_std": 2.0}, "label": "Stretch por desvio padrão"},
    ],
    "imagem_lavada": [
        {"kind": "histogram", "method": "stretch_percentile", "params": {"low_pct": 5.0, "high_pct": 95.0}, "label": "Stretch por percentil"},
        {"kind": "color", "method": "tonal_ranges", "params": {"shadows": -20, "midtones": 0, "highlights": -10}, "label": "Sombras/Médios/Realces"},
    ],
    "imagem_azulada": [
        {"kind": "color", "method": "cast_blue", "params": {"intensity": 1.0}, "label": "Redução de dominância azulada"},
        {"kind": "color", "method": "gray_world", "params": {}, "label": "Balanceamento Gray World"},
    ],
    "imagem_amarelada": [
        {"kind": "color", "method": "cast_yellow", "params": {"intensity": 1.0}, "label": "Redução de dominância amarelada"},
        {"kind": "color", "method": "gray_world", "params": {}, "label": "Balanceamento Gray World"},
    ],
    "realce_geral": [
        {"kind": "histogram", "method": "stretch_percentile", "params": {"low_pct": 2.0, "high_pct": 98.0}, "label": "Stretch por percentil"},
        {"kind": "color", "method": "hue_saturation", "params": {"hue_shift": 0.0, "saturation": 1.15}, "label": "Matiz/Saturação"},
    ],
    "falsa_cor_vegetacao": [
        {"kind": "histogram", "method": "stretch_percentile", "params": {"low_pct": 2.0, "high_pct": 98.0}, "label": "Stretch por percentil"},
    ],
}

BUILTIN_PRESET_LABELS = {
    "ortofoto_urbana": "Ortofoto urbana",
    "vegetacao": "Vegetação",
    "solo_exposto": "Solo exposto",
    "imagem_escura": "Imagem escura",
    "imagem_lavada": "Imagem lavada",
    "imagem_azulada": "Imagem azulada",
    "imagem_amarelada": "Imagem amarelada",
    "realce_geral": "Realce geral",
    "falsa_cor_vegetacao": "Falsa-cor vegetação",
}


def list_user_presets(presets_dir: Path) -> list[str]:
    """Lista nomes (sem extensão) dos presets salvos pelo usuário em `presets_dir`."""
    if not presets_dir.exists():
        return []
    return sorted(p.stem for p in presets_dir.glob("*.json"))


def save_user_preset(presets_dir: Path, name: str, operations: list[dict]) -> Path:
    """Salva um preset personalizado (lista de operações simplificadas, sem máscaras)."""
    presets_dir.mkdir(parents=True, exist_ok=True)
    safe_name = "".join(c if c.isalnum() or c in "-_" else "_" for c in name)
    path = presets_dir / f"{safe_name}.json"
    path.write_text(json.dumps(operations, indent=2), encoding="utf-8")
    logger.info("Preset salvo: %s", path)
    return path


def load_user_preset(presets_dir: Path, name: str) -> list[dict]:
    path = presets_dir / f"{name}.json"
    if not path.exists():
        raise FileNotFoundError(f"Preset não encontrado: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def get_preset_operations(preset_key: str, presets_dir: Optional[Path] = None) -> list[dict]:
    """Retorna a lista de operações de um preset, builtin ou do usuário."""
    if preset_key in BUILTIN_PRESETS:
        return BUILTIN_PRESETS[preset_key]
    if presets_dir is not None:
        return load_user_preset(presets_dir, preset_key)
    raise KeyError(f"Preset não encontrado: {preset_key}")