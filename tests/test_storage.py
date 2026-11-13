"""Tests unitaires du service de stockage JSON."""

import json
from pathlib import Path
import pytest
from src.storage.json_storage import JsonStorage
from src.scraper.models import Announcement


def test_storage_init_empty(tmp_path: Path):
    """Vérifie l'initialisation sur un fichier inexistant."""
    data_file = tmp_path / "seen.json"
    storage = JsonStorage(data_file)
    assert storage.total_count == 0
    assert not storage.is_seen("12345")


def test_storage_mark_seen_and_filter(tmp_path: Path):
    """Vérifie le marquage et le filtrage des annonces."""
    data_file = tmp_path / "seen.json"
    storage = JsonStorage(data_file)

    ann1 = Announcement(id="id-1", title="Maison 1", url="http://test.com/1", price="200 000 €")
    ann2 = Announcement(id="id-2", title="Maison 2", url="http://test.com/2", price="300 000 €")

    # Au départ, aucune n'est vue
    unseen = storage.filter_unseen([ann1, ann2])
    assert len(unseen) == 2

    # On marque ann1 comme vue
    res = storage.mark_seen(ann1.id, title=ann1.title, price=ann1.price, url=ann1.url)
    assert res is True
    assert storage.is_seen("id-1") is True
    assert storage.is_seen("id-2") is False

    # Le nouveau filtre ne doit contenir que ann2
    unseen_after = storage.filter_unseen([ann1, ann2])
    assert len(unseen_after) == 1
    assert unseen_after[0].id == "id-2"


def test_storage_persistence(tmp_path: Path):
    """Vérifie que save() persiste correctement et est rechargé lors d'une nouvelle instance."""
    data_file = tmp_path / "seen.json"
    storage1 = JsonStorage(data_file)
    storage1.mark_seen("alpha", title="Maison Alpha", url="http://alpha.com")
    assert storage1.save() is True

    # Nouvelle instance lisant le même fichier
    storage2 = JsonStorage(data_file)
    assert storage2.total_count == 1
    assert storage2.is_seen("alpha") is True
    assert not storage2.is_seen("beta")


def test_storage_corrupted_file_recovery(tmp_path: Path):
    """Vérifie la robustesse si le fichier JSON est altéré ou tronqué."""
    data_file = tmp_path / "seen.json"
    # Écriture de JSON invalide
    data_file.write_text("{ ce n'est pas du json valide", encoding="utf-8")

    storage = JsonStorage(data_file)
    # L'application ne doit pas crasher, mais réinitialiser proprement
    assert storage.total_count == 0
    storage.mark_seen("test-id", title="Test")
    assert storage.save() is True
    assert storage.is_seen("test-id") is True
