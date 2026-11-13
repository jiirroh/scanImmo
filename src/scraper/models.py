"""Modèles de données pour le scraping immobilier."""

from dataclasses import dataclass, field
import re
from typing import Optional


@dataclass
class Announcement:
    """Représente une annonce immobilière extraite d'un portail."""

    id: str
    title: str
    url: str
    price: Optional[str] = None
    location: Optional[str] = None
    surface: Optional[str] = None
    rooms: Optional[str] = None
    image_url: Optional[str] = None
    source: str = "Web"
    published_at: Optional[str] = None

    def __post_init__(self) -> None:
        """Nettoie et normalise les champs après initialisation."""
        self.id = str(self.id).strip()
        self.title = self._clean_string(self.title)
        # Supprime le préfixe de prix redondant en début de titre si présent
        self.title = re.sub(r"^(?:À partir de\s+)?\d+[\d\s.,]*\s*€\s*", "", self.title).strip()
        if not self.title:
            self.title = "Annonce immobilière"
        self.url = self.url.strip()
        if self.price:
            self.price = self._format_price(self.price)
        if self.location:
            self.location = self._clean_string(self.location)
        if self.surface:
            self.surface = self._clean_string(self.surface)
        if self.rooms:
            self.rooms = self._clean_string(self.rooms)

    @staticmethod
    def _clean_string(val: Optional[str]) -> str:
        """Supprime les espaces multiples et sauts de ligne superflus."""
        if not val:
            return ""
        return " ".join(val.replace("\xa0", " ").split()).strip()

    @staticmethod
    def _format_price(val: str) -> str:
        """Normalise la présentation du prix (ex: 250 000 €)."""
        clean = " ".join(val.replace("\xa0", " ").split()).strip()
        # Si un symbole € est présent, capturer les chiffres juste avant
        match_euro = re.search(r"(\d[\d\s.,]*?)\s*€", clean)
        if match_euro:
            digits = re.sub(r"[^\d]", "", match_euro.group(1))
            if digits:
                try:
                    return f"{int(digits):,}".replace(",", " ") + " €"
                except ValueError:
                    pass

        digits_only = re.sub(r"[^\d]", "", clean)
        if digits_only:
            try:
                formatted = f"{int(digits_only):,}".replace(",", " ")
                return f"{formatted} €"
            except ValueError:
                pass
        return clean
