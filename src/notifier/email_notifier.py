"""Service d'envoi de rapports récapitulatifs par e-mail (SMTP).

Génère un e-mail HTML élégant et responsive ainsi qu'une version texte brut
regroupant les offres immobilières trouvées pour chaque URL de recherche surveillée.
"""

from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import smtplib
from typing import Dict, List, Optional
from urllib.parse import urlparse

from src.logger import setup_logger
from src.scraper.models import Announcement

logger = setup_logger("notifier.email")


class EmailNotifier:
    """Service d'envoi d'e-mails récapitulatifs via SMTP."""

    def __init__(
        self,
        smtp_host: str,
        smtp_port: int,
        smtp_user: str,
        smtp_password: str,
        email_to: str,
        email_from: Optional[str] = None,
        use_tls: bool = True,
        use_ssl: bool = False,
        timeout: int = 20,
    ):
        """Initialise le notificateur e-mail.

        Args:
            smtp_host: Serveur SMTP (ex: smtp.gmail.com).
            smtp_port: Port SMTP (587 pour STARTTLS, 465 pour SSL).
            smtp_user: Nom d'utilisateur ou adresse d'expédition.
            smtp_password: Mot de passe ou mot de passe d'application.
            email_to: Adresse e-mail du destinataire (ou liste séparée par des virgules).
            email_from: Adresse d'expédition affichée (par défaut: smtp_user).
            use_tls: Active le chiffrement STARTTLS (recommandé port 587).
            use_ssl: Active SSL direct (recommandé port 465).
            timeout: Délai d'attente maximum pour la connexion SMTP en secondes.
        """
        self.smtp_host = smtp_host.strip()
        self.smtp_port = int(smtp_port)
        self.smtp_user = smtp_user.strip()
        self.smtp_password = smtp_password.strip()
        self.email_to = email_to.strip()
        self.email_from = (email_from or smtp_user).strip()
        self.use_tls = use_tls
        self.use_ssl = use_ssl
        self.timeout = timeout

    def send_daily_report(
        self,
        offers_by_url: Dict[str, List[Announcement]],
        date_str: Optional[str] = None,
    ) -> bool:
        """Envoie le rapport quotidien regroupant les annonces par URL de recherche.

        Args:
            offers_by_url: Dictionnaire associant chaque URL de recherche à ses annonces.
            date_str: Date du rapport (par défaut: date du jour formatée).

        Returns:
            bool: True si l'e-mail a été envoyé avec succès, False sinon.
        """
        if not self.smtp_host or not self.smtp_user or not self.email_to:
            logger.error("Configuration e-mail incomplète : hôte, utilisateur ou destinataire manquant.")
            return False

        current_date = date_str or datetime.now().strftime("%d/%m/%Y")
        total_offers = sum(len(offers) for offers in offers_by_url.values())

        subject = f"🏡 Veille Immo : Rapport quotidien du {current_date} ({total_offers} offre{'s' if total_offers > 1 else ''})"

        html_content = self._render_html_report(offers_by_url, current_date, total_offers)
        text_content = self._render_text_report(offers_by_url, current_date, total_offers)

        return self._send_email(subject, html_content, text_content)

    def _render_text_report(
        self,
        offers_by_url: Dict[str, List[Announcement]],
        date_str: str,
        total_offers: int,
    ) -> str:
        """Génère la version texte brut du rapport (fallback)."""
        lines = [
            f"=== RAPPORT QUOTIDIEN DE VEILLE IMMOBILIÈRE ({date_str}) ===",
            f"Total des nouvelles offres récupérées : {total_offers}",
            "",
        ]

        for url, offers in offers_by_url.items():
            domain = urlparse(url).netloc.replace("www.", "")
            lines.append("=" * 60)
            lines.append(f"Site : {domain}")
            lines.append(f"Lien de recherche : {url}")
            lines.append(f"Offres trouvées : {len(offers)}")
            lines.append("-" * 60)

            if not offers:
                lines.append("Aucune nouvelle offre sur ce lien aujourd'hui.")
            else:
                for idx, ann in enumerate(offers, start=1):
                    lines.append(f"[{idx}] {ann.title}")
                    lines.append(f"    Prix   : {ann.price or 'Non communiqué'}")
                    if ann.location:
                        lines.append(f"    Lieu   : {ann.location}")
                    lines.append(f"    Lien   : {ann.url}")
                    lines.append("")

            lines.append("")

        return "\n".join(lines)

    def _render_html_report(
        self,
        offers_by_url: Dict[str, List[Announcement]],
        date_str: str,
        total_offers: int,
    ) -> str:
        """Génère un e-mail HTML moderne, lisible et responsive."""
        sections_html = []

        for url, offers in offers_by_url.items():
            domain = urlparse(url).netloc.replace("www.", "")
            offers_count = len(offers)

            cards_html = []
            if not offers:
                cards_html.append(
                    """
                    <div style="background-color: #f8fafc; border: 1px dashed #cbd5e1; border-radius: 8px; padding: 16px; text-align: center; color: #64748b; font-size: 14px;">
                        Aucune nouvelle annonce sur cette recherche aujourd'hui.
                    </div>
                    """
                )
            else:
                for ann in offers:
                    img_block = ""
                    if ann.image_url and ann.image_url.startswith("http"):
                        img_block = f"""
                        <div style="width: 140px; height: 105px; overflow: hidden; border-radius: 8px; flex-shrink: 0; background-color: #e2e8f0;">
                            <img src="{ann.image_url}" alt="{ann.title}" style="width: 100%; height: 100%; object-fit: cover;" />
                        </div>
                        """

                    location_info = f"<span style='color: #64748b; font-size: 13px; margin-right: 12px;'>📍 {ann.location}</span>" if ann.location else ""
                    surface_info = f"<span style='color: #64748b; font-size: 13px; margin-right: 12px;'>📐 {ann.surface}</span>" if ann.surface else ""
                    rooms_info = f"<span style='color: #64748b; font-size: 13px;'>🚪 {ann.rooms}</span>" if ann.rooms else ""

                    card = f"""
                    <div style="background: #ffffff; border: 1px solid #e2e8f0; border-radius: 10px; padding: 16px; margin-bottom: 14px; box-shadow: 0 1px 3px rgba(0,0,0,0.05);">
                        <div style="display: flex; gap: 16px; align-items: flex-start;">
                            {img_block}
                            <div style="flex: 1; min-width: 0;">
                                <div style="display: flex; justify-content: space-between; align-items: baseline; margin-bottom: 6px;">
                                    <h3 style="margin: 0; font-size: 16px; font-weight: 600; color: #1e293b; line-height: 1.3;">
                                        {ann.title}
                                    </h3>
                                    <span style="background-color: #ecfdf5; color: #047857; font-weight: 700; font-size: 15px; padding: 4px 10px; border-radius: 6px; white-space: nowrap; margin-left: 12px;">
                                        {ann.price or 'Prix N/C'}
                                    </span>
                                </div>
                                <div style="margin-bottom: 12px;">
                                    {location_info}
                                    {surface_info}
                                    {rooms_info}
                                </div>
                                <div>
                                    <a href="{ann.url}" target="_blank" style="display: inline-block; background-color: #2563eb; color: #ffffff; text-decoration: none; font-size: 13px; font-weight: 600; padding: 8px 14px; border-radius: 6px;">
                                        Voir l'offre sur {ann.source or domain} &rarr;
                                    </a>
                                </div>
                            </div>
                        </div>
                    </div>
                    """
                    cards_html.append(card)

            section = f"""
            <div style="margin-bottom: 32px;">
                <div style="background-color: #f1f5f9; border-left: 4px solid #2563eb; padding: 12px 16px; border-radius: 0 8px 8px 0; margin-bottom: 16px;">
                    <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 8px;">
                        <div>
                            <strong style="color: #0f172a; font-size: 15px;">🌐 Source : {domain}</strong>
                            <span style="background-color: #e2e8f0; color: #334155; font-size: 12px; font-weight: 600; padding: 2px 8px; border-radius: 12px; margin-left: 8px;">
                                {offers_count} offre{'s' if offers_count > 1 else ''}
                            </span>
                        </div>
                        <a href="{url}" target="_blank" style="color: #2563eb; font-size: 13px; text-decoration: underline; font-weight: 500;">
                            Ouvrir la page de recherche complète &nearr;
                        </a>
                    </div>
                </div>
                {''.join(cards_html)}
            </div>
            """
            sections_html.append(section)

        html_body = f"""
        <!DOCTYPE html>
        <html lang="fr">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Rapport Veille Immobilière</title>
        </head>
        <body style="margin: 0; padding: 0; background-color: #f8fafc; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; color: #1e293b;">
            <div style="max-width: 680px; margin: 24px auto; background-color: #ffffff; border-radius: 12px; overflow: hidden; box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);">
                <!-- Entête du rapport -->
                <div style="background: linear-gradient(135deg, #1e3a8a 0%, #3b82f6 100%); padding: 32px 24px; text-align: center; color: #ffffff;">
                    <h1 style="margin: 0 0 8px 0; font-size: 24px; font-weight: 700; letter-spacing: -0.5px;">
                        🏡 Rapport Quotidien de Veille Immobilière
                    </h1>
                    <p style="margin: 0; font-size: 15px; opacity: 0.9;">
                        Synthèse du <strong>{date_str}</strong> &bull; <strong>{total_offers} nouvelle{'s' if total_offers > 1 else ''} annonce{'s' if total_offers > 1 else ''}</strong> détectée{'s' if total_offers > 1 else ''}
                    </p>
                </div>

                <!-- Corps du rapport -->
                <div style="padding: 24px;">
                    {''.join(sections_html)}
                </div>

                <!-- Pied de page -->
                <div style="background-color: #f8fafc; border-top: 1px solid #e2e8f0; padding: 16px 24px; text-align: center; font-size: 12px; color: #94a3b8;">
                    Veille immobilière automatisée 100% gratuite &bull; Généré automatiquement via GitHub Actions
                </div>
            </div>
        </body>
        </html>
        """
        return html_body

    def _send_email(self, subject: str, html_body: str, text_body: str) -> bool:
        """Se connecte au serveur SMTP et expédie l'e-mail."""
        logger.info("Connexion au serveur SMTP %s:%d...", self.smtp_host, self.smtp_port)

        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = self.email_from
        msg["To"] = self.email_to

        # Attacher le texte brut puis le HTML
        part_text = MIMEText(text_body, "plain", "utf-8")
        part_html = MIMEText(html_body, "html", "utf-8")
        msg.attach(part_text)
        msg.attach(part_html)

        recipients = [r.strip() for r in self.email_to.split(",") if r.strip()]

        try:
            if self.use_ssl:
                server = smtplib.SMTP_SSL(self.smtp_host, self.smtp_port, timeout=self.timeout)
            else:
                server = smtplib.SMTP(self.smtp_host, self.smtp_port, timeout=self.timeout)
                if self.use_tls:
                    server.starttls()

            if self.smtp_user and self.smtp_password:
                server.login(self.smtp_user, self.smtp_password)

            server.sendmail(self.email_from, recipients, msg.as_string())
            server.quit()

            logger.info("Rapport par e-mail envoyé avec succès à %s", self.email_to)
            return True

        except smtplib.SMTPAuthenticationError as err:
            logger.critical("Échec d'authentification SMTP : %s. Vérifiez SMTP_USER et SMTP_PASSWORD.", err)
            return False
        except smtplib.SMTPConnectError as err:
            logger.error("Impossible de se connecter au serveur SMTP : %s", err)
            return False
        except Exception as err:
            logger.error("Erreur inattendue lors de l'envoi de l'e-mail : %s", err, exc_info=True)
            return False
