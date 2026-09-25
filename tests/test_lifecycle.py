"""
اختبارات طبقة Lifecycle Management — ADR-019.

تُغطي:
- PollingRunner: توزيع التحديثات، backoff، الإغلاق.
- signals: install / uninstall لا يُثيران استثناء.
"""

import asyncio
import sys
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from titan.lifecycle.runner import PollingRunner
from titan.lifecycle.registry import LifecycleRegistry


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_raw(update_id: int, chat_id: int = 1) -> dict:
    return {
        "update_id": update_id,
        "message": {
            "message_id": update_id,
            "text": "hi",
            "from": {"id": 1, "username": "u"},
            "chat": {"id": chat_id, "type": "private"},
        },
    }


def _make_runner(
    *,
    updates_sequence: list,
    chat_id_from_raw=None,
    handle_update=None,
    ensure_chat_worker=None,
    chat_queues=None,
    chat_workers=None,
    lifecycle=None,
) -> PollingRunner:
    """ينشئ PollingRunner مع mocks بسيطة."""
    api = MagicMock()
    api.get_updates = AsyncMock(side_effect=updates_sequence)

    if handle_update is None:
        handle_update = AsyncMock()
    if chat_id_from_raw is None:
        chat_id_from_raw = lambda raw: None  # كل التحديثات بدون chat → direct task
    if ensure_chat_worker is None:
        ensure_chat_worker = MagicMock()
    if lifecycle is None:
        lifecycle = LifecycleRegistry()
    if chat_queues is not None:
        lifecycle.chat_queues = chat_queues
    if chat_workers is not None:
        lifecycle.chat_workers = chat_workers

    return PollingRunner(
        api=api,
        handle_update=handle_update,
        chat_id_from_raw=chat_id_from_raw,
        ensure_chat_worker=ensure_chat_worker,
        lifecycle=lifecycle,
        log=lambda msg: None,
    )


# ---------------------------------------------------------------------------
# PollingRunner — التوزيع
# ---------------------------------------------------------------------------

class TestPollingRunnerDispatch:

    @pytest.mark.asyncio
    async def test_polling_tasks_are_owned_by_the_run_registry(self):
        """المهام المباشرة تمر عبر سجل دورة polling المحلي."""
        raw = _make_raw(1)
        cancelled = asyncio.CancelledError()
        lifecycle = LifecycleRegistry()
        handle_update = AsyncMock()

        runner = _make_runner(
            updates_sequence=[[raw], cancelled],
            chat_id_from_raw=lambda r: None,
            handle_update=handle_update,
            lifecycle=lifecycle,
        )

        with pytest.raises(asyncio.CancelledError):
            await runner.run(initial_offset=0, debug=False, offset_updated=None)

        await asyncio.sleep(0)
        assert len(lifecycle.tasks) == 1
        assert lifecycle.handler_tasks == lifecycle.tasks
        task = next(iter(lifecycle.handler_tasks))
        assert task.get_name() == "titan-update-1"

        await task
        handle_update.assert_awaited_once_with(raw)
        assert task.done()

    @pytest.mark.asyncio
    async def test_completed_task_is_removed_from_registry(self):
        """المهمة المكتملة تُزال من السجل بعد ملاحظتها."""
        lifecycle = LifecycleRegistry()

        async def successful():
            return "ok"

        task = lifecycle.create_task(
            successful(),
            name="titan-test-success",
            kind="handler",
        )

        await task
        await asyncio.sleep(0)

        assert task not in lifecycle.tasks
        assert task not in lifecycle.handler_tasks

    @pytest.mark.asyncio
    async def test_task_exception_is_logged_once_and_removed(self):
        """استثناء المهمة يُسجّل مرة واحدة ولا يبقى غير مرصود."""
        lifecycle = LifecycleRegistry()
        failure = RuntimeError("lifecycle failure")

        async def failing():
            raise failure

        with patch("titan.lifecycle.registry._log") as mock_log:
            task = lifecycle.create_task(
                failing(),
                name="titan-test-failure",
                kind="handler",
            )
            with pytest.raises(RuntimeError, match="lifecycle failure"):
                await task
            await asyncio.sleep(0)

        assert task not in lifecycle.tasks
        assert task not in lifecycle.handler_tasks
        assert mock_log.error.call_count == 1
        assert mock_log.error.call_args.args[:2] == (
            "Unhandled exception in lifecycle task %s",
            "titan-test-failure",
        )

    @pytest.mark.asyncio
    async def test_cancelled_task_is_not_logged_as_failure(self):
        """الإلغاء حالة lifecycle طبيعية ولا يُسجّل كفشل."""
        lifecycle = LifecycleRegistry()

        async def waiting():
            await asyncio.Future()

        with patch("titan.lifecycle.registry._log") as mock_log:
            task = lifecycle.create_task(
                waiting(),
                name="titan-test-cancelled",
                kind="handler",
            )
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await task
            await asyncio.sleep(0)

        assert task not in lifecycle.tasks
        assert task not in lifecycle.handler_tasks
        mock_log.error.assert_not_called()

    @pytest.mark.asyncio
    async def test_update_without_chat_creates_direct_task(self):
        """تحديث بدون chat_id → asyncio.create_task مباشرةً."""
        raw = _make_raw(1)
        cancelled = asyncio.CancelledError()

        runner = _make_runner(
            updates_sequence=[[raw], cancelled],
            chat_id_from_raw=lambda r: None,
        )

        with pytest.raises(asyncio.CancelledError):
            await runner.run(initial_offset=0, debug=False, offset_updated=None)

    @pytest.mark.asyncio
    async def test_update_with_chat_enqueues_to_worker(self):
        """تحديث بـ chat_id → يُضاف إلى قائمة الـ chat."""
        raw = _make_raw(1, chat_id=42)
        queue = asyncio.Queue()
        cancelled = asyncio.CancelledError()

        ensure_chat_worker = MagicMock(return_value=queue)

        runner = _make_runner(
            updates_sequence=[[raw], cancelled],
            chat_id_from_raw=lambda r: r.get("message", {}).get("chat", {}).get("id"),
            ensure_chat_worker=ensure_chat_worker,
        )

        with pytest.raises(asyncio.CancelledError):
            await runner.run(initial_offset=0, debug=False, offset_updated=None)

        ensure_chat_worker.assert_called_once_with(42)
        assert not queue.empty()

    @pytest.mark.asyncio
    async def test_offset_updated_called_for_each_update(self):
        """offset_updated يُستدعى لكل تحديث مع update_id الصحيح."""
        raws = [_make_raw(i) for i in range(1, 4)]
        cancelled = asyncio.CancelledError()
        collected: list[int] = []

        runner = _make_runner(
            updates_sequence=[raws, cancelled],
        )

        with pytest.raises(asyncio.CancelledError):
            await runner.run(
                initial_offset=0,
                debug=False,
                offset_updated=lambda ofs: collected.append(ofs),
            )

        assert collected == [1, 2, 3]

    @pytest.mark.asyncio
    async def test_update_with_no_update_id_is_skipped(self):
        """تحديث بدون update_id يُتجاهَل بصمت — لا crash."""
        raw_invalid = {"message": {"text": "hi"}}   # no update_id
        cancelled = asyncio.CancelledError()
        collected: list[int] = []

        runner = _make_runner(
            updates_sequence=[[raw_invalid], cancelled],
        )

        with pytest.raises(asyncio.CancelledError):
            await runner.run(
                initial_offset=0,
                debug=False,
                offset_updated=lambda ofs: collected.append(ofs),
            )

        assert collected == []   # لم يُحدَّث الـ offset


# ---------------------------------------------------------------------------
# PollingRunner — Backoff
# ---------------------------------------------------------------------------

class TestPollingRunnerBackoff:

    @pytest.mark.asyncio
    async def test_backoff_on_transient_error(self):
        """خطأ مؤقت → asyncio.sleep يُستدعى، ثم تُستأنف الحلقة."""
        raw = _make_raw(1)
        cancelled = asyncio.CancelledError()

        runner = _make_runner(
            updates_sequence=[RuntimeError("network"), [raw], cancelled],
        )

        with patch("titan.lifecycle.runner.asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
            with pytest.raises(asyncio.CancelledError):
                await runner.run(initial_offset=0, debug=False, offset_updated=None)

        mock_sleep.assert_called_once()
        sleep_duration = mock_sleep.call_args[0][0]
        assert sleep_duration > 0

    @pytest.mark.asyncio
    async def test_backoff_resets_after_success(self):
        """backoff يرجع إلى صفر بعد نجاح get_updates."""
        raw = _make_raw(1)
        cancelled = asyncio.CancelledError()

        # خطأ → نجاح → خطأ → تأكيد أن backoff بدأ من البداية مرة ثانية
        sleep_durations: list[float] = []

        runner = _make_runner(
            updates_sequence=[
                RuntimeError("first error"),
                [raw],
                RuntimeError("second error"),
                cancelled,
            ],
        )

        async def mock_sleep(duration: float) -> None:
            sleep_durations.append(duration)

        with patch("titan.lifecycle.runner.asyncio.sleep", side_effect=mock_sleep):
            with pytest.raises(asyncio.CancelledError):
                await runner.run(initial_offset=0, debug=False, offset_updated=None)

        assert len(sleep_durations) == 2
        # الـ backoff الثاني يبدأ من _BACKOFF_BASE — لا يتراكم من السابق
        from titan.lifecycle.runner import _BACKOFF_BASE
        assert sleep_durations[1] == _BACKOFF_BASE


# ---------------------------------------------------------------------------
# PollingRunner — Shutdown
# ---------------------------------------------------------------------------

class TestPollingRunnerShutdown:

    @pytest.mark.asyncio
    async def test_shutdown_sends_sentinel_and_drains(self):
        """shutdown() يُرسل None لكل قائمة وينتظر انتهاء الـ workers."""
        queue: asyncio.Queue = asyncio.Queue()

        sentinel_received: list[bool] = []

        async def fake_worker():
            item = await queue.get()
            sentinel_received.append(item is None)

        task = asyncio.create_task(fake_worker())
        chat_queues = {1: queue}
        chat_workers = {1: task}

        runner = _make_runner(
            updates_sequence=[],
            chat_queues=chat_queues,
            chat_workers=chat_workers,
        )

        await runner.shutdown()

        assert sentinel_received == [True]
        assert chat_queues == {}
        assert chat_workers == {}

    @pytest.mark.asyncio
    async def test_shutdown_clears_state(self):
        """shutdown() يُفرّغ chat_queues وchat_workers."""
        chat_queues: dict = {1: asyncio.Queue(), 2: asyncio.Queue()}

        async def dummy():
            await asyncio.sleep(0)

        chat_workers: dict = {
            1: asyncio.create_task(dummy()),
            2: asyncio.create_task(dummy()),
        }

        runner = _make_runner(
            updates_sequence=[],
            chat_queues=chat_queues,
            chat_workers=chat_workers,
        )

        await runner.shutdown()

        assert chat_queues == {}
        assert chat_workers == {}


# ---------------------------------------------------------------------------
# signals — install / uninstall
# ---------------------------------------------------------------------------

class TestSignals:

    def test_install_and_uninstall_do_not_raise(self):
        """install() وuninstall() لا يُثيران استثناء في أي بيئة."""
        from titan.lifecycle import signals

        loop = asyncio.new_event_loop()
        try:
            # MagicMock كافٍ — signals.install تستدعي task.cancel() فقط،
            # ولا تحتاج asyncio.Task حقيقياً.
            task = MagicMock()
            signals.install(loop, task)
            signals.uninstall(loop)
        finally:
            loop.close()

    def test_uninstall_without_install_does_not_raise(self):
        """uninstall() قبل install() آمنة تماماً."""
        from titan.lifecycle import signals

        loop = asyncio.new_event_loop()
        try:
            signals.uninstall(loop)  # لا استثناء
        finally:
            loop.close()


# ---------------------------------------------------------------------------
# Lifecycle ownership and shutdown tests
# ---------------------------------------------------------------------------

class TestLifecycleGate:
    """Deterministic lifecycle ownership and shutdown gates."""

    @pytest.mark.asyncio
    async def test_direct_update_task_is_registered_through_polling_path(self):
        raw = _make_raw(701)
        handler_started = asyncio.Event()
        release_handler = asyncio.Event()

        async def handle_update(update):
            handler_started.set()
            await release_handler.wait()

        polling_blocked = asyncio.Event()
        first_call = True

        async def get_updates(*, offset):
            nonlocal first_call
            if first_call:
                first_call = False
                return [raw]
            await polling_blocked.wait()
            raise asyncio.CancelledError

        api = MagicMock()
        api.get_updates = get_updates
        lifecycle = LifecycleRegistry()
        runner = PollingRunner(
            api=api,
            handle_update=handle_update,
            chat_id_from_raw=lambda _raw: None,
            ensure_chat_worker=MagicMock(),
            lifecycle=lifecycle,
            log=lambda _message: None,
        )

        polling_task = asyncio.create_task(
            runner.run(initial_offset=0, debug=False, offset_updated=None)
        )
        await handler_started.wait()

        assert len(lifecycle.tasks) == 1
        assert lifecycle.handler_tasks == lifecycle.tasks
        handler_task = next(iter(lifecycle.handler_tasks))
        assert handler_task.get_name() == "titan-update-701"

        polling_task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await polling_task

        release_handler.set()
        await handler_task
        await runner.shutdown()

        assert lifecycle.tasks == set()
        assert lifecycle.handler_tasks == set()

    @pytest.mark.asyncio
    async def test_chat_worker_and_handler_share_registry_ownership(self):
        from titan.bot import Titan

        bot = Titan("fake-token")
        lifecycle = LifecycleRegistry()
        handler_started = asyncio.Event()
        release_handler = asyncio.Event()

        @bot.on("message")
        async def handler(_ctx):
            handler_started.set()
            await release_handler.wait()

        queue = bot._ensure_chat_worker(702, lifecycle)
        await queue.put(_make_raw(702, chat_id=702))
        await handler_started.wait()

        worker_task = lifecycle.chat_workers[702]
        handler_task = next(iter(lifecycle.handler_tasks))

        assert lifecycle.chat_queues[702] is queue
        assert worker_task in lifecycle.tasks
        assert handler_task in lifecycle.tasks
        assert worker_task is not handler_task
        assert worker_task.get_name() == "titan-chat-702"
        assert handler_task.get_name() == "titan-update-702"

        release_handler.set()
        await handler_task

        runner = _make_runner(
            updates_sequence=[],
            lifecycle=lifecycle,
        )
        await runner.shutdown()

        assert lifecycle.tasks == set()
        assert lifecycle.handler_tasks == set()
        assert lifecycle.chat_queues == {}
        assert lifecycle.chat_workers == {}

    @pytest.mark.asyncio
    async def test_polling_accepted_chat_updates_are_not_dropped_on_shutdown(self):
        from titan.bot import Titan

        bot = Titan("fake-token")
        lifecycle = LifecycleRegistry()
        raws = [_make_raw(703, chat_id=703), _make_raw(704, chat_id=703)]
        accepted_ids = []
        handled_ids = []
        accepted = asyncio.Event()
        polling_blocked = asyncio.Event()
        first_call = True

        async def get_updates(*, offset):
            nonlocal first_call
            if first_call:
                first_call = False
                return raws
            await polling_blocked.wait()
            raise asyncio.CancelledError

        @bot.on("message")
        async def handler(ctx):
            handled_ids.append(ctx.raw["update_id"])

        def on_offset(update_id):
            accepted_ids.append(update_id)
            if len(accepted_ids) == len(raws):
                accepted.set()

        api = MagicMock()
        api.get_updates = get_updates
        runner = PollingRunner(
            api=api,
            handle_update=bot._handle_update,
            chat_id_from_raw=bot._chat_id_from_raw,
            ensure_chat_worker=lambda chat_id: bot._ensure_chat_worker(
                chat_id, lifecycle
            ),
            lifecycle=lifecycle,
            log=lambda _message: None,
        )

        polling_task = asyncio.create_task(
            runner.run(initial_offset=0, debug=False, offset_updated=on_offset)
        )
        await accepted.wait()

        # Acceptance is proved by PollingRunner's own dispatch and offset
        # callback; the test never injects either update into a queue.
        assert accepted_ids == [703, 704]

        polling_task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await polling_task
        await runner.shutdown()

        assert handled_ids == [703, 704]
        assert lifecycle.tasks == set()
        assert lifecycle.handler_tasks == set()
        assert lifecycle.chat_queues == {}
        assert lifecycle.chat_workers == {}

    @pytest.mark.asyncio
    async def test_handler_finishing_during_grace_is_not_cancelled(self):
        raw = _make_raw(705)
        handler_started = asyncio.Event()
        grace_started = asyncio.Event()
        handler_finished = asyncio.Event()
        release_handler = asyncio.Event()
        polling_blocked = asyncio.Event()
        first_call = True

        async def handle_update(_raw):
            handler_started.set()
            await release_handler.wait()
            handler_finished.set()

        async def get_updates(*, offset):
            nonlocal first_call
            if first_call:
                first_call = False
                return [raw]
            await polling_blocked.wait()
            raise asyncio.CancelledError

        api = MagicMock()
        api.get_updates = get_updates
        lifecycle = LifecycleRegistry()
        runner = PollingRunner(
            api=api,
            handle_update=handle_update,
            chat_id_from_raw=lambda _raw: None,
            ensure_chat_worker=MagicMock(),
            lifecycle=lifecycle,
            log=lambda _message: None,
        )

        polling_task = asyncio.create_task(
            runner.run(initial_offset=0, debug=False, offset_updated=None)
        )
        await handler_started.wait()
        polling_task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await polling_task

        real_wait = asyncio.wait

        async def observed_wait(*args, **kwargs):
            grace_started.set()
            return await real_wait(*args, **kwargs)

        with patch("titan.lifecycle.runner.asyncio.wait", side_effect=observed_wait):
            shutdown_task = asyncio.create_task(runner.shutdown())
            await grace_started.wait()
            assert not handler_finished.is_set()
            release_handler.set()
            await shutdown_task

        assert handler_finished.is_set()
        assert lifecycle.tasks == set()
        assert lifecycle.handler_tasks == set()

    @pytest.mark.asyncio
    async def test_handler_pending_after_grace_is_cancelled_and_cleaned(self):
        raw = _make_raw(706)
        handler_started = asyncio.Event()
        handler_cancelled = asyncio.Event()
        never = asyncio.Future()
        polling_blocked = asyncio.Event()
        first_call = True

        async def handle_update(_raw):
            handler_started.set()
            try:
                await never
            except asyncio.CancelledError:
                handler_cancelled.set()
                raise

        async def get_updates(*, offset):
            nonlocal first_call
            if first_call:
                first_call = False
                return [raw]
            await polling_blocked.wait()
            raise asyncio.CancelledError

        api = MagicMock()
        api.get_updates = get_updates
        lifecycle = LifecycleRegistry()
        runner = PollingRunner(
            api=api,
            handle_update=handle_update,
            chat_id_from_raw=lambda _raw: None,
            ensure_chat_worker=MagicMock(),
            lifecycle=lifecycle,
            log=lambda _message: None,
        )

        polling_task = asyncio.create_task(
            runner.run(initial_offset=0, debug=False, offset_updated=None)
        )
        await handler_started.wait()
        polling_task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await polling_task

        with patch("titan.lifecycle.runner._HANDLER_GRACE_PERIOD", 0):
            await runner.shutdown()

        assert handler_cancelled.is_set()
        assert never.cancelled()
        assert lifecycle.tasks == set()
        assert lifecycle.handler_tasks == set()

    @pytest.mark.asyncio
    async def test_handler_cancellation_is_not_reported_as_failure(self):
        raw = _make_raw(707)
        handler_started = asyncio.Event()
        polling_blocked = asyncio.Event()
        first_call = True

        async def handle_update(_raw):
            handler_started.set()
            await asyncio.Future()

        async def get_updates(*, offset):
            nonlocal first_call
            if first_call:
                first_call = False
                return [raw]
            await polling_blocked.wait()
            raise asyncio.CancelledError

        api = MagicMock()
        api.get_updates = get_updates
        lifecycle = LifecycleRegistry()
        runner = PollingRunner(
            api=api,
            handle_update=handle_update,
            chat_id_from_raw=lambda _raw: None,
            ensure_chat_worker=MagicMock(),
            lifecycle=lifecycle,
            log=lambda _message: None,
        )

        polling_task = asyncio.create_task(
            runner.run(initial_offset=0, debug=False, offset_updated=None)
        )
        await handler_started.wait()
        polling_task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await polling_task

        with patch("titan.lifecycle.registry._log") as lifecycle_log:
            with patch("titan.lifecycle.runner._HANDLER_GRACE_PERIOD", 0):
                await runner.shutdown()

        lifecycle_log.error.assert_not_called()
        assert lifecycle.tasks == set()
        assert lifecycle.handler_tasks == set()

    @pytest.mark.asyncio
    async def test_escaped_lifecycle_exception_is_observed_once(self):
        raw = _make_raw(708)
        failure = RuntimeError("escaped lifecycle failure")
        accepted = asyncio.Event()
        observed = asyncio.Event()
        polling_blocked = asyncio.Event()
        first_call = True
        accepted_ids = []

        async def handle_update(_raw):
            raise failure

        async def get_updates(*, offset):
            nonlocal first_call
            if first_call:
                first_call = False
                return [raw]
            await polling_blocked.wait()
            raise asyncio.CancelledError

        def on_offset(update_id):
            accepted_ids.append(update_id)
            accepted.set()

        api = MagicMock()
        api.get_updates = get_updates
        lifecycle = LifecycleRegistry()
        runner = PollingRunner(
            api=api,
            handle_update=handle_update,
            chat_id_from_raw=lambda _raw: None,
            ensure_chat_worker=MagicMock(),
            lifecycle=lifecycle,
            log=lambda _message: None,
        )

        with patch("titan.lifecycle.registry._log") as lifecycle_log:
            def report(*args, **kwargs):
                observed.set()

            lifecycle_log.error.side_effect = report
            polling_task = asyncio.create_task(
                runner.run(
                    initial_offset=0,
                    debug=False,
                    offset_updated=on_offset,
                )
            )
            await asyncio.wait_for(accepted.wait(), timeout=2)
            try:
                await asyncio.wait_for(observed.wait(), timeout=2)
            except asyncio.TimeoutError as exc:
                raise AssertionError(
                    f"observer did not report; log calls={lifecycle_log.error.call_args_list}; "
                    f"owned tasks={lifecycle.tasks}"
                ) from exc

            assert accepted_ids == [708]
            lifecycle_log.error.assert_called_once()
            assert lifecycle_log.error.call_args.args[:2] == (
                "Unhandled exception in lifecycle task %s",
                "titan-update-708",
            )

            polling_task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await polling_task
            await runner.shutdown()

        assert lifecycle.tasks == set()
        assert lifecycle.handler_tasks == set()

    @pytest.mark.asyncio
    async def test_handled_update_exception_is_not_reported_by_observer_again(self):
        from titan.bot import Titan

        bot = Titan("fake-token")
        lifecycle = LifecycleRegistry()
        failure = RuntimeError("handled update failure")
        error_seen = asyncio.Event()
        release_error_handler = asyncio.Event()
        error_calls = []
        polling_blocked = asyncio.Event()
        first_call = True

        @bot.error_handler
        async def on_error(_ctx, exc):
            error_calls.append(exc)
            assert exc is failure
            error_seen.set()
            await release_error_handler.wait()

        @bot.on("message")
        async def handler(_ctx):
            raise failure

        async def get_updates(*, offset):
            nonlocal first_call
            if first_call:
                first_call = False
                return [_make_raw(709, chat_id=709)]
            await polling_blocked.wait()
            raise asyncio.CancelledError

        api = MagicMock()
        api.get_updates = get_updates
        runner = PollingRunner(
            api=api,
            handle_update=bot._handle_update,
            chat_id_from_raw=bot._chat_id_from_raw,
            ensure_chat_worker=lambda chat_id: bot._ensure_chat_worker(
                chat_id, lifecycle
            ),
            lifecycle=lifecycle,
            log=lambda _message: None,
        )

        with patch("titan.lifecycle.registry._log") as lifecycle_log:
            polling_task = asyncio.create_task(
                runner.run(initial_offset=0, debug=False, offset_updated=None)
            )
            await error_seen.wait()

            handler_task = next(iter(lifecycle.handler_tasks))
            release_error_handler.set()
            await handler_task

            polling_task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await polling_task
            await runner.shutdown()

            assert error_calls == [failure]
            assert lifecycle.tasks == set()
            assert lifecycle.handler_tasks == set()
            lifecycle_log.error.assert_not_called()

    @pytest.mark.asyncio
    async def test_shutdown_waits_for_worker_and_handler_cleanup(self):
        from titan.bot import Titan

        bot = Titan("fake-token")
        lifecycle = LifecycleRegistry()
        handler_started = asyncio.Event()
        handler_finished = asyncio.Event()
        release_handler = asyncio.Event()

        @bot.on("message")
        async def handler(_ctx):
            handler_started.set()
            await release_handler.wait()
            handler_finished.set()

        queue = bot._ensure_chat_worker(710, lifecycle)
        await queue.put(_make_raw(710, chat_id=710))
        await handler_started.wait()
        worker_task = lifecycle.chat_workers[710]
        worker_finished = asyncio.Event()
        worker_task.add_done_callback(lambda _task: worker_finished.set())

        runner = _make_runner(
            updates_sequence=[],
            lifecycle=lifecycle,
        )
        shutdown_task = asyncio.create_task(runner.shutdown())

        await worker_finished.wait()
        assert not shutdown_task.done()
        assert not handler_finished.is_set()

        release_handler.set()
        await shutdown_task

        assert handler_finished.is_set()
        assert lifecycle.tasks == set()
        assert lifecycle.handler_tasks == set()
        assert lifecycle.chat_queues == {}
        assert lifecycle.chat_workers == {}

    @pytest.mark.asyncio
    async def test_shutdown_final_invariant_has_no_owned_tasks_or_unobserved_exceptions(self):
        from titan.bot import Titan

        bot = Titan("fake-token")
        lifecycle = LifecycleRegistry()
        escaped_failure = RuntimeError("final invariant failure")
        observed = asyncio.Event()
        accepted = asyncio.Event()
        accepted_ids = []
        polling_blocked = asyncio.Event()
        first_call = True

        @bot.on("message")
        async def handler(_ctx):
            return None

        async def handle_update(raw):
            if raw["update_id"] == 711:
                raise escaped_failure
            await bot._handle_update(raw)

        async def get_updates(*, offset):
            nonlocal first_call
            if first_call:
                first_call = False
                return [
                    {"update_id": 711, "inline_query": {"id": "iq-711"}},
                    _make_raw(712, chat_id=712),
                ]
            await polling_blocked.wait()
            raise asyncio.CancelledError

        def on_offset(update_id):
            accepted_ids.append(update_id)
            if len(accepted_ids) == 2:
                accepted.set()

        api = MagicMock()
        api.get_updates = get_updates
        runner = PollingRunner(
            api=api,
            handle_update=handle_update,
            chat_id_from_raw=bot._chat_id_from_raw,
            ensure_chat_worker=lambda chat_id: bot._ensure_chat_worker(
                chat_id, lifecycle
            ),
            lifecycle=lifecycle,
            log=lambda _message: None,
        )

        with patch("titan.lifecycle.registry._log") as lifecycle_log:
            def report(*args, **kwargs):
                observed.set()

            lifecycle_log.error.side_effect = report
            polling_task = asyncio.create_task(
                runner.run(
                    initial_offset=0,
                    debug=False,
                    offset_updated=on_offset,
                )
            )
            await accepted.wait()
            await observed.wait()

            polling_task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await polling_task
            await runner.shutdown()

            lifecycle_log.error.assert_called_once()

        assert accepted_ids == [711, 712]
        assert lifecycle.chat_queues == {}
        assert lifecycle.chat_workers == {}
        assert lifecycle.tasks == set()
        assert lifecycle.handler_tasks == set()

    @pytest.mark.asyncio
    async def test_repeated_shutdown_is_safe_non_public_property(self):
        from titan.bot import Titan

        bot = Titan("fake-token")
        lifecycle = LifecycleRegistry()
        bot._ensure_chat_worker(713, lifecycle)
        runner = _make_runner(updates_sequence=[], lifecycle=lifecycle)

        await runner.shutdown()
        await runner.shutdown()

        assert lifecycle.chat_queues == {}
        assert lifecycle.chat_workers == {}
        assert lifecycle.tasks == set()
        assert lifecycle.handler_tasks == set()
