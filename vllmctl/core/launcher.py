import subprocess
import time
import requests
from .vllm_probe import get_listening_ports
from typing import Optional


def launch_vllm(
    server: str,
    model: str = "Qwen/Qwen2.5-Coder-32B-Instruct",
    tensor_parallel_size: int = 8,
    remote_port: int = 8000,
    local_range: tuple = (16100, 16199),
    conda_env: str = "vllm_env",
    timeout: int = 60,
    console=None,
) -> Optional[int]:
    """
    Launch vllm on the server and forward the port to the local machine through tmux.
    Returns the local port or None if there is an error.
    """
    l1, l2 = local_range
    used = set(get_listening_ports())
    local_port = None
    for port in range(l1, l2+1):
        if port not in used:
            local_port = port
            break
    if not local_port:
        if console:
            console.print("[red]No free local ports available[/red]")
        return None
    tunnel_tmux = f"vllmctl_tunnel_{server}_{local_port}"
    ssh_forward = f"ssh -N -L {local_port}:localhost:{remote_port} {server} -o ServerAliveInterval=30 -o ServerAliveCountMax=3"
    tmux_tunnel_cmd = [
        "tmux", "new-session", "-d", "-s", tunnel_tmux, ssh_forward
    ]
    subprocess.run(tmux_tunnel_cmd)
    vllm_tmux = f"vllmctl_vllm_{server}_{remote_port}"
    vllm_cmd = f"source ~/.bashrc && conda activate {conda_env} && vllm serve {model} --tensor-parallel-size {tensor_parallel_size} --port {remote_port}"
    ssh_vllm = f"ssh {server} '{vllm_cmd}'"
    tmux_vllm_cmd = [
        "tmux", "new-session", "-d", "-s", vllm_tmux, ssh_vllm
    ]
    subprocess.run(tmux_vllm_cmd)
    if console:
        console.print(f"[bold]Tunnel:[/bold] tmux attach -t {tunnel_tmux}")
        console.print(f"[bold]vllm server:[/bold] tmux attach -t {vllm_tmux}")
        console.print(f"[bold]API endpoint:[/bold] http://localhost:{local_port}/v1/completions")
    url = f"http://localhost:{local_port}/v1/models"
    start = time.time()
    while True:
        try:
            r = requests.get(url, timeout=1)
            if r.status_code == 200 and r.text.strip().startswith('{'):
                if console:
                    console.print(f"[green]vllm started![green] [bold]{url}[/bold]")
                break
        except Exception:
            pass
        if time.time() - start > timeout:
            if console:
                console.print(f"[red]vllm did not start in {timeout} seconds[/red]")
                console.print(f"[yellow]For logs: tmux attach -t {vllm_tmux}")
            return None
        time.sleep(2)
    if console:
        console.print(f"[bold green]Done! You can use vllm through the local port {local_port}[/bold green]")
    return local_port 