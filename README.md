# vllmctl

A production-ready CLI tool for launching, managing, and monitoring vllm model servers on remote machines via SSH and tmux.

## Features
- Launch vllm servers on remote hosts in isolated tmux sessions
- Automatic SSH tunneling for secure local API access
- Health checks: wait until vllm API is ready
- List, attach, and kill tmux sessions for full process control
- Flexible model/port/env selection per launch
- Safe for production: no processes die on SSH disconnect

## Installation

1. Install Python 3.8+ and pip.
2. Install requirements:
   ```bash
   pip install -r requirements.txt
   ```
3. Ensure `tmux` is installed on your local machine and remote servers.
4. Ensure passwordless SSH access to your remote servers.

## Usage

All commands support `--help` for detailed options:
```bash
vllmctl --help
vllmctl launch --help
```

### Launch a vllm server on a remote host
```bash
vllmctl launch --server <host> --model <model_name> [--conda-env <env>] [--remote-port <port>] [--local-range <range>] [--timeout <seconds>]
```
- Launches vllm in a remote tmux session and sets up a local SSH tunnel.
- Waits until the vllm API is available or fails with error output.
- Example:
  ```bash
  vllmctl launch --server myserver --model Qwen/Qwen2.5-Coder-32B-Instruct --conda-env vllm_env --remote-port 8000
  ```

### List active tmux sessions (forwards)
```bash
vllmctl tmux-forwards
```
- Shows all active SSH tunnel tmux sessions and their status.

### Attach to a tmux session
```bash
vllmctl attach-tmux <session_name>
```
- Attach to a running tmux session to view logs or interact.

### Kill a tmux session
```bash
vllmctl kill-tmux <session_name>
```
- Terminates the specified tmux session (and the associated vllm or tunnel process).

### Clean up dead/unused tmux sessions
```bash
vllmctl clean-tmux-forwards
```
- Removes tmux sessions with no active vllm or SSH tunnel.

## Best Practices
- Always use tmux for remote process management: it is safer and more transparent than nohup.
- Use SSH keys for authentication and restrict access to trusted users.
- Monitor your vllm endpoints with health checks and logs (see `tmux attach`).
- Clean up unused sessions regularly.
- For static, always-on production deployments, consider systemd (see documentation).

## Example Workflow
1. Launch vllm on server1:
   ```bash
   vllmctl launch --server server1 --model Qwen/Qwen2.5-Coder-32B-Instruct
   ```
2. Launch vllm on server2:
   ```bash
   vllmctl launch --server server2 --model Qwen/Qwen2.5-Coder-7B-Instruct --remote-port 8001
   ```
3. List all active sessions:
   ```bash
   vllmctl tmux-forwards
   ```
4. Attach to a session for logs:
   ```bash
   vllmctl attach-tmux vllmctl_vllm_server1_8000
   ```
5. Kill a session:
   ```bash
   vllmctl kill-tmux vllmctl_vllm_server1_8000
   ```

## Help
All commands support `--help` for detailed usage information.

## License
MIT


