"""Tests unitaires pour le service Telegram et l'échappement MarkdownV2."""

from unittest.mock import MagicMock, patch
import pytest

from src.notifier.telegram import TelegramNotifier, escape_markdown_v2, escape_url_markdown
from src.scraper.models import Announcement


def test_escape_markdown_v2():
    """Vérifie l'échappement correct de tous les caractères spéciaux Telegram MarkdownV2."""
    raw_text = "Maison 4 pces - 250.000 € ! (Proche mer / Rennes) #SuperDeal [Exclu] ~Barré~ *Gras* _Italique_"
    escaped = escape_markdown_v2(raw_text)

    # Vérification que les caractères critiques sont bien précédés d'un antislash
    assert r"\-" in escaped
    assert r"\." in escaped
    assert r"\!" in escaped
    assert r"\(" in escaped
    assert r"\)" in escaped
    assert r"\#" in escaped
    assert r"\[" in escaped
    assert r"\]" in escaped
    assert r"\~" in escaped
    assert r"\*" in escaped
    assert r"\_" in escaped


def test_escape_url_markdown():
    """Vérifie que les parenthèses dans les URLs sont protégées."""
    url = "https://example.com/item(123)/view"
    escaped_url = escape_url_markdown(url)
    assert r"\)" in escaped_url


def test_format_announcement():
    """Vérifie la mise en forme du message d'alerte."""
    notifier = TelegramNotifier(token="fake_token", chat_id="123456")
    ann = Announcement(
        id="immo-999",
        title="Belle Maison 5 pièces avec jardin",
        url="https://example.com/annonces/immo-999",
        price="320 000 €",
        location="Rennes (35000)",
        surface="120 m²",
        rooms="5 pièces",
        source="TestPortal",
    )

    message = notifier.format_announcement(ann)
    assert "NOUVELLE ANNONCE IMMOBILIÈRE" in message
    assert "320 000 €" in message
    assert "`immo\\-999`" in message
    assert "[👉 Consulter l'annonce](https://example.com/annonces/immo-999)" in message


@patch("requests.post")
def test_send_message_success(mock_post):
    """Vérifie l'appel API HTTP réussi vers Telegram."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"ok": True, "result": {"message_id": 42}}
    mock_post.return_value = mock_response

    notifier = TelegramNotifier(token="test_token", chat_id="123456")
    success = notifier.send_message("Hello World")

    assert success is True
    assert mock_post.called
    endpoint_called = mock_post.call_args[0][0]
    assert "https://api.telegram.org/bottest_token/sendMessage" in endpoint_called


@patch("requests.post")
def test_send_message_fallback_on_parse_error(mock_post):
    """Vérifie le repli en texte brut si MarkdownV2 échoue avec code 400."""
    first_response = MagicMock()
    first_response.status_code = 400
    first_response.json.return_value = {
        "ok": False,
        "error_code": 400,
        "description": "Bad Request: can't parse entities",
    }

    fallback_response = MagicMock()
    fallback_response.status_code = 200
    fallback_response.json.return_value = {"ok": True, "result": {"message_id": 43}}

    mock_post.side_effect = [first_response, fallback_response]

    notifier = TelegramNotifier(token="test_token", chat_id="123456")
    success = notifier.send_message("Texte avec syntaxe douteuse")

    assert success is True
    assert mock_post.call_count == 2
    # Deuxième appel sans parse_mode
    second_call_payload = mock_post.call_args_list[1][1]["json"]
    assert second_call_payload["parse_mode"] is None
