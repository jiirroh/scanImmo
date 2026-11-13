"""Serveur Web léger pour l'interface de configuration des sites surveillés.

Fournit une interface utilisateur moderne et réactive (HTML/Tailwind/JS)
pour gérer les recherches immobilières, activer/désactiver des sites et
tester le scraping en temps réel, sans aucune dépendance externe lourde.
"""

from dataclasses import asdict
from http.server import HTTPServer, BaseHTTPRequestHandler
import json
from pathlib import Path
import sys
from urllib.parse import parse_qs, urlparse
import webbrowser

# Inclusion de la racine du projet dans le chemin
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.config import DATA_FILE, SITES_CONFIG_FILE
from src.logger import setup_logger
from src.main import run_email_test
from src.scraper.generic import get_scraper_for_url
from src.storage.json_storage import JsonStorage

logger = setup_logger("web.server")
TEMPLATE_PATH = PROJECT_ROOT / "public" / "index.html"
if not TEMPLATE_PATH.exists():
    TEMPLATE_PATH = PROJECT_ROOT / "src" / "templates" / "index.html"


def load_sites_config() -> dict:
    """Charge le fichier data/sites_config.json ou initialise une structure par défaut."""
    if not SITES_CONFIG_FILE.exists():
        initial = {"version": "1.0", "sites": []}
        save_sites_config(initial)
        return initial
    try:
        with open(SITES_CONFIG_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as err:
        logger.error("Erreur lors de la lecture de sites_config.json : %s", err)
        return {"version": "1.0", "sites": []}


def save_sites_config(data: dict) -> bool:
    """Persiste le fichier data/sites_config.json."""
    try:
        SITES_CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
        temp_path = SITES_CONFIG_FILE.with_suffix(".tmp")
        with open(temp_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        import os
        os.replace(temp_path, SITES_CONFIG_FILE)
        return True
    except Exception as err:
        logger.error("Erreur lors de l'enregistrement de sites_config.json : %s", err)
        return False


class ConfigRequestHandler(BaseHTTPRequestHandler):
    """Gestionnaire de requêtes HTTP pour l'interface de gestion."""

    def _send_json(self, data: dict, status: int = 200) -> None:
        """Envoie une réponse JSON formatée."""
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _read_json_body(self) -> dict:
        """Lit et analyse le corps de requête JSON."""
        content_length = int(self.headers.get("Content-Length", 0))
        if content_length == 0:
            return {}
        raw = self.rfile.read(content_length).decode("utf-8")
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return {}

    def do_GET(self) -> None:
        """Traite les requêtes GET."""
        parsed_url = urlparse(self.path)
        path = parsed_url.path

        if path in ("/", "/index.html"):
            if not TEMPLATE_PATH.exists():
                self.send_error(404, "Page non trouvée")
                return
            html_bytes = TEMPLATE_PATH.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(html_bytes)))
            self.end_headers()
            self.wfile.write(html_bytes)

        elif path == "/api/sites":
            config = load_sites_config()
            self._send_json(config)

        elif path == "/api/stats":
            storage = JsonStorage(DATA_FILE)
            self._send_json({
                "total_seen": storage.total_count,
                "metadata": storage.metadata,
            })

        else:
            self.send_error(404, "Ressource non trouvée")

    def do_POST(self) -> None:
        """Traite les requêtes POST."""
        path = urlparse(self.path).path
        data = self._read_json_body()

        if path == "/api/sites":
            # Ajouter ou mettre à jour un site
            config = load_sites_config()
            sites = config.get("sites", [])
            site_id = data.get("id")

            existing_idx = next((i for i, s in enumerate(sites) if s.get("id") == site_id), None)
            if existing_idx is not None:
                sites[existing_idx] = data
            else:
                sites.append(data)

            config["sites"] = sites
            success = save_sites_config(config)
            self._send_json({"success": success, "site": data})

        elif path == "/api/sites/toggle":
            # Activer ou désactiver une recherche
            site_id = data.get("id")
            enabled = data.get("enabled", True)
            config = load_sites_config()
            for s in config.get("sites", []):
                if s.get("id") == site_id:
                    s["enabled"] = enabled
                    break
            save_sites_config(config)
            self._send_json({"success": True})

        elif path == "/api/test-scrape":
            # Lancer un test de scraping sur une URL spécifique
            url = data.get("url", "").strip()
            if not url:
                self._send_json({"error": "URL manquante"}, status=400)
                return

            try:
                scraper = get_scraper_for_url(url)
                results = scraper.scrape(url)
                payload = [asdict(ann) for ann in results]
                self._send_json({
                    "success": True,
                    "url": url,
                    "count": len(payload),
                    "announcements": payload,
                })
            except Exception as err:
                logger.error("Erreur test scraping (%s) : %s", url, err, exc_info=True)
                self._send_json({"success": False, "error": str(err)}, status=500)

        elif path == "/api/test-email":
            # Déclencher un envoi d'e-mail de test
            exit_code = run_email_test()
            self._send_json({"success": exit_code == 0})

        elif path == "/api/trigger-run":
            # Exécution locale immédiate en arrière-plan
            import threading
            from src.main import main as run_main
            threading.Thread(target=run_main, daemon=True).start()
            self._send_json({"success": True, "message": "Veille lancée avec succès en local !"})

        else:
            self.send_error(404, "Action non trouvée")

    def do_DELETE(self) -> None:
        """Traite les requêtes DELETE."""
        path = urlparse(self.path).path
        data = self._read_json_body()

        if path == "/api/sites":
            site_id = data.get("id")
            config = load_sites_config()
            config["sites"] = [s for s in config.get("sites", []) if s.get("id") != site_id]
            success = save_sites_config(config)
            self._send_json({"success": success})
        else:
            self.send_error(404, "Action non trouvée")

    def log_message(self, format, *args):
        """Redirige les logs HTTP vers le logger centralisé."""
        logger.debug("%s - - [%s] %s", self.address_string(), self.log_date_time_string(), format % args)


def run_server(port: int = 8080, open_browser: bool = True) -> None:
    """Démarre le serveur HTTP local."""
    server_address = ("", port)
    try:
        httpd = HTTPServer(server_address, ConfigRequestHandler)
    except OSError:
        # En cas de port occupé, tenter 8081
        port = 8081
        server_address = ("", port)
        httpd = HTTPServer(server_address, ConfigRequestHandler)

    url = f"http://localhost:{port}"
    print("=" * 65)
    print(f"🚀 INTERFACE DE CONFIGURATION ACTIVE : {url}")
    print("   Gérez vos recherches immobilières et testez les scrapers.")
    print("   Appuyez sur Ctrl+C pour arrêter le serveur.")
    print("=" * 65)

    if open_browser:
        webbrowser.open(url)

    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nArrêt du serveur web.")
        httpd.server_close()


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Serveur Web de configuration de la veille")
    parser.add_argument("--port", type=int, default=8080, help="Port HTTP d'écoute")
    parser.add_argument("--no-browser", action="store_true", help="Ne pas ouvrir automatiquement le navigateur")
    args = parser.parse_args()

    run_server(port=args.port, open_browser=not args.no_browser)
