"""
Session Security and Browser Authentication Module
Sprint 23 — Enterprise-Grade Security Hardening, Multi-Process Concurrency & Operational Readiness

Eliminates raw operator token injection in browser JavaScript:
- Generates server-managed session tokens stored in HttpOnly, SameSite=Strict cookies.
- Cryptographically strong CSRF protection for all state-changing mutations.
- Constant-time verification, session fixation prevention, and bounded TTL expiration.
- Complete revocation support on logout or credential rotation.
"""

from __future__ import annotations

import hashlib
import hmac
import os
import re
import secrets
import sqlite3
import sys
import tempfile
import threading
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from coin_behavior_engine.product.credential_manager import CredentialManager


@dataclass
class SessionRecord:
    session_id: str
    csrf_token: str
    client_ip: str
    user_agent: str
    created_at_utc: str
    last_active_utc: str
    expires_at_utc: str
    is_revoked: bool = False

    def is_expired(self) -> bool:
        try:
            dt = datetime.fromisoformat(self.expires_at_utc.replace("Z", "+00:00"))
            return datetime.now(timezone.utc) > dt
        except Exception:
            return True


class SqliteSessionStore:
    """
    Shared SQLite session store operating in WAL mode with busy timeout handling.
    Enforces process-safe transactional semantics across multiple worker processes.
    Stores cryptographically secure hashes of session tokens, never plaintext tokens.
    """

    def __init__(self, db_path: Optional[str | Path] = None):
        if db_path:
            self.db_path = Path(db_path)
        else:
            env_path = os.environ.get("CBE_SESSION_DB_PATH")
            if env_path:
                self.db_path = Path(env_path)
            elif os.environ.get("CBE_ENV", "staging").lower() in ("staging", "production"):
                self.db_path = Path("/app/data/prospective/sessions.db")
            else:
                self.db_path = Path(tempfile.gettempdir()) / "cbe_sessions.db"

        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path), timeout=5.0, isolation_level=None)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA busy_timeout=5000;")
        conn.execute("PRAGMA synchronous=NORMAL;")
        return conn

    def _init_db(self) -> None:
        with self._get_connection() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS sessions (
                    session_id_hash TEXT PRIMARY KEY,
                    csrf_token TEXT NOT NULL,
                    client_ip TEXT NOT NULL,
                    user_agent TEXT NOT NULL,
                    created_at_utc TEXT NOT NULL,
                    last_active_utc TEXT NOT NULL,
                    expires_at_utc TEXT NOT NULL,
                    is_revoked INTEGER NOT NULL DEFAULT 0
                );
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_sessions_expires ON sessions(expires_at_utc);")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_sessions_revoked ON sessions(is_revoked);")

    @staticmethod
    def hash_token(token: str) -> str:
        return hashlib.sha256(token.encode("utf-8")).hexdigest()

    def save_session(self, record: SessionRecord) -> None:
        h = self.hash_token(record.session_id)
        with self._get_connection() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO sessions
                (session_id_hash, csrf_token, client_ip, user_agent, created_at_utc, last_active_utc, expires_at_utc, is_revoked)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?);
                """,
                (
                    h,
                    record.csrf_token,
                    record.client_ip,
                    record.user_agent,
                    record.created_at_utc,
                    record.last_active_utc,
                    record.expires_at_utc,
                    1 if record.is_revoked else 0,
                ),
            )
            # Bounded capacity: purge expired when total rows exceed 500
            cur = conn.execute("SELECT count(*) as cnt FROM sessions;")
            row = cur.fetchone()
            if row and row["cnt"] > 500:
                now_iso = datetime.now(timezone.utc).isoformat()
                conn.execute("DELETE FROM sessions WHERE expires_at_utc < ?;", (now_iso,))

    def get_session(self, session_id: str) -> Optional[SessionRecord]:
        h = self.hash_token(session_id)
        with self._get_connection() as conn:
            cur = conn.execute(
                """
                SELECT csrf_token, client_ip, user_agent, created_at_utc, last_active_utc, expires_at_utc, is_revoked
                FROM sessions WHERE session_id_hash = ?;
                """,
                (h,),
            )
            row = cur.fetchone()
            if not row:
                return None
            return SessionRecord(
                session_id=session_id,
                csrf_token=row["csrf_token"],
                client_ip=row["client_ip"],
                user_agent=row["user_agent"],
                created_at_utc=row["created_at_utc"],
                last_active_utc=row["last_active_utc"],
                expires_at_utc=row["expires_at_utc"],
                is_revoked=bool(row["is_revoked"]),
            )

    def touch_session(self, session_id: str) -> None:
        h = self.hash_token(session_id)
        now_iso = datetime.now(timezone.utc).isoformat()
        with self._get_connection() as conn:
            conn.execute("UPDATE sessions SET last_active_utc = ? WHERE session_id_hash = ?;", (now_iso, h))

    def revoke_session(self, session_id: str) -> bool:
        h = self.hash_token(session_id)
        with self._get_connection() as conn:
            cur = conn.execute("UPDATE sessions SET is_revoked = 1 WHERE session_id_hash = ? AND is_revoked = 0;", (h,))
            return cur.rowcount > 0

    def revoke_all_sessions(self) -> int:
        with self._get_connection() as conn:
            cur = conn.execute("UPDATE sessions SET is_revoked = 1 WHERE is_revoked = 0;")
            return cur.rowcount

    def cleanup_expired_sessions(self) -> int:
        now_iso = datetime.now(timezone.utc).isoformat()
        with self._get_connection() as conn:
            cur = conn.execute("DELETE FROM sessions WHERE expires_at_utc < ?;", (now_iso,))
            return cur.rowcount

    def get_total_sessions(self) -> int:
        with self._get_connection() as conn:
            cur = conn.execute("SELECT count(*) as cnt FROM sessions WHERE is_revoked = 0;")
            row = cur.fetchone()
            return row["cnt"] if row else 0


class SessionManager:
    """Thread-safe and multi-worker process-aware server session manager backed by SQLite WAL storage."""

    DEFAULT_TTL_SECONDS = 3600  # 1 hour
    SESSION_COOKIE_NAME = "cbe_session_id"
    CSRF_HEADER_NAME = "x-csrf-token"

    def __init__(self, db_path: Optional[str | Path] = None):
        self.store = SqliteSessionStore(db_path=db_path)
        self._lock = threading.Lock()

    @property
    def _sessions(self) -> Dict[str, Any]:
        """Backward compatibility view for active sessions inspection."""
        class _SessionProxy(dict):
            def __init__(self, store: SqliteSessionStore):
                self._store = store
            def __len__(self):
                return self._store.get_total_sessions()
            def __bool__(self):
                return self._store.get_total_sessions() > 0
        return _SessionProxy(self.store)

    def create_session(
        self,
        operator_token: str,
        client_ip: str = "127.0.0.1",
        user_agent: str = "Unknown",
        ttl_seconds: int = DEFAULT_TTL_SECONDS,
    ) -> SessionRecord:
        """
        Exchanges a verified operator token for a secure authenticated session record.
        Raises PermissionError if token is invalid or revoked.
        """
        valid, reason = CredentialManager.verify_operator_token(operator_token)
        if not valid:
            raise PermissionError(f"AUTHENTICATION_FAILED: {reason}")

        now = datetime.now(timezone.utc)
        expires_at = datetime.fromtimestamp(now.timestamp() + ttl_seconds, tz=timezone.utc)

        session_id = secrets.token_urlsafe(32)
        csrf_token = secrets.token_urlsafe(32)

        record = SessionRecord(
            session_id=session_id,
            csrf_token=csrf_token,
            client_ip=client_ip,
            user_agent=user_agent[:128],
            created_at_utc=now.isoformat(),
            last_active_utc=now.isoformat(),
            expires_at_utc=expires_at.isoformat(),
            is_revoked=False,
        )

        with self._lock:
            self.store.save_session(record)

        return record

    def validate_session(
        self,
        session_id: Optional[str],
        csrf_token: Optional[str] = None,
        client_ip: Optional[str] = None,
        check_csrf: bool = False,
    ) -> Tuple[bool, str, Optional[SessionRecord]]:
        """
        Validates session validity, expiration, revocation, and optional CSRF match across worker processes.
        """
        if not session_id or not isinstance(session_id, str):
            return False, "SESSION_ID_MISSING", None

        with self._lock:
            record = self.store.get_session(session_id)

        if not record:
            return False, "SESSION_NOT_FOUND", None

        if record.is_revoked:
            return False, "SESSION_REVOKED", None

        if record.is_expired():
            return False, "SESSION_EXPIRED", None

        # CSRF Protection for state-changing operations
        if check_csrf:
            if not csrf_token or not isinstance(csrf_token, str):
                return False, "CSRF_TOKEN_MISSING", None
            if not hmac.compare_digest(csrf_token.strip().encode("utf-8"), record.csrf_token.encode("utf-8")):
                return False, "CSRF_TOKEN_MISMATCH", None

        # Update last active timestamp
        with self._lock:
            self.store.touch_session(session_id)

        return True, "SESSION_VALID", record

    def revoke_session(self, session_id: str) -> bool:
        """Revokes an active session across all worker processes."""
        with self._lock:
            return self.store.revoke_session(session_id)

    def revoke_all_sessions(self) -> int:
        """Revokes all active sessions across all worker processes."""
        with self._lock:
            return self.store.revoke_all_sessions()

    @classmethod
    def extract_session_id(cls, headers: Optional[Dict[str, str]]) -> Optional[str]:
        """Extracts session ID from Cookie header or X-Session-ID header."""
        if not headers:
            return None
        hdr_map = {k.lower(): v for k, v in headers.items()}

        # 1. From X-Session-ID header
        if "x-session-id" in hdr_map:
            return hdr_map["x-session-id"].strip()

        # 2. From Cookie header
        cookie_str = hdr_map.get("cookie", "")
        if cookie_str:
            match = re.search(r"(?:^|;\s*)" + re.escape(cls.SESSION_COOKIE_NAME) + r"=([^;]+)", cookie_str)
            if match:
                return match.group(1).strip()

        return None

    @classmethod
    def extract_csrf_token(cls, headers: Optional[Dict[str, str]]) -> Optional[str]:
        """Extracts CSRF token from headers."""
        if not headers:
            return None
        hdr_map = {k.lower(): v for k, v in headers.items()}
        return hdr_map.get(cls.CSRF_HEADER_NAME)

    @classmethod
    def build_set_cookie_header(
        cls,
        session_id: str,
        max_age: int = DEFAULT_TTL_SECONDS,
        secure: bool = False,
    ) -> str:
        """Builds an HttpOnly, SameSite=Strict Set-Cookie header string."""
        parts = [
            f"{cls.SESSION_COOKIE_NAME}={session_id}",
            "Path=/",
            "HttpOnly",
            "SameSite=Strict",
            f"Max-Age={max_age}",
        ]
        if secure:
            parts.append("Secure")
        return "; ".join(parts)

    @classmethod
    def build_clear_cookie_header(cls) -> str:
        """Builds an expiration Set-Cookie header to clear session on client."""
        return f"{cls.SESSION_COOKIE_NAME}=; Path=/; HttpOnly; SameSite=Strict; Max-Age=0"


# Global singleton instance
session_manager = SessionManager()
