"""
Testes do módulo core.project_file: salvar/carregar projeto e presets.
"""
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import numpy as np
import pytest

from core import project_file as pf


@dataclass
class FakeHistoryEntry:
    """Stand-in simples para HistoryEntry (definido em main_window.py),
    evitando import circular nos testes do core."""
    kind: str
    method: str
    params: dict = field(default_factory=dict)
    label: str = ""
    scope: str = "global"
    mask: Optional[np.ndarray] = None
    enabled: bool = True


def test_save_and_load_project_roundtrip(tmp_path):
    history = [
        FakeHistoryEntry(kind="histogram", method="gamma", params={"gamma": 1.5}, label="Gamma"),
        FakeHistoryEntry(kind="color", method="gray_world", params={}, label="Gray World"),
    ]

    project_path = tmp_path / "project.json"
    image_path = tmp_path / "image.tif"
    image_path.touch()

    pf.save_project(
        output_path=project_path, image_path=image_path,
        band_composition=(1, 2, 3), history=history,
    )

    assert project_path.exists()

    loaded = pf.load_project(project_path, history_entry_cls=FakeHistoryEntry)
    assert loaded["band_composition"] == (1, 2, 3)
    assert len(loaded["history"]) == 2
    assert loaded["history"][0].method == "gamma"
    assert loaded["history"][1].method == "gray_world"


def test_save_project_with_local_mask_roundtrip(tmp_path):
    mask = np.zeros((10, 10))
    mask[2:5, 2:5] = 1.0

    history = [FakeHistoryEntry(kind="histogram", method="gamma", params={}, label="Gamma local", scope="local", mask=mask)]

    project_path = tmp_path / "project_with_mask.json"
    image_path = tmp_path / "image.tif"
    image_path.touch()

    pf.save_project(project_path, image_path, (1, 2, 3), history)
    loaded = pf.load_project(project_path, history_entry_cls=FakeHistoryEntry)

    assert loaded["history"][0].mask is not None
    assert loaded["history"][0].mask.shape == (10, 10)


def test_load_project_missing_file_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        pf.load_project(tmp_path / "nao_existe.json", history_entry_cls=FakeHistoryEntry)


def test_builtin_presets_have_labels():
    for key in pf.BUILTIN_PRESETS:
        assert key in pf.BUILTIN_PRESET_LABELS


def test_save_and_load_user_preset(tmp_path):
    operations = [{"kind": "histogram", "method": "gamma", "params": {"gamma": 1.2}, "label": "Gamma"}]
    pf.save_user_preset(tmp_path, "meu_preset", operations)

    loaded = pf.load_user_preset(tmp_path, "meu_preset")
    assert loaded == operations

    names = pf.list_user_presets(tmp_path)
    assert "meu_preset" in names