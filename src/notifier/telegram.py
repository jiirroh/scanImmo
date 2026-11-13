"""Service d'envoi de notifications via l'API Telegram Bot.

Gère l'échappement MarkdownV2, l'envoi de messages texte formatés,
l'envoi d'images d'aperçu d'annonces, et la gestion rigoureuse des erreurs d'API.
"""

import re
import time
from typing import Optional
import requests

from src.logger import setup_logger
from src.scraper.models import Announcement

logger = setup_logger("notifier.telegram")


def escape_markdown_v2(text: str) -> str:
    """Échappe tous les caractères réservés de la syntaxe Telegram MarkdownV2.

    Caractères réservés : _ * [ ] ( ) ~ ` > # + - = | { } . ! \\

    Args:
        text: Chaîne brute à échapper.

    Returns:
        str: Chaîne sécurisée pour MarkdownV2.
    """
    if not text:
        return ""
    # Caractères obligatoires à précéder d'un antislash
    escape_chars = r"_*[]()~`>#+-=|{}.!\\"
    return re.sub(f"([{re.escape(escape_chars)}])", r"\\\1", str(text))


def escape_url_markdown(url: str) -> str:
    """Échappe les caractères réservés dans l'URL d'un lien MarkdownV2 ([text](url)).

    Dans la partie URL, seuls ')' et '\\' nécessitent un échappement.
    """
    if not url:
        return ""
    return str(url).replace("\\", "\\\\").replace(")", "\\)")


class TelegramNotifier:
    """Client Telegram pour l'envoi d'alertes immobilières."""

    def __init__(self, token: str, chat_id: str, timeout: int = 15):
        """Initialise le notificateur Telegram.

        Args:
            token: Jeton d'API du Bot fourni par @BotFather.
            chat_id: ID du destinataire (utilisateur, groupe ou canal).
            timeout: Délai d'expiration HTTP en secondes.
        """
        self.token = token.strip()
        self.chat_id = chat_id.strip()
        self.timeout = timeout
        self.api_url = f"https://api.telegram.org/bot{self.token}"

    def send_message(
        self,
        text: str,
        parse_mode: str = "MarkdownV2",
        disable_web_page_preview: bool = False,
    ) -> bool:
        """Envoie un message texte simple ou formaté.

        Args:
            text: Contenu du message.
            parse_mode: Format du texte ('MarkdownV2', 'HTML' ou None).
            disable_web_page_preview: Désactive l'aperçu du lien web si True.

        Returns:
            bool: True si délivré avec succès, False sinon.
        """
        if not self.token or not self.chat_id:
            logger.error("Impossible d'envoyer le message : token ou chat_id non configuré.")
            return False

        endpoint = f"{self.api_url}/sendMessage"
        payload = {
            "chat_id": self.chat_id,
            "text": text,
            "parse_mode": parse_mode,
            "disable_web_page_preview": disable_web_page_preview,
        }

        try:
            response = requests.post(endpoint, json=payload, timeout=self.timeout)
            data = response.json()

            if response.status_code == 200 and data.get("ok"):
                logger.debug("Message Telegram envoyé avec succès.")
                return True

            # Analyse des erreurs courantes Telegram
            error_code = data.get("error_code")
            desc = data.get("description", "Erreur inconnue")

            if error_code == 400 and "can't parse entities" in desc.lower():
                logger.error(
                    "Erreur de syntaxe MarkdownV2 Telegram (%s). "
                    "Tentative de repli en texte brut...",
                    desc,
                )
                # Fallback : envoi en texte brut sans formatage
                payload["parse_mode"] = None
                fallback_resp = requests.post(endpoint, json=payload, timeout=self.timeout)
                return fallback_resp.status_code == 200

            elif error_code == 401:
                logger.critical("TELEGRAM_TOKEN invalide (401 Unauthorized). Vérifiez vos identifiants.")
            elif error_code == 403:
                logger.error("Bot bloqué par l'utilisateur ou droits insuffisants dans le chat (%d : %s)", error_code, desc)
            elif error_code == 429:
                retry_after = data.get("parameters", {}).get("retry_after", 5)
                logger.warning("Limite de requêtes Telegram atteinte. Attente recommandée : %ds", retry_after)
            else:
                logger.error("Échec de l'envoi Telegram (%s : %s)", error_code, desc)

            return False

        except requests.exceptions.Timeout:
            logger.error("Timeout lors de l'appel à l'API Telegram (%ds)", self.timeout)
            return False
        except requests.exceptions.RequestException as err:
            logger.error("Erreur réseau lors de l'envoi du message Telegram : %s", err)
            return False

    def send_photo(self, photo_url: str, caption: str, parse_mode: str = "MarkdownV2") -> bool:
        """Tente d'envoyer une photo avec légende. En cas d'échec de l'image, bascule sur send_message."""
        endpoint = f"{self.api_url}/sendPhoto"
        payload = {
            "chat_id": self.chat_id,
            "photo": photo_url,
            "caption": caption,
            "parse_mode": parse_mode,
        }
        try:
            resp = requests.post(endpoint, json=payload, timeout=self.timeout)
            if resp.status_code == 200 and resp.json().get("ok"):
                logger.debug("Photo Telegram envoyée avec succès.")
                return True
            logger.warning("Échec de l'envoi de l'image Telegram (%s), bascule sur texte seul.", resp.text)
        except requests.exceptions.RequestException:
            logger.warning("Erreur réseau sur l'envoi d'image, bascule sur texte seul.")

        # Repli sur message texte
        return self.send_message(caption, parse_mode=parse_mode)

    def format_announcement(self, announcement: Announcement) -> str:
        """Génère le message MarkdownV2 élégamment structuré pour une annonce.

        Args:
            announcement: Données de l'annonce immobilière.

        Returns:
            str: Message prêt pour Telegram MarkdownV2.
        """
        escaped_title = escape_markdown_v2(announcement.title or "Maison sans titre")
        escaped_price = escape_markdown_v2(announcement.price or "Non communiqué")
        escaped_source = escape_markdown_v2(announcement.source or "Web")
        escaped_id = escape_markdown_v2(announcement.id)
        escaped_url = escape_url_markdown(announcement.url)

        lines = [
            "🏠 *NOUVELLE ANNONCE IMMOBILIÈRE*",
            "━━━━━━━━━━━━━━━━━━━━━━━",
            f"📌 *Titre :* {escaped_title}",
            f"💰 *Prix :* {escaped_price}",
        ]

        if announcement.location:
            lines.append(f"📍 *Ville :* {escape_markdown_v2(announcement.location)}")

        if announcement.surface:
            lines.append(f"📐 *Surface :* {escape_markdown_v2(announcement.surface)}")

        if announcement.rooms:
            lines.append(f"🚪 *Pièces :* {escape_markdown_v2(announcement.rooms)}")

        lines.extend([
            f"🌐 *Source :* {escaped_source}",
            f"🆔 *Réf :* `{escaped_id}`",
            "━━━━━━━━━━━━━━━━━━━━━━━",
            f"🔗 [👉 Consulter l'annonce]({escaped_url})",
        ])

        return "\n".join(lines)

    def send_announcement(self, announcement: Announcement) -> bool:
        """Envoie l'annonce sur Telegram avec ou sans photo d'illustration.

        Args:
            announcement: L'annonce à notifier.

        Returns:
            bool: True si envoyée, False sinon.
        """
        caption = self.format_announcement(announcement)

        # Si l'annonce a une image valide (URL absolue HTTP/HTTPS)
        if announcement.image_url and announcement.image_url.startswith("http"):
            success = self.send_photo(announcement.image_url, caption=caption)
        else:
            success = self.send_message(caption)

        # Petite temporisation pour respecter le débit Telegram (limite de 30 msgs/sec global, 1 msg/sec par chat)
        time.sleep(1.0)
        return success
