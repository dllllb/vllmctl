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

### 7. `launch`
Launch a vLLM server on a remote host and set up a local SSH tunnel.

```bash
vllmctl launch --server <host> --model <model_name> [--conda-env <env>] [--remote-port <port>] [--local-range <range>] [--timeout <seconds>]
```

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


