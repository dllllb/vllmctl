import subprocess
import time
from .ssh_utils import list_remote_models, run_ssh_command
from .vllm_probe import get_ssh_forwardings, get_listening_ports, get_tmux_sessions, ping_vllm
from rich.progress import track
import psutil
import re
from rich.console import Console
from dataclasses import dataclass
from typing import Optional

TMUX_PREFIX = "vllmctl_"
console = Console()

@dataclass
class ForwardSession:
    local_port: int
    remote_port: int
    server: str
    tmux_session: Optional[str]
    model_name: Optional[str]
    status: str = "unknown"
    alive: bool = False
    reason: Optional[str] = None

    def check_alive(self):
        # Check if local tmux session exists for the SSH tunnel
        session_name = f"vllmctl_{self.server}_{self.remote_port}_{self.local_port}"
        tmux_sessions = get_tmux_sessions()  # This should list local tmux sessions
        tmux_exists = session_name in tmux_sessions
        # Check if model API responds
        model_alive = False
        try:
            info = ping_vllm(self.local_port)
            if info and 'data' in info and info['data']:
                model_alive = True
        except Exception:
            pass
        self.alive = tmux_exists and model_alive
        if not tmux_exists:
            self.reason = "No local tmux session for SSH tunnel"
        elif not model_alive:
            self.reason = "Model API not responding"
        else:
            self.reason = None
        return self.alive

def find_free_local_port(port_range=(16100, 16199)):
    """
    Find a free local port in the given range (tuple).
    Args:
        port_range: Tuple (start, end) of port range.
    Returns:
        An available port number, or None if none are available.
    """
    used = set(get_listening_ports())
    for port in range(port_range[0], port_range[1]+1):
        if port not in used:
            return port
    return None

def create_tmux_ssh_forward(session_name, host, remote_port, local_port):
    """
    Create a local tmux session that runs an SSH tunnel forwarding local_port to remote_port on host.
    The session name is always vllmctl_{host}_{remote_port}_{local_port}.
    """
    session_name = f"vllmctl_{host}_{remote_port}_{local_port}"
    cmd = [
        "tmux", "new-session", "-d", "-s", session_name,
        f"ssh -N -L {local_port}:localhost:{remote_port} {host}"
    ]
    try:
        subprocess.run(cmd, check=True)
        time.sleep(1)
    except FileNotFoundError:
        console.print("[red]Error: 'tmux' or 'ssh' not found. Please install them (sudo apt install tmux openssh-client).[/red]")
    except subprocess.CalledProcessError as e:
        console.print(f"[red]Failed to create tmux SSH forward: {e}[/red]")
    except Exception as e:
        console.print(f"[red]Unexpected error in create_tmux_ssh_forward: {e}[/red]")

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
        session_name = f"vllmctl_{host}_{remote_port}_{local_port if local_port else ''}"
        if has_model and not already:
            if any(s.startswith(f"vllmctl_{host}_{remote_port}_") for s in tmux_sessions):
                local_port_dup = None
                for lport, (h, rport, pid) in ssh_forwards.items():
                    if h == host and rport == remote_port:
                        local_port_dup = lport
                        break
                # Try to ping model on local_port_dup
                model_id = None
                if local_port_dup:
                    model_info = ping_vllm(local_port_dup)
                    if model_info and 'data' in model_info and model_info['data']:
                        model_id = model_info['data'][0].get('id', None)
                results.append((host, remote_port, local_port_dup, f"Duplicate session: vllmctl_{host}_{remote_port}_{local_port_dup}", model_id or model_name))
                continue
            local_port = find_free_local_port(local_range)
            if not local_port:
                results.append((host, remote_port, None, "No free local ports", model_name))
                continue
            create_tmux_ssh_forward(None, host, remote_port, local_port)
            # After creating, ping the model
            model_id = None
            model_info = ping_vllm(local_port)
            if model_info and 'data' in model_info and model_info['data']:
                model_id = model_info['data'][0].get('id', None)
            results.append((host, remote_port, local_port, "Forwarded", model_id or model_name))
        elif has_model and already:
            # Always ping model on local_port and show model name if available
            model_id = None
            if local_port:
                model_info = ping_vllm(local_port)
                if model_info and 'data' in model_info and model_info['data']:
                    model_id = model_info['data'][0].get('id', None)
            results.append((host, remote_port, local_port, "Already forwarded", model_id or model_name))
        elif not has_model and already and not no_kill:
            kill_tmux_session(session_name)
            results.append((host, remote_port, local_port, "Forward killed (model not found)", None))
        elif not has_model and already and no_kill:
            results.append((host, remote_port, local_port, "Forward kept (model not found, no-kill)", None))
        else:
            pass
    return results

def get_tmux_ports():
    try:
        result = subprocess.run(["tmux", "ls"], capture_output=True, text=True)
        if result.returncode != 0:
            raise FileNotFoundError
        sessions = []
        for line in result.stdout.splitlines():
            if line.startswith("vllmctl_"):
                name = line.split(':')[0]
                sessions.append(name)
        tmux_ports = {}
        for session in sessions:
            try:
                pid_out = subprocess.run(
                    ["tmux", "list-panes", "-t", session, "-F", "#{pane_pid}"],
                    capture_output=True, text=True
                )
                for pid_str in pid_out.stdout.splitlines():
                    try:
                        pid = int(pid_str)
                        proc = psutil.Process(pid)
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
                    except (psutil.NoSuchProcess, psutil.AccessDenied) as e:
                        console.print(f"[yellow]Warning: Could not inspect process {pid_str}: {e}[/yellow]")
                    except Exception as e:
                        console.print(f"[yellow]Unexpected error inspecting process {pid_str}: {e}[/yellow]")
            except FileNotFoundError:
                console.print("[red]Error: 'tmux' not found. Please install tmux.[/red]")
            except Exception as e:
                console.print(f"[red]Error running 'tmux list-panes': {e}[/red]")
        return tmux_ports
    except FileNotFoundError:
        console.print("[red]Error: 'tmux' not found. Please install tmux.[/red]")
        return {}
    except Exception as e:
        console.print(f"[red]Error running 'tmux ls': {e}[/red]")
        return {}

def kill_tmux_session(session_name):
    try:
        subprocess.run(["tmux", "kill-session", "-t", session_name], check=True)
    except FileNotFoundError:
        console.print("[red]Error: 'tmux' not found. Please install tmux.[/red]")
    except subprocess.CalledProcessError as e:
        console.print(f"[red]Failed to kill tmux session {session_name}: {e}[/red]")
    except Exception as e:
        console.print(f"[red]Unexpected error killing tmux session {session_name}: {e}[/red]")

def list_forward_sessions():
    """
    Returns a list of ForwardSession objects for all current forwards.
    Checks for local tmux sessions for SSH tunnels using the correct session name pattern.
    """
    ssh_forwards = get_ssh_forwardings()
    tmux_sessions = get_tmux_sessions()
    sessions = []
    for local_port, (server, remote_port, pid) in ssh_forwards.items():
        session_name = f"vllmctl_{server}_{remote_port}_{local_port}"
        tmux_exists = session_name in tmux_sessions
        # Try to get model name
        model_name = None
        info = ping_vllm(local_port)
        if info and 'data' in info and info['data']:
            model_name = info['data'][0].get('id', None)
        session = ForwardSession(
            local_port=local_port,
            remote_port=remote_port,
            server=server,
            tmux_session=session_name if tmux_exists else None,
            model_name=model_name
        )
        session.check_alive()
        sessions.append(session)
    return sessions 