"""Run two simultaneous requests against the blocking HTTP wrapper."""

from __future__ import annotations

import argparse
import json
import threading
import time
from unittest import result
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

DEFAULT_URL = "http://127.0.0.1:8000/generate"
DEFAULT_PROMPT = (
    "Explain in one short paragraph what unified memory means on Apple Silicon."
)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default=DEFAULT_URL)
    parser.add_argument("--prompt", default=DEFAULT_PROMPT)
    parser.add_argument("--max-tokens", type=int, default=128)
    parser.add_argument("--temperature", type=float, default=0.0)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument(
        "--output",
        default="results/logs/http-concurrency-01.json",
        help="Path to write the combined concurrency result JSON.",
    )
    args = parser.parse_args()

    payload = {
        "prompt": args.prompt,
        "max_tokens": args.max_tokens,
        "temperature": args.temperature,
        "seed": args.seed,
    }

    ready = threading.Barrier(3)
    results: list[dict[str, Any] | None] = [None, None]
    threads = [
        threading.Thread(
            target=worker, args=(i + 1, args.url, payload, ready, results, i)
        )
        for i in range(2)
    ]

    for thread in threads:
        thread.start()

    start = time.perf_counter()
    ready.wait()

    for thread in threads:
        thread.join()
    end = time.perf_counter()

    summary = {
        "run_id": "http-concurrency-01",
        "url": args.url,
        "payload": payload,
        "started_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "total_wall_time_seconds": round(end - start, 3),
        "requests": results,
        "observation": summarize(results, end - start),
    }

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(summary, ensure_ascii=True, indent=2) + "\n")
    print(json.dumps(summary, ensure_ascii=True, indent=2))

def worker(
    request_id: int,
    url: str,
    payload: dict[str, Any],
    ready: threading.Barrier,
    results: list[dict[str, Any] | None],
    index: int,
) -> None:
    body = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=body,
        headers={"Content-Type": "application/json", "Accept": "application/json"},
        method="POST",
    )

    ready.wait()
    started = time.perf_counter()

    try:
        with urllib.request.urlopen(request, timeout=300) as response:
            raw_body = response.read().decode("utf-8")
            parsed_body = json.loads(raw_body)
            finished = time.perf_counter()
            results[index] = {
                "request_id": request_id,
                "status_code": response.status,
                "duration_seconds": round(finished - started, 3),
                "completion_tokens": parsed_body.get("usage", {}).get(
                    "completion_tokens"
                ),
                "finish_reason": parsed_body.get("finish_reason"),
                "response": parsed_body,
            }
    except urllib.error.HTTPError as exc:
        error_body = exc.read().decode("utf-8")
        finished = time.perf_counter()
        results[index] = {
            "request_id": request_id,
            "status_code": exc.code,
            "duration_seconds": round(finished - started, 3),
            "error": error_body,
        }
    except Exception as exc:
        finished = time.perf_counter()
        results[index] = {
            "request_id": request_id,
            "status_code": None,
            "duration_seconds": round(finished - started, 3),
            "error": str(exc),
        }

def summarize(results: list[dict[str, Any] | None], total_wall_time: float) -> str:
    for result in results:
        if not result or result.get("status_code") != 200:
            return "incomplete_run_or_server_unreachable"

    durations = sorted(
        result["duration_seconds"]
        for result in results
        if result and isinstance(result.get("duration_seconds"), (int, float))
    )
    if len(durations) != 2:
        return "incomplete_run"

    short, long = durations
    if long > short * 1.5 and total_wall_time > short * 1.5:
        return "requests_appear_serialized_or_queued"
    return "requests_appear_to_overlap_more_than_expected"

if __name__ == "__main__":
    main()
