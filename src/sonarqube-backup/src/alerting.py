"""Alerting across e-mail, generic webhook and Microsoft Teams.

stdlib only (smtplib + urllib) — no extra dependencies. Alerts are best-effort:
a failing channel is logged and never masks the backup's own outcome.
"""

from __future__ import annotations

import json
import logging
import smtplib
import urllib.request
from email.message import EmailMessage

from .config import Config

log = logging.getLogger(__name__)

# Ordering so we can compare against the configured threshold.
_LEVELS = {"all": 0, "info": 0, "warnings": 1, "warning": 1, "errors": 2, "error": 2}


def _should_send(cfg: Config, level: str) -> bool:
    if not cfg.alert_enabled or not cfg.alert_channels:
        return False
    threshold = _LEVELS.get(cfg.alert_level, 1)
    return _LEVELS.get(level, 2) >= threshold


class Alerter:
    def __init__(self, cfg: Config) -> None:
        self._cfg = cfg

    def notify(self, level: str, subject: str, body: str) -> None:
        if not _should_send(self._cfg, level):
            return
        for channel in self._cfg.alert_channels:
            try:
                if channel == "email":
                    self._email(subject, body)
                elif channel == "webhook":
                    self._webhook(level, subject, body)
                elif channel == "teams":
                    self._teams(level, subject, body)
                else:
                    log.warning("alert: unknown channel %r — skipped", channel)
            except Exception as exc:  # noqa: BLE001 — alerts must never raise
                log.warning("alert: channel %s failed: %s", channel, exc)

    # -- channels -------------------------------------------------------------

    def _email(self, subject: str, body: str) -> None:
        cfg = self._cfg
        if not (cfg.smtp_host and cfg.smtp_from and cfg.alert_email):
            log.warning("alert: email channel not fully configured — skipped")
            return
        msg = EmailMessage()
        msg["From"] = cfg.smtp_from
        msg["To"] = cfg.alert_email
        msg["Subject"] = subject
        msg.set_content(body)

        if cfg.smtp_secure == "ssl":
            smtp = smtplib.SMTP_SSL(cfg.smtp_host, cfg.smtp_port, timeout=30)
        else:
            smtp = smtplib.SMTP(cfg.smtp_host, cfg.smtp_port, timeout=30)
        with smtp:
            if cfg.smtp_secure == "starttls":
                smtp.starttls()
            if cfg.smtp_username:
                smtp.login(cfg.smtp_username, cfg.smtp_password)
            smtp.send_message(msg)

    def _post_json(self, url: str, payload: dict, headers: dict | None = None) -> None:
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(url, data=data, method="POST")
        req.add_header("Content-Type", "application/json")
        for key, value in (headers or {}).items():
            req.add_header(key, value)
        with urllib.request.urlopen(req, timeout=30) as resp:  # noqa: S310 — operator-supplied URL
            resp.read()

    def _webhook(self, level: str, subject: str, body: str) -> None:
        cfg = self._cfg
        if not cfg.webhook_url:
            return
        headers = {"X-Webhook-Secret": cfg.webhook_secret} if cfg.webhook_secret else None
        self._post_json(
            cfg.webhook_url,
            {"instance": cfg.instance_name, "level": level, "subject": subject, "body": body},
            headers,
        )

    def _teams(self, level: str, subject: str, body: str) -> None:
        cfg = self._cfg
        if not cfg.teams_webhook_url:
            return
        colour = {"errors": "D13438", "error": "D13438", "warnings": "F2C811"}.get(level, "2EB886")
        card = {
            "@type": "MessageCard",
            "@context": "https://schema.org/extensions",
            "themeColor": colour,
            "summary": subject,
            "title": f"[{cfg.instance_name}] {subject}",
            "text": body.replace("\n", "  \n"),
        }
        self._post_json(cfg.teams_webhook_url, card)
