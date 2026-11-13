"""Module de configuration centralisée de la journalisation (logging)."""

import logging
import sys
from typing import Optional


def setup_logger(name: str = "veille_immo", level: Optional[str] = None) -> logging.Logger:
    """Configure et retourne une instance de logger avec un formattage propre.

    Args:
        name: Nom du logger (par défaut: veille_immo)
        level: Niveau de log textuel (DEBUG, INFO, WARNING, ERROR).

    Returns:
        logging.Logger: Logger configuré.
    """
    logger = logging.getLogger(name)

    # Éviter d'ajouter plusieurs handlers si déjà configuré
    if logger.handlers:
        return logger

    log_level = getattr(logging, (level or "INFO").upper(), logging.INFO)
    logger.setLevel(log_level)

    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(log_level)

    formatter = logging.Formatter(
        fmt="[%(asctime)s] [%(levelname)-7s] [%(name)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)

    return logger
