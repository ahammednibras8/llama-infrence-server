# llama.cpp Inference Server — From Scratch

> Benchmarking the physics of local LLM inference: RAM, throughput, and concurrency behavior under real load.

---

## What This Is

A minimal HTTP inference server built directly on top of [llama.cpp](https://github.com/ggerganov/llama.cpp) — no Ollama, no managed APIs, no abstractions. The goal is to feel the physics of inference firsthand: how much RAM a 7B model actually consumes, what quantization does to quality versus speed, and what happens at the hardware level when two requests arrive simultaneously.

This is not a production server. It is a controlled experiment with a clean HTTP interface.

---

## Environment

| Component | Details |
|-----------|---------|
| Hardware | MacBook Air M2 — 8GB Unified Memory |
| OS | macOS — Apple Silicon (ARM64) |
| Accelerator | Metal (Apple GPU via llama.cpp Metal backend) |
| llama.cpp commit | `a1cfb6453` |
| Model | `Mistral-7B-Instruct-v0.2.Q4_K_M.gguf` |
| Quantization tested | `Q4_K_M` |
| Effective context size | `4096` |
| Python | `3.11.x (uv-managed .venv)` |

---

## Hypotheses (Written Before Running Any Benchmark)

> These are pre-experiment predictions. Reality will confirm or break them — the divergence is the point.

1. **RAM** — A 7B model at Q4_K_M quantization will consume approximately `5.5` GB of unified memory after load.
2. **Concurrency degradation** — Two simultaneous requests will reduce per-request throughput by approximately `35%`, not `50%`, because the bottleneck is shared memory bandwidth and backend scheduling, not two perfectly isolated compute lanes.
3. **Quantization quality** — Q4 vs Q8 quality delta will be noticeable on multi-step reasoning, exact instruction following, and borderline factual recall, but not on short-form chat, summarization, or simple retrieval.
4. **Time-to-first-token** — TTFT will be dominated by prompt evaluation rather than generation speed.
5. **Metal acceleration** — Metal backend will make this model usable on the M2 Air and improve tokens/sec materially over CPU-only inference, but memory pressure will remain the main constraint under concurrent load.

---

## Setup

Start with:

```text
make help
```

### 1. Add `llama.cpp` as a Git Submodule

Use this once when setting up the repository structure for the first time:

```bash
make add-submodule
git commit -m "Add llama.cpp as a submodule"
```

This creates:

- `llama.cpp/` as a tracked submodule directory
- `.gitmodules` in the repo root
- a pinned `llama.cpp` commit in your main repo history

### 2. Initialize the Submodule After Clone

For an existing clone, pull the pinned submodule commit with:

```bash
make submodule
```

You can also clone with submodules from the start:

```bash
git clone --recurse-submodules <your-repo-url>
```

### 3. Create the Python Environment

```bash
make venv
```

### 4. Install Python Dependencies

```bash
make install
```

### 5. Download Model

```bash
make download-model
```

This downloads:

- Hugging Face repo: `QuantFactory/Mistral-7B-Instruct-v0.2-GGUF`
- local file: `models/Mistral-7B-Instruct-v0.2.Q4_K_M.gguf`
- quantization: `Q4_K_M`

### 6. Compile `llama.cpp`

```bash
make build-llama
```

This target uses the macOS SDK `libc++` header path as a workaround for the broken Command Line Tools libc++ install on this machine.

### 7. Measure the Raw CLI Baseline

```bash
make cli-baseline CLI_LOG=results/logs/cli-baseline-01.txt
```

This runs `llama-completion` directly against the local GGUF model, with:

- `--perf` enabled for internal timing output
- deterministic settings: `--temp 0`, `--seed 42`
- fixed context size: `4096`
- default GPU offload mode: `-ngl auto` (`31/33` layers on this machine)
- benchmark log saved under `results/logs/`

Record these fields from the output:

- `common_perf_print: load time`
- `common_perf_print: prompt eval time`
- `common_perf_print: eval time`
- `common_perf_print: total time`
- `/usr/bin/time -l` maximum resident set size

Optional comparison experiment:

```bash
make cli-all-metal CLI_LOG=results/logs/cli-all-metal-01.txt
```

This forces `-ngl all` and attempts full Metal offload of all `33/33` layers.

CPU-only comparison:

```bash
make cli-cpu-only CLI_LOG=results/logs/cli-cpu-only-01.txt
```

This forces `-ngl 0` and keeps all model layers on CPU.

### 8. Start the Inference Server

```bash
make run-server
```

---

## Project Structure

```text
llama-inference-server/
│
├── llama.cpp/                    # Git submodule — pulled from source
│
├── models/                       # GGUF model files
│   └── .gitkeep                  # Folder tracked, models gitignored
│
├── server/
│   ├── server.py                 # Raw Python HTTP wrapper (the core build)
│   └── handler.py                # Request/response parsing logic
│
├── benchmark/
│   ├── run.py                    # Runs all benchmark scenarios
│   ├── memory.py                 # RAM profiling at each stage
│   └── concurrency.py            # Two simultaneous requests test
│
├── results/
│   ├── benchmarks.md             # Raw numbers, every run, timestamped
│   └── logs/                     # Per-run output logs (gitignored)
│
├── .gitignore
├── Makefile
├── requirements.txt
└── README.md
```

### Structure Rules

1. `llama.cpp` is a submodule, not a copy-paste. This pins an exact upstream commit so benchmark runs can be reproduced against the same compiled source.
2. `models/` is gitignored except for `.gitkeep`. GGUF artifacts stay out of the repo; the README should record the exact model name and download source instead.
3. `benchmark/` stays separate from `server/`. The server is the system under test, and the benchmark code is the measurement layer around it.

### Automation

The root `Makefile` is the main interface for repeated project commands. Start with:

```bash
make help
```

Main targets:

- `make add-submodule`
- `make submodule`
- `make venv`
- `make install`
- `make download-model`
- `make model-path`
- `make cli-baseline`
- `make cli-all-metal`
- `make cli-cpu-only`
- `make build-llama`
- `make clean-llama`
- `make run-server`

---

## Methodology

All benchmarks are run under controlled conditions:

- **Single request baseline** — one request at a time, model fully loaded, no cache warm-up
- **Concurrent load** — two simultaneous requests via threading, measuring throughput degradation
- **Memory profiling** — RSS sampled at: process start → model load → single request → concurrent requests
- **Quality delta** — same prompt across Q4_K_M and Q8_0, evaluated manually on reasoning, factual recall, and instruction following

Each benchmark run records: hardware state, llama.cpp commit hash, model file hash, and exact generation parameters. Results are reproducible.

---

## Results

> *The CLI baseline below is the first measured data point. Server and concurrency results will be added after the HTTP layer is built.*

### Raw CLI Baseline

- Tool: `llama-completion`
- GPU layers: `auto`
- Prompt: `Explain in one short paragraph what unified memory means on Apple Silicon.`
- Load time: `14271.82 ms`
- Prompt eval: `263.43 ms / 17 tokens` (`64.53 tokens/sec`)
- Generation: `5635.77 ms / 98 tokens` (`17.39 tokens/sec`)
- Total inference time: `5910.06 ms / 115 tokens`
- Wall time: `20.78 s`
- Max RSS: `2913042432 bytes` (`2.91 GB`)
- Metal memory total: `5461 MiB`
- Notes: `31/33` layers offloaded to GPU, context auto-fit observed at `4096`

### Full Metal Comparison

- Tool: `llama-completion`
- GPU layers: `all`
- Prompt: `Explain in one short paragraph what unified memory means on Apple Silicon.`
- Load time: `12723.11 ms`
- Prompt eval: `328.95 ms / 17 tokens` (`51.68 tokens/sec`)
- Generation: `5702.88 ms / 98 tokens` (`17.18 tokens/sec`)
- Total inference time: `6194.04 ms / 115 tokens`
- Wall time: `19.31 s`
- Max RSS: `2500460544 bytes` (`2.50 GB`)
- Metal memory total: `5461 MiB`
- Notes: `33/33` layers offloaded to GPU, free Metal headroom reduced to `741 MiB`, slightly worse inference latency than the `31/33` baseline

### CPU-Only Comparison

- Tool: `llama-completion`
- GPU layers: `0`
- Prompt: `Explain in one short paragraph what unified memory means on Apple Silicon.`
- Load time: `61582.60 ms`
- Prompt eval: `4927.31 ms / 17 tokens` (`3.45 tokens/sec`)
- Generation: `8200.84 ms / 93 tokens` (`11.34 tokens/sec`)
- Total inference time: `13484.44 ms / 110 tokens`
- Wall time: `75.79 s`
- Max RSS: `4524343296 bytes` (`4.52 GB`)
- Metal memory total: `0 MiB`
- Notes: `0/33` layers offloaded to GPU, model and KV cache stayed on host memory, clearly slower than both Metal-backed runs

### Memory Usage

| Stage | RAM (GB) |
|-------|----------|
| Process start | |
| After model load | |
| During single request | |
| During 2 concurrent requests | |

### Throughput

| Scenario | Tokens/sec (p50) | Tokens/sec (p99) | Time-to-first-token (ms) |
|----------|-----------------|-----------------|--------------------------|
| Single request — Q4_K_M | | | |
| Single request — Q8_0 | | | |
| 2 concurrent — Q4_K_M | | | |
| 2 concurrent — Q8_0 | | | |

### Concurrency Behavior

> What actually happens at the HTTP layer when request 2 arrives while request 1 is generating? Does it queue, block, or fail? Document the exact behavior here.

---

## What I Learned

> *Written after the experiment. Not a summary — a precise argument about what the numbers revealed.*

### What I Expected vs What Happened

*(The divergences between hypotheses and results — with the physics explanation for each gap.)*

### The Most Surprising Finding

*(The one non-obvious thing this experiment revealed about inference infrastructure.)*

### What This Changes About How I Think About Managed APIs

*(What do the tradeoffs in services like OpenAI, Fireworks, Together look like differently after watching the hardware directly?)*

---

## Raw Benchmark Logs

See [`results/benchmarks.md`](results/benchmarks.md) for full run logs with timestamps, hardware state, and generation parameters for every experiment.
The first raw CLI log is stored under `results/logs/cli-baseline-02.txt`.

---

## References

- [llama.cpp](https://github.com/ggerganov/llama.cpp) — Georgi Gerganov
- [The Hardware Lottery](https://arxiv.org/abs/2009.06489) — Sara Hooker
- [GGUF format spec](https://github.com/ggerganov/ggml/blob/master/docs/gguf.md)
