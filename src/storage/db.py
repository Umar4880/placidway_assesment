"""
Dual-mode Database Manager: Turso (Cloud libSQL) and SQLite (Local).
Provides persistent storage for Lead Inquiries (NTH-4) and Content Gap Logging (NTH-5).
"""

from __future__ import annotations
import logging
import sqlite3
from datetime import datetime, timezone
from typing import List, Optional, Any, TYPE_CHECKING
import libsql_client
from src.utils.config import settings

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from src.orchestration.schemas import LeadSubmission, ContentGapItem



class DatabaseManager:
    """
    Manages database connections and CRUD operations across Turso and SQLite.
    Automatically switches to Turso Cloud when TURSO_DATABASE_URL is provided,
    otherwise falls back gracefully to local SQLite.
    """

    def __init__(self, db_path: Optional[str] = None):
        raw_url = settings.TURSO_DATABASE_URL.strip() if settings.TURSO_DATABASE_URL else ""
        if raw_url.startswith("turso://"):
            raw_url = "https://" + raw_url[len("turso://") :]
        elif raw_url.startswith("libsql://"):
            raw_url = "https://" + raw_url[len("libsql://") :]
        elif raw_url.startswith("http://"):
            raw_url = "https://" + raw_url[len("http://") :]

        self.turso_url = raw_url
        self.turso_token = settings.TURSO_AUTH_TOKEN.strip() if settings.TURSO_AUTH_TOKEN else ""
        self.local_db_path = str(db_path or settings.SQLITE_DB_PATH)
        self.is_turso = bool(self.turso_url and self.turso_token)

        # Ensure parent directory exists for local db
        settings.DATA_DIR.mkdir(parents=True, exist_ok=True)

        try:
            self.init_db()
            if self.is_turso:
                logger.info("DatabaseManager successfully connected to Turso Cloud at %s", self.turso_url)
            else:
                logger.info("DatabaseManager initialized with local SQLite at %s", self.local_db_path)
        except Exception as e:
            if self.is_turso:
                logger.warning(
                    "Turso Cloud connection failed (%s). Falling back to local SQLite at %s",
                    e,
                    self.local_db_path,
                )
                self.is_turso = False
                self.init_db()
            else:
                raise

    def _get_connection(self):
        """Return a Turso sync client or local sqlite3 connection."""
        if self.is_turso:
            try:
                return libsql_client.create_client_sync(self.turso_url, auth_token=self.turso_token)
            except Exception as e:
                logger.warning("Turso client connection failed: %s. Using local SQLite.", e)
                self.is_turso = False
                return sqlite3.connect(self.local_db_path)
        return sqlite3.connect(self.local_db_path)

    def init_db(self) -> None:
        """Create leads and content_gaps tables if they do not exist."""
        create_leads_sql = """
        CREATE TABLE IF NOT EXISTS leads (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT NOT NULL,
            treatment_interest TEXT NOT NULL,
            notes TEXT,
            session_id TEXT,
            created_at TEXT NOT NULL
        );
        """
        create_gaps_sql = """
        CREATE TABLE IF NOT EXISTS content_gaps (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            query TEXT NOT NULL,
            standalone_query TEXT,
            session_id TEXT,
            created_at TEXT NOT NULL
        );
        """

        if self.is_turso:
            with self._get_connection() as client:
                client.execute(create_leads_sql)
                client.execute(create_gaps_sql)
        else:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(create_leads_sql)
                cursor.execute(create_gaps_sql)
                conn.commit()

    def insert_lead(self, lead: LeadSubmission) -> int:
        """Store a patient lead submission."""
        now = datetime.now(timezone.utc).isoformat()
        sql = """
        INSERT INTO leads (name, email, treatment_interest, notes, session_id, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
        """
        params = [lead.name, lead.email, lead.treatment_interest, lead.notes or "", lead.session_id or "", now]

        if self.is_turso:
            with self._get_connection() as client:
                res = client.execute(sql, params)
                return getattr(res, "last_insert_rowid", 1)
        else:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(sql, params)
                conn.commit()
                return cursor.lastrowid or 1

    def save_lead(self, lead: LeadSubmission) -> int:
        """Alias for insert_lead."""
        return self.insert_lead(lead)

    def get_leads(self, limit: int = 50) -> List[Any]:
        """Fetch saved patient leads."""
        from src.orchestration.schemas import LeadSubmission

        sql = "SELECT name, email, treatment_interest, notes, session_id FROM leads ORDER BY id DESC LIMIT ?"
        leads: List[LeadSubmission] = []

        if self.is_turso:
            with self._get_connection() as client:
                res = client.execute(sql, [limit])
                for row in res.rows:
                    leads.append(LeadSubmission(
                        name=row[0],
                        email=row[1],
                        treatment_interest=row[2],
                        notes=row[3],
                        session_id=row[4]
                    ))
        else:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(sql, (limit,))
                for row in cursor.fetchall():
                    leads.append(LeadSubmission(
                        name=row[0],
                        email=row[1],
                        treatment_interest=row[2],
                        notes=row[3],
                        session_id=row[4]
                    ))
        return leads

    save_lead = insert_lead

    def save_content_gap(self, gap: Any) -> int:
        """Alias accepting ContentGapItem or query string."""
        if hasattr(gap, "query"):
            return self.log_content_gap(
                query=gap.query,
                standalone_query=getattr(gap, "standalone_query", None),
                session_id=getattr(gap, "session_id", None),
            )
        return self.log_content_gap(query=str(gap))

    def log_content_gap(self, query: str, standalone_query: Optional[str] = None, session_id: Optional[str] = None) -> int:
        """Log an unanswered query to content gaps table."""
        now = datetime.now(timezone.utc).isoformat()
        sql = """
        INSERT INTO content_gaps (query, standalone_query, session_id, created_at)
        VALUES (?, ?, ?, ?)
        """
        params = [query, standalone_query or "", session_id or "", now]

        if self.is_turso:
            with self._get_connection() as client:
                res = client.execute(sql, params)
                return getattr(res, "last_insert_rowid", 1)
        else:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(sql, params)
                conn.commit()
                return cursor.lastrowid or 1

    def get_content_gaps(self, limit: int = 50) -> List[Any]:
        """Fetch logged content gaps."""
        from src.orchestration.schemas import ContentGapItem

        sql = "SELECT id, query, standalone_query, session_id, created_at FROM content_gaps ORDER BY id DESC LIMIT ?"
        gaps: List[ContentGapItem] = []

        if self.is_turso:
            with self._get_connection() as client:
                res = client.execute(sql, [limit])
                for row in res.rows:
                    gaps.append(ContentGapItem(
                        id=row[0],
                        query=row[1],
                        standalone_query=row[2],
                        session_id=row[3],
                        timestamp=row[4]
                    ))
        else:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(sql, (limit,))
                for row in cursor.fetchall():
                    gaps.append(ContentGapItem(
                        id=row[0],
                        query=row[1],
                        standalone_query=row[2],
                        session_id=row[3],
                        timestamp=row[4]
                    ))
        return gaps


# Singleton instance
db_manager = DatabaseManager()
