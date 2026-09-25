"""Small, process-local settings sessions; no credentials in public snapshots."""
from __future__ import annotations

import secrets
import time
from threading import RLock


PRIVATE_STATE_FIELDS = {"finishPassword", "settingsPassword", "hotspotPassword"}


def public_data(value):
    if isinstance(value, dict):
        return {key: public_data(item) for key, item in value.items() if key not in PRIVATE_STATE_FIELDS}
    if isinstance(value, (list, tuple)):
        return [public_data(item) for item in value]
    return value


class SettingsSessions:
    def __init__(self, idle_seconds: float = 12 * 60 * 60) -> None:
        self.idle_seconds = idle_seconds
        self.tokens: dict[str, float] = {}
        self.lock = RLock()

    def issue(self) -> str:
        with self.lock:
            now = time.monotonic()
            self.tokens = {token: expiry for token, expiry in self.tokens.items() if expiry > now}
            # Bound abandoned sessions without adding a cleanup thread.
            if len(self.tokens) >= 128:
                self.tokens.pop(min(self.tokens, key=self.tokens.get))
            token = secrets.token_urlsafe(32)
            self.tokens[token] = now + self.idle_seconds
            return token

    def valid(self, token: str) -> bool:
        with self.lock:
            now = time.monotonic()
            if self.tokens.get(token, 0) <= now:
                self.tokens.pop(token, None)
                return False
            self.tokens[token] = now + self.idle_seconds
            return True

    def peek_valid(self, token: str) -> bool:
        """Check a session without extending its idle lifetime."""
        with self.lock:
            now = time.monotonic()
            if self.tokens.get(token, 0) <= now:
                self.tokens.pop(token, None)
                return False
            return True

    def revoke(self, token: str) -> None:
        with self.lock:
            self.tokens.pop(token, None)

    def keep_only(self, token: str) -> None:
        with self.lock:
            self.tokens = {token: self.tokens[token]} if token in self.tokens else {}
