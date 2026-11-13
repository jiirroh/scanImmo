"""Tests unitaires pour les modèles et l'analyse HTML des annonces."""

from src.scraper.generic import GenericHtmlScraper, get_scraper_for_url, ParuVenduScraper, PapScraper
from src.scraper.models import Announcement


def test_announcement_model_cleaning():
    """Vérifie le nettoyage des espaces et le formattage des prix."""
    ann = Announcement(
        id="  ABC12345  ",
        title="  Maison contemporaine \n 4 pièces   ",
        url=" https://example.com/annonce/123 ",
        price="250000",
        location=" Rennes \xa0centre ",
    )

    assert ann.id == "ABC12345"
    assert ann.title == "Maison contemporaine 4 pièces"
    assert ann.url == "https://example.com/annonce/123"
    assert ann.price == "250 000 €"
    assert ann.location == "Rennes centre"


def test_generic_scraper_parse_html():
    """Vérifie l'extraction d'annonces à partir d'un fragment HTML typique."""
    sample_html = """
    <html>
      <body>
        <div class="listing">
          <div class="card" data-id="ANN-1001">
            <h2 class="title">Superbe Maison avec grand jardin</h2>
            <div class="price">350 000 €</div>
            <a href="/annonces/maison-1001.html" class="item-title">Voir le bien</a>
            <img src="/images/photo1.jpg" />
          </div>
          <div class="card" data-id="ANN-1002">
            <h3 class="title">Maison de ville 90m2</h3>
            <span class="price">210000 €</span>
            <a href="https://example.com/annonces/maison-1002.html">Consulter</a>
          </div>
        </div>
      </body>
    </html>
    """

    scraper = GenericHtmlScraper()
    announcements = scraper.parse_html(sample_html, base_url="https://example.com")

    assert len(announcements) == 2

    # Annonce 1
    assert announcements[0].id == "ANN-1001"
    assert announcements[0].title == "Superbe Maison avec grand jardin"
    assert announcements[0].price == "350 000 €"
    assert announcements[0].url == "https://example.com/annonces/maison-1001.html"
    assert announcements[0].image_url == "https://example.com/images/photo1.jpg"

    # Annonce 2
    assert announcements[1].id == "ANN-1002"
    assert announcements[1].title == "Maison de ville 90m2"
    assert announcements[1].price == "210 000 €"
    assert announcements[1].url == "https://example.com/annonces/maison-1002.html"


def test_get_scraper_for_url_factory():
    """Vérifie que la factory associe les bons scrapers aux domaines."""
    s1 = get_scraper_for_url("https://www.paruvendu.fr/immobilier/vente/maison/")
    assert isinstance(s1, ParuVenduScraper)

    s2 = get_scraper_for_url("https://www.pap.fr/annonce/vente-maisons-rennes")
    assert isinstance(s2, PapScraper)

    s3 = get_scraper_for_url("https://www.immo-agence-locale.com/ventes")
    assert isinstance(s3, GenericHtmlScraper)
