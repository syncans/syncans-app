# SYNCANS

SYNCANS is a real-time, interest-based activity matching app for spontaneous plans.

## What this repo contains

- `server.py`: Python backend and static file server
- `index.html`, `app.js`, `styles.css`: hosted frontend
- `render.yaml`: Render deployment blueprint
- `Dockerfile`: alternative container deployment path
- `vendor/`: browser builds for React, React DOM, and HTM

## Core features

- Post real-time activities by category, city, time, radius, and safety settings
- Match nearby users with city-aware ordering and verification filters
- Approve or decline join requests
- Invite users directly into an activity
- Save organizer defaults such as home city, radius, and favorite categories
- Reuse activity history and quick templates
- Store data in SQLite with a persistent disk on Render

## Local run

```powershell
C:\Users\adars\AppData\Local\Programs\Python\Python314\python.exe D:\SYNCANS\server.py
```

Then open `http://127.0.0.1:8000`.
