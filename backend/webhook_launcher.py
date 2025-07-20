import json
import os
import random
import socket

CONFIG_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'configs', 'config.json'))
WEBHOOK_PORT_RANGE = list(range(9000, 9101))
WEBHOOK_PATH = '/webhook'


def is_port_free(port):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(('127.0.0.1', port)) != 0


def pick_free_port():
    random.shuffle(WEBHOOK_PORT_RANGE)
    for port in WEBHOOK_PORT_RANGE:
        if is_port_free(port):
            return port
    raise RuntimeError("No free webhook port found in range 9000-9100")


def load_config():
    with open(CONFIG_PATH, 'r') as f:
        return json.load(f)


def save_config(cfg):
    with open(CONFIG_PATH, 'w') as f:
        json.dump(cfg, f, indent=2)


def main():
    cfg = load_config()
    # Parse port from webhook_url if present
    url = cfg.get('webhook_url', '')
    port_in_url = None
    try:
        port_in_url = int(url.split(':')[2].split('/')[0])
    except Exception:
        pass
    if not port_in_url or not is_port_free(port_in_url):
        port = pick_free_port()
        cfg['webhook_url'] = f"http://localhost:{port}{WEBHOOK_PATH}"
        save_config(cfg)
        print(f"[webhook_launcher.py] Picked free webhook port: {port}")
    else:
        print(f"[webhook_launcher.py] Using configured webhook port: {port_in_url}")
    # Here you could start the webhook server on the chosen port
    # For example: subprocess.run(f"python webhook_server.py --port {port}", shell=True)

if __name__ == "__main__":
    main()
