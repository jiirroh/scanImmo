"""Scrapers HTML modulaires et configurables avec BeautifulSoup.

Fournit :
1. `GenericHtmlScraper` : scraper basé sur des sélecteurs CSS personnalisables.
2. `ParuVenduScraper` : scraper spécialisé pour paruvendu.fr.
3. `PapScraper` : scraper spécialisé pour pap.fr.
4. `get_scraper_for_url` : fabrique qui sélectionne automatiquement le bon scraper selon l'URL.
"""

import hashlib
import re
from typing import Dict, List, Optional
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup

from src.logger import setup_logger
from src.scraper.base import BaseScraper
from src.scraper.models import Announcement

logger = setup_logger("scraper.parser")


class GenericHtmlScraper(BaseScraper):
    """Scraper universel utilisant des sélecteurs CSS configurables."""

    def __init__(
        self,
        name: str = "GenericScraper",
        card_selector: str = "article, .card, .annonce, .listing-item, .property-card",
        title_selector: str = "h2, h3, .title, a.title, .item-title",
        price_selector: str = ".price, .prix, .item-price, span[class*='price']",
        link_selector: str = "a[href*='annonce'], a[href*='immobilier'], a.item-title, h2 a, h3 a",
        id_attribute: Optional[str] = "data-id",
        source_name: str = "Web",
        **kwargs,
    ):
        super().__init__(name=name, **kwargs)
        self.card_selector = card_selector
        self.title_selector = title_selector
        self.price_selector = price_selector
        self.link_selector = link_selector
        self.id_attribute = id_attribute
        self.source_name = source_name

    def scrape(self, url: str) -> List[Announcement]:
        """Télécharge la page et extrait les annonces correspondantes."""
        html = self.fetch_html(url)
        if not html:
            logger.warning("[%s] Aucun contenu HTML récupéré pour %s", self.name, url)
            return []

        return self.parse_html(html, base_url=url)

    def parse_html(self, html: str, base_url: str) -> List[Announcement]:
        """Analyse le HTML et extrait les objets Announcement."""
        soup = BeautifulSoup(html, "html.parser")
        cards = soup.select(self.card_selector)
        logger.info("[%s] %d cartes d'annonces trouvées avec le sélecteur '%s'", self.name, len(cards), self.card_selector)

        announcements: List[Announcement] = []
        for card in cards:
            ann = self._parse_card(card, base_url)
            if ann:
                announcements.append(ann)

        return announcements

    def _parse_card(self, card, base_url: str) -> Optional[Announcement]:
        """Extrait les attributs d'une seule carte d'annonce."""
        try:
            # 1. Extraction du lien
            link_el = card.select_one(self.link_selector)
            if not link_el and card.name == "a" and card.get("href"):
                link_el = card
            elif not link_el:
                # Chercher le premier <a> contenant un href
                link_el = card.find("a", href=True)

            if not link_el or not link_el.get("href"):
                return None

            raw_href = link_el["href"].strip()
            # Ignorer les ancres pures ou liens javascript
            if raw_href.startswith("#") or raw_href.startswith("javascript:"):
                return None

            absolute_url = urljoin(base_url, raw_href)

            # 2. Extraction de l'ID unique
            ann_id = None
            if self.id_attribute and card.get(self.id_attribute):
                ann_id = card.get(self.id_attribute)

            # Recherche d'attributs de données explicites (data-annonce, product_id)
            if not ann_id:
                for el in [card] + card.find_all(attrs={"data-annonce": True}):
                    if el.has_attr("data-annonce"):
                        try:
                            import json
                            raw_json = json.loads(el["data-annonce"])
                            if "id" in raw_json:
                                ann_id = str(raw_json["id"])
                                break
                        except Exception:
                            pass

            if not ann_id:
                # Recherche ciblée dans le dernier segment du chemin de l'URL
                # ex: /annonces/maison-frepillon-95740-r463400770 -> 463400770
                # ou /annonce-123456.html -> 123456 ou ?id=987654
                path = urlparse(absolute_url).path.rstrip("/")
                last_segment = path.split("/")[-1] if path else ""
                match = re.search(r"(?:-r|/r|-id-|_id_|-|_|id=)(\d{5,16})", last_segment, re.IGNORECASE)
                if not match:
                    match = re.search(r"(\d{5,16})", last_segment)

                if match:
                    ann_id = match.group(1)
                else:
                    # Fallback fiable et déterministe : hash MD5 de l'URL sans paramètres de tracking
                    clean_url_key = absolute_url.split("?")[0].rstrip("/")
                    ann_id = hashlib.md5(clean_url_key.encode("utf-8")).hexdigest()[:12]

            # 3. Extraction du titre
            title = ""
            title_el = card.select_one(self.title_selector)
            if title_el:
                title = title_el.get_text(strip=True)
            elif link_el and link_el.get("title"):
                title = link_el["title"].strip()
            elif link_el:
                title = link_el.get_text(strip=True)

            if not title:
                title = f"Annonce immobilière {ann_id}"

            # 4. Extraction du prix
            price = None
            price_el = card.select_one(self.price_selector)
            if price_el:
                price = price_el.get_text(strip=True)
            else:
                # Chercher un texte contenant le symbole €
                price_match = card.find(string=re.compile(r"\b\d+[\s\d]*\s*€"))
                if price_match:
                    price = price_match.strip()

            # 5. Extraction de l'image (si disponible)
            img_el = card.find("img")
            image_url = None
            if img_el:
                image_src = (
                    img_el.get("data-src")
                    or img_el.get("data-lazy")
                    or img_el.get("data-original")
                    or img_el.get("src")
                )
                if image_src and not image_src.startswith("data:"):
                    image_url = urljoin(base_url, image_src)

            return Announcement(
                id=str(ann_id),
                title=title,
                url=absolute_url,
                price=price,
                image_url=image_url,
                source=self.source_name,
            )
        except Exception as err:
            logger.debug("[%s] Erreur lors du parsing d'une carte : %s", self.name, err)
            return None


class ParuVenduScraper(GenericHtmlScraper):
    """Scraper spécialisé pour le site ParuVendu.fr."""

    def __init__(self, **kwargs):
        defaults = {
            "name": "ParuVendu",
            "card_selector": "div.ergov3-card, div.card-ann, div[data-id], .lazy-ann, div.annonce, article, div[class*='ann-']",
            "title_selector": "h3, .ergov3-title, .titre, a.titre",
            "price_selector": "div.ergov3-price, .price, span.price",
            "link_selector": "a.ergov3-url, a[href*='/immobilier/'], a.titre",
            "id_attribute": "data-id",
            "source_name": "ParuVendu",
        }
        defaults.update(kwargs)
        super().__init__(**defaults)


class PapScraper(GenericHtmlScraper):
    """Scraper spécialisé pour le site PAP.fr (Particulier à Particulier)."""

    def __init__(self, **kwargs):
        defaults = {
            "name": "PAP",
            "card_selector": "div.search-list-item-alt, div.search-results-item, article.item, .item",
            "title_selector": "h2, .item-title, a.item-title, span.item-title",
            "price_selector": "span.item-price, .price",
            "link_selector": "a[href*='/annonces/']",
            "id_attribute": "data-id",
            "source_name": "PAP",
        }
        defaults.update(kwargs)
        super().__init__(**defaults)


def get_scraper_for_url(url: str) -> BaseScraper:
    """Sélectionne dynamiquement le scraper approprié en fonction du domaine de l'URL.

    Args:
        url: L'adresse web de recherche.

    Returns:
        BaseScraper: Instance configurée prête à l'emploi.
    """
    domain = urlparse(url).netloc.lower()

    if "paruvendu.fr" in domain:
        return ParuVenduScraper()
    elif "pap.fr" in domain:
        return PapScraper()
    else:
        # Scraper générique passe-partout avec nommage basé sur le domaine
        clean_name = domain.replace("www.", "").split(".")[0].capitalize()
        return GenericHtmlScraper(name=clean_name, source_name=clean_name)
