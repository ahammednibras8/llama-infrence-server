"""Measure combined RSS for the blocking wrapper and its llama.cpp backend."""

from __future__ import annotations

import argparse
import json
import os
import signal
import subprocess
import sys
import threading
import time
from pathlib import Path
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
SERVER_SCRIPT = ROOT / "server" / "server.py"
PROMPT = "Explain in one short paragraph what unified memory means on Apple Silicon."


def main() -> None:
    args = parse_args()
    url = f"http://127.0.0.1:{args.server_port}/generate"
    env = os.environ.copy()
    env.update(
        {
            "SERVER_HOST": "127.0.0.1",
            "SERVER_PORT": str(args.server_port),
            "LLAMA_BACKEND_HOST": "127.0.0.1",
            "LLAMA_BACKEND_PORT": str(args.backend_port),
            "LLAMA_GPU_LAYERS": args.gpu_layers,
            "LLAMA_CTX_SIZE": str(args.ctx_size),
            "DEFAULT_MAX_TOKENS": str(args.max_tokens),
            "DEFAULT_TEMPERATURE": str(args.temperature),
            "DEFAULT_SEED": str(args.seed),
        }
    )

    process = subprocess.Popen(
        [sys.executable, str(SERVER_SCRIPT)],
        cwd=ROOT,
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        text=True,
    )

    sampler = ProcessTreeSampler(process.pid, args.sample_interval)
    sampler.start()

    try:
        sampler.wait_for_first_sample(timeout=5.0)
        process_start_bytes = sampler.current_rss_bytes()

        wait_for_health(args.server_port, args.startup_timeout)
        after_model_load_bytes = sampler.current_rss_bytes()

        single_request_peak_bytes = measure_request_peak(
            sampler,
            [build_payload(args)],
            url,
        )

        concurrent_peak_bytes = measure_request_peak(
            sampler,
            [build_payload(args), build_payload(args)],
            url,
        )
    finally:
        stop_process(process)
        sampler.stop()

    result = {
        "run_id": args.run_id,
        "measured_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "server_port": args.server_port,
        "backend_port": args.backend_port,
        "gpu_layers": args.gpu_layers,
        "ctx_size": args.ctx_size,
        "prompt": PROMPT,
        "stages": {
            "process_start": format_stage(process_start_bytes),
            "after_model_load": format_stage(after_model_load_bytes),
            "during_single_request": format_stage(single_request_peak_bytes),
            "during_two_concurrent_requests": format_stage(concurrent_peak_bytes),
        },
    }

    output = json.dumps(result, indent=2)
    if args.output:
        Path(args.output).write_text(output + "\n", encoding="utf-8")
    print(output)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-id", default="memory-profile-01")
    parser.add_argument("--output")
    parser.add_argument("--server-port", type=int, default=18000)
    parser.add_argument("--backend-port", type=int, default=18080)
    parser.add_argument("--startup-timeout", type=float, default=120.0)
    parser.add_argument("--sample-interval", type=float, default=0.05)
    parser.add_argument("--gpu-layers", default="auto")
    parser.add_argument("--ctx-size", type=int, default=4096)
    parser.add_argument("--max-tokens", type=int, default=128)
    parser.add_argument("--temperature", type=float, default=0.0)
    parser.add_argument("--seed", type=int, default=42)
    return parser.parse_args()


def build_payload(args: argparse.Namespace) -> dict[str, object]:
    return {
        "prompt": PROMPT,
        "max_tokens": args.max_tokens,
        "temperature": args.temperature,
        "seed": args.seed,
    }


def wait_for_health(server_port: int, timeout: float) -> None:
    deadline = time.time() + timeout
    url = f"http://127.0.0.1:{server_port}/health"

    while time.time() < deadline:
        try:
            with urlopen(url, timeout=2.0) as response:
                if response.status == 200:
                    return
        except Exception:
            pass
        time.sleep(0.25)

    raise TimeoutError("Timed out waiting for the server to become healthy.")


def measure_request_peak(
    sampler: "ProcessTreeSampler",
    payloads: list[dict[str, object]],
    url: str,
) -> int:
    barrier = threading.Barrier(len(payloads) + 1)
    failures: list[str] = []
    threads = [
        threading.Thread(
            target=perform_request,
            args=(url, payload, barrier, failures),
            daemon=True,
        )
        for payload in payloads
    ]

    for thread in threads:
        thread.start()

    start_sample = sampler.sample_count()
    barrier.wait()

    while any(thread.is_alive() for thread in threads):
        time.sleep(0.02)

    for thread in threads:
        thread.join()

    if failures:
        raise RuntimeError(f"request phase failed: {failures[0]}")

    return sampler.peak_since(start_sample)


def perform_request(
    url: str,
    payload: dict[str, object],
    barrier: threading.Barrier,
    failures: list[str],
) -> None:
    barrier.wait()
    request = Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )

    try:
        with urlopen(request, timeout=180.0) as response:
            if response.status != 200:
                failures.append(f"unexpected status {response.status}")
            else:
                json.loads(response.read().decode("utf-8"))
    except Exception as exc:
        failures.append(str(exc))


def format_stage(rss_bytes: int) -> dict[str, object]:
    return {
        "rss_bytes": rss_bytes,
        "rss_mib": round(rss_bytes / (1024 * 1024), 2),
        "rss_gib": round(rss_bytes / (1024 * 1024 * 1024), 2),
    }


def stop_process(process: subprocess.Popen[str]) -> None:
    if process.poll() is not None:
        return

    process.send_signal(signal.SIGINT)
    try:
        process.wait(timeout=10)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=5)


class ProcessTreeSampler:
    def __init__(self, root_pid: int, interval: float) -> None:
        self.root_pid = root_pid
        self.interval = interval
        self.samples: list[int] = []
        self._stop = threading.Event()
        self._ready = threading.Event()
        self._thread = threading.Thread(target=self._run, daemon=True)

    def start(self) -> None:
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        self._thread.join(timeout=2.0)

    def wait_for_first_sample(self, timeout: float) -> None:
        if not self._ready.wait(timeout=timeout):
            raise TimeoutError("No RSS sample was collected in time.")

    def current_rss_bytes(self) -> int:
        if not self.samples:
            raise RuntimeError("No RSS samples collected yet.")
        return self.samples[-1]

    def peak_since(self, sample_index: int) -> int:
        window = self.samples[sample_index:]
        if not window:
            return self.current_rss_bytes()
        return max(window)

    def sample_count(self) -> int:
        return len(self.samples)

    def _run(self) -> None:
        while not self._stop.is_set():
            rss_bytes = read_process_tree_rss(self.root_pid)
            self.samples.append(rss_bytes)
            self._ready.set()
            time.sleep(self.interval)


def read_process_tree_rss(root_pid: int) -> int:
    table = read_process_table()
    descendants = collect_descendants(root_pid, table)
    return sum(table[pid]["rss_kib"] * 1024 for pid in descendants if pid in table)


def read_process_table() -> dict[int, dict[str, int]]:
    result = subprocess.run(
        ["ps", "-ax", "-o", "pid=,ppid=,rss="],
        check=True,
        capture_output=True,
        text=True,
    )

    table: dict[int, dict[str, int]] = {}
    for line in result.stdout.splitlines():
        parts = line.split()
        if len(parts) != 3:
            continue
        pid, ppid, rss_kib = (int(part) for part in parts)
        table[pid] = {"ppid": ppid, "rss_kib": rss_kib}
    return table


def collect_descendants(root_pid: int, table: dict[int, dict[str, int]]) -> set[int]:
    descendants = {root_pid}
    changed = True
    while changed:
        changed = False
        for pid, row in table.items():
            if row["ppid"] in descendants and pid not in descendants:
                descendants.add(pid)
                changed = True
    return descendants


if __name__ == "__main__":
    main()
