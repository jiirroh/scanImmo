"""Handler Serverless Vercel pour l'API de gestion des sites immobiliers.

Compatible avec l'environnement Vercel Serverless (classe handler héritant de BaseHTTPRequestHandler)
et avec l'exécution locale.
Gère la lecture et la mise à jour de data/sites_config.json soit localement,
soit directement via l'API GitHub (permettant la mise à jour depuis un smartphone sur Vercel).
"""

import base64
from dataclasses import asdict
from http.server import BaseHTTPRequestHandler
import json
import os
from pathlib import Path
import sys
from urllib.parse import urlparse
import requests

# Inclusion de la racine du projet dans sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.scraper.generic import get_scraper_for_url

GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "").strip()
GITHUB_REPO = os.getenv("GITHUB_REPO", "").strip()  # Format: "pseudo/nom-du-repo"
LOCAL_CONFIG_FILE = PROJECT_ROOT / "data" / "sites_config.json"


def get_github_headers() -> dict:
    return {
        "Authorization": f"Bearer {GITHUB_TOKEN}",
        "Accept": "application/vnd.github.v3+json",
        "User-Agent": "VeilleImmo-Vercel",
    }


def get_sites_config() -> tuple[dict, str]:
    """Récupère la configuration des sites (soit via GitHub API si sur Vercel, soit en local).

    Returns:
        tuple[dict, str]: (contenu_json, sha_du_fichier_si_github)
    """
    if GITHUB_TOKEN and GITHUB_REPO:
        api_url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/data/sites_config.json"
        try:
            resp = requests.get(api_url, headers=get_github_headers(), timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                raw_bytes = base64.b64decode(data.get("content", ""))
                parsed = json.loads(raw_bytes.decode("utf-8"))
                return parsed, data.get("sha", "")
        except Exception:
            pass

    # Repli sur le fichier local
    if LOCAL_CONFIG_FILE.exists():
        try:
            with open(LOCAL_CONFIG_FILE, "r", encoding="utf-8") as f:
                return json.load(f), ""
        except Exception:
            pass

    return {
        "version": "1.0",
        "sites": [
            {
                "id": "pap-rennes-maisons",
                "name": "PAP - Maisons Rennes & alentours",
                "portal": "PAP",
                "url": "https://www.pap.fr/annonce/vente-maisons-rennes-35000-g43564",
                "enabled": True,
                "location": "Rennes (35000)",
            }
        ],
    }, ""


def save_sites_config(new_config: dict) -> bool:
    """Sauvegarde la configuration (commit GitHub sur Vercel ou écriture locale)."""
    # Si les variables GitHub sont configurées sur Vercel : commit via l'API GitHub
    if GITHUB_TOKEN and GITHUB_REPO:
        api_url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/data/sites_config.json"
        try:
            # 1. Récupérer le SHA actuel du fichier
            sha = ""
            get_resp = requests.get(api_url, headers=get_github_headers(), timeout=10)
            if get_resp.status_code == 200:
                sha = get_resp.json().get("sha", "")

            # 2. Encoder le nouveau contenu JSON en base64
            content_str = json.dumps(new_config, ensure_ascii=False, indent=2)
            content_b64 = base64.b64encode(content_str.encode("utf-8")).decode("utf-8")

            payload = {
                "message": "chore(config): mise à jour des sites surveillés [skip ci]",
                "content": content_b64,
            }
            if sha:
                payload["sha"] = sha

            put_resp = requests.put(api_url, json=payload, headers=get_github_headers(), timeout=10)
            return put_resp.status_code in (200, 201)
        except Exception:
            return False

    # Sinon écriture locale
    try:
        LOCAL_CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(LOCAL_CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(new_config, f, ensure_ascii=False, indent=2)
        return True
    except Exception:
        return False


def trigger_github_workflow() -> tuple[bool, str]:
    """Déclenche l'exécution immédiate de la veille immobilière sur GitHub Actions."""
    if not GITHUB_TOKEN or not GITHUB_REPO:
        return False, "GITHUB_TOKEN ou GITHUB_REPO non configuré dans les variables d'environnement Vercel."

    api_url = f"https://api.github.com/repos/{GITHUB_REPO}/actions/workflows/scraper.yml/dispatches"
    payload = {"ref": "main", "inputs": {"channel": "email"}}

    try:
        resp = requests.post(api_url, json=payload, headers=get_github_headers(), timeout=10)
        if resp.status_code == 204:
            return True, "Veille déclenchée avec succès sur GitHub Actions !"
        return False, f"Code HTTP GitHub : {resp.status_code} ({resp.text})"
    except Exception as err:
        return False, f"Erreur réseau : {err}"


class handler(BaseHTTPRequestHandler):
    """Point d'entrée Serverless pour Vercel."""

    def _send_json(self, data: dict, status: int = 200) -> None:
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, DELETE, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _read_json_body(self) -> dict:
        content_length = int(self.headers.get("Content-Length", 0))
        if content_length == 0:
            return {}
        raw = self.rfile.read(content_length).decode("utf-8")
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return {}

    def do_OPTIONS(self) -> None:
        """Gère les requêtes préliminaires CORS."""
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, DELETE, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self) -> None:
        path = urlparse(self.path).path

        if path.startswith("/api/sites"):
            config, _ = get_sites_config()
            self._send_json(config)

        elif path.startswith("/api/stats"):
            total_seen = 0
            seen_file = PROJECT_ROOT / "data" / "seen_announcements.json"
            if seen_file.exists():
                try:
                    with open(seen_file, "r", encoding="utf-8") as f:
                        data = json.load(f)
                        total_seen = len(data.get("seen_ids", {}))
                except Exception:
                    pass

            self._send_json({
                "total_seen": total_seen,
                "is_vercel": bool(os.getenv("VERCEL")),
                "github_connected": bool(GITHUB_TOKEN and GITHUB_REPO),
            })

        else:
            self._send_json({"error": "Route inconnue"}, status=404)

    def do_POST(self) -> None:
        path = urlparse(self.path).path
        data = self._read_json_body()

        if path.startswith("/api/sites/toggle"):
            site_id = data.get("id")
            enabled = data.get("enabled", True)
            config, _ = get_sites_config()
            for s in config.get("sites", []):
                if s.get("id") == site_id:
                    s["enabled"] = enabled
                    break
            success = save_sites_config(config)
            self._send_json({"success": success})

        elif path.startswith("/api/sites"):
            config, _ = get_sites_config()
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

        elif path.startswith("/api/test-scrape"):
            url = data.get("url", "").strip()
            if not url:
                self._send_json({"error": "URL requise"}, status=400)
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
                self._send_json({"success": False, "error": str(err)}, status=500)

        elif path.startswith("/api/trigger-run"):
            success, message = trigger_github_workflow()
            self._send_json({"success": success, "message": message})

        else:
            self._send_json({"error": "Action inconnue"}, status=404)

    def do_DELETE(self) -> None:
        path = urlparse(self.path).path
        data = self._read_json_body()

        if path.startswith("/api/sites"):
            site_id = data.get("id")
            config, _ = get_sites_config()
            config["sites"] = [s for s in config.get("sites", []) if s.get("id") != site_id]
            success = save_sites_config(config)
            self._send_json({"success": success})
        else:
            self._send_json({"error": "Action inconnue"}, status=404)
