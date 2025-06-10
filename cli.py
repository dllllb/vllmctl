import typer
import re as regexlib
from .vllm_probe import list_local_models, get_listening_ports, ping_vllm, get_tmux_sessions
from .ssh_utils import parse_ssh_config, list_remote_models
from .forward import auto_forward_ports
from rich.progress import track
from rich.table import Table
from rich.console import Console
import subprocess
import psutil
import requests
import time

app = typer.Typer()

@app.command()
def list_local():
    """Показать локальные vllm-модели (по портам, включая проброшенные)."""
    ports = get_listening_ports()
    tmux_sessions = get_tmux_sessions()
    models = {}
    for port in track(ports, description="Проверка портов..."):
        info = ping_vllm(port)
        if info:
            models[port] = info
    table = Table(title="Local vllm models")
    table.add_column("Сервер")
    table.add_column("Remote\nport")
    table.add_column("Local\nport")
    table.add_column("Статус")
    table.add_column("Модель")
    if not models:
        typer.echo("Нет доступных vllm моделей на локальных портах.")
    else:
        local_models = list_local_models()
        for port, info in models.items():
            entry = local_models.get(port, {})
            model_name = entry.get('model_name', '-')
            if entry.get('forwarded'):
                server = entry.get('server', '-')
                remote_port = str(entry.get('remote_port', '-'))
                local_port = str(port)
                status = "Проброшено"
                if entry.get('tmux') and not entry.get('ssh_pid'):
                    status = f"{entry['tmux']}"
            else:
                # best effort: если есть tmux-сессия с такой моделью, показать её
                server = "-"
                remote_port = "-"
                local_port = str(port)
                status = "Локальный запуск"
                for tmux_name in tmux_sessions:
                    if model_name in tmux_name:
                        status = f"tmux: {tmux_name}"
                        break
            table.add_row(server, remote_port, local_port, status, model_name)
    console = Console()
    console.print(table)

@app.command()
def list_remote(
    host_regex: str = typer.Option(None, help="Regex для фильтрации серверов по имени"),
    debug: bool = typer.Option(False, help="Показывать подробную информацию и пустые сервера"),
    remote_port: int = typer.Option(8000, help="Порт для проверки на удалённых серверах (по умолчанию 8000)")
):
    """Показать vllm-модели на всех серверах из ssh-конфига."""
    hosts = parse_ssh_config()
    if host_regex:
        hosts = [h for h in hosts if regexlib.search(host_regex, h)]
    if not hosts:
        typer.echo("Нет подходящих хостов в ~/.ssh/config")
        return
    table = Table(title="Remote vllm models")
    table.add_column("Сервер")
    table.add_column("Remote\nport")
    table.add_column("Модель")
    for host in track(hosts, description="Проверка серверов..."):
        try:
            models = list_remote_models(host, port=remote_port)
        except Exception as e:
            if debug:
                table.add_row(host, str(remote_port), f"Ошибка: {e}")
            continue
        if models:
            for port, info in models.items():
                model_name = info['data'][0]['id'] if info.get('data') and info['data'] else 'unknown'
                table.add_row(host, str(port), model_name)
        elif debug:
            table.add_row(host, str(remote_port), "-")
    console = Console()
    console.print(table)

@app.command()
def auto_forward(
    host_regex: str = typer.Option(None, help="Regex для фильтрации серверов по имени"),
    remote_port: int = typer.Option(8000, help="Порт для проверки на удалённых серверах (по умолчанию 8000)"),
    local_range: str = typer.Option("16100-16199", help="Диапазон локальных портов для проброса (например, 16100-16199)"),
    no_kill: bool = typer.Option(False, help="Не убивать пробросы, если модель не найдена"),
    debug: bool = typer.Option(False, help="Подробный вывод")
):
    """Автоматически пробросить порты с моделями на локалку."""
    hosts = parse_ssh_config()
    if host_regex:
        hosts = [h for h in hosts if regexlib.search(host_regex, h)]
    if not hosts:
        typer.echo("Нет подходящих хостов в ~/.ssh/config")
        return
    try:
        l1, l2 = map(int, local_range.split('-'))
        local_range_tuple = (l1, l2)
    except Exception:
        typer.echo("Ошибка в формате local_range. Пример: 16100-16199")
        return
    results = auto_forward_ports(
        hosts,
        remote_port=remote_port,
        local_range=local_range_tuple,
        no_kill=no_kill,
        debug=debug
    )
    table = Table(title="Auto-forward results")
    table.add_column("Сервер")
    table.add_column("Remote\nport")
    table.add_column("Local\nport")
    table.add_column("Статус")
    table.add_column("Модель")
    for host, rport, lport, status, model in results:
        show_model = False
        if status.startswith("Проброшено") or status.startswith("Уже проброшено") or status.startswith("duplicate session"):
            show_model = True
        elif debug and model:
            show_model = True
        table.add_row(
            str(host),
            str(rport),
            str(lport) if lport else "-",
            status,
            model if (show_model and model) else "-"
        )
    console = Console()
    console.print(table)

@app.command()
def launch(
    server: str = typer.Option(..., help="Имя сервера (из ssh-конфига)"),
    model: str = typer.Option("Qwen/Qwen2.5-Coder-32B-Instruct", help="Имя модели для vllm serve"),
    tensor_parallel_size: int = typer.Option(8, help="tensor-parallel-size для vllm serve"),
    remote_port: int = typer.Option(8000, help="Порт на сервере для vllm serve"),
    local_range: str = typer.Option("16100-16199", help="Диапазон локальных портов для проброса (например, 16100-16199)"),
    conda_env: str = typer.Option("vllm_env", help="Conda-окружение для запуска vllm на сервере"),
    timeout: int = typer.Option(60, help="Максимальное время ожидания запуска vllm (сек)")
):
    """Запустить vllm на сервере и пробросить порт на локалку через tmux. Можно attach к любой сессии."""
    import subprocess
    import time
    import requests
    from .vllm_probe import get_listening_ports
    from rich.console import Console
    console = Console()
    # 1. Находим свободный локальный порт
    l1, l2 = map(int, local_range.split('-'))
    used = set(get_listening_ports())
    local_port = None
    for port in range(l1, l2+1):
        if port not in used:
            local_port = port
            break
    if not local_port:
        console.print("[red]Нет свободных локальных портов[/red]")
        raise typer.Exit(1)
    # 2. Поднимаем tmux для туннеля
    tunnel_tmux = f"vllmctl_tunnel_{server}_{local_port}"
    ssh_forward = f"ssh -N -L {local_port}:localhost:{remote_port} {server} -o ServerAliveInterval=30 -o ServerAliveCountMax=3"
    tmux_tunnel_cmd = [
        "tmux", "new-session", "-d", "-s", tunnel_tmux, ssh_forward
    ]
    subprocess.run(tmux_tunnel_cmd)
    # 3. Поднимаем tmux для vllm на сервере
    vllm_tmux = f"vllmctl_vllm_{server}_{remote_port}"
    vllm_cmd = f"source ~/.bashrc && conda activate {conda_env} && vllm serve {model} --tensor-parallel-size {tensor_parallel_size} --port {remote_port}"
    ssh_vllm = f"ssh {server} '{vllm_cmd}'"
    tmux_vllm_cmd = [
        "tmux", "new-session", "-d", "-s", vllm_tmux, ssh_vllm
    ]
    subprocess.run(tmux_vllm_cmd)
    console.print(f"[bold]Туннель:[/bold] tmux attach -t {tunnel_tmux}")
    console.print(f"[bold]vllm сервер:[/bold] tmux attach -t {vllm_tmux}")
    console.print(f"[bold]API endpoint:[/bold] http://localhost:{local_port}/v1/completions")
    # 4. Ждём, пока vllm не поднимется
    url = f"http://localhost:{local_port}/v1/models"
    start = time.time()
    while True:
        try:
            r = requests.get(url, timeout=1)
            if r.status_code == 200 and r.text.strip().startswith('{'):
                console.print(f"[green]vllm поднялся![/green] [bold]{url}[/bold]")
                break
        except Exception:
            pass
        if time.time() - start > timeout:
            console.print(f"[red]vllm не поднялся за {timeout} секунд[/red]")
            console.print(f"[yellow]Для логов: tmux attach -t {vllm_tmux}")
            raise typer.Exit(1)
        time.sleep(2)
    console.print(f"[bold green]Готово! Можно использовать vllm через локальный порт {local_port}[/bold green]")

@app.command()
def tmux_forwards(
    tmux_prefix: str = typer.Option("vllmctl_", help="Префикс tmux-сессий для поиска пробросов")
):
    """Показать все tmux-пробросы (vllmctl_*) и статус: есть ли модель на порту."""
    # Получаем список tmux-сессий
    result = subprocess.run(["tmux", "ls"], capture_output=True, text=True)
    sessions = []
    for line in result.stdout.splitlines():
        if line.startswith(tmux_prefix):
            name = line.split(':')[0]
            sessions.append(name)
    table = Table(title="Tmux-forwards status")
    table.add_column("Tmux session")
    table.add_column("Local port")
    table.add_column("Remote port")
    table.add_column("Модель на порту?")
    table.add_column("SSH cmd")
    for session in sessions:
        # Получаем PID процесса в tmux-сессии
        pid_out = subprocess.run(
            ["tmux", "list-panes", "-t", session, "-F", "#{pane_pid}"],
            capture_output=True, text=True
        )
        found = False
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
                            # Проверяем, слушает ли порт vllm
                            model_status = "-"
                            model_info = ping_vllm(local_port)
                            if model_info:
                                model_status = "есть модель"
                            else:
                                model_status = "нет модели"
                            table.add_row(session, str(local_port), str(remote_port), model_status, cmdline)
                            found = True
            except Exception:
                continue
        if not found:
            table.add_row(session, "-", "-", "нет ssh-проброса", "-")
    console = Console()
    console.print(table)

@app.command()
def clean_tmux_forwards(
    tmux_prefix: str = typer.Option("vllmctl_", help="Префикс tmux-сессий для поиска пробросов")
):
    """Удалить все tmux-сессии vllmctl_*, где нет ssh-проброса или модель не пингуется."""
    import subprocess
    import psutil
    from .vllm_probe import ping_vllm
    result = subprocess.run(["tmux", "ls"], capture_output=True, text=True)
    sessions = []
    for line in result.stdout.splitlines():
        if line.startswith(tmux_prefix):
            name = line.split(':')[0]
            sessions.append(name)
    killed = []
    for session in sessions:
        pid_out = subprocess.run(
            ["tmux", "list-panes", "-t", session, "-F", "#{pane_pid}"],
            capture_output=True, text=True
        )
        found = False
        for pid_str in pid_out.stdout.splitlines():
            try:
                pid = int(pid_str)
                proc = psutil.Process(pid)
                for child in proc.children(recursive=True):
                    if child.name() == "ssh":
                        cmdline = " ".join(child.cmdline())
                        import re
                        m = re.search(r"-L\s*(\d+):localhost:(\d+)", cmdline)
                        if m:
                            local_port = int(m.group(1))
                            # Проверяем, слушает ли порт vllm
                            model_info = ping_vllm(local_port)
                            if not model_info:
                                subprocess.run(["tmux", "kill-session", "-t", session])
                                killed.append((session, local_port, "нет модели"))
                                found = True
                            else:
                                found = True
            except Exception:
                continue
        if not found:
            subprocess.run(["tmux", "kill-session", "-t", session])
            killed.append((session, "-", "нет ssh-проброса"))
    if killed:
        from rich.table import Table
        from rich.console import Console
        table = Table(title="Удалённые tmux-сессии")
        table.add_column("Tmux session")
        table.add_column("Local port")
        table.add_column("Причина")
        for session, port, reason in killed:
            table.add_row(session, str(port), reason)
        console = Console()
        console.print(table)
    else:
        print("Нет tmux-сессий для удаления.")

@app.command()
def kill_tmux(
    session: str = typer.Argument(..., help="Имя tmux-сессии для убийства (например, vllmctl_server_port)")
):
    """Убить tmux-сессию по имени."""
    import subprocess
    from rich.console import Console
    console = Console()
    result = subprocess.run(["tmux", "kill-session", "-t", session], capture_output=True, text=True)
    if result.returncode == 0:
        console.print(f"[green]Сессия {session} убита[/green]")
    else:
        console.print(f"[red]Ошибка при убийстве {session}:[/red] {result.stderr}")
