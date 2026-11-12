"""Daily reminders delivered as Web Push notifications.

Each user stores, inside their user configs, a ``reminder`` dict:
    {"enabled": bool, "time": "HH:MM", "tz": "America/Santiago",
     "last_sent": "YYYY-MM-DD", "subscriptions": [<PushSubscription JSON>]}

A background task wakes up every minute and, for every user whose local time
has passed their reminder time and who has not been notified today, sends a
push listing the habits still pending today.
"""

import asyncio
import datetime
import json
from pathlib import Path

import pytz
from cryptography.hazmat.primitives import serialization
from loguru import logger
from py_vapid import Vapid, b64urlencode
from pywebpush import WebPushException, webpush

from beaverhabits.app import crud
from beaverhabits.app.db import User
from beaverhabits.configs import USER_DATA_FOLDER, settings
from beaverhabits.storage.storage import HabitStatus

REMINDER_KEY = "reminder"
DEFAULT_TIME = "20:00"
MAX_SUBSCRIPTIONS = 5
CHECK_INTERVAL_SECONDS = 60

_vapid: Vapid | None = None


def get_vapid() -> Vapid:
    """Load the VAPID key pair, creating and persisting one on first use."""
    global _vapid
    if _vapid:
        return _vapid

    if settings.VAPID_PRIVATE_KEY:
        _vapid = Vapid.from_string(settings.VAPID_PRIVATE_KEY)
        return _vapid

    path = Path(USER_DATA_FOLDER) / "vapid_private.pem"
    if path.exists():
        _vapid = Vapid.from_file(str(path))
    else:
        path.parent.mkdir(parents=True, exist_ok=True)
        _vapid = Vapid()
        _vapid.generate_keys()
        _vapid.save_key(str(path))
        logger.info(f"Generated new VAPID key at {path}")
    return _vapid


def public_key() -> str:
    raw = get_vapid().public_key.public_bytes(
        serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint
    )
    return b64urlencode(raw)


def vapid_subject() -> str:
    if settings.VAPID_SUBJECT:
        return settings.VAPID_SUBJECT
    if settings.APP_URL.startswith("https://"):
        return settings.APP_URL.rstrip("/")
    return "mailto:noreply@localhost"


# ---------------------------------------------------------------- user config


async def get_reminder(user: User) -> dict:
    configs = await crud.get_user_configs(user) or {}
    reminder = dict(configs.get(REMINDER_KEY) or {})
    reminder.setdefault("enabled", False)
    reminder.setdefault("time", DEFAULT_TIME)
    reminder.setdefault("subscriptions", [])
    return reminder


async def save_reminder(user: User, reminder: dict) -> None:
    await crud.update_user_configs(user, {REMINDER_KEY: reminder})


async def add_subscription(user: User, subscription: dict, tz: str | None) -> None:
    if not isinstance(subscription, dict) or not subscription.get("endpoint"):
        raise ValueError("Invalid subscription")
    reminder = await get_reminder(user)
    subs = [s for s in reminder["subscriptions"] if s.get("endpoint") != subscription["endpoint"]]
    subs.append(subscription)
    reminder["subscriptions"] = subs[-MAX_SUBSCRIPTIONS:]
    if tz and tz in pytz.all_timezones_set:
        reminder["tz"] = tz
    await save_reminder(user, reminder)


# ------------------------------------------------------------------- sending


def pending_habit_names(habit_list, today: datetime.date) -> list[str]:
    names = []
    for habit in habit_list.habits:
        if habit.status != HabitStatus.ACTIVE:
            continue
        if today not in set(habit.ticked_days):
            names.append(habit.name)
    return names


def build_message(pending: list[str]) -> dict:
    if not pending:
        return {"title": "¡Día completo! 🎉", "body": "Marcaste todos tus hábitos de hoy."}
    shown = ", ".join(pending[:3]) + ("…" if len(pending) > 3 else "")
    count = len(pending)
    title = f"Te {'falta' if count == 1 else 'faltan'} {count} {'hábito' if count == 1 else 'hábitos'} hoy"
    return {"title": title, "body": shown}


def _send_one(subscription: dict, payload: dict) -> bool:
    """Send a push; return False if the subscription is gone and should be dropped."""
    try:
        webpush(
            subscription_info=subscription,
            data=json.dumps(payload, ensure_ascii=False),
            vapid_private_key=get_vapid(),
            vapid_claims={"sub": vapid_subject()},
            ttl=60 * 60 * 6,
        )
        return True
    except WebPushException as e:
        status = getattr(e.response, "status_code", None)
        if status in (404, 410):
            return False
        logger.warning(f"Push failed ({status}): {e}")
        return True


async def send_to_user(user: User, payload: dict) -> int:
    """Send to every device of a user. Returns the number of live subscriptions."""
    reminder = await get_reminder(user)
    alive = []
    for sub in reminder["subscriptions"]:
        if await asyncio.to_thread(_send_one, sub, payload):
            alive.append(sub)
    if len(alive) != len(reminder["subscriptions"]):
        reminder["subscriptions"] = alive
        await save_reminder(user, reminder)
    return len(alive)


async def send_test(user: User) -> int:
    return await send_to_user(
        user, {"title": "MenosClick Hábitos", "body": "Así te llegarán los recordatorios. 👋"}
    )


def is_due(reminder: dict, now_utc: datetime.datetime) -> tuple[bool, str]:
    """Whether a reminder should fire now. Returns (due, local_date_iso)."""
    tz = pytz.timezone(settings.TIME_ZONE or reminder.get("tz") or "UTC")
    local = now_utc.astimezone(tz)
    today = local.date().isoformat()
    try:
        hh, mm = (int(x) for x in reminder.get("time", DEFAULT_TIME).split(":"))
    except ValueError:
        return False, today
    if reminder.get("last_sent") == today:
        return False, today
    return (local.hour, local.minute) >= (hh, mm), today


async def run_due_reminders(now_utc: datetime.datetime | None = None) -> int:
    from beaverhabits import views  # avoid import cycle

    now_utc = now_utc or datetime.datetime.now(pytz.utc)
    sent = 0
    for user in await crud.get_user_list():
        if not user.is_active:
            continue
        reminder = await get_reminder(user)
        if not reminder["enabled"] or not reminder["subscriptions"]:
            continue
        due, today = is_due(reminder, now_utc)
        if not due:
            continue

        habit_list = await views.get_user_habit_list(user)
        if habit_list is None:
            continue
        pending = pending_habit_names(habit_list, datetime.date.fromisoformat(today))
        if pending:
            await send_to_user(user, {**build_message(pending), "url": "/gui"})
            sent += 1
        # Re-read to keep subscriptions pruned by send_to_user.
        reminder = await get_reminder(user)
        reminder["last_sent"] = today
        await save_reminder(user, reminder)
    return sent


async def reminder_task():
    logger.info("Starting reminder task")
    while True:
        await asyncio.sleep(CHECK_INTERVAL_SECONDS)
        try:
            await run_due_reminders()
        except Exception:
            logger.exception("Error during reminder task")
