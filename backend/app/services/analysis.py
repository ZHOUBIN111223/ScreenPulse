"""Screenshot persistence, multimodal analysis calls, and hourly summary refresh helpers."""

import base64
import io
import json
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from uuid import uuid4

import requests
from PIL import Image, UnidentifiedImageError
from fastapi import HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import FrameCapture, HourlySummary, TeamSetting, VisionResult

logger = logging.getLogger(__name__)
settings = get_settings()
ALLOWED_FRAME_CONTENT_TYPES = {"image/png", "image/jpeg"}


@dataclass(slots=True)
class VisionAnalysis:
    recognized_content: str
    activity_description: str
    model_name: str


def save_frame_file(file: UploadFile, team_id: int, session_id: int) -> tuple[Path, int, int]:
    if file.content_type not in ALLOWED_FRAME_CONTENT_TYPES:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unsupported image type")

    payload = file.file.read(settings.max_frame_upload_bytes + 1)
    if len(payload) > settings.max_frame_upload_bytes:
        file.file.close()
        raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="Screenshot is too large")

    target_dir = settings.storage_path / "frames" / str(team_id) / str(session_id)
    target_dir.mkdir(parents=True, exist_ok=True)

    filename = f"{uuid4().hex}.png"
    target_path = target_dir / filename

    try:
        try:
            with Image.open(io.BytesIO(payload)) as image:
                width, height = image.size
                if width * height > settings.max_frame_pixels:
                    raise HTTPException(
                        status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                        detail="Screenshot dimensions are too large",
                    )
                normalized = image.convert("RGB")
                normalized.save(target_path, format="PNG", optimize=True)
        except HTTPException:
            raise
        except (OSError, UnidentifiedImageError) as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid image upload") from exc
    finally:
        file.file.close()

    return target_path, width, height


def _extract_content(payload: dict) -> str:
    choices = payload.get("choices", [])
    if not choices:
        return ""

    content = choices[0].get("message", {}).get("content", "")
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        chunks = [part.get("text", "") for part in content if isinstance(part, dict)]
        return "\n".join(chunk for chunk in chunks if chunk).strip()
    return ""


def _call_model(prompt: str, image_path: Path | None = None, model_name: str = "") -> str:
    if not settings.model_api_base_url or not model_name:
        return ""

    messages: list[dict] = [{"role": "user", "content": [{"type": "text", "text": prompt}]}]
    if image_path is not None:
        encoded = base64.b64encode(image_path.read_bytes()).decode("utf-8")
        messages[0]["content"].append(
            {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{encoded}"}}
        )

    headers = {"Content-Type": "application/json"}
    if settings.model_api_key:
        headers["Authorization"] = f"Bearer {settings.model_api_key}"

    response = requests.post(
        f"{settings.model_api_base_url.rstrip('/')}/chat/completions",
        headers=headers,
        json={"model": model_name, "messages": messages},
        timeout=90,
    )
    response.raise_for_status()
    return _extract_content(response.json())


def analyze_screenshot(image_path: Path, width: int, height: int) -> VisionAnalysis:
    prompt = (
        "You are analyzing a desktop screenshot. Return valid JSON with two string fields: "
        "recognized_content and activity_description. recognized_content should describe the software "
        "and visible page content. activity_description should describe the user's main activity in one sentence. "
        "Do not invent details that are not visible."
    )

    fallback_content = (
        f"Captured one {width}x{height} desktop frame. "
        "No vision model is configured, so only basic frame metadata was recorded."
    )
    fallback_activity = "No vision model is configured, so no activity description is available."
    fallback_model = settings.vision_model or "fallback"

    try:
        result = _call_model(prompt, image_path=image_path, model_name=settings.vision_model)
        if result:
            try:
                parsed = json.loads(result)
                recognized_content = str(parsed.get("recognized_content", "")).strip()
                activity_description = str(parsed.get("activity_description", "")).strip()
                if recognized_content or activity_description:
                    return VisionAnalysis(
                        recognized_content=recognized_content or activity_description,
                        activity_description=activity_description or recognized_content,
                        model_name=settings.vision_model,
                    )
            except json.JSONDecodeError:
                cleaned = " ".join(result.split())
                if cleaned:
                    return VisionAnalysis(
                        recognized_content=cleaned,
                        activity_description=cleaned,
                        model_name=settings.vision_model,
                    )
    except Exception as exc:  # pragma: no cover - external dependency
        logger.warning("Vision model call failed: %s", exc)

    return VisionAnalysis(
        recognized_content=fallback_content,
        activity_description=fallback_activity,
        model_name=fallback_model,
    )


def summarize_hour(entries: list[str]) -> tuple[str, str]:
    model_name = settings.summary_model or "fallback"
    if not entries:
        return "No frame observations are available for this hour.", model_name

    prompt = (
        "Summarize the following screen observations from one team member within the same hour. "
        "Return 2 to 4 short English sentences covering the main work, software in use, and context changes. "
        "Do not use bullets.\n\n"
        + "\n".join(f"- {entry}" for entry in entries)
    )

    try:
        result = _call_model(prompt, model_name=settings.summary_model)
        if result:
            return result, model_name
    except Exception as exc:  # pragma: no cover - external dependency
        logger.warning("Summary model call failed: %s", exc)

    unique_entries = list(dict.fromkeys(entries))
    compact = "; ".join(unique_entries[:3])
    return f"This hour includes {len(entries)} captured frames. Main observations: {compact}", model_name


def get_team_setting(db: Session, team_id: int) -> TeamSetting:
    setting = db.scalar(select(TeamSetting).where(TeamSetting.team_id == team_id))
    if setting is None:
        setting = TeamSetting(
            team_id=team_id,
            frame_interval_seconds=settings.default_sampling_interval_seconds,
            frame_interval_minutes=settings.default_sampling_interval_minutes,
        )
        db.add(setting)
        db.commit()
        db.refresh(setting)
    return setting


def refresh_hourly_summary(db: Session, team_id: int, user_id: int, hour_start: datetime) -> HourlySummary:
    hour_end = hour_start + timedelta(hours=1)
    observations = db.scalars(
        select(VisionResult.activity_description)
        .join(FrameCapture, VisionResult.frame_id == FrameCapture.id)
        .where(
            VisionResult.team_id == team_id,
            VisionResult.user_id == user_id,
            FrameCapture.captured_at >= hour_start,
            FrameCapture.captured_at < hour_end,
        )
        .order_by(FrameCapture.captured_at.asc())
    ).all()

    summary = db.scalar(
        select(HourlySummary).where(
            HourlySummary.team_id == team_id,
            HourlySummary.user_id == user_id,
            HourlySummary.hour_start == hour_start,
        )
    )

    summary_text, model_name = summarize_hour(observations)
    frame_count = len(observations)

    if summary is None:
        summary = HourlySummary(
            team_id=team_id,
            user_id=user_id,
            hour_start=hour_start,
            hour_end=hour_end,
            summary_text=summary_text,
            frame_count=frame_count,
            model_name=model_name,
        )
        db.add(summary)
    else:
        summary.hour_end = hour_end
        summary.summary_text = summary_text
        summary.frame_count = frame_count
        summary.model_name = model_name

    db.commit()
    db.refresh(summary)
    return summary
