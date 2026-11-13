"""Module de notification externe (Telegram & E-mail)."""

from .telegram import TelegramNotifier, escape_markdown_v2
from .email_notifier import EmailNotifier

__all__ = ["TelegramNotifier", "escape_markdown_v2", "EmailNotifier"]
