"""
titan.links.store

واجهة التخزين لـ Message Links Protocol.

MessageStore: Protocol يحدد العمليات المطلوبة لـ Identity Layer.
SqliteMessageStore: التطبيق الافتراضي — SQLite محلي، صفر تهيئة.
"""

from __future__ import annotations

import asyncio
import os
import sqlite3
import threading
from datetime import datetime, timezone
from typing import Any

from titan.links.identity import TitanMessageIdentity


class MessageStore:
    """
    واجهة التخزين المطلوبة لـ Identity Layer.

    يمكن استبدال التطبيق الافتراضي (SqliteMessageStore) بأي تطبيق
    يُلبي هذه الواجهة عبر bot.links.set_store(custom_store).

    ملاحظة: Archive Layer في v1 تعمل مع SqliteMessageStore فقط.
    دعم custom stores للأرشيف مخطط لإصدار مستقبلي.
    """

    async def save_identity(
        self,
        bot_username: str,
        chat_id: int,
        telegram_message_id: int,
    ) -> TitanMessageIdentity:
        """حفظ هوية رسالة جديدة وإعادة الهوية مع titan_id المُولَّد."""
        raise NotImplementedError

    async def get_by_titan_id(
        self,
        titan_id: int,
    ) -> TitanMessageIdentity | None:
        """جلب هوية رسالة بمعرفها Titan."""
        raise NotImplementedError

    async def get_by_telegram_id(
        self,
        chat_id: int,
        telegram_message_id: int,
    ) -> TitanMessageIdentity | None:
        """جلب هوية رسالة بمعرف Telegram ومعرف الشات."""
        raise NotImplementedError

    async def mark_deleted(self, titan_id: int) -> None:
        """تعليم رسالة كمحذوفة مع الحفاظ على titan_id للأبد."""
        raise NotImplementedError


# ---------------------------------------------------------------------------
# SQLite implementation
# ---------------------------------------------------------------------------

_CREATE_IDENTITY_TABLE = """
CREATE TABLE IF NOT EXISTS message_identity (
    titan_id            INTEGER PRIMARY KEY AUTOINCREMENT,
    bot_username        TEXT    NOT NULL,
    chat_id             INTEGER NOT NULL,
    telegram_message_id INTEGER NOT NULL,
    deleted             INTEGER NOT NULL DEFAULT 0,
    UNIQUE(chat_id, telegram_message_id)
)
"""

_CREATE_ARCHIVE_TABLE = """
CREATE TABLE IF NOT EXISTS message_archive (
    titan_id  INTEGER PRIMARY KEY REFERENCES message_identity(titan_id),
    text      TEXT,
    chat_type TEXT    NOT NULL DEFAULT 'unknown',
    sent_at   TEXT    NOT NULL
)
"""


class SqliteMessageStore(MessageStore):
    """
    تخزين SQLite لـ Message Links Protocol.

    يُنشئ قاعدة البيانات تلقائياً عند أول استخدام.
    آمن للاستخدام المتزامن من خلال threading.Lock.

    مسار قاعدة البيانات:
        - مسار ملف عادي: يُنشئ المجلد تلقائياً إن لم يوجد.
        - ":memory:": قاعدة بيانات مؤقتة في الذاكرة (للاختبار).

    الاستخدام:
        store = SqliteMessageStore("/path/to/.titan/links.db")
        store = SqliteMessageStore(":memory:")  # للاختبار
    """

    def __init__(self, db_path: str) -> None:
        self._db_path = db_path
        self._conn: sqlite3.Connection | None = None
        self._lock = threading.Lock()
        self._archive_initialized = False

    # -------------------------
    # Internal helpers
    # -------------------------

    def _get_conn(self) -> sqlite3.Connection:
        """الحصول على الاتصال أو إنشاؤه عند أول استدعاء.

        آمن للاستخدام المتزامن — التحقق والإنشاء داخل lock واحد
        لتفادي race window عند الاستدعاء من خيوط متعددة.
        """
        if self._conn is None:
            with self._lock:
                # Double-checked locking — التحقق مجدداً داخل الـ lock
                if self._conn is None:
                    if self._db_path != ":memory:":
                        db_dir = os.path.dirname(self._db_path)
                        if db_dir:
                            os.makedirs(db_dir, exist_ok=True)
                    conn = sqlite3.connect(
                        self._db_path,
                        check_same_thread=False,
                    )
                    conn.row_factory = sqlite3.Row
                    conn.execute(_CREATE_IDENTITY_TABLE)
                    conn.commit()
                    self._conn = conn
        return self._conn

    def _ensure_archive_table(self, conn: sqlite3.Connection) -> None:
        if not self._archive_initialized:
            with self._lock:
                if not self._archive_initialized:
                    conn.execute(_CREATE_ARCHIVE_TABLE)
                    conn.commit()
                    self._archive_initialized = True

    def _row_to_identity(self, row: sqlite3.Row) -> TitanMessageIdentity:
        return TitanMessageIdentity(
            titan_id=row["titan_id"],
            bot_username=row["bot_username"],
            chat_id=row["chat_id"],
            telegram_message_id=row["telegram_message_id"],
            deleted=bool(row["deleted"]),
        )

    # -------------------------
    # MessageStore implementation
    # -------------------------

    async def save_identity(
        self,
        bot_username: str,
        chat_id: int,
        telegram_message_id: int,
    ) -> TitanMessageIdentity:

        def _do() -> TitanMessageIdentity:
            conn = self._get_conn()
            with self._lock:
                cursor = conn.execute(
                    """
                    INSERT INTO message_identity (bot_username, chat_id, telegram_message_id)
                    VALUES (?, ?, ?)
                    """,
                    (bot_username, chat_id, telegram_message_id),
                )
                titan_id = cursor.lastrowid
                conn.commit()
            return TitanMessageIdentity(
                titan_id=titan_id,
                bot_username=bot_username,
                chat_id=chat_id,
                telegram_message_id=telegram_message_id,
            )

        return await asyncio.to_thread(_do)

    async def get_by_titan_id(self, titan_id: int) -> TitanMessageIdentity | None:

        def _do() -> TitanMessageIdentity | None:
            conn = self._get_conn()
            with self._lock:
                row = conn.execute(
                    "SELECT * FROM message_identity WHERE titan_id = ?",
                    (titan_id,),
                ).fetchone()
            return self._row_to_identity(row) if row else None

        return await asyncio.to_thread(_do)

    async def get_by_telegram_id(
        self,
        chat_id: int,
        telegram_message_id: int,
    ) -> TitanMessageIdentity | None:

        def _do() -> TitanMessageIdentity | None:
            conn = self._get_conn()
            with self._lock:
                row = conn.execute(
                    """
                    SELECT * FROM message_identity
                    WHERE chat_id = ? AND telegram_message_id = ?
                    """,
                    (chat_id, telegram_message_id),
                ).fetchone()
            return self._row_to_identity(row) if row else None

        return await asyncio.to_thread(_do)

    async def mark_deleted(self, titan_id: int) -> None:

        def _do() -> None:
            conn = self._get_conn()
            with self._lock:
                conn.execute(
                    "UPDATE message_identity SET deleted = 1 WHERE titan_id = ?",
                    (titan_id,),
                )
                conn.commit()

        await asyncio.to_thread(_do)

    # -------------------------
    # Archive (concrete — not part of MessageStore protocol)
    # -------------------------

    async def save_archive(
        self,
        titan_id: int,
        text: str | None,
        chat_type: str,
    ) -> None:
        """
        حفظ بيانات الأرشيف لرسالة موجودة في Identity Layer.

        يُستدعى فقط عند تفعيل Archive Layer.
        """
        sent_at = datetime.now(timezone.utc).isoformat()

        def _do() -> None:
            conn = self._get_conn()
            self._ensure_archive_table(conn)
            with self._lock:
                conn.execute(
                    """
                    INSERT OR IGNORE INTO message_archive (titan_id, text, chat_type, sent_at)
                    VALUES (?, ?, ?, ?)
                    """,
                    (titan_id, text, chat_type, sent_at),
                )
                conn.commit()

        await asyncio.to_thread(_do)
