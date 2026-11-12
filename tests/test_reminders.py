import datetime
from types import SimpleNamespace

import pytz

from beaverhabits import reminders
from beaverhabits.storage.storage import HabitStatus

UTC = pytz.utc


def at(hour, minute):
    # 2026-11-12 in UTC; Santiago is UTC-3 in November.
    return datetime.datetime(2026, 11, 12, hour, minute, tzinfo=UTC)


def test_is_due_respects_local_time():
    r = {"time": "20:00", "tz": "America/Santiago"}
    assert reminders.is_due(r, at(22, 59)) == (False, "2026-11-12")  # 19:59 local
    assert reminders.is_due(r, at(23, 0)) == (True, "2026-11-12")  # 20:00 local


def test_is_due_only_once_per_day():
    r = {"time": "08:00", "tz": "America/Santiago", "last_sent": "2026-11-12"}
    assert reminders.is_due(r, at(15, 0))[0] is False
    r["last_sent"] = "2026-11-11"
    assert reminders.is_due(r, at(15, 0))[0] is True


def test_is_due_rejects_bad_time():
    assert reminders.is_due({"time": "xx", "tz": "UTC"}, at(23, 0))[0] is False


def test_pending_habit_names_skips_done_and_archived():
    today = datetime.date(2026, 11, 12)
    habits = [
        SimpleNamespace(name="Correr", status=HabitStatus.ACTIVE, ticked_days=[today]),
        SimpleNamespace(name="Leer", status=HabitStatus.ACTIVE, ticked_days=[]),
        SimpleNamespace(name="Viejo", status=HabitStatus.ARCHIVED, ticked_days=[]),
    ]
    assert reminders.pending_habit_names(SimpleNamespace(habits=habits), today) == ["Leer"]


def test_build_message():
    assert reminders.build_message(["Leer"])["title"] == "Te falta 1 hábito hoy"
    msg = reminders.build_message(["A", "B", "C", "D"])
    assert msg["title"] == "Te faltan 4 hábitos hoy"
    assert msg["body"] == "A, B, C…"


def test_public_key_is_uncompressed_p256_point():
    key = reminders.public_key()
    # 65 bytes -> 87 base64url chars without padding
    assert len(key) == 87
