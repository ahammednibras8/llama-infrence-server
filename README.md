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
| Model | `<!-- e.g. Mistral-7B-Instruct-v0.2 -->` |
| Quantization tested | `<!-- e.g. Q4_K_M, Q8_0 -->` |
| Python | `<!-- e.g. 3.11.x -->` |

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

### 1. Clone and Compile llama.cpp

```bash
git clone https://github.com/ggerganov/llama.cpp
cd llama.cpp

# For Apple Silicon with Metal acceleration
cmake -B build -DGGML_METAL=ON
cmake --build build --config Release -j$(nproc)
```

### 2. Download Model

```bash
# Example — fill in your actual model source
# huggingface-cli download <model-repo> --include "*.gguf" --local-dir ./models
```

### 3. Install Python Dependencies

```bash
pip install -r requirements.txt
```

### 4. Start the Inference Server

```bash
python server.py
```

---

## Project Structure

```
.
├── server.py              # Raw Python HTTP wrapper over llama.cpp
├── benchmark.py           # Load testing and measurement script
├── models/                # GGUF model files (gitignored)
├── results/
│   └── benchmarks.md      # Raw numbers from every experiment run
├── requirements.txt
└── README.md
```

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
