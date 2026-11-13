"""Service de stockage et de persistance des annonces déjà vues.

Ce module gère la lecture et l'écriture du fichier `data/seen_announcements.json`.
L'écriture se fait de manière atomique (via un fichier temporaire puis remplacement)
afin d'éviter toute corruption en cas d'interruption du processus.
"""

from datetime import datetime, timezone
import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.logger import setup_logger

logger = setup_logger("storage")


class JsonStorage:
    """Gestionnaire de persistance JSON pour les annonces immobilières."""

    def __init__(self, file_path: Path):
        """Initialise le gestionnaire de stockage.

        Args:
            file_path: Chemin vers le fichier JSON de stockage.
        """
        self.file_path = Path(file_path)
        self.seen_data: Dict[str, Any] = {}
        self.metadata: Dict[str, Any] = {}
        self._newly_added_count = 0
        self._load()

    def _load(self) -> None:
        """Charge l'état depuis le fichier JSON s'il existe, ou initialise une structure vide."""
        if not self.file_path.exists():
            logger.info("Fichier de stockage non existant, initialisation d'un nouvel état : %s", self.file_path)
            self._init_empty_state()
            return

        try:
            with open(self.file_path, "r", encoding="utf-8") as f:
                content = json.load(f)
                self.metadata = content.get("metadata", {})
                self.seen_data = content.get("seen_ids", {})
                logger.info(
                    "État chargé avec succès depuis %s (%d annonces connues).",
                    self.file_path.name,
                    len(self.seen_data),
                )
        except (json.JSONDecodeError, OSError) as err:
            logger.error(
                "Erreur lors de la lecture du fichier de stockage (%s). Sauvegarde d'un backup et réinitialisation.",
                err,
            )
            # Sauvegarder une copie corrompue pour inspection
            backup_path = self.file_path.with_suffix(f".corrupt.{int(datetime.now().timestamp())}.json")
            try:
                if self.file_path.exists():
                    os.replace(self.file_path, backup_path)
                    logger.warning("Fichier corrompu déplacé vers %s", backup_path)
            except OSError:
                pass
            self._init_empty_state()

    def _init_empty_state(self) -> None:
        """Crée la structure initiale par défaut."""
        self.metadata = {
            "version": "1.0",
            "last_updated": None,
            "total_seen": 0,
        }
        self.seen_data = {}

    def is_seen(self, announcement_id: str) -> bool:
        """Vérifie si un identifiant d'annonce a déjà été traité.

        Args:
            announcement_id: Identifiant unique de l'annonce.

        Returns:
            bool: True si déjà vue, False sinon.
        """
        if not announcement_id:
            return False
        return str(announcement_id) in self.seen_data

    def mark_seen(
        self,
        announcement_id: str,
        title: Optional[str] = None,
        price: Optional[str] = None,
        url: Optional[str] = None,
        source: Optional[str] = None,
    ) -> bool:
        """Enregistre une annonce comme vue en mémoire.

        Args:
            announcement_id: ID unique de l'annonce.
            title: Titre de l'annonce.
            price: Prix formaté.
            url: URL complète de l'annonce.
            source: Nom du site source.

        Returns:
            bool: True si nouvellement ajoutée, False si déjà présente.
        """
        clean_id = str(announcement_id).strip()
        if not clean_id:
            return False

        if clean_id in self.seen_data:
            return False

        self.seen_data[clean_id] = {
            "first_seen": datetime.now(timezone.utc).isoformat(),
            "title": title or "",
            "price": price or "",
            "url": url or "",
            "source": source or "",
        }
        self._newly_added_count += 1
        return True

    def filter_unseen(self, announcements: List[Any]) -> List[Any]:
        """Filtre une liste d'annonces pour ne conserver que celles jamais vues.

        Args:
            announcements: Liste d'objets (possédant l'attribut `id`) ou de dictionnaires (clé `id`).

        Returns:
            List[Any]: Liste des annonces non encore enregistrées.
        """
        unseen = []
        for item in announcements:
            item_id = getattr(item, "id", None) if hasattr(item, "id") else item.get("id")
            if item_id and not self.is_seen(str(item_id)):
                unseen.append(item)
        return unseen

    def save(self) -> bool:
        """Sauvegarde atomique de l'état dans le fichier JSON.

        Utilise un fichier temporaire puis le renomme (`os.replace`) afin
        d'assurer l'atomicité et d'éviter les fichiers corrompus en cas de crash.

        Returns:
            bool: True si la sauvegarde a réussi, False sinon.
        """
        try:
            # S'assurer que le dossier parent existe
            self.file_path.parent.mkdir(parents=True, exist_ok=True)

            self.metadata["last_updated"] = datetime.now(timezone.utc).isoformat()
            self.metadata["total_seen"] = len(self.seen_data)

            payload = {
                "metadata": self.metadata,
                "seen_ids": self.seen_data,
            }

            temp_path = self.file_path.with_suffix(".tmp")
            with open(temp_path, "w", encoding="utf-8") as f:
                json.dump(payload, f, ensure_ascii=False, indent=2)

            os.replace(temp_path, self.file_path)
            logger.info(
                "État persisté avec succès dans %s (%d annonces totales, +%d nouvelles).",
                self.file_path.name,
                len(self.seen_data),
                self._newly_added_count,
            )
            self._newly_added_count = 0
            return True
        except OSError as err:
            logger.error("Échec de la sauvegarde de l'état dans %s : %s", self.file_path, err)
            return False

    @property
    def total_count(self) -> int:
        """Retourne le nombre total d'annonces mémorisées."""
        return len(self.seen_data)
