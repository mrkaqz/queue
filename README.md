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
- **PIN Security** — 4-digit PIN locks `/admin` and `/settings` with backend-enforced session tokens (LAN & cloud-safe)
- **SQLite** — Zero-config database, data persists via Docker volume
- **Single Docker Container** — Easy to deploy anywhere on your local network or the cloud

---

## Pages

| Page | URL | Description |
|---|---|---|
| TV Display | `/tv` | Full-screen queue display for smart TV |
| Admin | `/admin` | Operator control panel |
| Settings | `/settings` | App configuration |
| Phone Status | `/status` | Customer-facing page via QR code |

---

## Compatible Platforms

| OS / Device | Docker | Python (no Docker) |
|---|---|---|
| Windows 10/11 | ✅ Docker Desktop | ✅ Python 3.11+ |
| macOS (Intel & Apple Silicon) | ✅ Docker Desktop | ✅ Python 3.11+ |
| Linux (Ubuntu, Debian, etc.) | ✅ Docker Engine | ✅ Python 3.11+ |
| Synology NAS (x86-64 / ARM64) | ✅ Container Manager | — |

> **Architectures:** pre-built images are available for `linux/amd64` and `linux/arm64`.
>
> **Synology NAS:** The default config uses a named volume (created automatically). If you switch to a bind mount (`./data:/app/data`), create the `data` folder in File Station first.

---

## Docker Image (GHCR)

Pre-built images are published automatically to the GitHub Container Registry on every release:

```
ghcr.io/mrkaqz/queue:latest       # latest main branch
ghcr.io/mrkaqz/queue:1.0.7        # specific version
```

[![Build & Push to GHCR](https://github.com/mrkaqz/queue/actions/workflows/docker-publish.yml/badge.svg)](https://github.com/mrkaqz/queue/actions/workflows/docker-publish.yml)

---

## Quick Start

### Option 1 — Docker via GHCR (recommended, no git clone needed)

Create a `docker-compose.yml` anywhere on your machine:

```yaml
services:
  queue:
    image: ghcr.io/mrkaqz/queue:latest
    ports:
      - "8080:8080"
      - "8443:8443"
    volumes:
      - queue_data:/app/data   # named volume — created automatically
    restart: unless-stopped

volumes:
  queue_data:
```

Then run — no folder setup needed:

```bash
docker compose up -d
```

The app will be available at:
- **HTTP:** `http://<server-ip>:8080`
- **HTTPS:** `https://<server-ip>:8443` *(self-signed cert, required for PWA push notifications)*

> A self-signed SSL certificate is auto-generated on first run inside the container.

**To update to the latest version:**

```bash
docker compose pull && docker compose up -d
```

---

### Option 2 — Docker (build from source)

```bash
git clone https://github.com/mrkaqz/queue.git
cd queue
docker compose up -d
```

---

### Option 3 — Python directly (no Docker)

**Requirements:** Python 3.11+ — [python.org/downloads](https://www.python.org/downloads/)

#### macOS / Linux

```bash
git clone https://github.com/mrkaqz/queue.git
cd queue
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --host 127.0.0.1 --port 8080 --reload
```

#### Windows (Command Prompt)

```cmd
git clone https://github.com/mrkaqz/queue.git
cd queue
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --host 127.0.0.1 --port 8080 --reload
```

#### Windows (PowerShell)

```powershell
git clone https://github.com/mrkaqz/queue.git
cd queue
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --host 127.0.0.1 --port 8080 --reload
```

Then open `http://localhost:8080` in your browser.

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

## Security (PIN Lock)

The `/admin` and `/settings` pages are protected by a **4-digit PIN** with backend-enforced session tokens — safe for both local network and internet/cloud deployments.

### First-time setup
On the very first visit to `/admin` or `/settings`, a **Set Up Admin PIN** screen appears. Enter and confirm a 4-digit PIN — the session is then unlocked for that browser tab.

### Returning visits
A PIN entry screen appears when no session token is found. The session is stored in `sessionStorage` — it survives page refresh within the same tab but requires re-entry in a new tab.

### Change PIN
A 🔑 button in the admin page nav opens a **Change PIN** modal. Requires the current PIN before accepting a new one.

### How it works
- PINs are stored as **SHA-256 hashes** — never plain text
- After a correct PIN entry the server issues a **Bearer token** (8-hour TTL, stored in `sessionStorage`)
- All protected API endpoints return `401 Unauthorized` without a valid token — the frontend lock cannot be bypassed by calling the API directly
- The TV display (`/tv`), customer status page (`/status`), and WebSocket are public and unaffected

---

## Voice Announcements

Voice announcements use [`edge-tts`](https://github.com/rany2/edge-tts) with Microsoft's neural voices — free, no API key required. Internet access is needed the first time a number is announced; audio is then **cached permanently** in `data/audio/`.

On startup, audio for numbers **1–100 is pre-generated in the background** so the first queue call plays instantly with no delay. The cache is automatically rebuilt whenever voice or language settings are changed.

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
| Announcement Sound Output | `TV only` | Where audio plays: `TV only` / `Admin + TV` / `Admin only` |
| Timezone Offset | `0` | UTC offset for admin timestamps. e.g. `0` = UTC, `7` = Bangkok (UTC+7), `-5` = EST, `5.5` = IST |
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
    │   ├── auth.py              # PIN auth endpoints & session token logic
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

> **Auth:** endpoints marked 🔒 require `Authorization: Bearer <token>` — obtain a token via `POST /api/auth/verify-pin`. Unmarked endpoints are public.

### Authentication

| Method | Endpoint | Auth | Description |
|---|---|---|---|
| `GET` | `/api/auth/status` | Public | Check whether a PIN is configured |
| `POST` | `/api/auth/set-pin` | Public | Set the PIN for the first time |
| `POST` | `/api/auth/verify-pin` | Public | Verify PIN → returns session token |
| `POST` | `/api/auth/change-pin` | 🔒 | Change PIN (verifies current PIN first) |

### Queue

| Method | Endpoint | Auth | Description |
|---|---|---|---|
| `GET` | `/api/queue/status` | Public | Current number, next, and waiting count |
| `GET` | `/api/queue/list` | 🔒 | Full queue list for today |
| `POST` | `/api/queue/add` | 🔒 | Add next queue number |
| `POST` | `/api/queue/call-next` | 🔒 | Call next waiting number |
| `POST` | `/api/queue/recall` | 🔒 | Re-announce current number |
| `POST` | `/api/queue/skip` | 🔒 | Skip current number |
| `POST` | `/api/queue/hold` | 🔒 | Put current number on hold |
| `POST` | `/api/queue/remove-last` | 🔒 | Remove the last waiting number |
| `POST` | `/api/queue/reset` | 🔒 | Reset all queues |

### Settings

| Method | Endpoint | Auth | Description |
|---|---|---|---|
| `GET` | `/api/settings` | 🔒 | Get all settings |
| `PUT` | `/api/settings` | 🔒 | Update settings |
| `POST` | `/api/settings/logo` | 🔒 | Upload shop logo |
| `DELETE` | `/api/settings/logo` | 🔒 | Remove shop logo |

### Push Notifications

| Method | Endpoint | Auth | Description |
|---|---|---|---|
| `GET` | `/api/push/vapid-key` | Public | Get public VAPID key |
| `POST` | `/api/push/subscribe` | Public | Register device for push |
| `POST` | `/api/push/unsubscribe` | Public | Remove device subscription |

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
