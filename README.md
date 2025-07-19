# Stable Civitai Download Daemon

Deze applicatie automatiseert downloads en updates van modellen via Civitai, met een FastAPI-backend, dynamische poortselectie en webhook-ondersteuning.

## Features
- FastAPI backend
- Webhook endpoint
- Automatische poortselectie
- Logging en queueing
- Uit te breiden met CI/CD, Telegram, reverse proxy, etc.

## Installatie
1. Clone deze repo:
   ```bash
   git clone <repo-url>
   cd CivitAI_Deamon
   ```
2. Installeer Python 3.11+ en uv (indien nodig)
3. Draai de installatie:
   ```bash
   python install.py
   ```
4. Start de daemon:
   ```bash
   python launch.py
   ```

## Bestanden
- `install.py` — Setup en dependency management
- `launch.py` — Start backend en webhook server
- `main.py` — FastAPI app
- `webhook_server.py` — Webhook endpoint
- `config.json` — Configuratie (wordt automatisch gevuld)
- `.gitignore` — Bestanden die niet in git komen

## GitHub koppeling
- Voeg deze map toe aan een nieuwe GitHub-repo
- Commit en push alleen de relevante bestanden (zie `.gitignore`)

## CI/CD (optioneel)
- Voeg een workflow toe in `.github/workflows/` voor automatische tests/deployment

---

Voor vragen of uitbreidingen: zie TODO_backend.md of open een issue.
