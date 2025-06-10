import subprocess
import time
from .ssh_utils import list_remote_models
from .vllm_probe import get_ssh_forwardings, get_listening_ports, get_tmux_sessions
from rich.progress import track
import psutil
import re

TMUX_PREFIX = "vllmctl_"

# --- Найти свободный локальный порт ---
def find_free_local_port(port_range=(16100, 16199)):
    used = set(get_listening_ports())
    for port in range(port_range[0], port_range[1]+1):
        if port not in used:
            return port
    return None

# --- Создать tmux-сессию с ssh-пробросом ---
def create_tmux_ssh_forward(session_name, host, remote_port, local_port):
    cmd = [
        "tmux", "new-session", "-d", "-s", session_name,
        f"ssh -N -L {local_port}:localhost:{remote_port} {host}"
    ]
    subprocess.run(cmd)
    # Ждём, чтобы ssh успел подняться
    time.sleep(1)

# --- Убить tmux-сессию ---
def kill_tmux_session(session_name):
    subprocess.run(["tmux", "kill-session", "-t", session_name])

# --- Основная функция автофорварда ---
def auto_forward_ports(
    hosts,
    remote_port=8000,
    local_range=(16100, 16199),
    no_kill=False,
    debug=False
):
    results = []
    ssh_forwards = get_ssh_forwardings()
    tmux_sessions = get_tmux_sessions()
    for host in track(hosts, description="Auto-forward..."):
        models = list_remote_models(host, port=remote_port)
        has_model = bool(models)
        model_name = None
        if has_model:
            info = list(models.values())[0]
            model_name = info['data'][0]['id'] if info.get('data') and info['data'] else 'unknown'
        already = False
        local_port = None
        for lport, (h, rport, pid) in ssh_forwards.items():
            if h == host and rport == remote_port:
                already = True
                local_port = lport
                break
        session_name = f"{TMUX_PREFIX}{host}_{remote_port}"
        if has_model and not already:
            if session_name in tmux_sessions:
                # ищем локальный порт по ssh_forwards (если есть)
                local_port_dup = None
                for lport, (h, rport, pid) in ssh_forwards.items():
                    if h == host and rport == remote_port:
                        local_port_dup = lport
                        break
                results.append((host, remote_port, local_port_dup, f"duplicate session: {session_name}", model_name))
                continue
            local_port = find_free_local_port(local_range)
            if not local_port:
                results.append((host, remote_port, None, "Нет свободных локальных портов", model_name))
                continue
            create_tmux_ssh_forward(session_name, host, remote_port, local_port)
            results.append((host, remote_port, local_port, "Проброшено", model_name))
        elif has_model and already:
            results.append((host, remote_port, local_port, "Уже проброшено", model_name))
        elif not has_model and already and not no_kill:
            kill_tmux_session(session_name)
            results.append((host, remote_port, local_port, "Проброс убит (модель не найдена)", None))
        elif not has_model and already and no_kill:
            results.append((host, remote_port, local_port, "Проброс остался (модель не найдена, no-kill)", None))
        else:
            pass
    return results

def get_tmux_ports():
    # Получаем список tmux-сессий vllmctl_*
    result = subprocess.run(["tmux", "ls"], capture_output=True, text=True)
    sessions = []
    for line in result.stdout.splitlines():
        if line.startswith("vllmctl_"):
            name = line.split(':')[0]
            sessions.append(name)
    tmux_ports = {}
    for session in sessions:
        # Получаем PID процесса в tmux-сессии
        pid_out = subprocess.run(
            ["tmux", "list-panes", "-t", session, "-F", "#{pane_pid}"],
            capture_output=True, text=True
        )
        for pid_str in pid_out.stdout.splitlines():
            try:
                pid = int(pid_str)
                proc = psutil.Process(pid)
                # Рекурсивно ищем дочерние процессы ssh
                for child in proc.children(recursive=True):
                    if child.name() == "ssh":
                        cmdline = " ".join(child.cmdline())
                        m = re.search(r"-L\s*(\d+):localhost:(\d+)", cmdline)
                        if m:
                            local_port = int(m.group(1))
                            remote_port = int(m.group(2))
                            tmux_ports[local_port] = {
                                "session": session,
                                "remote_port": remote_port,
                                "ssh_cmd": cmdline
                            }
            except Exception:
                continue
    return tmux_ports

# Пример использования:
if __name__ == "__main__":
    print(get_tmux_ports())
