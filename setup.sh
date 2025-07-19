#!/bin/bash
set -e

# Bash installer voor Civitai Download Daemon

echo "[setup.sh] Start installatie..."

# Check Python
if ! command -v python3 &> /dev/null; then
  echo "Python 3 is niet geïnstalleerd."
  exit 1
fi

# Check uv
if ! python3 -m uv --version &> /dev/null; then
  echo "[setup.sh] uv niet gevonden, installeren..."
  python3 -m pip install uv
fi

# Maak venv indien nodig
if [ ! -d ".venv" ]; then
  echo "[setup.sh] Virtuele omgeving aanmaken..."
  python3 -m uv venv .venv
fi

# Installeer dependencies
echo "[setup.sh] Dependencies installeren..."
.venv/bin/uv pip install fastapi uvicorn[standard] httpx jinja2 sqlite-utils python-multipart apscheduler

# Draai install.py voor config, poorten, systemd, etc.
echo "[setup.sh] Draai install.py..."
.venv/bin/python install.py

echo "\n[setup.sh] Installatie voltooid! Start de daemon met:"
echo ".venv/bin/python launch.py"
