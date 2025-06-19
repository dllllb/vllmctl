# vllmctl

A powerful CLI for launching, managing, and monitoring vLLM model servers on remote machines via SSH and tmux.

---

## ⚠️ SSH Configuration Required

Many commands in `vllmctl` rely on your SSH configuration (`~/.ssh/config`).
- Make sure all your remote servers are properly listed in your SSH config.
- The tool will automatically discover and use these hosts for remote operations, port forwarding, and GPU monitoring.

Example SSH config entry:
```
Host myserver
    HostName myserver.example.com
    User myuser
    IdentityFile ~/.ssh/id_rsa
```

---

## 🚀 Features
- Launch vLLM servers on remote hosts in isolated tmux sessions
- Automatic SSH tunneling for secure local API access
- Real-time health checks and queue monitoring
- List, attach, and kill tmux sessions for full process control
- GPU utilization dashboard across your cluster
- Flexible model/port/env selection per launch
- Safe for production: no processes die on SSH disconnect

---

## 📦 Installation

```bash
pip install -r requirements.txt
```
- Requires Python 3.8+
- Ensure `tmux` is installed on both local and remote machines
- Passwordless SSH access is recommended

## 🐚 Shell Autocompletion

To enable shell autocompletion for vllmctl, run:

```bash
vllmctl --install-completion
```

Or, to see the completion script for your shell:

```bash
vllmctl --show-completion
```

You can add the output to your shell profile (e.g., `.bashrc`, `.zshrc`) for persistent autocompletion.

---

## 🛠️ Commands Overview

### 1. `list_local`
Show all local vLLM models (including forwarded ports).

```bash
vllmctl list-local
```

**Sample Output:**
```
┏━━━━━━━━━━┳━━━━━━━━━━━━┳━━━━━━━━━━━┳━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃ Server   ┃ Remote port┃ Local port┃ Status       ┃ Model                                ┃
┡━━━━━━━━━━╇━━━━━━━━━━━━╇━━━━━━━━━━━╇━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┩
│ -        │ -          │ 8000      │ Local launch │ Qwen/Qwen2.5-Coder-32B-Instruct      │
│ server1  │ 8000       │ 16100     │ Forwarded    │ Llama-2-13B-chat                     │
└──────────┴────────────┴───────────┴──────────────┴──────────────────────────────────────┘
```

---

### 2. `list_remote`
Show vLLM models running on all servers from your SSH config.

```bash
vllmctl list-remote [--host-regex <pattern>] [--remote-port <port>] [--debug]
```

---

### 3. `auto_forward`
Automatically forward ports with running models to your local machine.

```bash
vllmctl auto-forward [--host-regex <pattern>] [--remote-port <port>] [--local-range <start-end>] [--no-kill] [--debug]
```

---

### 4. `tmux_forwards`
Show all tmux-based SSH forwards and their status.

```bash
vllmctl tmux-forwards
```

---

### 5. `vllm_queue_top`
Real-time dashboard for vLLM queue status on all local ports (like `nvtop` for vLLM).

```bash
vllmctl vllm-queue-top
```

**Sample Output:**
```
Scanning ports for vLLM models... ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 100% 0:00:00
                                         \ vLLM Queue Status (refreshes every 1.0s)                                          
┏━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━┳━━━━━━━━━┳━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━┳━━━━━━━━━┓
┃ Local Port ┃ Model          ┃ Waiting ┃ Running ┃ Wait graph             ┃ Run graph               ┃ Prompt TPT ┃ Gen TPT ┃
┡━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━╇━━━━━━━━━╇━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━╇━━━━━━━━━┩
│ 16004      │ Qwen/Qwen3-32B │ 774     │ 226     │ ▁▁▂▂▂▂▃▂▂▃▃▃▄▃▄▄▄▅▅▅▅… │ █▇▆▆▆▆▅▆▆▅▅▄▄▅▄▄▄▃▃▃▃▂… │ -          │ -       │
│ 16101      │ Qwen/Qwen3-32B │ 774     │ 226     │ ▁▁▂▂▁▂▃▁▂▃▃▃▃▃▄▄▄▅▅▅▅… │ █▇▆▆▇▆▅▇▆▅▅▅▄▅▄▄▄▃▃▃▃▂… │ -          │ -       │
│ 16102      │ Qwen/Qwen3-4B  │ 663     │ 113     │ ▁▁▁▂▂▂▃▃▄▄▄▄▄▄▄▄▅▅▄▅▅… │ █▇▇▆▆▆▆▆▅▅▅▄▄▄▄▄▃▃▃▂▂▂… │ -          │ -       │
└────────────┴────────────────┴─────────┴─────────┴────────────────────────┴─────────────────────────┴────────────┴─────────┘
```

---

### 6. `gpu_idle_top`
Live GPU utilization and memory dashboard for all servers in your SSH config.

```bash
vllmctl gpu-idle-top --host-regex <pattern>
```

**Sample Output:**
```
Scanning GPU utilization on hosts... ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 100% 0:00:27
                            | GPU Idle Top (refreshes every 0.5s)                            
┏━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━┳━━━━━━━━━━━┓
┃ Host              ┃ Util (%) ┃ Util Graph                     ┃ Mem (%) ┃ Mem Graph ┃
┡━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━╇━━━━━━━━━━━┩
│ host-a            │ 0.0      │ ▁▁                             │ 5.1     │ ▁▁        │
│ host-b            │ 0.0      │ ▁▁                             │ 94.4    │ ▁▁        │
│ host-c            │ 0.0      │ ▁▁                             │ 0.0     │ ▁▁        │
│ host-d            │ 86.5     │                             █▁ │ 90.9    │ ▁▁        │
│ host-e            │ 89.0     │                             █▁ │ 59.3    │ ▁▁        │
│ host-f            │ 91.9     │                             ▁█ │ 92.9    │ ▁▁        │
│ host-g            │ 95.0     │                             █▁ │ 93.3    │ ▁▁        │
│ host-h            │ 97.4     │                             ▁█ │ 52.3    │ ▁▁        │
│ host-i            │ 100.0    │                             ▁█ │ 91.9    │ ▁▁        │
└───────────────────┴──────────┴────────────────────────────────┴─────────┴───────────┘
```

---

### 7. `serve` (recommended)
Launch a vLLM server on a remote host and set up a local SSH tunnel.

```bash
vllmctl serve --server <host> [OPTIONS] <model_name> [EXTRA_ARGS]
```

**Key options:**
- `--conda-env <env>`: Conda environment to use on the remote server (default: vllm_env)
- `--local-range <start-end>`: Range of local ports for forwarding (default: 16100-16199)
- `--timeout <seconds>`: Maximum waiting time for vLLM API to become available (default: 600)
- `--lifetime <duration>`: Maximum lifetime for the vLLM process. Supports formats like `10m` (minutes), `2h` (hours), `1d` (days), `30s` (seconds)
- `--tensor-parallel-size <N>`: Number of GPUs to use (passed to vllm serve)
- `--remote-port <port>`: Port to use on the remote server (default: 8000)
- Any additional arguments after the model name are passed directly to `vllm serve` (e.g. `--reasoning-parser ...`)

**Examples:**
```bash
vllmctl serve --server myserver Qwen/Qwen3-4B --tensor-parallel-size 2 --remote-port 8001
vllmctl serve --server myserver --lifetime 2h Qwen/Qwen3-4B --tensor-parallel-size 2 --port 8001
vllmctl serve --server myserver Qwen/Qwen3-4B --reasoning-parser deepseek_r1 --tensor-parallel-size 8
```

- After the specified lifetime, the vLLM server will be automatically stopped on the remote server.
- Both the vLLM process and the SSH tunnel run in tmux sessions for reliability.
- You can view logs with:
  ```bash
  ssh <host> tmux attach -t vllmctl_server_<port>
  ```

#### ⚠️ `launch` is deprecated
The `launch` command is now deprecated and will be removed in a future release. Please use `serve` instead. If you call `launch`, it will redirect to `serve` and print a warning.

---

### 8. Other Utilities

- **Attach to tmux session:**
  ```bash
  vllmctl attach-tmux <session_name>
  ```
- **Kill a tmux session:**
  ```bash
  vllmctl kill-tmux <session_name>
  ```
- **Clean up dead/unused tmux sessions:**
  ```bash
  vllmctl clean-tmux-forwards
  ```

---

## 📝 Best Practices
- Always use tmux for remote process management
- Use SSH keys for authentication
- Monitor endpoints with health checks and logs
- Clean up unused sessions regularly
- For production, consider systemd for static deployments

---

## ℹ️ Help
All commands support `--help` for detailed usage:

```bash
vllmctl <command> --help
```

---

## License
MIT


