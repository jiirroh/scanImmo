"""Classe de base pour les scrapers HTTP avec headers réalistes et gestion des erreurs."""

from abc import ABC, abstractmethod
import random
import time
from typing import Dict, List, Optional
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from src.config import REQUEST_TIMEOUT, USER_AGENTS
from src.logger import setup_logger
from src.scraper.models import Announcement

logger = setup_logger("scraper.base")


class BaseScraper(ABC):
    """Scraper abstrait fournissant une session HTTP configurée avec User-Agent dynamique,

    headers modernes, retries automatiques et gestion des erreurs (403, timeout).
    """

    def __init__(self, name: str = "BaseScraper", timeout: int = REQUEST_TIMEOUT):
        """Initialise le scraper.

        Args:
            name: Nom du scraper (utilisé dans les logs).
            timeout: Délai d'attente maximum pour chaque requête en secondes.
        """
        self.name = name
        self.timeout = timeout
        self.session = self._create_session()

    def _create_session(self) -> requests.Session:
        """Crée une session requests avec politique de retry robuste pour erreurs transitoires."""
        session = requests.Session()
        retries = Retry(
            total=3,
            backoff_factor=1.5,
            status_forcelist=[429, 500, 502, 503, 504],
            raise_on_status=False,
        )
        adapter = HTTPAdapter(max_retries=retries)
        session.mount("http://", adapter)
        session.mount("https://", adapter)
        return session

    def _get_random_user_agent(self) -> str:
        """Sélectionne un User-Agent aléatoire parmi la liste prédéfinie."""
        return random.choice(USER_AGENTS)

    def _get_realistic_headers(self, referer: Optional[str] = None) -> Dict[str, str]:
        """Génère des en-têtes HTTP simulant un navigateur web moderne."""
        headers = {
            "User-Agent": self._get_random_user_agent(),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
            "Accept-Language": "fr-FR,fr;q=0.9,en-US;q=0.8,en;q=0.7",
            "Accept-Encoding": "gzip, deflate, br",
            "DNT": "1",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "same-origin" if referer else "none",
            "Sec-Fetch-User": "?1",
            "Sec-Ch-Ua": '"Chromium";v="124", "Google Chrome";v="124", "Not-A.Brand";v="99"',
            "Sec-Ch-Ua-Mobile": "?0",
            "Sec-Ch-Ua-Platform": '"Windows"',
        }
        if referer:
            headers["Referer"] = referer
        return headers

    def fetch_html(self, url: str) -> Optional[str]:
        """Effectue une requête GET sur l'URL cible avec headers réalistes et gestion des erreurs.

        Args:
            url: URL à récupérer.

        Returns:
            Optional[str]: Le code HTML sous forme de chaîne de caractères, ou None en cas d'échec.
        """
        headers = self._get_realistic_headers()
        logger.info("[%s] Requête HTTP GET vers : %s", self.name, url)

        try:
            # Légère temporisation aléatoire pour éviter un comportement trop mécanique
            time.sleep(random.uniform(0.5, 1.5))

            response = self.session.get(
                url,
                headers=headers,
                timeout=self.timeout,
                allow_redirects=True,
            )

            # Analyse des codes retour
            if response.status_code == 200:
                logger.info(
                    "[%s] Succès HTTP 200 pour %s (%d octets)",
                    self.name,
                    url,
                    len(response.content),
                )
                return response.text

            elif response.status_code == 403:
                logger.warning(
                    "[%s] ERREUR 403 (Accès interdit / Protection anti-bot) sur : %s. "
                    "Le site bloque la requête HTTP directe.",
                    self.name,
                    url,
                )
                return None

            elif response.status_code == 429:
                logger.warning(
                    "[%s] ERREUR 429 (Trop de requêtes / Rate limiting) sur : %s",
                    self.name,
                    url,
                )
                return None

            else:
                logger.warning(
                    "[%s] Code HTTP inattendu (%d) pour : %s",
                    self.name,
                    response.status_code,
                    url,
                )
                return None

        except requests.exceptions.Timeout:
            logger.error(
                "[%s] TIMEOUT (%ds dépassé) lors de la requête vers : %s",
                self.name,
                self.timeout,
                url,
            )
            return None

        except requests.exceptions.SSLError as err:
            logger.error("[%s] Erreur SSL sur %s : %s", self.name, url, err)
            return None

        except requests.exceptions.RequestException as err:
            logger.error(
                "[%s] Erreur réseau lors de la requête vers %s : %s",
                self.name,
                url,
                err,
            )
            return None

    @abstractmethod
    def scrape(self, url: str) -> List[Announcement]:
        """Méthode abstraite à implémenter pour extraire les annonces depuis une URL.

        Args:
            url: URL de la page de recherche.

        Returns:
            List[Announcement]: Liste des annonces trouvées.
        """
        pass
