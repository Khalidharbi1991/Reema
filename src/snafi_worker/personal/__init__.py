"""Personal services (mail, calendar, files) behind their own adapters. See base.py."""

from . import fake  # noqa: F401  (registers the fake providers for tests)
from .base import (Calendar, Draft, Event, FileInfo, Files, Mail, MailMessage, MailSummary,  # noqa: F401
                   NotConnected, ServiceError)
