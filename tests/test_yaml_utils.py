"""Tests for the shared YAML loading helper."""

from astraant.yaml_utils import load_yaml


def test_load_yaml_returns_dict(tmp_path):
    p = tmp_path / "part.yaml"
    p.write_text("id: part_1\nprice_usd: 9.5\n", encoding="utf-8")
    assert load_yaml(p) == {"id": "part_1", "price_usd": 9.5}


def test_load_yaml_empty_file_returns_empty_dict(tmp_path):
    p = tmp_path / "empty.yaml"
    p.write_text("", encoding="utf-8")
    assert load_yaml(p) == {}
