"""Emplacement des données selon le mode de lancement."""

import importlib
import sys
from pathlib import Path


def test_dossier_donnees(monkeypatch, tmp_path):
    from musee_zoune import config
    monkeypatch.delenv("MUSEE_ZOUNE_DONNEES", raising=False)
    assert config.dossier_donnees() == config.RACINE / "data"  # développement

    monkeypatch.setattr(sys, "frozen", True, raising=False)  # exécutable
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    assert config.dossier_donnees() == tmp_path / "MuseeZoune"

    monkeypatch.setenv("MUSEE_ZOUNE_DONNEES", str(tmp_path / "test"))
    assert config.dossier_donnees() == Path(tmp_path / "test")
    importlib.reload(config)
    monkeypatch.delattr(sys, "frozen")
    monkeypatch.delenv("MUSEE_ZOUNE_DONNEES")
    importlib.reload(config)
