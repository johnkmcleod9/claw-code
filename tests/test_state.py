"""Tests for the src/state subsystem."""
from __future__ import annotations

import threading
import time

import pytest

# ---------------------------------------------------------------------------
# observable
# ---------------------------------------------------------------------------
from src.state.observable import (
    Observable,
    Store,
    filter_private_keys,
    make_teammate_view,
    merge_state,
    select,
    select_many,
    select_where,
)


def test_observable_basic():
    obs = Observable(42)
    assert obs.value == 42
    changes = []

    unsub = obs.on_change(lambda old, new: changes.append((old, new)))
    obs.set(100)
    assert obs.value == 100
    assert changes == [(42, 100)]
    unsub()


def test_observable_no_change_on_identical():
    obs = Observable("hello")
    changes = []
    obs.on_change(lambda *a: changes.append(a))
    obs.set("hello")
    assert len(changes) == 0


def test_observable_unsubscribe():
    obs = Observable(0)
    called = []

    unsub = obs.on_change(lambda *_: called.append(1))
    obs.on_change(lambda *_: called.append(2))
    unsub()  # remove first callback
    obs.set(1)  # only second callback fires
    assert called == [2]


def test_store_basic():
    store = Store({"a": 1, "b": 2})
    assert store.get("a") == 1
    assert store.get("missing", "default") == "default"
    assert store["a"] == 1
    assert "a" in store


def test_store_set_triggers_callback():
    store = Store()
    events = []

    store.watch("key", lambda old, new: events.append((old, new)))
    store.set("key", "v1")
    store.set("key", "v2")
    assert events == [(None, "v1"), ("v1", "v2")]


def test_store_watch_all():
    store = Store()
    events = []

    store.watch_all(lambda k, o, n: events.append((k, o, n)))
    store.set("a", 1)
    store.set("b", 2)
    store.delete("a")
    assert events == [("a", None, 1), ("b", None, 2), ("a", 1, None)]


def test_store_delete():
    store = Store({"k": "v"})
    assert store.delete("k")
    assert "k" not in store
    assert not store.delete("nonexistent")


def test_store_update():
    store = Store()
    store.update(a=1, b=2, c=3)
    assert store.get("c") == 3


def test_store_clear():
    store = Store({"a": 1, "b": 2})
    store.clear()
    assert len(store.snapshot()) == 0


def test_store_snapshot():
    store = Store({"a": 1})
    snap = store.snapshot()
    snap["a"] = 999
    assert store.get("a") == 1  # snapshot is a copy


def test_select():
    store = Store({"name": "claw"})
    assert select(store, "name") == "claw"
    assert select(store, "missing") is None


def test_select_many():
    store = Store({"a": 1, "b": 2, "c": 3})
    result = select_many(store, ["a", "c"])
    assert result == {"a": 1, "c": 3}


def test_select_where():
    store = Store({"x": 1, "y": 2, "z": 3})
    result = select_where(store, lambda k, v: v > 1)
    assert result == {"y": 2, "z": 3}


def test_filter_private_keys():
    data = {"name": "test", "_secret": "hide", "_internal": 42, "public": True}
    result = filter_private_keys(data)
    assert "_secret" not in result
    assert "name" in result
    assert "public" in result


def test_make_teammate_view():
    store = Store({"name": "Claw", "_token": "secret123"})
    view = make_teammate_view(store)
    assert "_token" not in view
    assert view["name"] == "Claw"


def test_merge_state():
    local = {"a": 1, "b": 2}
    remote = {"b": 99, "c": 3}
    result = merge_state(local, remote)
    assert result == {"a": 1, "b": 99, "c": 3}


def test_merge_state_conflict_resolver():
    local = {"x": 1}
    remote = {"x": 2}
    result = merge_state(local, remote, conflict_resolver=lambda k, l, r: l + r)
    assert result == {"x": 3}


def test_observable_threadsafe():
    obs = Observable(0)
    errors = []

    def writer():
        try:
            for i in range(200):
                obs.set(i)
        except Exception as e:
            errors.append(e)

    def reader():
        try:
            for _ in range(200):
                _ = obs.value
                time.sleep(0.001)
        except Exception as e:
            errors.append(e)

    threads = [threading.Thread(target=writer), threading.Thread(target=reader)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert not errors, f"Thread errors: {errors}"


# ---------------------------------------------------------------------------
# app_state
# ---------------------------------------------------------------------------
from src.state.app_state import AppMode, AppState, AppStateStore, ApprovalMode


def test_app_state_defaults():
    s = AppState()
    assert s.mode == AppMode.INTERACTIVE
    assert s.approval_mode == ApprovalMode.ON
    assert s.plan_mode is False


def test_app_state_serialization():
    s = AppState(model="sonnet", workdir="/tmp")
    d = {
        "mode": s.mode.value,
        "model": s.model,
        "session_id": s.session_id,
        "workdir": s.workdir,
        "approval_mode": s.approval_mode.value,
        "stream_enabled": s.stream_enabled,
        "compaction_threshold": s.compaction_threshold,
        "team_mode": s.team_mode,
        "plan_mode": s.plan_mode,
        "cost_limit_usd": s.cost_limit_usd,
        "max_turns": s.max_turns,
    }
    assert d["model"] == "sonnet"


def test_app_state_store_singleton():
    AppStateStore.reset()
    inst1 = AppStateStore.get_instance()
    inst2 = AppStateStore.get_instance()
    assert inst1 is inst2


def test_app_state_store_mode():
    AppStateStore.reset()
    store = AppStateStore.get_instance()
    unsub = store.on_mode_change(lambda m: None)
    store.set_mode(AppMode.PLAN)
    assert store.mode == AppMode.PLAN
    unsub()


def test_app_state_store_set_model():
    AppStateStore.reset()
    store = AppStateStore.get_instance()
    store.set_model("claude-3-5")
    assert store.model == "claude-3-5"


def test_app_state_store_set_plan_mode():
    AppStateStore.reset()
    store = AppStateStore.get_instance()
    store.set_plan_mode(True)
    assert store.is_plan_mode is True
    assert store.mode == AppMode.PLAN
    store.set_plan_mode(False)
    assert store.is_plan_mode is False


def test_app_state_store_extra():
    AppStateStore.reset()
    store = AppStateStore.get_instance()
    store.set_extra("custom_key", "custom_value")
    assert store.get_extra("custom_key") == "custom_value"
    assert store.get_extra("missing", "default") == "default"


def test_app_state_store_snapshot():
    AppStateStore.reset()
    store = AppStateStore.get_instance()
    store.set_model("deepseek")
    store.set_workdir("/home")
    snap = store.snapshot()
    assert snap["model"] == "deepseek"
    assert snap["workdir"] == "/home"


# ---------------------------------------------------------------------------
# __init__ re-exports
# ---------------------------------------------------------------------------
from src.state import (
    ARCHIVE_NAME,
    MODULE_COUNT,
    PORTING_NOTE,
    Observable as _Obs,
    AppMode as _AM,
    Store as _St,
)


def test_init_re_exports():
    assert ARCHIVE_NAME == "state"
    assert MODULE_COUNT == 6
    assert "Ported" in PORTING_NOTE or "ported" in PORTING_NOTE
    assert isinstance(_Obs(1), Observable)
    assert issubclass(_AM, AppMode)
    assert issubclass(_St, Store)
