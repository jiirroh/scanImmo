"""Point d'entrée principal de l'application de veille immobilière.

Orchestre les composants :
1. Chargement de la configuration et validation
2. Initialisation du stockage persistant (seen_announcements.json)
3. Exécution des scrapers sur les URLs cibles
4. Filtrage des annonces non vues (anti-doublons)
5. Envoi des alertes (Rapport quotidien par E-mail et/ou alertes Telegram)
6. Persistance de l'état mis à jour
"""

import argparse
from collections import defaultdict
from datetime import datetime
from pathlib import Path
import sys
from typing import Dict, List

# Permet d'exécuter directement 'python src/main.py' depuis la racine du projet
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.config import (
    DATA_FILE,
    DEFAULT_SEARCH_URLS,
    EMAIL_FROM,
    EMAIL_TO,
    SMTP_HOST,
    SMTP_PASSWORD,
    SMTP_PORT,
    SMTP_USE_SSL,
    SMTP_USER,
    TELEGRAM_CHAT_ID,
    TELEGRAM_TOKEN,
    validate_config,
)
from src.logger import setup_logger
from src.notifier.email_notifier import EmailNotifier
from src.notifier.telegram import TelegramNotifier
from src.scraper.generic import get_scraper_for_url
from src.scraper.models import Announcement
from src.storage.json_storage import JsonStorage

logger = setup_logger("main")


def parse_arguments() -> argparse.Namespace:
    """Analyse les arguments passés en ligne de commande."""
    parser = argparse.ArgumentParser(
        description="Veille immobilière automatisée avec rapport quotidien par E-mail et alertes Telegram",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--channel",
        choices=["email", "telegram", "both"],
        default="email",
        help="Canal de notification à utiliser : 'email' (rapport groupé), 'telegram' (alertes unitaires) ou 'both'.",
    )
    parser.add_argument(
        "--daily-report",
        action="store_true",
        help="Génère et envoie le rapport récapitulatif quotidien par e-mail avec toutes les offres trouvées.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Mode simulation : scrape les annonces, affiche les offres et génère un aperçu HTML sans envoyer ni modifier la base.",
    )
    parser.add_argument(
        "--test-telegram",
        action="store_true",
        help="Envoie un message de test sur Telegram pour valider les identifiants puis quitte.",
    )
    parser.add_argument(
        "--test-email",
        action="store_true",
        help="Envoie un e-mail de test pour valider la configuration SMTP puis quitte.",
    )
    parser.add_argument(
        "--url",
        type=str,
        default=None,
        help="URL spécifique à tester au lieu des URLs configurées par défaut.",
    )
    parser.add_argument(
        "--ui",
        action="store_true",
        help="Lance l'interface Web interactive de configuration des sites et recherches sur http://localhost:8080.",
    )
    return parser.parse_args()


def run_telegram_test() -> int:
    """Effectue un test de connexion à Telegram."""
    logger.info("--- Test de connectivité Telegram ---")
    try:
        validate_config(require_telegram=True)
    except ValueError as err:
        logger.error("Configuration invalide : %s", err)
        return 1

    notifier = TelegramNotifier(token=TELEGRAM_TOKEN, chat_id=TELEGRAM_CHAT_ID)
    test_msg = (
        "🤖 *Veille Immobilière Connectée*\n\n"
        "✅ Votre bot Telegram est correctement configuré et prêt à relayer les nouvelles annonces !"
    )
    success = notifier.send_message(test_msg)
    if success:
        logger.info("Test Telegram RÉUSSI ! Le message a été délivré.")
        return 0
    else:
        logger.error("Test Telegram ÉCHOUÉ. Vérifiez TELEGRAM_TOKEN et TELEGRAM_CHAT_ID.")
        return 1


def run_email_test() -> int:
    """Effectue un test de connexion et d'envoi d'e-mail SMTP."""
    logger.info("--- Test d'envoi d'e-mail (SMTP) ---")
    try:
        validate_config(require_email=True)
    except ValueError as err:
        logger.error("Configuration invalide : %s", err)
        return 1

    notifier = EmailNotifier(
        smtp_host=SMTP_HOST,
        smtp_port=SMTP_PORT,
        smtp_user=SMTP_USER,
        smtp_password=SMTP_PASSWORD,
        email_to=EMAIL_TO,
        email_from=EMAIL_FROM,
        use_ssl=SMTP_USE_SSL,
        use_tls=not SMTP_USE_SSL,
    )

    dummy_ann = Announcement(
        id="test-12345",
        title="Maison témoin contemporaine 5 pièces 130m²",
        price="295 000 €",
        url="https://www.pap.fr",
        location="Rennes centre",
        surface="130 m²",
        rooms="5 pièces",
        source="Test Configuration",
    )
    test_offers = {"https://www.pap.fr/annonce/test": [dummy_ann]}

    success = notifier.send_daily_report(test_offers, date_str=datetime.now().strftime("%d/%m/%Y (TEST)"))
    if success:
        logger.info("Test E-mail RÉUSSI ! Le rapport de test a été envoyé à %s", EMAIL_TO)
        return 0
    else:
        logger.error("Test E-mail ÉCHOUÉ. Vérifiez vos identifiants SMTP dans .env.")
        return 1


def main() -> int:
    """Fonction principale de surveillance et notification."""
    args = parse_arguments()

    # Interface Web
    if args.ui:
        from src.server import run_server
        run_server(port=8080)
        return 0

    # Tests de connectivité
    if args.test_telegram:
        return run_telegram_test()
    if args.test_email:
        return run_email_test()

    logger.info("==================================================")
    logger.info(" Démarrage de la veille immobilière automatisée  ")
    logger.info("==================================================")

    # Déterminer les canaux cibles
    use_email = args.daily_report or args.channel in ("email", "both")
    use_telegram = args.channel in ("telegram", "both") and not args.daily_report

    # 1. Validation de la configuration selon le canal
    try:
        validate_config(
            require_telegram=use_telegram and not args.dry_run,
            require_email=use_email and not args.dry_run,
        )
    except ValueError as err:
        logger.error("Erreur de configuration : %s", err)
        return 1

    # 2. Initialisation du stockage persistant
    storage = JsonStorage(file_path=DATA_FILE)

    target_urls: List[str] = [args.url] if args.url else DEFAULT_SEARCH_URLS
    logger.info("%d URL(s) de recherche à explorer.", len(target_urls))

    total_scraped = 0
    new_announcements: List[Announcement] = []
    new_offers_by_url: Dict[str, List[Announcement]] = defaultdict(list)

    # 3. Scraping des annonces sur chaque URL cible
    for idx, url in enumerate(target_urls, start=1):
        logger.info("[%d/%d] Scraping de : %s", idx, len(target_urls), url)
        scraper = get_scraper_for_url(url)
        try:
            found = scraper.scrape(url)
            total_scraped += len(found)
            logger.info("-> %d annonce(s) trouvée(s) sur cette page.", len(found))

            for ann in found:
                if not storage.is_seen(ann.id):
                    new_announcements.append(ann)
                    new_offers_by_url[url].append(ann)
        except Exception as err:
            logger.error("Erreur inattendue lors du scraping de %s : %s", url, err, exc_info=True)

    logger.info(
        "Bilan du scraping : %d annonces extraites, %d nouvelle(s) non vue(s).",
        total_scraped,
        len(new_announcements),
    )

    # 4. Mode simulation (Dry-Run)
    if args.dry_run:
        logger.info("=== MODE DRY-RUN ACTIF : aucune notification ni modification persistée ===")
        for ann in new_announcements:
            print(f"\n[NOUVELLE OFFRE DÉTECTÉE]")
            print(f"  ID     : {ann.id}")
            print(f"  Titre  : {ann.title}")
            print(f"  Prix   : {ann.price}")
            print(f"  Lien   : {ann.url}")
            print(f"  Source : {ann.source}")

        # Générer un aperçu HTML local du rapport par e-mail pour prévisualisation
        email_notifier = EmailNotifier(
            smtp_host="localhost",
            smtp_port=25,
            smtp_user="preview",
            smtp_password="",
            email_to="preview@local",
        )
        preview_html = email_notifier._render_html_report(
            new_offers_by_url,
            date_str=datetime.now().strftime("%d/%m/%Y"),
            total_offers=len(new_announcements),
        )
        preview_file = PROJECT_ROOT / "data" / "preview_daily_report.html"
        preview_file.write_text(preview_html, encoding="utf-8")
        logger.info("Aperçu HTML du rapport e-mail enregistré dans : %s", preview_file)
        return 0

    if not new_announcements:
        logger.info("Aucune nouvelle annonce détectée. Fin de la session.")
        return 0

    # 5. Envoi des notifications par E-mail (Rapport Quotidien groupé)
    if use_email:
        logger.info("Génération et envoi du rapport quotidien par e-mail à %s...", EMAIL_TO)
        email_notifier = EmailNotifier(
            smtp_host=SMTP_HOST,
            smtp_port=SMTP_PORT,
            smtp_user=SMTP_USER,
            smtp_password=SMTP_PASSWORD,
            email_to=EMAIL_TO,
            email_from=EMAIL_FROM,
            use_ssl=SMTP_USE_SSL,
            use_tls=not SMTP_USE_SSL,
        )
        email_sent = email_notifier.send_daily_report(new_offers_by_url)
        if not email_sent:
            logger.warning("L'envoi de l'e-mail récapitulatif a échoué.")

    # 6. Envoi des alertes individuelles par Telegram (si activé)
    if use_telegram:
        logger.info("Envoi des alertes instantanées sur Telegram...")
        telegram_notifier = TelegramNotifier(token=TELEGRAM_TOKEN, chat_id=TELEGRAM_CHAT_ID)
        for ann in new_announcements:
            telegram_notifier.send_announcement(ann)

    # 7. Mémorisation des annonces traitées
    for ann in new_announcements:
        storage.mark_seen(
            announcement_id=ann.id,
            title=ann.title,
            price=ann.price,
            url=ann.url,
            source=ann.source,
        )

    # 8. Sauvegarde atomique de l'état
    storage.save()

    logger.info(
        "Session terminée avec succès : %d nouvelle(s) offre(s) traitée(s) et sauvegardée(s).",
        len(new_announcements),
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
