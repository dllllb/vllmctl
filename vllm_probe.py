import subprocess
import re
import requests
import psutil

TMUX_PREFIX = "vllmctl_"

def get_listening_ports():
    # Используем ss для получения всех слушающих портов на 127.0.0.1
    result = subprocess.run(
        ["ss", "-tulpen"], capture_output=True, text=True
    )
    ports = set()
    for line in result.stdout.splitlines():
        m = re.search(r"127.0.0.1:(\d+)", line)
        if m:
            ports.add(int(m.group(1)))
    return sorted(ports)

def ping_vllm(port):
    try:
        r = requests.get(f"http://127.0.0.1:{port}/v1/models", timeout=0.2)
        if r.status_code == 200:
            return r.json()
    except Exception:
        pass
    return None

def get_ssh_forwardings():
    """Возвращает dict: локальный порт -> (server, remote_port, pid)"""
    forwards = {}
    for p in psutil.process_iter(['pid', 'name', 'cmdline']):
        if p.info['name'] == 'ssh':
            cmd = ' '.join(p.info['cmdline'])
            # ищем -L 16001:localhost:8000 или -L 127.0.0.1:16001:localhost:8000
            m = re.findall(r"-L\s*(\d+):[\w\.-]+:(\d+)", cmd)
            if m:
                for local_port, remote_port in m:
                    # ищем имя хоста (после всех -L)
                    host = None
                    parts = p.info['cmdline']
                    for i, part in enumerate(parts):
                        if part == '-L' and i+1 < len(parts):
                            continue
                        if part.startswith('-'): continue
                        if ':' not in part and not part.endswith('.sh'):
                            host = part
                            break
                    forwards[int(local_port)] = (host, int(remote_port), p.info['pid'])
    return forwards

def get_tmux_sessions():
    result = subprocess.run(["tmux", "ls"], capture_output=True, text=True)
    sessions = {}
    for line in result.stdout.splitlines():
        if line.startswith(TMUX_PREFIX):
            name = line.split(':')[0]
            sessions[name] = True
    return sessions

def list_local_models():
    ports = get_listening_ports()
    ssh_forwards = get_ssh_forwardings()
    tmux_sessions = get_tmux_sessions()
    models = {}
    for port in ports:
        info = ping_vllm(port)
        if info:
            entry = {'model': info, 'port': port}
            model_name = info['data'][0]['id'] if info.get('data') and info['data'] else 'unknown'
            if port in ssh_forwards:
                host, rport, pid = ssh_forwards[port]
                entry['forwarded'] = True
                entry['server'] = host
                entry['remote_port'] = rport
                entry['ssh_pid'] = pid
                tmux_name = f"{TMUX_PREFIX}{host}_{rport}"
                entry['tmux'] = tmux_name if tmux_name in tmux_sessions else None
            else:
                # ищем tmux-сессию по шаблону vllmctl_{server}_{remote_port}
                found = False
                for tmux_name in tmux_sessions:
                    m = re.match(rf"{TMUX_PREFIX}(.+?)_(\d+)", tmux_name)
                    if m:
                        host, rport = m.group(1), int(m.group(2))
                        if port not in ssh_forwards and port in ports:
                            entry['forwarded'] = True
                            entry['server'] = host
                            entry['remote_port'] = rport
                            entry['ssh_pid'] = None
                            entry['tmux'] = tmux_name
                            found = True
                            break
                if not found:
                    entry['forwarded'] = False
                    entry['tmux'] = None
            entry['model_name'] = model_name
            models[port] = entry
    return models
