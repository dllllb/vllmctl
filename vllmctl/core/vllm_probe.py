import subprocess
import re
import requests
import psutil

TMUX_PREFIX = "vllmctl_"

def get_listening_ports():
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
    result = subprocess.run(["ps", "aux"], capture_output=True, text=True)
    forwards = {}
    for line in result.stdout.splitlines():
        if "ssh -N -L" in line:
            m = re.search(r"ssh -N -L (\d+):localhost:(\d+) ([^ ]+)", line)
            if m:
                local_port = int(m.group(1))
                remote_port = int(m.group(2))
                host = m.group(3)
                pid = int(line.split()[1])
                forwards[local_port] = (host, remote_port, pid)
    return forwards

def get_tmux_sessions():
    result = subprocess.run(["tmux", "ls"], capture_output=True, text=True)
    sessions = []
    for line in result.stdout.splitlines():
        name = line.split(':')[0]
        sessions.append(name)
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
                entry['forwarded'] = False
                entry['server'] = None
                entry['remote_port'] = None
                entry['ssh_pid'] = None
                entry['tmux'] = None
            entry['model_name'] = model_name
            models[port] = entry
    return models