"""Database-backed, worker-safe in-app reminder scheduling."""
import os
import threading
import uuid
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy import update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .database import SessionLocal
from .models.document import ActionItem, InAppNotification, ReminderDelivery, SchedulerLease, UserPreference

REMINDER_DAYS = {7, 3, 1, 0}
LEASE_NAME = "in_app_reminder_scheduler"
WINDOWS_TIMEZONE_FALLBACKS = {
    "UTC": timezone.utc,
    "Asia/Kolkata": timezone(timedelta(hours=5, minutes=30)),
    "Asia/Calcutta": timezone(timedelta(hours=5, minutes=30)),
}


def _timezone_for(db: Session, user_id: int):
    preference = db.query(UserPreference).filter(UserPreference.user_id == user_id).first()
    try:
        return ZoneInfo(preference.timezone) if preference else timezone.utc
    except ZoneInfoNotFoundError:
        # Windows Python may lack tzdata. Use an explicit, safe fixed-offset
        # fallback rather than silently accepting an unknown timezone.
        return WINDOWS_TIMEZONE_FALLBACKS.get(preference.timezone, timezone.utc)


def schedule_due_reminders(db: Session, now_utc: datetime | None = None, user_id: int | None = None) -> int:
    """Create a single durable in-app notification for every due interval.

    The delivery row's unique constraint is the final concurrency safeguard. It
    makes a scheduler restart, manual API call, or second worker harmless.
    """
    now_utc = now_utc or datetime.now(timezone.utc)
    actions = db.query(ActionItem).filter(
        ActionItem.status.in_(("pending", "in_progress")), ActionItem.deadline.is_not(None)
    )
    if user_id is not None:
        actions = actions.filter(ActionItem.user_id == user_id)
    created = 0
    for action in actions.all():
        if action.user_id is None:
            continue
        local_tz = _timezone_for(db, action.user_id)
        due = action.deadline.replace(tzinfo=timezone.utc).astimezone(local_tz)
        local_now = now_utc.astimezone(local_tz)
        days = (due.date() - local_now.date()).days
        if days not in REMINDER_DAYS:
            continue
        kind = f"reminder-{days}d"
        delivery = ReminderDelivery(
            user_id=action.user_id, action_id=action.id, reminder_kind=kind,
            scheduled_for=due.replace(tzinfo=None),
        )
        try:
            with db.begin_nested():
                db.add(delivery)
                db.flush()
                db.add(InAppNotification(
                    user_id=action.user_id, action_id=action.id, kind=kind,
                    title=f"Upcoming deadline in {days} day{'s' if days != 1 else ''}",
                    body=f"Action '{action.title}' is due on {due.date().isoformat()}.",
                    document_id=action.document_id, scheduled_for=due.replace(tzinfo=None),
                ))
            created += 1
        except IntegrityError:
            # A concurrent worker or earlier restart has already persisted it.
            continue
    db.commit()
    return created


def cancel_action_reminders(db: Session, action_id: int, user_id: int) -> None:
    """Stop future/in-app reminder visibility while retaining audit state."""
    now = datetime.utcnow()
    db.query(ReminderDelivery).filter(
        ReminderDelivery.action_id == action_id,
        ReminderDelivery.user_id == user_id,
        ReminderDelivery.cancelled_at.is_(None),
    ).update({ReminderDelivery.cancelled_at: now}, synchronize_session=False)
    db.query(InAppNotification).filter(
        InAppNotification.user_id == user_id,
        InAppNotification.action_id == action_id,
        InAppNotification.kind.like("reminder-%"),
    ).delete(synchronize_session=False)


def acquire_scheduler_lease(db: Session, owner_id: str, now: datetime | None = None, seconds: int = 90) -> bool:
    """Atomically acquire the scheduler lease. Safe with multiple processes."""
    now = now or datetime.utcnow()
    until = now + timedelta(seconds=seconds)
    existing = db.get(SchedulerLease, LEASE_NAME)
    if existing is None:
        try:
            db.add(SchedulerLease(name=LEASE_NAME, owner_id=owner_id, locked_until=until))
            db.commit()
            return True
        except IntegrityError:
            db.rollback()
            return False
    result = db.execute(
        update(SchedulerLease).where(
            SchedulerLease.name == LEASE_NAME,
            SchedulerLease.locked_until <= now,
        ).values(owner_id=owner_id, locked_until=until, updated_at=now)
    )
    db.commit()
    return result.rowcount == 1


class ReminderScheduler:
    """Small internal polling service; no user token or admin account is involved."""
    def __init__(self, interval_seconds: int | None = None):
        self.interval_seconds = interval_seconds or int(os.getenv("CIRCULARLENS_REMINDER_INTERVAL_SECONDS", "300"))
        self.owner_id = f"{os.getpid()}-{uuid.uuid4().hex}"
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def run_once(self) -> int:
        db = SessionLocal()
        try:
            if not acquire_scheduler_lease(db, self.owner_id):
                return 0
            return schedule_due_reminders(db)
        finally:
            db.close()

    def _run(self) -> None:
        while not self._stop.is_set():
            try:
                self.run_once()
            except Exception:
                # Scheduler failures must not terminate the FastAPI server; durable
                # state and the next interval provide recovery.
                pass
            self._stop.wait(max(10, self.interval_seconds))

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._thread = threading.Thread(target=self._run, name="circularlens-reminders", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=2)
