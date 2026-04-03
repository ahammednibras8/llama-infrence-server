# Benchmark Results

This file is the canonical tracked benchmark record for this repository.

- `benchmark/` contains the measurement code.
- `results/logs/` contains raw per-run command output and stays gitignored.
- `README.md` keeps only the benchmark overview and headline findings.

## Shared Configuration

- Date recorded: `2026-04-03`
- Hardware: `MacBook Air M2 — 8GB Unified Memory`
- OS: `macOS on Apple Silicon`
- Backend build: `llama.cpp` commit `a1cfb6453`
- Model: `Mistral-7B-Instruct-v0.2.Q4_K_M.gguf`
- Prompt: `Explain in one short paragraph what unified memory means on Apple Silicon.`
- Context size: `4096`
- Max generation: `128`
- Sampling: `--temp 0 --seed 42`
- Timing mode: `--perf` plus `/usr/bin/time -l`

## CLI Comparison Summary

| Run ID | Mode | GPU Layers | Observed Offload | Load Time | Prompt Eval | Prompt Throughput | Eval Time | Generation Throughput | Total Inference | Wall Time | Max RSS |
|---|---|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `cli-baseline-02` | Auto Metal baseline | `auto` | `31/33` | `14271.82 ms` | `263.43 ms / 17 tok` | `64.53 tok/s` | `5635.77 ms / 98 tok` | `17.39 tok/s` | `5910.06 ms / 115 tok` | `20.78 s` | `2913042432 bytes` |
| `cli-all-metal-01` | Full Metal experiment | `all` | `33/33` | `12723.11 ms` | `328.95 ms / 17 tok` | `51.68 tok/s` | `5702.88 ms / 98 tok` | `17.18 tok/s` | `6194.04 ms / 115 tok` | `19.31 s` | `2500460544 bytes` |
| `cli-cpu-only-01` | CPU-only experiment | `0` | `0/33` | `61582.60 ms` | `4927.31 ms / 17 tok` | `3.45 tok/s` | `8200.84 ms / 93 tok` | `11.34 tok/s` | `13484.44 ms / 110 tok` | `75.79 s` | `4524343296 bytes` |

## HTTP Summary

| Run ID | Mode | Endpoint | Wall Time | Completion Tokens | Finish Reason | Model |
|---|---|---|---:|---:|---|---|
| `http-baseline-01` | Blocking HTTP baseline | `/generate` | `7.35 s` | `125` | `stop` | `mistral-7b-instruct-q4-k-m` |

## Canonical Runs

### `cli-baseline-02` — Auto Metal Baseline

- Log file: `results/logs/cli-baseline-02.txt`
- Invocation: `make cli-baseline CLI_LOG=results/logs/cli-baseline-02.txt`
- GPU layers requested: `auto`
- GPU layers observed: `31/33`
- Load time: `14271.82 ms`
- Prompt eval: `263.43 ms / 17 tokens` (`64.53 tokens/sec`)
- Generation: `5635.77 ms / 98 tokens` (`17.39 tokens/sec`)
- Total inference: `5910.06 ms / 115 tokens`
- Wall time: `20.78 s`
- Max RSS: `2913042432 bytes`
- Memory breakdown:
  - Metal total: `5461 MiB`
  - Metal used: `4414 MiB`
  - Model: `3830 MiB`
  - Context: `480 MiB`
  - Compute: `104 MiB`
- Notes: auto-fit reduced the effective context to `4096`; this is the main baseline to compare later HTTP results against.

### `cli-all-metal-01` — Full Metal Experiment

- Log file: `results/logs/cli-all-metal-01.txt`
- Invocation: `make cli-all-metal CLI_LOG=results/logs/cli-all-metal-01.txt`
- GPU layers requested: `all`
- GPU layers observed: `33/33`
- Load time: `12723.11 ms`
- Prompt eval: `328.95 ms / 17 tokens` (`51.68 tokens/sec`)
- Generation: `5702.88 ms / 98 tokens` (`17.18 tokens/sec`)
- Total inference: `6194.04 ms / 115 tokens`
- Wall time: `19.31 s`
- Max RSS: `2500460544 bytes`
- Memory breakdown:
  - Metal total: `5461 MiB`
  - Metal used: `4719 MiB`
  - Model: `4095 MiB`
  - Context: `512 MiB`
  - Compute: `112 MiB`
- Notes: startup improved slightly, but steady-state inference was a bit worse than the `31/33` baseline and GPU headroom dropped to `741 MiB`.

### `cli-cpu-only-01` — CPU-Only Experiment

- Log file: `results/logs/cli-cpu-only-01.txt`
- Invocation: `make cli-cpu-only CLI_LOG=results/logs/cli-cpu-only-01.txt`
- GPU layers requested: `0`
- GPU layers observed: `0/33`
- Load time: `61582.60 ms`
- Prompt eval: `4927.31 ms / 17 tokens` (`3.45 tokens/sec`)
- Generation: `8200.84 ms / 93 tokens` (`11.34 tokens/sec`)
- Total inference: `13484.44 ms / 110 tokens`
- Wall time: `75.79 s`
- Max RSS: `4524343296 bytes`
- Memory breakdown:
  - Metal total: `5461 MiB`
  - Metal used: `0 MiB`
  - Host used: `4797 MiB`
  - CPU_REPACK: `4094 MiB`
- Notes: Metal still initializes because the binary was compiled with backend support, but inference remained CPU-only and was clearly slower.

## HTTP Runs

### `http-baseline-01` — Blocking HTTP Baseline

- Log file: `results/logs/http-baseline-01.json`
- Invocation: `curl http://127.0.0.1:8000/generate`
- Endpoint: `/generate`
- Prompt: `Explain in one short paragraph what unified memory means on Apple Silicon.`
- Max tokens: `128`
- Temperature: `0`
- Seed: `42`
- Wall time: `7.35 s`
- Completion tokens: `125`
- Prompt tokens: `24`
- Total tokens: `149`
- Finish reason: `stop`
- Model alias returned: `mistral-7b-instruct-q4-k-m`
- Notes: first HTTP baseline against the blocking Python wrapper; detailed CLI-vs-HTTP comparison should be interpreted carefully because token counts differ from the raw CLI baseline.

## Exploratory Run Kept Out Of The Comparison Table

### `cli-baseline-01`

- Log file: `results/logs/cli-baseline-01.txt`
- Tool used: `llama-cli`
- Status: exploratory only
- Reason excluded: the run stayed interactive, so it is not the cleanest one-shot baseline and should not be treated as the canonical comparison point.
