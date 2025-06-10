import pytest
from typer.testing import CliRunner
from vllmctl.cli import app
import subprocess

runner = CliRunner()

# --- Общий state для моков ---
class State:
    def __init__(self):
        self.remote_models = {"server1": {8000: {"data": [{"id": "Qwen2.5"}]}}}
        self.forwarded_ports = {}
        self.tmux_sessions = set()
        self.local_models = {}

state = State()

@pytest.fixture(autouse=True)
def patch_all(monkeypatch):
    # Мокаем parse_ssh_config
    monkeypatch.setattr("vllmctl.ssh_utils.parse_ssh_config", lambda: ["server1"])
    # Мокаем list_remote_models
    monkeypatch.setattr("vllmctl.ssh_utils.list_remote_models", lambda host, port=8000: state.remote_models.get(host, {}))
    # Мокаем get_listening_ports
    monkeypatch.setattr("vllmctl.vllm_probe.get_listening_ports", lambda: set(state.forwarded_ports.keys()))
    # Мокаем ping_vllm
    monkeypatch.setattr("vllmctl.vllm_probe.ping_vllm", lambda port: state.local_models.get(port))
    # Мокаем get_tmux_sessions
    monkeypatch.setattr("vllmctl.vllm_probe.get_tmux_sessions", lambda: {s: True for s in state.tmux_sessions})
    # Мокаем subprocess.run для tmux и ssh
    def fake_run(cmd, *a, **kw):
        if "tmux" in cmd:
            if "new-session" in cmd:
                # auto_forward и launch создают tmux-сессию
                session = cmd[cmd.index("-s") + 1]
                state.tmux_sessions.add(session)
                # auto_forward: сессия вида vllmctl_server1_8000
                if "ssh" in cmd[-1]:
                    # эмулируем проброс порта
                    if "-L" in cmd[-1]:
                        # auto_forward
                        local_port = 16100
                        state.forwarded_ports[local_port] = ("server1", 8000, 1234)
                        state.local_models[local_port] = {"data": [{"id": "Qwen2.5"}]}
                return type("Fake", (), {"stdout": "", "stderr": "", "returncode": 0})()
            if "ls" in cmd:
                out = "".join(f"{s}: 1 windows\n" for s in state.tmux_sessions)
                return type("Fake", (), {"stdout": out, "stderr": "", "returncode": 0})()
        return type("Fake", (), {"stdout": "", "stderr": "", "returncode": 0})()
    monkeypatch.setattr(subprocess, "run", fake_run)

# --- Тесты ---
def test_list_remote():
    result = runner.invoke(app, ["list-remote"])
    assert result.exit_code == 0
    assert "server1" in result.output
    assert "Qwen2.5" in result.output

def test_auto_forward():
    result = runner.invoke(app, ["auto-forward", "--host-regex", "server1", "--remote-port", "8000", "--local-range", "16100-16100"])
    assert result.exit_code == 0
    assert "Проброшено" in result.output or "Уже проброшено" in result.output
    # Проверяем, что порт проброшен
    assert 16100 in state.forwarded_ports

def test_list_local():
    result = runner.invoke(app, ["list-local"])
    assert result.exit_code == 0
    assert "Qwen2.5" in result.output
    assert "Проброшено" in result.output

def test_tmux_forwards():
    result = runner.invoke(app, ["tmux-forwards"])
    assert result.exit_code == 0
    assert any(s in result.output for s in state.tmux_sessions) 