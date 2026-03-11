from pydantic import BaseModel
from typing import Optional


class QueueEntry(BaseModel):
    id: int
    number: int
    number_display: str
    status: str  # waiting, serving, served, skipped, held
    created_at: str
    called_at: Optional[str] = None


class QueueStatus(BaseModel):
    current: Optional[str] = None
    current_number: Optional[int] = None
    next: Optional[str] = None
    waiting: int = 0


class Settings(BaseModel):
    shop_name: str = "My Queue"
    queue_padding: int = 3
    daily_reset_time: str = "00:00"
    announcement_sound: str = "chime"
    announcement_message: str = ""
    announcement_language: str = "th"
    thai_voice: str = "th-TH-PremwadeeNeural"
    english_voice: str = "en-US-JennyNeural"
    vapid_email: str = ""
    vapid_public_key: str = ""
    vapid_private_key: str = ""


class PushSubscription(BaseModel):
    endpoint: str
    p256dh: str
    auth: str
    queue_number: Optional[int] = None
