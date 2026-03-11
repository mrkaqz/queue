# Queue — Self-Hosted Queue Management App

A lightweight, self-hosted queue management system designed for small businesses (clinics, shops, service counters). Runs entirely in a single Docker container with no external dependencies.

---

## Features

- **TV Display Page** — Large queue number display for a wall-mounted screen or smart TV
- **Admin Page** — Operator controls to call, skip, recall, hold, and manage the queue
- **Settings Page** — Configure shop name, announcements, voice language, and more
- **Phone Status Page** — Customers scan a QR code to follow their queue on their phone
- **PWA Web Push Notifications** — Notify customers on their phone when their number is called (works in background)
- **Thai/English Voice Announcements** — Natural TTS via `edge-tts` (Microsoft Neural voices, no API key needed)
- **Real-time Updates** — WebSocket-powered live sync across all connected devices
- **SQLite** — Zero-config database, data persists via Docker volume
- **Single Docker Container** — Easy to deploy anywhere on your local network

---

## Pages

| Page | URL | Description |
|---|---|---|
| TV Display | `/tv` | Full-screen queue display for smart TV |
| Admin | `/admin` | Operator control panel |
| Settings | `/settings` | App configuration |
| Phone Status | `/status` | Customer-facing page via QR code |

---

## Quick Start

### Docker (recommended)

**Requirements:** Docker & Docker Compose

```bash
git clone https://github.com/mrkaqz/queue.git
cd queue
docker compose up -d
```

The app will be available at:
- **HTTP:** `http://<server-ip>:8080`
- **HTTPS:** `https://<server-ip>:8443` *(self-signed cert, required for PWA push notifications)*

> A self-signed SSL certificate is auto-generated on first run inside the container.

### Local Development (no Docker)

**Requirements:** Python 3.11+

```bash
git clone https://github.com/mrkaqz/queue.git
cd queue
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --host 127.0.0.1 --port 8080 --reload
```

---

## Usage

### TV Setup
Open `http://<server-ip>:8080/tv` in your smart TV browser and set it to fullscreen. It auto-updates via WebSocket whenever a queue number is called.

### Admin (Operator)
Open `http://<server-ip>:8080/admin` on any device. Use the controls to:

| Button | Action |
|---|---|
| **Call Next** | Advance to the next waiting number |
| **Add Queue** | Manually add a walk-in number |
| **Remove Last** | Remove the last waiting number (undo accidental add) |
| **Recall** | Re-announce the current number |
| **Skip** | Skip the current number (marks as skipped, calls next) |
| **Hold** | Put the current number on hold |
| **Reset** | Clear all queues (start of day) |

### Customer Phone
A QR code is shown on the TV page. Customers scan it to open `/status` on their phone and subscribe to push notifications — they'll be alerted when their number is called, even with the screen off.

---

## Voice Announcements

Voice announcements use [`edge-tts`](https://github.com/rany2/edge-tts) with Microsoft's neural voices — free, no API key required. Internet access is needed the first time a number is announced; audio is then **cached permanently** in `data/audio/`.

- Thai: `th-TH-PremwadeeNeural` → *"หมายเลขคิวที่ห้า"*
- English: `en-US-JennyNeural` → *"Queue number five"*
- Bilingual: Thai followed by English

Numbers are spoken naturally — `005` is announced as *"ห้า"* (five), not *"ศูนย์ศูนย์ห้า"*.

---

## Configuration

All settings are managed through `/settings` in the UI. No config files needed.

| Setting | Default | Description |
|---|---|---|
| Shop Name | `My Queue` | Displayed on TV and admin pages |
| Web App URL | *(empty)* | LAN URL for QR code, e.g. `http://192.168.1.100:8080` |
| Queue Padding | `3` | Display format: `005` vs `5` |
| Daily Reset Time | `00:00` | Auto-reset queue at this time each day |
| Announcement Message | *(empty)* | Scrolling ticker text on TV display |
| Announcement Language | `th` | `th` / `en` / `th+en` |
| Announcement Sound | `chime` | Sound before voice: `chime` / `bell` / `beep` / `none` |
| Thai Voice | `th-TH-PremwadeeNeural` | edge-tts voice for Thai |
| English Voice | `en-US-JennyNeural` | edge-tts voice for English |
| VAPID Email | *(required for push)* | Email used for Web Push VAPID keys |

> **Web App URL** — set this to your server's LAN IP so the QR code on the TV points to the right address when customers scan it from their phones.

---

## Project Structure

```
queue/
├── docker-compose.yml
├── Dockerfile
├── requirements.txt
│
└── app/
    ├── main.py                  # FastAPI entry point, lifespan, routes
    ├── database.py              # SQLite setup & all DB helpers
    ├── models.py                # Pydantic data models
    ├── tts.py                   # edge-tts voice generation & file cache
    ├── number_to_words.py       # Integer → Thai/English word converter
    ├── websocket.py             # WebSocket broadcast manager
    ├── routers/
    │   ├── queue.py             # Queue API endpoints
    │   ├── settings.py          # Settings API endpoints
    │   └── push.py              # Web Push subscription endpoints
    └── static/
        ├── manifest.json        # PWA manifest
        ├── sw.js                # Service Worker (push notifications)
        ├── tv/index.html        # TV display page
        ├── admin/index.html     # Admin/operator page
        ├── settings/index.html  # Settings page
        └── status/index.html    # Customer phone page
```

---

## API Reference

### Queue

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/queue/status` | Current number, next, and waiting count |
| `GET` | `/api/queue/list` | Full queue list for today |
| `POST` | `/api/queue/add` | Add next queue number |
| `POST` | `/api/queue/call-next` | Call next waiting number |
| `POST` | `/api/queue/recall` | Re-announce current number |
| `POST` | `/api/queue/skip` | Skip current number |
| `POST` | `/api/queue/hold` | Put current number on hold |
| `POST` | `/api/queue/remove-last` | Remove the last waiting number |
| `POST` | `/api/queue/reset` | Reset all queues |

### Settings

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/settings` | Get all settings |
| `PUT` | `/api/settings` | Update settings |

### Push Notifications

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/push/vapid-key` | Get public VAPID key |
| `POST` | `/api/push/subscribe` | Register device for push |
| `POST` | `/api/push/unsubscribe` | Remove device subscription |

### WebSocket

Connect to `ws://<server>:8080/ws` for real-time events.

```json
{ "event": "init",             "status": {...}, "shop_name": "My Queue" }
{ "event": "queue_called",     "current": "005", "next": "006", "waiting": 12, "audio_urls": [...] }
{ "event": "queue_added",      "number": "018",  "waiting": 13 }
{ "event": "queue_recalled",   "current": "005", "audio_urls": [...] }
{ "event": "queue_skipped",    "current": "006", "waiting": 11 }
{ "event": "queue_held",       "held": "005" }
{ "event": "queue_removed",    "number": "018",  "waiting": 12 }
{ "event": "queue_reset" }
{ "event": "settings_updated", "shop_name": "My Clinic", "announcement_message": "..." }
```

---

## PWA & Push Notifications

Web Push requires HTTPS. The container auto-generates a self-signed certificate on first run.

- **Android (Chrome):** native "Allow notifications" prompt
- **iOS (Safari 16.4+):** customer must **Add to Home Screen** first, then enable notifications

---

## Tech Stack

| Layer | Technology |
|---|---|
| Backend | [FastAPI](https://fastapi.tiangolo.com/) (Python 3.11) |
| Database | SQLite via `aiosqlite` |
| Real-time | WebSockets |
| TTS | [edge-tts](https://github.com/rany2/edge-tts) |
| Push | Web Push API + `pywebpush` |
| Frontend | Vanilla HTML / CSS / JavaScript |
| Container | Docker + Docker Compose |

---

## License

MIT — free to use, modify, and self-host.
