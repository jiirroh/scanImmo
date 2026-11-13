"""Tests unitaires pour l'API Vercel (api/index.py)."""

from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest

from api.index import get_sites_config, save_sites_config, trigger_github_workflow


def test_get_sites_config_local():
    """Vérifie que get_sites_config lit le fichier local par défaut."""
    config, sha = get_sites_config()
    assert "sites" in config
    assert isinstance(config["sites"], list)


def test_save_sites_config_local(tmp_path: Path):
    """Vérifie la sauvegarde locale de la configuration."""
    test_config = {
        "version": "1.0",
        "sites": [
            {
                "id": "test-site",
                "name": "Test Site",
                "url": "https://example.com",
                "enabled": True,
            }
        ],
    }

    with patch("api.index.LOCAL_CONFIG_FILE", tmp_path / "sites_config.json"):
        with patch("api.index.GITHUB_TOKEN", ""):
            success = save_sites_config(test_config)
            assert success is True
            assert (tmp_path / "sites_config.json").exists()


@patch("requests.post")
def test_trigger_github_workflow(mock_post):
    """Vérifie l'appel API GitHub pour déclencher le workflow."""
    mock_resp = MagicMock()
    mock_resp.status_code = 204
    mock_post.return_value = mock_resp

    with patch("api.index.GITHUB_TOKEN", "fake_token"):
        with patch("api.index.GITHUB_REPO", "owner/repo"):
            success, msg = trigger_github_workflow()
            assert success is True
            assert "succès" in msg.lower()
            assert mock_post.called
