from fastapi import APIRouter, Depends
from app import database as db
from app import tts
from app.websocket import manager
from app.routers.auth import require_auth

router = APIRouter(prefix="/api/queue", tags=["queue"])


async def _get_voice_settings() -> tuple[str, str, str]:
    settings = await db.get_all_settings()
    lang = settings.get("announcement_language", "th")
    voice_th = settings.get("thai_voice", "th-TH-PremwadeeNeural")
    voice_en = settings.get("english_voice", "en-US-JennyNeural")
    return lang, voice_th, voice_en


@router.get("/status")
async def queue_status():
    return await db.get_queue_status()


@router.get("/list", dependencies=[Depends(require_auth)])
async def queue_list():
    return await db.get_queue_list()


@router.post("/add", dependencies=[Depends(require_auth)])
async def add_queue():
    entry = await db.add_queue_entry()
    status = await db.get_queue_status()
    await manager.broadcast({
        "event": "queue_added",
        "number": entry["number_display"],
        "waiting": status["waiting"],
    })
    return entry


@router.post("/call-next", dependencies=[Depends(require_auth)])
async def call_next():
    lang, voice_th, voice_en = await _get_voice_settings()
    called = await db.call_next()
    if not called:
        return {"message": "No waiting numbers"}
    status = await db.get_queue_status()

    audio_urls = await tts.get_or_generate(called["number"], lang, voice_th, voice_en)

    await manager.broadcast({
        "event": "queue_called",
        "current": called["number_display"],
        "next": status["next"],
        "waiting": status["waiting"],
        "audio_urls": audio_urls,
    })
    return {**called, "audio_urls": audio_urls}


@router.post("/recall", dependencies=[Depends(require_auth)])
async def recall():
    lang, voice_th, voice_en = await _get_voice_settings()
    current = await db.recall_current()
    if not current:
        return {"message": "No number currently being served"}

    audio_urls = await tts.get_or_generate(current["number"], lang, voice_th, voice_en)

    await manager.broadcast({
        "event": "queue_recalled",
        "current": current["number_display"],
        "audio_urls": audio_urls,
    })
    return {**current, "audio_urls": audio_urls}


@router.post("/skip", dependencies=[Depends(require_auth)])
async def skip():
    lang, voice_th, voice_en = await _get_voice_settings()
    result = await db.skip_current()
    if not result:
        return {"message": "No number currently being served"}

    status = await db.get_queue_status()
    audio_urls = []
    if result.get("number"):
        audio_urls = await tts.get_or_generate(result["number"], lang, voice_th, voice_en)

    await manager.broadcast({
        "event": "queue_skipped",
        "skipped": result["skipped"],
        "current": result.get("number_display"),
        "waiting": status["waiting"],
        "audio_urls": audio_urls,
    })
    return result


@router.post("/hold", dependencies=[Depends(require_auth)])
async def hold():
    result = await db.hold_current()
    if not result:
        return {"message": "No number currently being served"}
    await manager.broadcast({
        "event": "queue_held",
        "held": result["number_display"],
    })
    return result


@router.post("/remove-last", dependencies=[Depends(require_auth)])
async def remove_last():
    result = await db.remove_last_waiting()
    if not result:
        return {"message": "No waiting numbers to remove"}
    status = await db.get_queue_status()
    await manager.broadcast({
        "event": "queue_removed",
        "number": result["number_display"],
        "waiting": status["waiting"],
    })
    return result


@router.post("/reset", dependencies=[Depends(require_auth)])
async def reset():
    await db.reset_queue()
    await manager.broadcast({"event": "queue_reset"})
    return {"message": "Queue reset"}
