import uuid

from sqlalchemy import distinct, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import is_local_mode, settings
from app.core.redis import store_refresh_session
from app.core.security import (
    create_access_token,
    create_refresh_token,
    hash_password,
    verify_password,
)
from app.models.user import DeviceTrial, User
from app.utils.auth_utils import current_token_version, hash_device_id


class DeviceTrialLimitError(Exception):
    """Raised when a device is already linked to too many accounts."""


def device_trial_enforcement_active() -> bool:
    return settings.DEVICE_TRIAL_ENFORCEMENT_ENABLED and not is_local_mode()


def device_account_limit_message() -> str:
    return f"This device is already linked to the maximum of {settings.DEVICE_TRIAL_MAX_ACCOUNTS} accounts."


async def register_user(db: AsyncSession, email: str, password: str) -> tuple[User, str, str]:
    user = User(email=email, password_hash=hash_password(password))
    db.add(user)
    await db.commit()
    await db.refresh(user)
    version = current_token_version(user)
    session_id = str(uuid.uuid4())
    await store_refresh_session(str(user.id), session_id, settings.JWT_REFRESH_EXPIRE_DAYS * 24 * 60 * 60)
    return user, create_access_token(str(user.id), version), create_refresh_token(str(user.id), version, session_id)


async def authenticate_user(db: AsyncSession, email: str, password: str) -> User | None:
    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar()
    if user and verify_password(password, user.password_hash):
        return user
    return None


async def ensure_device_trial_available(db: AsyncSession, device_id: str) -> None:
    if not device_trial_enforcement_active():
        return
    device_id_hash = hash_device_id(device_id)
    existing_trial_count = (
        await db.execute(
            select(func.count(distinct(DeviceTrial.user_id)))
            .select_from(DeviceTrial)
            .where(DeviceTrial.device_id_hash == device_id_hash)
        )
    ).scalar_one()
    if int(existing_trial_count or 0) >= settings.DEVICE_TRIAL_MAX_ACCOUNTS:
        raise DeviceTrialLimitError(device_account_limit_message())


async def link_device_to_user_if_allowed(
    db: AsyncSession,
    user_id: uuid.UUID,
    device_id: str,
    *,
    strict: bool = True,
) -> None:
    if not device_trial_enforcement_active():
        return

    device_id_hash = hash_device_id(device_id)
    existing_link = (
        await db.execute(
            select(DeviceTrial.id)
            .where(
                DeviceTrial.user_id == user_id,
                DeviceTrial.device_id_hash == device_id_hash,
            )
            .limit(1)
        )
    ).scalar_one_or_none()
    if existing_link is not None:
        return

    linked_account_count = (
        await db.execute(
            select(func.count(distinct(DeviceTrial.user_id)))
            .select_from(DeviceTrial)
            .where(DeviceTrial.device_id_hash == device_id_hash)
        )
    ).scalar_one()
    if int(linked_account_count or 0) >= settings.DEVICE_TRIAL_MAX_ACCOUNTS:
        if strict:
            raise DeviceTrialLimitError(device_account_limit_message())
        return

    db.add(build_device_trial(user_id, device_id))


def build_device_trial(user_id: uuid.UUID, device_id: str) -> DeviceTrial:
    return DeviceTrial(
        user_id=user_id,
        device_id_hash=hash_device_id(device_id),
    )
