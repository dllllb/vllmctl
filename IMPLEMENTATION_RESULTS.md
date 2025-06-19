# Реализация поддержки произвольных аргументов VLLM в vllmctl

## Обзор выполненной работы

Была добавлена новая команда `serve` в vllmctl, которая позволяет передавать произвольные аргументы VLLM, делая команду максимально похожей на оригинальную `vllm serve`, но с поддержкой дополнительных аргументов vllmctl.

## Новая функциональность

### Команда `vllmctl serve`

Новая команда работает точно как `vllm serve`, но с добавлением аргументов vllmctl:

**Синтаксис:**
```bash
vllmctl serve --server <server> [vllmctl-args] <model> [vllm-args]
```

**Примеры использования:**

1. **Базовый запуск:**
```bash
vllmctl serve --server server1 Qwen/Qwen2.5-32B
```

2. **С дополнительными аргументами VLLM:**
```bash
vllmctl serve --server server1 Qwen/Qwen2.5-32B --tensor-parallel-size 8 --port 8000
```

3. **С новыми аргументами VLLM (reasoning):**
```bash
vllmctl serve --server gpu-node --lifetime 2h \
    Qwen/Qwen3-32B --reasoning-parser deepseek_r1 --tensor-parallel-size 8
```

4. **С любыми другими аргументами VLLM:**
```bash
vllmctl serve --server server1 --conda-env custom_env \
    microsoft/DialoGPT-medium --max-model-len 4096 --dtype float16 --quantization awq
```

### Аргументы vllmctl

Команда `serve` поддерживает следующие аргументы vllmctl (которые не конфликтуют с VLLM):

- `--server` (обязательный): Имя сервера из SSH config
- `--conda-env`: Conda окружение для VLLM (по умолчанию: `vllm_env`)
- `--local-range`: Диапазон локальных портов для проброса (по умолчанию: `16100-16199`)
- `--timeout`: Максимальное время ожидания запуска VLLM в секундах (по умолчанию: 600)
- `--lifetime`: Максимальное время жизни процесса VLLM (например: `10m`, `2h`, `1d`, `30s`)

### Позиционный аргумент модели

Модель указывается как позиционный аргумент (как в `vllm serve`):
```bash
vllmctl serve --server server1 Qwen/Qwen2.5-32B [дополнительные-аргументы]
```

## Технические детали реализации

### 1. Новая команда serve в CLI

В файле `vllmctl/cli.py` добавлена новая команда с настройками Typer для принятия произвольных аргументов:

```python
@app.command(context_settings={"allow_extra_args": True, "ignore_unknown_options": True})
def serve(
    server: str = typer.Option(..., "--server", help="Server name (from ssh-config)"),
    conda_env: str = typer.Option("vllm_env", "--conda-env", help="Conda environment for running vllm on server"),
    local_range: str = typer.Option("16100-16199", "--local-range", help="Range of local ports for forwarding"),
    timeout: int = typer.Option(600, "--timeout", help="Maximum waiting time for vllm start (sec)"),
    lifetime: str = typer.Option(None, "--lifetime", help="Maximum lifetime for vllm process"),
    model: str = typer.Argument(help="Model name or path to serve"),
    ctx: typer.Context = None,
):
```

### 2. Новая функция launch_vllm_with_args

В файле `vllmctl/core/launcher.py` добавлена функция `launch_vllm_with_args`, которая:

- Принимает произвольные аргументы VLLM в списке `vllm_extra_args`
- Автоматически извлекает порт из аргументов VLLM или использует порт по умолчанию (8000)
- Строит команду VLLM с переданными аргументами
- Запускает VLLM на удаленном сервере через tmux
- Создает SSH туннель для доступа к API

### 3. Обратная совместимость

Оригинальная команда `launch` остается неизменной и продолжает работать с фиксированными аргументами.

## Примеры команд

### Использование с новыми функциями VLLM

```bash
# Reasoning с DeepSeek R1
vllmctl serve --server gpu-server Qwen/Qwen3-32B --enable-reasoning --reasoning-parser deepseek_r1

# Reasoning с Granite
vllmctl serve --server gpu-server granite-model --enable-reasoning --reasoning-parser granite

# Кастомные настройки памяти и quantization
vllmctl serve --server server1 Llama-3-70B --tensor-parallel-size 4 --max-model-len 8192 --quantization awq

# Мультимодальные модели
vllmctl serve --server vision-server llava-model --trust-remote-code --limit-mm-per-prompt image=4
```

### Проброс любых новых аргументов

Если в новой версии VLLM появится новый аргумент, например `--new-feature`, он автоматически будет поддерживаться:

```bash
vllmctl serve --server server1 model-name --new-feature value --another-new-arg
```

## Преимущества

1. **Полная совместимость**: Команда работает точно как `vllm serve`, но с удаленным выполнением
2. **Будущеустойчивость**: Автоматически поддерживает любые новые аргументы VLLM
3. **Безопасность**: Аргументы vllmctl не конфликтуют с аргументами VLLM
4. **Гибкость**: Можно передавать любые комбинации аргументов VLLM
5. **Обратная совместимость**: Старая команда `launch` продолжает работать

## Тестирование

Команда была протестирована и корректно обрабатывает:
- Базовые аргументы (модель, tensor-parallel-size, port)
- Новые аргументы reasoning (reasoning-parser deepseek_r1)
- Сложные аргументы с несколькими значениями
- Автоматическое определение порта из аргументов VLLM

Пример успешного парсинга:
```bash
# Команда:
vllmctl serve --server test_server Qwen/Qwen2.5-32B --tensor-parallel-size 8 --reasoning-parser deepseek_r1

# Сгенерированная команда VLLM:
vllm serve Qwen/Qwen2.5-32B --tensor-parallel-size 8 --reasoning-parser deepseek_r1 --port 8000
```

## Заключение

Реализация полностью выполняет поставленную задачу: теперь vllmctl может принимать любые аргументы VLLM, делая запуск полностью идентичным оригинальной команде `vllm serve`, но с поддержкой удаленного выполнения и управления через SSH/tmux.