import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from titan.bot import Titan
from titan.errors import TitanError


RAW_MESSAGE_42 = {
    "update_id": 42,
    "message": {
        "message_id": 1,
        "text": "hi",
        "from": {"id": 1, "username": "u"},
        "chat": {"id": 1, "type": "private"},
    },
}


def make_bot():
    return Titan("fake-token")


class TestExtractCommand:
    def setup_method(self):
        self.bot = make_bot()

    def test_simple_command(self):
        assert self.bot._extract_command("/start") == "start"

    def test_command_with_bot_name(self):
        assert self.bot._extract_command("/start@MyBot") == "start"

    def test_command_with_args(self):
        assert self.bot._extract_command("/help me please") == "help"

    def test_not_a_command(self):
        assert self.bot._extract_command("hello") is None

    def test_empty_string(self):
        assert self.bot._extract_command("") is None

    def test_slash_only(self):
        assert self.bot._extract_command("/") is None

    def test_command_with_at_and_args(self):
        assert self.bot._extract_command("/ban@MyBot user123") == "ban"


class TestHandlerRegistration:
    def setup_method(self):
        self.bot = make_bot()

    def test_on_registers_handler(self):
        async def handler(ctx): pass
        self.bot.on("message")(handler)
        assert handler in self.bot.handlers["message"]

    def test_on_multiple_handlers_same_event(self):
        async def h1(ctx): pass
        async def h2(ctx): pass
        self.bot.on("message")(h1)
        self.bot.on("message")(h2)
        assert len(self.bot.handlers["message"]) == 2

    def test_on_returns_func(self):
        async def handler(ctx): pass
        result = self.bot.on("message")(handler)
        assert result is handler

    def test_command_registers(self):
        async def start(ctx): pass
        self.bot.command("start")(start)
        assert self.bot.commands["start"] is start

    def test_command_duplicate_raises(self):
        async def h(ctx): pass
        self.bot.command("start")(h)
        with pytest.raises(TitanError, match=r"Command 'start' is already registered"):
            self.bot.command("start")(h)

    def test_command_returns_func(self):
        async def start(ctx): pass
        result = self.bot.command("start")(start)
        assert result is start

    def test_callback_registers(self):
        async def on_yes(ctx): pass
        self.bot.callback("yes")(on_yes)
        assert self.bot.callback_handlers["yes"] is on_yes

    def test_callback_duplicate_raises(self):
        async def h(ctx): pass
        self.bot.callback("yes")(h)
        with pytest.raises(TitanError, match=r"Callback data 'yes' is already registered"):
            self.bot.callback("yes")(h)

    def test_callback_returns_func(self):
        async def h(ctx): pass
        result = self.bot.callback("yes")(h)
        assert result is h


class TestDispatch:
    def setup_method(self):
        self.bot = make_bot()

    @pytest.mark.asyncio
    async def test_dispatch_calls_handler(self):
        called = []

        async def h(ctx):
            called.append(True)

        self.bot.on("message")(h)
        mock_ctx = MagicMock()
        await self.bot._dispatch("message", mock_ctx)
        assert called == [True]

    @pytest.mark.asyncio
    async def test_dispatch_calls_multiple_handlers(self):
        results = []

        async def h1(ctx): results.append("h1")
        async def h2(ctx): results.append("h2")

        self.bot.on("message")(h1)
        self.bot.on("message")(h2)
        await self.bot._dispatch("message", MagicMock())
        assert results == ["h1", "h2"]

    @pytest.mark.asyncio
    async def test_dispatch_no_handler_is_safe(self):
        await self.bot._dispatch("unknown_event", MagicMock())

    @pytest.mark.asyncio
    async def test_dispatch_handler_exception_is_caught(self):
        async def bad(ctx):
            raise RuntimeError("oops")

        self.bot.on("message")(bad)
        await self.bot._dispatch("message", MagicMock())


class TestHandleUpdate:
    def setup_method(self):
        self.bot = make_bot()
        self.bot._api = MagicMock()
        self.bot._api.send_message = AsyncMock(return_value={"ok": True})

    @pytest.mark.asyncio
    async def test_routes_message_to_message_handler(self):
        calls = []

        @self.bot.on("message")
        async def h(ctx):
            calls.append("message")

        raw = {
            "update_id": 1,
            "message": {
                "message_id": 1,
                "text": "hi",
                "from": {"id": 1, "username": "u"},
                "chat": {"id": 1, "type": "private"},
            },
        }
        await self.bot._handle_update(raw)
        assert calls == ["message"]

    @pytest.mark.asyncio
    async def test_routes_command_to_command_handler(self):
        calls = []

        @self.bot.command("start")
        async def h(ctx):
            calls.append("start")

        raw = {
            "update_id": 1,
            "message": {
                "message_id": 1,
                "text": "/start",
                "from": {"id": 1, "username": "u"},
                "chat": {"id": 1, "type": "private"},
            },
        }
        await self.bot._handle_update(raw)
        assert calls == ["start"]

    @pytest.mark.asyncio
    async def test_unknown_command_falls_through_to_message(self):
        calls = []

        @self.bot.on("message")
        async def h(ctx):
            calls.append("message")

        raw = {
            "update_id": 1,
            "message": {
                "message_id": 1,
                "text": "/unknown",
                "from": {"id": 1, "username": "u"},
                "chat": {"id": 1, "type": "private"},
            },
        }
        await self.bot._handle_update(raw)
        assert calls == ["message"]

    @pytest.mark.asyncio
    async def test_routes_channel_post(self):
        calls = []

        @self.bot.on("channel")
        async def h(ctx):
            calls.append("channel")

        raw = {
            "update_id": 2,
            "channel_post": {
                "message_id": 2,
                "text": "news",
                "chat": {"id": 2, "type": "channel"},
            },
        }
        await self.bot._handle_update(raw)
        assert calls == ["channel"]

    @pytest.mark.asyncio
    async def test_routes_callback_to_specific_handler(self):
        calls = []

        @self.bot.callback("yes")
        async def h(ctx):
            calls.append("yes")

        raw = {
            "update_id": 3,
            "callback_query": {
                "id": "cq1",
                "data": "yes",
                "from": {"id": 1, "username": "u"},
                "message": {"message_id": 1, "chat": {"id": 1, "type": "private"}},
            },
        }
        await self.bot._handle_update(raw)
        assert calls == ["yes"]

    @pytest.mark.asyncio
    async def test_callback_falls_back_to_generic_handler(self):
        calls = []

        @self.bot.on("callback")
        async def h(ctx):
            calls.append("generic")

        raw = {
            "update_id": 3,
            "callback_query": {
                "id": "cq1",
                "data": "unknown",
                "from": {"id": 1, "username": "u"},
                "message": {"message_id": 1, "chat": {"id": 1, "type": "private"}},
            },
        }
        await self.bot._handle_update(raw)
        assert calls == ["generic"]

    @pytest.mark.asyncio
    async def test_routes_new_member(self):
        calls = []

        @self.bot.on("new_member")
        async def h(ctx):
            calls.append("new_member")

        raw = {
            "update_id": 4,
            "message": {
                "message_id": 4,
                "chat": {"id": 1, "type": "supergroup"},
                "new_chat_members": [{"id": 77, "first_name": "Ali"}],
            },
        }
        await self.bot._handle_update(raw)
        assert calls == ["new_member"]

    @pytest.mark.asyncio
    async def test_routes_left_member(self):
        calls = []

        @self.bot.on("left_member")
        async def h(ctx):
            calls.append("left_member")

        raw = {
            "update_id": 5,
            "message": {
                "message_id": 5,
                "chat": {"id": 1, "type": "supergroup"},
                "left_chat_member": {"id": 88, "first_name": "Sara"},
            },
        }
        await self.bot._handle_update(raw)
        assert calls == ["left_member"]

    @pytest.mark.asyncio
    async def test_command_handler_exception_is_caught(self):
        @self.bot.command("crash")
        async def h(ctx):
            raise RuntimeError("crash!")

        raw = {
            "update_id": 1,
            "message": {
                "message_id": 1,
                "text": "/crash",
                "from": {"id": 1, "username": "u"},
                "chat": {"id": 1, "type": "private"},
            },
        }
        await self.bot._handle_update(raw)

    @pytest.mark.asyncio
    async def test_callback_handler_exception_is_caught(self):
        @self.bot.callback("boom")
        async def h(ctx):
            raise RuntimeError("boom!")

        raw = {
            "update_id": 1,
            "callback_query": {
                "id": "cq1",
                "data": "boom",
                "from": {"id": 1, "username": "u"},
                "message": {"message_id": 1, "chat": {"id": 1, "type": "private"}},
            },
        }
        await self.bot._handle_update(raw)

    # ------------------------------------------------------------------
    # Fallback logging — Investigation #3 (Error Handling & Propagation)
    # ------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_fallback_logs_with_exc_info_when_no_error_handler(self):
        """
        عندما لا يُسجَّل error handler، يجب أن يُسجَّل الاستثناء مع exc_info
        حتى يتمكن المطور من تحديد موضع الخطأ في كوده.

        العقد: لا error handler مسجَّل → _log.error مع exc_info يحتوي الاستثناء.
        """
        @self.bot.command("crash")
        async def h(ctx):
            raise RuntimeError("boom")

        raw = {
            "update_id": 1,
            "message": {
                "message_id": 1,
                "text": "/crash",
                "from": {"id": 1, "username": "u"},
                "chat": {"id": 1, "type": "private"},
            },
        }

        with patch("titan.bot._log") as mock_log:
            await self.bot._handle_update(raw)

        calls = mock_log.error.call_args_list
        assert calls, "expected _log.error to be called"
        # exc_info يجب أن يكون الاستثناء نفسه — لا None، لا False
        exc_info = calls[0].kwargs.get("exc_info") or (
            calls[0].args[1] if len(calls[0].args) > 1 else None
        )
        assert exc_info is not None, (
            "fallback must log with exc_info so the traceback is preserved"
        )

    @pytest.mark.asyncio
    async def test_inner_exception_in_error_handler_logs_with_exc_info(self):
        """
        عندما يرمي error handler نفسه استثناءً، يجب أن يُسجَّل مع exc_info.

        العقد: استثناء داخل error handler → _log.error مع exc_info يحتوي الاستثناء.
        """
        @self.bot.error_handler
        async def on_error(ctx, exc):
            raise RuntimeError("error handler crashed")

        @self.bot.command("crash")
        async def h(ctx):
            raise RuntimeError("original")

        raw = {
            "update_id": 2,
            "message": {
                "message_id": 2,
                "text": "/crash",
                "from": {"id": 1, "username": "u"},
                "chat": {"id": 1, "type": "private"},
            },
        }

        with patch("titan.bot._log") as mock_log:
            await self.bot._handle_update(raw)

        calls = mock_log.error.call_args_list
        assert calls, "expected _log.error to be called"
        exc_info = calls[0].kwargs.get("exc_info") or (
            calls[0].args[1] if len(calls[0].args) > 1 else None
        )
        assert exc_info is not None, (
            "inner exception in error handler must log with exc_info"
        )

    # ------------------------------------------------------------------
    # Unrouted updates — CONTRACT §4 (Unrouted Updates)
    # ------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_unsupported_update_type_does_not_reach_message_handler(self):
        """
        update من نوع معروف في Telegram لكن غير مدعوم في Titan (مثل poll)
        لا يجب أن يصل لأي message handler.

        العقد: update بلا route → لا handler يُستدعى.
        """
        calls = []

        @self.bot.on("message")
        async def h(ctx):
            calls.append("message")

        raw = {
            "update_id": 10,
            "poll": {
                "id": "poll1",
                "question": "اختر",
                "options": [{"text": "أ"}, {"text": "ب"}],
                "total_voter_count": 0,
                "is_closed": False,
                "is_anonymous": True,
                "type": "regular",
                "allows_multiple_answers": False,
            },
        }
        await self.bot._handle_update(raw)
        assert calls == [], (
            "poll update (unsupported type) must not reach on('message') handlers"
        )

    @pytest.mark.asyncio
    async def test_unknown_update_type_does_not_reach_message_handler(self):
        """
        update من نوع أضافه Telegram بعد بناء هذا الإصدار (مثل message_reaction)
        لا يجب أن يصل لأي message handler.

        العقد: update بلا route → لا handler يُستدعى.
        """
        calls = []

        @self.bot.on("message")
        async def h(ctx):
            calls.append("message")

        raw = {
            "update_id": 11,
            "message_reaction": {
                "chat": {"id": 1, "type": "supergroup"},
                "message_id": 42,
                "user": {"id": 99, "first_name": "Ali"},
                "new_reaction": [{"type": "emoji", "emoji": "👍"}],
                "old_reaction": [],
            },
        }
        await self.bot._handle_update(raw)
        assert calls == [], (
            "message_reaction update (unknown type) must not reach on('message') handlers"
        )

    @pytest.mark.asyncio
    async def test_unrouted_update_does_not_trigger_error_handler(self):
        """
        update بلا route لا يُعامَل كخطأ — error handler لا يُستدعى.

        العقد: update بلا route → لا خطأ، لا error handler.
        """
        errors = []

        @self.bot.error_handler
        async def on_error(ctx, exc):
            errors.append(exc)

        raw = {
            "update_id": 12,
            "poll_answer": {
                "poll_id": "poll1",
                "user": {"id": 99, "first_name": "Ali"},
                "option_ids": [0],
            },
        }
        await self.bot._handle_update(raw)
        assert errors == [], (
            "unrouted update must not invoke error_handler"
        )

    @pytest.mark.asyncio
    async def test_unrouted_update_does_not_affect_real_message_routing(self):
        """
        regression: update بلا route لا يؤثر على routing الرسائل العادية.
        رسالة حقيقية تصل بعد unknown update يجب أن تُعالَج بشكل طبيعي.
        """
        calls = []

        @self.bot.on("message")
        async def h(ctx):
            calls.append("message")

        unknown_raw = {"update_id": 20, "message_reaction": {"chat": {"id": 1}}}
        real_raw = {
            "update_id": 21,
            "message": {
                "message_id": 5,
                "text": "hello",
                "from": {"id": 1, "username": "u"},
                "chat": {"id": 1, "type": "private"},
            },
        }
        await self.bot._handle_update(unknown_raw)
        await self.bot._handle_update(real_raw)
        assert calls == ["message"], (
            "real message after unknown update must still reach on('message') handler"
        )


class TestStartupGetMeFailure:
    """SF-06: فشل get_me() عند startup يُصدر warning ولا يوقف التشغيل."""

    def _make_bot_failing_get_me(self):
        bot = Titan("fake-token")
        bot._api = MagicMock()
        bot._api.start = AsyncMock()
        bot._api.close = AsyncMock()
        bot._api.get_me = AsyncMock(side_effect=RuntimeError("network down"))
        bot._api.get_updates = AsyncMock(side_effect=RuntimeError("stop polling"))
        return bot

    @pytest.mark.asyncio
    async def test_get_me_failure_emits_warning(self):
        # patch the module-level _log directly — logging.getLogger() runs at
        # import time, so patching it after the fact has no effect on _log.
        bot = self._make_bot_failing_get_me()
        with patch("titan.bot._log") as mock_log:
            try:
                await asyncio.wait_for(bot.run_async(), timeout=2.0)
            except (asyncio.TimeoutError, RuntimeError):
                pass
            warning_calls = [
                call for call in mock_log.warning.call_args_list
                if "startup" in call[0][0]
            ]
            assert warning_calls, "expected a startup warning to be logged"

    @pytest.mark.asyncio
    async def test_get_me_failure_does_not_stop_startup(self):
        """Polling still starts after get_me() fails — failure is non-fatal."""
        bot = self._make_bot_failing_get_me()
        try:
            await asyncio.wait_for(bot.run_async(), timeout=2.0)
        except (asyncio.TimeoutError, RuntimeError):
            pass
        bot._api.get_updates.assert_called()


class TestOnOffsetOrdering:
    """§8 CONTRACT: update handled → bot.offset updated → on_offset(offset)"""

    def _make_bot_with_mocked_api(self, updates_sequence):
        bot = Titan("fake-token")
        call_count = 0

        async def fake_get_updates(offset):
            nonlocal call_count
            call_count += 1
            if call_count <= len(updates_sequence):
                return updates_sequence[call_count - 1]
            raise RuntimeError("stop polling")

        bot._api = MagicMock()
        bot._api.get_updates = fake_get_updates
        bot._api.start = AsyncMock()
        bot._api.close = AsyncMock()
        bot._api.get_me = AsyncMock(return_value={"username": "testbot"})
        return bot

    @pytest.mark.asyncio
    async def test_async_on_offset_is_rejected_before_polling(self):
        """Async callbacks fail before the API is started."""
        bot = self._make_bot_with_mocked_api([])

        async def bad_offset(offset):
            pass

        with pytest.raises(
            TitanError,
            match="async callbacks are not supported",
        ):
            await bot.run_async(on_offset=bad_offset)

        bot._api.start.assert_not_awaited()
        assert bot._on_offset is None

    @pytest.mark.asyncio
    async def test_offset_updated_after_dispatch(self):
        """
        bot.offset is updated after the update is dispatched to its chat queue,
        which happens before the handler completes (per §8 — updated contract).

        With per-chat dispatch, offset tracks what has been accepted for
        processing, not what has finished processing.
        """
        bot = self._make_bot_with_mocked_api([[RAW_MESSAGE_42]])
        offset_during_handler = []

        @bot.on("message")
        async def handler(ctx):
            offset_during_handler.append(bot.offset)

        try:
            await asyncio.wait_for(bot.run_async(), timeout=2.0)
        except (asyncio.TimeoutError, RuntimeError):
            pass

        assert offset_during_handler == [42], (
            "bot.offset is updated to 42 after dispatch (before handler completes) — §8"
        )

    @pytest.mark.asyncio
    async def test_offset_updated_before_on_offset_called(self):
        """When on_offset(offset) is called, bot.offset already equals offset."""
        bot = self._make_bot_with_mocked_api([[RAW_MESSAGE_42]])
        bot_offset_at_callback_time = []

        def on_offset(offset):
            bot_offset_at_callback_time.append(bot.offset)

        try:
            await asyncio.wait_for(bot.run_async(on_offset=on_offset), timeout=2.0)
        except (asyncio.TimeoutError, RuntimeError):
            pass

        assert bot_offset_at_callback_time == [42], (
            "bot.offset must already be updated to 42 when on_offset(42) is called — §8"
        )

    @pytest.mark.asyncio
    async def test_on_offset_receives_correct_value(self):
        """on_offset receives the update_id of the processed update."""
        bot = self._make_bot_with_mocked_api([[RAW_MESSAGE_42]])
        received = []

        def on_offset(offset):
            received.append(offset)

        try:
            await asyncio.wait_for(bot.run_async(on_offset=on_offset), timeout=2.0)
        except (asyncio.TimeoutError, RuntimeError):
            pass

        assert received == [42]

    @pytest.mark.asyncio
    async def test_sync_on_offset_exception_uses_polling_error_path(self):
        """Sync callback errors are handled by PollingRunner's backoff path."""
        bot = self._make_bot_with_mocked_api([[RAW_MESSAGE_42]])
        bot._api.get_updates = AsyncMock(
            side_effect=[[RAW_MESSAGE_42], asyncio.CancelledError()]
        )
        on_offset = MagicMock(side_effect=RuntimeError("offset persistence failed"))

        with patch("titan.lifecycle.runner.asyncio.sleep", new=AsyncMock()):
            with pytest.raises(asyncio.CancelledError):
                await bot.run_async(on_offset=on_offset)

        on_offset.assert_called_once_with(42)
        assert bot.offset == 42
        assert bot._api.get_updates.await_count == 2

    @pytest.mark.asyncio
    async def test_on_offset_not_called_when_no_updates(self):
        """on_offset is not called when get_updates returns empty list."""
        bot = self._make_bot_with_mocked_api([[]])
        received = []

        def on_offset(offset):
            received.append(offset)

        try:
            await asyncio.wait_for(bot.run_async(on_offset=on_offset), timeout=2.0)
        except (asyncio.TimeoutError, RuntimeError):
            pass

        assert received == []


# ---------------------------------------------------------------------------
# run_async lifecycle boundary
# ---------------------------------------------------------------------------

class TestRunAsyncLifecycle:

    @pytest.mark.asyncio
    async def test_run_async_cancellation_remains_visible_after_cleanup(self):
        bot = Titan("fake-token")
        handler_started = asyncio.Event()
        handler_cancelled = asyncio.Event()
        polling_blocked = asyncio.Event()
        first_call = True

        @bot.on("message")
        async def handler(_ctx):
            handler_started.set()
            try:
                await asyncio.Future()
            except asyncio.CancelledError:
                handler_cancelled.set()
                raise

        async def get_updates(*, offset):
            nonlocal first_call
            if first_call:
                first_call = False
                return [RAW_MESSAGE_42]
            await polling_blocked.wait()
            raise asyncio.CancelledError

        bot._api = MagicMock()
        bot._api.start = AsyncMock()
        bot._api.get_me = AsyncMock(return_value={"username": "testbot"})
        bot._api.get_updates = get_updates
        bot._api.close = AsyncMock()

        run_task = asyncio.create_task(bot.run_async())
        await handler_started.wait()

        with patch("titan.lifecycle.runner._HANDLER_GRACE_PERIOD", 0):
            run_task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await run_task

        assert handler_cancelled.is_set()
        bot._api.close.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_api_close_happens_after_lifecycle_cleanup(self):
        bot = Titan("fake-token")
        handler_started = asyncio.Event()
        grace_started = asyncio.Event()
        release_handler = asyncio.Event()
        polling_blocked = asyncio.Event()
        events = []
        first_call = True

        @bot.on("message")
        async def handler(_ctx):
            handler_started.set()
            await release_handler.wait()
            events.append("handler_finished")

        async def get_updates(*, offset):
            nonlocal first_call
            if first_call:
                first_call = False
                return [RAW_MESSAGE_42]
            await polling_blocked.wait()
            raise asyncio.CancelledError

        async def close():
            assert events == ["handler_finished"]
            events.append("api_close")

        close_mock = AsyncMock(side_effect=close)
        bot._api = MagicMock()
        bot._api.start = AsyncMock()
        bot._api.get_me = AsyncMock(return_value={"username": "testbot"})
        bot._api.get_updates = get_updates
        bot._api.close = close_mock

        real_wait = asyncio.wait

        async def observed_wait(*args, **kwargs):
            grace_started.set()
            return await real_wait(*args, **kwargs)

        with patch("titan.lifecycle.runner.asyncio.wait", side_effect=observed_wait):
            run_task = asyncio.create_task(bot.run_async())
            await handler_started.wait()
            run_task.cancel()
            await grace_started.wait()

            assert events == []
            release_handler.set()

            with pytest.raises(asyncio.CancelledError):
                await run_task

        assert events == ["handler_finished", "api_close"]
        close_mock.assert_awaited_once()
