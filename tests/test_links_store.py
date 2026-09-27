"""
اختبارات SqliteMessageStore — التخزين الافتراضي لـ Identity Layer.

تستخدم ":memory:" لقاعدة بيانات مؤقتة بدون ملفات.
"""

import pytest
import sqlite3
from titan.links.store import SqliteMessageStore


@pytest.fixture
def store():
    return SqliteMessageStore(":memory:")


@pytest.mark.parametrize(
    ("db_path", "expected_file"),
    [
        (":memory:", None),
        ("links.db", "links.db"),
        ("nested/links.db", "nested/links.db"),
        (".titan/links.db", ".titan/links.db"),
    ],
)
@pytest.mark.asyncio
async def test_sqlite_store_supports_database_paths(
    tmp_path, monkeypatch, db_path, expected_file
):
    """كل مسارات قاعدة البيانات تنشئ الجدول وتحفظ البيانات فعلياً."""
    monkeypatch.chdir(tmp_path)
    store = SqliteMessageStore(db_path)

    saved = await store.save_identity("Bot", 100, 1)
    found = await store.get_by_titan_id(saved.titan_id)

    assert found is not None
    assert found.bot_username == "Bot"
    assert found.chat_id == 100
    assert found.telegram_message_id == 1

    if expected_file is None:
        assert list(tmp_path.iterdir()) == []
    else:
        database_path = tmp_path / expected_file
        assert database_path.is_file()
        with sqlite3.connect(database_path) as connection:
            row = connection.execute(
                """
                SELECT bot_username, chat_id, telegram_message_id
                FROM message_identity
                """
            ).fetchone()
        assert row == ("Bot", 100, 1)


class TestSaveIdentity:
    @pytest.mark.asyncio
    async def test_save_returns_identity(self, store):
        ident = await store.save_identity(
            bot_username="MyBot",
            chat_id=100,
            telegram_message_id=50,
        )
        assert ident.titan_id == 1
        assert ident.bot_username == "MyBot"
        assert ident.chat_id == 100
        assert ident.telegram_message_id == 50
        assert ident.deleted is False

    @pytest.mark.asyncio
    async def test_sequential_titan_ids(self, store):
        a = await store.save_identity("Bot", 100, 1)
        b = await store.save_identity("Bot", 100, 2)
        c = await store.save_identity("Bot", 100, 3)
        assert a.titan_id == 1
        assert b.titan_id == 2
        assert c.titan_id == 3

    @pytest.mark.asyncio
    async def test_titan_id_never_reused_after_delete(self, store):
        """titan_id لرسالة محذوفة لا يُعاد تخصيصه."""
        ident = await store.save_identity("Bot", 100, 1)
        await store.mark_deleted(ident.titan_id)
        next_ident = await store.save_identity("Bot", 100, 2)
        assert next_ident.titan_id == 2  # لا يعود إلى 1


class TestGetByTitanId:
    @pytest.mark.asyncio
    async def test_found(self, store):
        saved = await store.save_identity("Bot", 200, 10)
        found = await store.get_by_titan_id(saved.titan_id)
        assert found is not None
        assert found.titan_id == saved.titan_id
        assert found.bot_username == "Bot"
        assert found.chat_id == 200
        assert found.telegram_message_id == 10

    @pytest.mark.asyncio
    async def test_not_found(self, store):
        result = await store.get_by_titan_id(9999)
        assert result is None


class TestGetByTelegramId:
    @pytest.mark.asyncio
    async def test_found(self, store):
        await store.save_identity("Bot", 300, 77)
        found = await store.get_by_telegram_id(chat_id=300, telegram_message_id=77)
        assert found is not None
        assert found.telegram_message_id == 77
        assert found.chat_id == 300

    @pytest.mark.asyncio
    async def test_not_found(self, store):
        result = await store.get_by_telegram_id(chat_id=999, telegram_message_id=999)
        assert result is None

    @pytest.mark.asyncio
    async def test_different_chat_same_msg_id_not_found(self, store):
        """نفس telegram_message_id في شات مختلف يعطي نتيجة مختلفة."""
        await store.save_identity("Bot", 100, 55)
        result = await store.get_by_telegram_id(chat_id=200, telegram_message_id=55)
        assert result is None


class TestMarkDeleted:
    @pytest.mark.asyncio
    async def test_deleted_flag_set(self, store):
        ident = await store.save_identity("Bot", 100, 20)
        await store.mark_deleted(ident.titan_id)
        found = await store.get_by_titan_id(ident.titan_id)
        assert found is not None
        assert found.deleted is True

    @pytest.mark.asyncio
    async def test_deleted_identity_still_retrievable(self, store):
        """الهوية تبقى موجودة حتى بعد الحذف — الحجز التاريخي."""
        ident = await store.save_identity("Bot", 100, 30)
        await store.mark_deleted(ident.titan_id)
        found = await store.get_by_titan_id(ident.titan_id)
        assert found is not None
        assert found.titan_id == ident.titan_id


class TestSaveArchive:
    @pytest.mark.asyncio
    async def test_archive_save(self, store):
        ident = await store.save_identity("Bot", 100, 40)
        # لا يجب أن يُثير استثناء
        await store.save_archive(
            titan_id=ident.titan_id,
            text="نص الرسالة",
            chat_type="private",
        )

    @pytest.mark.asyncio
    async def test_archive_save_none_text(self, store):
        ident = await store.save_identity("Bot", 100, 50)
        await store.save_archive(
            titan_id=ident.titan_id,
            text=None,
            chat_type="group",
        )

    @pytest.mark.asyncio
    async def test_archive_idempotent(self, store):
        """حفظ أرشيف لنفس titan_id مرتين يبقى صامتاً (INSERT OR IGNORE)."""
        ident = await store.save_identity("Bot", 100, 60)
        await store.save_archive(ident.titan_id, "first", "private")
        await store.save_archive(ident.titan_id, "second", "group")  # يُتجاهَل
