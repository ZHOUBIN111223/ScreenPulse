"""LiveKit token creation helper kept for the optional media integration path."""

from livekit.api import AccessToken, VideoGrants

from app.config import get_settings

settings = get_settings()


def create_livekit_token(identity: str, room_name: str) -> tuple[str, str]:
    if not settings.livekit_url or not settings.livekit_api_key or not settings.livekit_api_secret:
        raise ValueError("LiveKit 环境变量未配置完整")

    token = (
        AccessToken(settings.livekit_api_key, settings.livekit_api_secret)
        .with_identity(identity)
        .with_name(identity)
        .with_grants(VideoGrants(room_join=True, room=room_name, can_publish=True))
        .to_jwt()
    )
    return settings.livekit_url, token
