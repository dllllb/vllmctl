import subprocess
import time
import requests
from typing import Optional, Tuple
from .vllm_probe import get_listening_ports
import re
from .forward import create_tmux_ssh_forward, find_free_local_port


def create_tmux_session(session_name: str, command: str) -> None:
    """Create a new tmux session with the given name and command."""
    subprocess.run([
        "tmux", "new-session",
        "-d",  # detached
        "-s", session_name,  # session name
        command
    ], check=True)


def wait_for_vllm_api(local_port: int, timeout: int = 60, console=None) -> bool:
    """Wait for VLLM API to become available."""
    url = f"http://localhost:{local_port}/v1/models"
    start = time.time()
    
    while True:
        try:
            r = requests.get(url, timeout=1)
            if r.status_code == 200 and r.text.strip().startswith('{'):
                if console:
                    console.print(f"[green]VLLM API is ready![/green] [bold]{url}[/bold]")
                return True
        except Exception:
            pass
            
        if time.time() - start > timeout:
            if console:
                console.print(f"[red]VLLM API did not start in {timeout} seconds[/red]")
            return False
            
        time.sleep(2)


def parse_lifetime_to_seconds(lifetime: str) -> int:
    if not lifetime:
        return None
    pattern = r"^(\d+)([smhd])$"
    m = re.match(pattern, lifetime.strip().lower())
    if not m:
        raise ValueError("Invalid lifetime format. Use e.g. 10m, 2h, 1d, 30s")
    value, unit = int(m.group(1)), m.group(2)
    if unit == 's':
        return value
    elif unit == 'm':
        return value * 60
    elif unit == 'h':
        return value * 3600
    elif unit == 'd':
        return value * 86400
    else:
        raise ValueError("Invalid time unit in lifetime. Use s, m, h, or d.")


def launch_vllm_with_args(
    server: str,
    model: str,
    vllm_extra_args: list = None,
    local_range: Tuple[int, int] = (16100, 16199),
    conda_env: str = "vllm_env",
    timeout: int = 60,
    lifetime: str = None,
    console=None,
) -> Optional[int]:
    """
    Launch VLLM on a remote server with arbitrary arguments and forward the port locally.
    Uses tmux for SSH tunnel and remote session, and prints detailed info (livetime, timeout, log commands).
    """
    if vllm_extra_args is None:
        vllm_extra_args = []
    # Find a free local port
    local_port = find_free_local_port(local_range)
    if not local_port:
        if console:
            console.print("[red]No free local ports available[/red]")
        return None
    try:
        # Extract port from vllm arguments or use default
        remote_port = 8000
        port_args = ['--port', '-p']
        for i, arg in enumerate(vllm_extra_args):
            if arg in port_args and i + 1 < len(vllm_extra_args):
                try:
                    remote_port = int(vllm_extra_args[i + 1])
                    break
                except ValueError:
                    pass
        # Создаём SSH туннель через tmux (как в launch_vllm)
        create_tmux_ssh_forward(None, server, remote_port, local_port)
        # Build vllm command with extra arguments
        vllm_cmd_parts = [
            "source ~/.bashrc",
            f"conda activate {conda_env}",
            f"vllm serve {model}"
        ]
        # Add extra arguments
        if vllm_extra_args:
            vllm_cmd_parts[-1] += " " + " ".join(vllm_extra_args)
        # If no port specified in extra args, add default port
        if not any(arg in ['--port', '-p'] for arg in vllm_extra_args):
            vllm_cmd_parts[-1] += f" --port {remote_port}"
        vllm_cmd = " && ".join(vllm_cmd_parts)
        if lifetime:
            seconds = parse_lifetime_to_seconds(lifetime)
            vllm_cmd = f"timeout {seconds} bash -c '{vllm_cmd}'"
        server_tmux_name = f"vllmctl_server_{remote_port}"
        remote_tmux_cmd = f'tmux new-session -d -s {server_tmux_name} "{vllm_cmd}"'
        subprocess.run(["ssh", server, remote_tmux_cmd], check=True)
        if console:
            console.print(f"\n[bold]Created sessions:[/bold]")
            console.print(f"  • SSH tunnel: [cyan]ssh -N -L {local_port}:localhost:{remote_port} {server}[/cyan] (running in background)")
            console.print(f"  • VLLM server: [cyan]tmux session on remote: {server_tmux_name}[/cyan]")
            console.print(f"  • VLLM livetime: [cyan]{lifetime}[/cyan]")
            console.print(f"  • VLLM timeout: [cyan]{timeout} sec[/cyan]")
            console.print(f"\n[bold]VLLM command:[/bold] {vllm_cmd}")
            console.print(f"\n[bold]Waiting for VLLM API to become available...[/bold]")
            console.print(f"\n[bold yellow]To view logs, run:[/bold yellow] ssh {server} tmux attach -t {server_tmux_name}")
        # Wait for the API to become available
        if not wait_for_vllm_api(local_port, timeout, console):
            if console:
                console.print(f"[yellow]Check server logs with: ssh {server} tmux attach -t {server_tmux_name}[/yellow]")
            return None
        if console:
            console.print(f"\n[bold green]✓ VLLM is ready![/bold green]")
            console.print(f"[bold]API endpoint:[/bold] http://localhost:{local_port}/v1/completions")
        return local_port
    except subprocess.CalledProcessError as e:
        if console:
            console.print(f"[red]Failed to create tmux session: {e}[/red]")
        return None 