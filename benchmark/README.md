# Benchmark Harness

This directory holds the benchmark code, not the benchmark evidence.

- Put measurement scripts here: runners, memory probes, concurrency tests.
- Put extracted benchmark results in `results/benchmarks.md`.
- Put raw per-run command output in `results/logs/` and keep it gitignored.

That split keeps the system under test, the measurement harness, and the recorded results separate.
