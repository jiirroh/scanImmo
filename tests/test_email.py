"""Tests unitaires pour le notificateur e-mail et le rapport quotidien."""

from unittest.mock import MagicMock, patch
import pytest

from src.notifier.email_notifier import EmailNotifier
from src.scraper.models import Announcement


@pytest.fixture
def sample_offers():
    """Jeu de données de test pour les annonces groupées par URL."""
    ann1 = Announcement(
        id="ann-001",
        title="Belle maison contemporaine 5 pièces",
        url="https://www.pap.fr/annonces/maison-001",
        price="310 000 €",
        location="Rennes centre",
        surface="120 m²",
        rooms="5 p.",
        source="PAP",
    )
    ann2 = Announcement(
        id="ann-002",
        title="Maison ancienne rénovée avec jardin",
        url="https://www.paruvendu.fr/annonces/maison-002",
        price="245 000 €",
        location="Cesson-Sévigné",
        source="ParuVendu",
    )
    return {
        "https://www.pap.fr/recherche/rennes": [ann1],
        "https://www.paruvendu.fr/recherche/rennes": [ann2],
    }


def test_render_html_report(sample_offers):
    """Vérifie que le rapport HTML contient bien les liens de recherche, les titres et les prix."""
    notifier = EmailNotifier(
        smtp_host="smtp.example.com",
        smtp_port=587,
        smtp_user="test@example.com",
        smtp_password="password",
        email_to="destinataire@example.com",
    )

    html = notifier._render_html_report(sample_offers, date_str="12/10/2026", total_offers=2)

    # Vérification des éléments indispensables
    assert "Rapport Quotidien de Veille Immobilière" in html
    assert "12/10/2026" in html
    assert "https://www.pap.fr/recherche/rennes" in html
    assert "https://www.paruvendu.fr/recherche/rennes" in html
    assert "Belle maison contemporaine 5 pièces" in html
    assert "310 000 €" in html
    assert "245 000 €" in html
    assert "https://www.pap.fr/annonces/maison-001" in html


def test_render_text_report(sample_offers):
    """Vérifie que la version texte brut contient les informations indispensables."""
    notifier = EmailNotifier(
        smtp_host="smtp.example.com",
        smtp_port=587,
        smtp_user="test@example.com",
        smtp_password="password",
        email_to="destinataire@example.com",
    )

    text = notifier._render_text_report(sample_offers, date_str="12/10/2026", total_offers=2)

    assert "RAPPORT QUOTIDIEN DE VEILLE IMMOBILIÈRE" in text
    assert "https://www.pap.fr/recherche/rennes" in text
    assert "Belle maison contemporaine 5 pièces" in text
    assert "310 000 €" in text


@patch("smtplib.SMTP")
def test_send_daily_report_smtp_success(mock_smtp_class, sample_offers):
    """Vérifie l'envoi réussi via SMTP avec STARTTLS."""
    mock_server = MagicMock()
    mock_smtp_class.return_value = mock_server

    notifier = EmailNotifier(
        smtp_host="smtp.gmail.com",
        smtp_port=587,
        smtp_user="user@gmail.com",
        smtp_password="app_password",
        email_to="client@example.com",
        use_tls=True,
    )

    success = notifier.send_daily_report(sample_offers)

    assert success is True
    mock_server.starttls.assert_called_once()
    mock_server.login.assert_called_once_with("user@gmail.com", "app_password")
    mock_server.sendmail.assert_called_once()
    mock_server.quit.assert_called_once()
