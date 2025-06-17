import subprocess
import time
import requests
from typing import Optional, Tuple
from .vllm_probe import get_listening_ports
import re


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


def find_free_local_port(start: int, end: int) -> Optional[int]:
    """Find a free local port in the given range."""
    used_ports = set(get_listening_ports())
    for port in range(start, end + 1):
        if port not in used_ports:
            return port
    return None


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


def launch_vllm(
    server: str,
    model: str = "Qwen/Qwen2.5-Coder-32B-Instruct",
    tensor_parallel_size: int = 8,
    remote_port: int = 8000,
    local_range: Tuple[int, int] = (16100, 16199),
    conda_env: str = "vllm_env",
    timeout: int = 60,
    lifetime: str = None,
    console=None,
) -> Optional[int]:
    """
    Launch VLLM on a remote server and forward the port locally using tmux sessions.
    
    Args:
        server: SSH host to launch VLLM on
        model: Model name/path to serve
        tensor_parallel_size: Number of GPUs to use
        remote_port: Port to use on the remote server
        local_range: Range of local ports to try for forwarding
        conda_env: Conda environment name with VLLM installed
        timeout: How long to wait for the API to become available
        lifetime: Lifetime for the VLLM server (optional)
        console: Rich console for output (optional)
        
    Returns:
        The local port number if successful, None otherwise
    """
    # Find a free local port
    local_port = find_free_local_port(*local_range)
    if not local_port:
        if console:
            console.print("[red]No free local ports available[/red]")
        return None

    try:
        # Create SSH tunnel (no tmux, just background process)
        tunnel_name = f"vllmctl_{server}_{remote_port}_{local_port}"
        ssh_forward_cmd = [
            "ssh", "-N", "-L", f"{local_port}:localhost:{remote_port}",
            server, "-o", "ServerAliveInterval=30", "-o", "ServerAliveCountMax=3"
        ]
        tunnel_proc = subprocess.Popen(ssh_forward_cmd)

        # Create VLLM server session (tmux on remote server)
        vllm_cmd = f"source ~/.bashrc && conda activate {conda_env} && vllm serve {model} --tensor-parallel-size {tensor_parallel_size} --port {remote_port}"
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