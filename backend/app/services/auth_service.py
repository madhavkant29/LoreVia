import uuid

from sqlalchemy import func, select
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
    """Raised when a device has already consumed its free-trial signup."""


def device_trial_enforcement_active() -> bool:
    return settings.DEVICE_TRIAL_ENFORCEMENT_ENABLED and not is_local_mode()


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
            select(func.count())
            .select_from(DeviceTrial)
            .where(DeviceTrial.device_id_hash == device_id_hash)
        )
    ).scalar_one()
    if int(existing_trial_count or 0) >= settings.DEVICE_TRIAL_MAX_ACCOUNTS:
        raise DeviceTrialLimitError(
            f"This device has already used the maximum of {settings.DEVICE_TRIAL_MAX_ACCOUNTS} trial accounts."
        )


def build_device_trial(user_id: uuid.UUID, device_id: str) -> DeviceTrial:
    return DeviceTrial(
        user_id=user_id,
        device_id_hash=hash_device_id(device_id),
    )
