"""Module de scraping immobilier."""

from .models import Announcement
from .base import BaseScraper
from .generic import (
    GenericHtmlScraper,
    ParuVenduScraper,
    PapScraper,
    get_scraper_for_url,
)

__all__ = [
    "Announcement",
    "BaseScraper",
    "GenericHtmlScraper",
    "ParuVenduScraper",
    "PapScraper",
    "get_scraper_for_url",
]
