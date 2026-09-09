import hashlib
import secrets

from app.models import ApiKey


def _hash_key(raw_key: str) -> str:
    return hashlib.sha256(raw_key.encode()).hexdigest()


def create_api_key(session, algorithm: str, capacity: int, window_seconds: int) -> str:
    raw_key = secrets.token_urlsafe(32)

    api_key = ApiKey(
        key_hash=_hash_key(raw_key),
        algorithm=algorithm,
        capacity=capacity,
        window_seconds=window_seconds,
    )
    session.add(api_key)
    session.commit()

    return raw_key


def get_config_by_key(session, raw_key: str) -> ApiKey | None:
    return session.query(ApiKey).filter_by(key_hash=_hash_key(raw_key)).first()
