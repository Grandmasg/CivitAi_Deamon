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

## Licentie

MIT License

Copyright (c) 2025 Grandmasg

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
