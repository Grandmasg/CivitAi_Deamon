import os
import subprocess

def run(cmd, check=True):
    print(f"[remove.py] $ {cmd}")
    result = subprocess.run(cmd, shell=True)
    if check and result.returncode != 0:
        print(f"[remove.py] Command failed: {cmd}")
        exit(result.returncode)

def main():
    service_path = '/etc/systemd/system/civitai-daemon.service'
    if os.path.exists(service_path):
        run('sudo systemctl stop civitai-daemon.service', check=False)
        run('sudo systemctl disable civitai-daemon.service', check=False)
        run(f'sudo rm {service_path}')
        run('sudo systemctl daemon-reload')
        print('[remove.py] Service removed.')
    else:
        print('[remove.py] Service file not found.')

if __name__ == "__main__":
    main()
