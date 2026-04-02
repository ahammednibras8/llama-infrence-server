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
| llama.cpp commit | `<!-- fill in: git rev-parse --short HEAD -->` |
| Model | `Mistral-7B-Instruct-v0.2.Q4_K_M.gguf` |
| Quantization tested | `Q4_K_M` |
| Python | `3.11.x (uv-managed .venv)` |

---

## Hypotheses (Written Before Running Any Benchmark)

> These are pre-experiment predictions. Reality will confirm or break them — the divergence is the point.

1. **RAM** — A 7B model at Q4_K_M quantization will consume approximately `__` GB of unified memory after load.
2. **Concurrency degradation** — Two simultaneous requests will reduce throughput by approximately `__%`, not `50%`, because `<!-- your reasoning here -->`.
3. **Quantization quality** — Q4 vs Q8 quality delta will be noticeable on `<!-- reasoning tasks / simple retrieval / math -->` but not on `<!-- other task type -->`.
4. **Time-to-first-token** — TTFT will be dominated by `<!-- prompt eval / KV cache / other factor -->` rather than generation speed.
5. **Metal acceleration** — Metal backend will `<!-- hypothesis about what it changes vs CPU-only -->`.

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

### 7. Start the Inference Server

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

> *To be filled in during the experiment. Table structure is pre-defined intentionally.*

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

---

## References

- [llama.cpp](https://github.com/ggerganov/llama.cpp) — Georgi Gerganov
- [The Hardware Lottery](https://arxiv.org/abs/2009.06489) — Sara Hooker
- [GGUF format spec](https://github.com/ggerganov/ggml/blob/master/docs/gguf.md)
