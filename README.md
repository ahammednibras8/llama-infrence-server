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
│   ├── server.py                 # Raw blocking Python HTTP wrapper (the core build)
│   └── handler.py                # Intentionally empty until extraction is justified
│
├── benchmark/
│   ├── README.md                 # Explains benchmark code vs benchmark results
│   ├── run.py                    # Runs all benchmark scenarios
│   ├── memory.py                 # RAM profiling at each stage
│   └── concurrency.py            # Two simultaneous requests test
│
├── results/
│   ├── benchmarks.md             # Canonical tracked benchmark record
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

### Deliberate Omissions

The first server implementation is intentionally naive:

- no async
- no threading
- no worker pool

This is deliberate. The first experiment is supposed to show what a blocking server does when two requests arrive at once. `handler.py` stays empty for now, and request parsing lives in `server.py` until the experiment proves that separation is worth doing.

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

`README.md` now keeps only the headline comparison. The tracked source of truth for extracted benchmark data is [`results/benchmarks.md`](results/benchmarks.md), and the raw per-run command logs stay local under `results/logs/`.

### Current CLI Summary

| Mode | Offload | Load Time | Prompt Throughput | Generation Throughput | Total Inference | Wall Time |
|------|---------|-----------|-------------------|-----------------------|-----------------|-----------|
| Auto Metal | `31/33` | `14271.82 ms` | `64.53 tok/s` | `17.39 tok/s` | `5910.06 ms` | `20.78 s` |
| Full Metal | `33/33` | `12723.11 ms` | `51.68 tok/s` | `17.18 tok/s` | `6194.04 ms` | `19.31 s` |
| CPU-only | `0/33` | `61582.60 ms` | `3.45 tok/s` | `11.34 tok/s` | `13484.44 ms` | `75.79 s` |

The reliable takeaway so far: on this machine, `-ngl auto` is the best steady-state baseline, `-ngl all` is a useful comparison experiment, and `-ngl 0` is the control condition for showing what Metal changes.

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

## Benchmark Records

- [`benchmark/README.md`](benchmark/README.md) explains what belongs in `benchmark/`.
- [`results/benchmarks.md`](results/benchmarks.md) is the canonical tracked benchmark record.
- `results/logs/` holds raw run output such as `cli-baseline-02.txt`, `cli-all-metal-01.txt`, and `cli-cpu-only-01.txt`.

---

## References

- [llama.cpp](https://github.com/ggerganov/llama.cpp) — Georgi Gerganov
- [The Hardware Lottery](https://arxiv.org/abs/2009.06489) — Sara Hooker
- [GGUF format spec](https://github.com/ggerganov/ggml/blob/master/docs/gguf.md)
