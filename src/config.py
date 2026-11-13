"""Module de configuration générale de l'application de veille immobilière."""

import os
from pathlib import Path
from typing import List
from dotenv import load_dotenv

# Chargement du fichier .env à la racine du projet
PROJECT_ROOT = Path(__file__).resolve().parent.parent
ENV_PATH = PROJECT_ROOT / ".env"
load_dotenv(dotenv_path=ENV_PATH)

# Chemins de fichiers
DATA_DIR = PROJECT_ROOT / "data"
DATA_FILE = DATA_DIR / "seen_announcements.json"

# Configuration Telegram
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "").strip()
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "").strip()

# Configuration E-mail / SMTP pour le rapport quotidien
SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com").strip()
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER", "").strip()
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "").strip()
EMAIL_TO = os.getenv("EMAIL_TO", "").strip()
EMAIL_FROM = os.getenv("EMAIL_FROM", "").strip() or SMTP_USER
SMTP_USE_SSL = os.getenv("SMTP_USE_SSL", "false").lower() in ("true", "1", "yes")

# Paramètres réseau & scraping
REQUEST_TIMEOUT = int(os.getenv("REQUEST_TIMEOUT", "15"))
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()

# Liste dynamique de User-Agents modernes et réalistes (Desktop Chrome, Firefox, Safari)
# Utilisés en rotation aléatoire pour simuler un vrai navigateur et contourner les blocages d'en-têtes simples
USER_AGENTS: List[str] = [
    (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/123.0.0.0 Safari/537.36"
    ),
    (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) "
        "Gecko/20100101 Firefox/125.0"
    ),
    (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 14.4; rv:125.0) "
        "Gecko/20100101 Firefox/125.0"
    ),
    (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_4_1) "
        "AppleWebKit/605.1.15 (KHTML, like Gecko) "
        "Version/17.4.1 Safari/605.1.15"
    ),
]

# Fichier de configuration des sites surveillés
SITES_CONFIG_FILE = DATA_DIR / "sites_config.json"


def get_configured_search_urls() -> List[str]:
    """Récupère la liste des URLs de recherche actives depuis data/sites_config.json ou .env."""
    import json

    # 1. Priorité au fichier data/sites_config.json s'il existe
    if SITES_CONFIG_FILE.exists():
        try:
            with open(SITES_CONFIG_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                active_urls = [
                    item["url"].strip()
                    for item in data.get("sites", [])
                    if item.get("enabled", True) and item.get("url", "").strip()
                ]
                if active_urls:
                    return active_urls
        except Exception:
            pass

    # 2. Repli sur la variable d'environnement SEARCH_URLS
    _env_urls = os.getenv("SEARCH_URLS", "").strip()
    if _env_urls:
        return [url.strip() for url in _env_urls.split(",") if url.strip()]

    # 3. Valeurs par défaut
    return [
        "https://www.pap.fr/annonce/vente-maisons-rennes-35000-g43564",
        "https://www.paruvendu.fr/immobilier/vente/maison/rennes-35000/?p=1",
    ]


DEFAULT_SEARCH_URLS = get_configured_search_urls()


def validate_config(require_telegram: bool = False, require_email: bool = False) -> None:
    """Valide les variables d'environnement indispensables au fonctionnement.

    Args:
        require_telegram: Si True, vérifie les identifiants Telegram.
        require_email: Si True, vérifie les identifiants SMTP et adresse e-mail.
    """
    missing = []
    if require_telegram:
        if not TELEGRAM_TOKEN:
            missing.append("TELEGRAM_TOKEN")
        if not TELEGRAM_CHAT_ID:
            missing.append("TELEGRAM_CHAT_ID")

    if require_email:
        if not SMTP_HOST:
            missing.append("SMTP_HOST")
        if not SMTP_USER:
            missing.append("SMTP_USER")
        if not SMTP_PASSWORD:
            missing.append("SMTP_PASSWORD")
        if not EMAIL_TO:
            missing.append("EMAIL_TO")

    if missing:
        raise ValueError(
            f"Variables d'environnement obligatoires manquantes : {', '.join(missing)}.\n"
            "Veuillez définir ces variables dans votre fichier .env ou dans les secrets GitHub Actions."
        )
