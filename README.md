# 🔢 Queue — Self-Hosted Queue Management App

A lightweight, self-hosted queue management system designed for small businesses (clinics, shops, service counters). Runs entirely in a single Docker container with no external dependencies.

---

## ✨ Features

- 📺 **TV Display Page** — Large queue number display for a wall-mounted screen or smart TV
- 🖥️ **Admin Page** — Operator controls to call, skip, recall, and manage the queue
- ⚙️ **Settings Page** — Configure shop name, announcements, voice language, and more
- 📱 **Phone Status Page** — Customers scan a QR code to follow their queue on their phone
- 🔔 **PWA Web Push Notifications** — Notify customers on their phone when their number is called (works in background)
- 🔊 **Thai/English Voice Announcements** — Natural human-sounding TTS via `edge-tts` (`th-TH-PremwadeeNeural`)
- ⚡ **Real-time Updates** — WebSocket-powered live sync across all connected devices
- 🗄️ **SQLite** — Zero-config database, data persists via Docker volume
- 🐳 **Single Docker Container** — Easy to deploy anywhere on your local network

---

## 📸 Pages

| Page | URL | Description |
|---|---|---|
| TV Display | `/tv` | Full-screen queue display for smart TV |
| Admin | `/admin` | Operator control panel |
| Settings | `/settings` | App configuration |
| Phone Status | `/status` | Customer-facing page via QR code |

---

## 🚀 Quick Start

### Requirements
- Docker & Docker Compose

### Run

```bash
git clone https://github.com/mrkaqz/queue.git
cd queue
docker compose up -d
```

The app will be available at:
- **HTTP:** `http://localhost:8080`
- **HTTPS:** `https://localhost:8443` *(self-signed cert, required for PWA push notifications)*

> On first run, a self-signed SSL certificate is automatically generated inside the container.

---

## 🖥️ Usage

### TV Setup
Open `http://<your-server-ip>:8080/tv` in your smart TV browser. Set it to fullscreen — it will auto-update via WebSocket whenever a queue number is called.

### Admin (Operator)
Open `http://<your-server-ip>:8080/admin` on any device. Use the controls to:
- **Call Next** — advance to the next waiting number
- **Recall** — re-announce the current number
- **Skip** — skip the current number
- **Add Queue** — manually add a walk-in number
- **Reset** — clear all queues (start of day)

### Customer Phone
A QR code is displayed on the TV page. Customers scan it to open `/status` on their phone. They can subscribe to push notifications to be alerted when their number is called — even with the screen off.

---

## 🔊 Voice Announcements

Voice announcements use [`edge-tts`](https://github.com/rany2/edge-tts) with Microsoft's neural voices — free, no API key required.

- Thai: `th-TH-PremwadeeNeural` → *"หมายเลขคิวที่ห้า"*
- English: `en-US-JennyNeural` → *"Queue number five"*
- Bilingual: Thai followed by English with a short pause

Numbers are spoken naturally — `005` is announced as *"ห้า"* (five), not *"ศูนย์ศูนย์ห้า"*.

Audio files are generated on first use and **cached permanently** in `/app/data/audio/` — fully offline after warmup.

---

## ⚙️ Configuration

All settings are managed through the `/settings` page in the UI. No environment variables or config files needed.

| Setting | Default | Description |
|---|---|---|
| Shop Name | `My Queue` | Displayed on all pages |
| Queue Padding | `3` | Display format: `005` vs `5` |
| Daily Reset Time | `00:00` | Auto-reset queue at this time |
| Announcement Sound | `chime` | Sound played before voice: `chime` / `bell` / `beep` |
| Announcement Message | *(empty)* | Scrolling banner text on TV display |
| Announcement Language | `th` | `th` / `en` / `th+en` |
| Thai Voice | `th-TH-PremwadeeNeural` | edge-tts voice for Thai |
| English Voice | `en-US-JennyNeural` | edge-tts voice for English |
| VAPID Email | *(required for push)* | Email used for Web Push VAPID keys |

---

## 📦 Project Structure

```
queue/
├── docker-compose.yml
├── Dockerfile
├── requirements.txt
│
└── app/
    ├── main.py                  # FastAPI entry point
    ├── database.py              # SQLite setup & helpers
    ├── models.py                # Data models
    ├── tts.py                   # edge-tts voice generation & cache
    ├── number_to_words.py       # Integer → Thai/English word converter
    ├── routers/
    │   ├── queue.py             # Queue CRUD API
    │   ├── settings.py          # Settings API
    │   └── push.py              # Web Push subscription API
    ├── websocket.py             # WebSocket broadcast manager
    └── static/
        ├── manifest.json        # PWA manifest
        ├── sw.js                # Service Worker (push notifications)
        ├── tv/index.html        # TV display page
        ├── admin/index.html     # Admin/operator page
        ├── settings/index.html  # Settings page
        └── status/index.html    # Phone status page
```

---

## 🔌 API Reference

### Queue

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/queue/status` | Current serving number, next, waiting count |
| `GET` | `/api/queue/list` | Full queue list for today |
| `POST` | `/api/queue/add` | Add next queue number |
| `POST` | `/api/queue/call-next` | Call next waiting number |
| `POST` | `/api/queue/recall` | Re-announce current number |
| `POST` | `/api/queue/skip` | Skip current number |
| `POST` | `/api/queue/hold` | Put current on hold |
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

| URL | Description |
|---|---|
| `WS /ws` | Real-time event stream for all clients |

#### WebSocket Events

```json
{ "event": "queue_called",     "current": "005", "next": "006", "waiting": 12 }
{ "event": "queue_added",      "number": "018",  "waiting": 13 }
{ "event": "queue_recalled",   "current": "005" }
{ "event": "queue_skipped",    "current": "006", "waiting": 11 }
{ "event": "queue_reset" }
{ "event": "announcement",     "message": "Counter 1 is now open" }
{ "event": "settings_updated", "shop_name": "My Clinic" }
```

---

## 🐳 Docker Details

```yaml
services:
  queue-app:
    build: .
    ports:
      - "8080:8080"   # HTTP
      - "8443:8443"   # HTTPS (required for PWA Web Push)
    volumes:
      - ./data:/app/data  # Persists SQLite DB + audio cache
    environment:
      - VAPID_EMAIL=admin@yourshop.com
```

Data is stored in `./data/` on your host machine — survives container restarts and upgrades.

---

## 📱 PWA & Push Notifications

For Web Push to work, the app must be served over **HTTPS**. The container auto-generates a self-signed certificate on first run.

On Android (Chrome), customers will see a native "Allow notifications" prompt.  
On iOS (Safari 16.4+), customers must first **Add to Home Screen** before enabling push.

---

## 🛠️ Tech Stack

| Layer | Technology |
|---|---|
| Backend | [FastAPI](https://fastapi.tiangolo.com/) (Python) |
| Database | SQLite via `aiosqlite` |
| Real-time | WebSockets (built into FastAPI) |
| TTS | [edge-tts](https://github.com/rany2/edge-tts) (Microsoft Neural voices) |
| Push | Web Push API + `pywebpush` |
| Frontend | Vanilla HTML/CSS/JavaScript |
| Container | Docker + Docker Compose |

---

## 📄 License

MIT License — free to use, modify, and self-host.
