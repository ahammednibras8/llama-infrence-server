"""Naive blocking HTTP wrapper for the first experiment."""

import atexit
import json
import os
import signal
import subprocess
import sys
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]

SERVER_HOST = os.environ.get("SERVER_HOST", "127.0.0.1")
SERVER_PORT = int(os.environ.get("SERVER_PORT", "8000"))

BACKEND_HOST = os.environ.get("LLAMA_BACKEND_HOST", "127.0.0.1")
BACKEND_PORT = int(os.environ.get("LLAMA_BACKEND_PORT", "8080"))
BACKEND_TIMEOUT = float(os.environ.get("LLAMA_BACKEND_TIMEOUT", "120"))
STARTUP_TIMEOUT = float(os.environ.get("LLAMA_STARTUP_TIMEOUT", "120"))

MODEL_PATH = ROOT / os.environ.get(
    "MODEL_PATH", "models/Mistral-7B-Instruct-v0.2.Q4_K_M.gguf"
)
LLAMA_SERVER_BIN = ROOT / os.environ.get(
    "LLAMA_SERVER_BIN", "llama.cpp/build/bin/llama-server"
)

MODEL_ALIAS = os.environ.get("MODEL_ALIAS", "mistral-7b-instruct-q4-k-m")
CTX_SIZE = int(os.environ.get("LLAMA_CTX_SIZE", "4096"))
GPU_LAYERS = os.environ.get("LLAMA_GPU_LAYERS", "auto")

DEFAULT_MAX_TOKENS = int(os.environ.get("DEFAULT_MAX_TOKENS", "128"))
DEFAULT_TEMPERATURE = float(os.environ.get("DEFAULT_TEMPERATURE", "0"))
DEFAULT_SEED = int(os.environ.get("DEFAULT_SEED", "42"))


def backend_url(path):
    return f"http://{BACKEND_HOST}:{BACKEND_PORT}{path}"


def send_json(handler, status, payload):
    body = json.dumps(payload, ensure_ascii=True).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


def backend_request(path, payload=None):
    data = None
    headers = {"Accept": "application/json"}

    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"

    request = Request(backend_url(path), data=data, headers=headers)

    try:
        with urlopen(request, timeout=BACKEND_TIMEOUT) as response:
            return response.status, json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        body = exc.read().decode("utf-8")
        try:
            return exc.code, json.loads(body)
        except json.JSONDecodeError:
            return exc.code, {"error": body}


def start_backend():
    if not LLAMA_SERVER_BIN.exists():
        raise FileNotFoundError(
            f"llama-server binary not found at {LLAMA_SERVER_BIN}. Run `make build-llama` first."
        )

    if not MODEL_PATH.exists():
        raise FileNotFoundError(
            f"Model file not found at {MODEL_PATH}. Download the model before starting the server."
        )

    process = subprocess.Popen(
        [
            str(LLAMA_SERVER_BIN),
            "--host",
            BACKEND_HOST,
            "--port",
            str(BACKEND_PORT),
            "-m",
            str(MODEL_PATH),
            "-c",
            str(CTX_SIZE),
            "-ngl",
            GPU_LAYERS,
            "--alias",
            MODEL_ALIAS,
            "--no-webui",
            "--perf",
        ],
        cwd=ROOT,
        text=True,
    )

    deadline = time.time() + STARTUP_TIMEOUT
    while time.time() < deadline:
        if process.poll() is not None:
            raise RuntimeError(
                f"llama-server exited early with code {process.returncode}."
            )

        try:
            status, _ = backend_request("/health")
            if status == 200:
                return process
        except Exception:
            pass

        time.sleep(0.5)

    process.terminate()
    raise TimeoutError("Timed out waiting for llama-server to become healthy.")


def stop_backend(process):
    if process is None or process.poll() is not None:
        return

    process.terminate()
    try:
        process.wait(timeout=10)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=5)


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):  # noqa: N802
        if self.path == "/health":
            try:
                status, body = backend_request("/health")
                send_json(
                    self,
                    200 if status == 200 else 503,
                    {"ok": status == 200, "backend": body},
                )
            except Exception as exc:
                send_json(self, 503, {"ok": False, "error": str(exc)})
            return

        send_json(self, 404, {"error": "Route not found."})

    def do_POST(self):  # noqa: N802
        if self.path != "/generate":
            send_json(self, 404, {"error": "Route not found."})
            return

        try:
            content_length = int(self.headers.get("Content-Length", "0"))
            if content_length <= 0:
                raise ValueError("Request body is required.")

            payload = json.loads(self.rfile.read(content_length).decode("utf-8"))
            if not isinstance(payload, dict):
                raise ValueError("JSON body must be an object.")

            prompt = payload.get("prompt")
            if not isinstance(prompt, str) or not prompt.strip():
                raise ValueError("prompt must be a non-empty string.")

            system_prompt = payload.get("system_prompt")
            if system_prompt is not None and not isinstance(system_prompt, str):
                raise ValueError("system_prompt must be a string.")

            max_tokens = payload.get("max_tokens", DEFAULT_MAX_TOKENS)
            temperature = payload.get("temperature", DEFAULT_TEMPERATURE)
            seed = payload.get("seed", DEFAULT_SEED)

            status, body = backend_request(
                "/v1/chat/completions",
                {
                    "model": MODEL_ALIAS,
                    "messages": (
                        (
                            [{"role": "system", "content": system_prompt}]
                            if system_prompt
                            else []
                        )
                        + [{"role": "user", "content": prompt}]
                    ),
                    "max_tokens": max_tokens,
                    "temperature": temperature,
                    "seed": seed,
                    "stream": False,
                },
            )

            if status >= 400:
                send_json(
                    self,
                    status,
                    {
                        "error": "llama.cpp backend rejected the request.",
                        "details": body,
                    },
                )
                return

            text = body["choices"][0]["message"]["content"]
            send_json(
                self,
                200,
                {
                    "content": text,
                    "model": body.get("model"),
                    "usage": body.get("usage"),
                    "finish_reason": body["choices"][0].get("finish_reason"),
                },
            )
        except ValueError as exc:
            send_json(self, 400, {"error": str(exc)})
        except URLError as exc:
            send_json(
                self,
                502,
                {"error": "Failed to contact llama.cpp backend.", "details": str(exc)},
            )
        except Exception as exc:
            send_json(
                self, 500, {"error": "Unhandled server error.", "details": str(exc)}
            )

    def log_message(self, format, *args):  # noqa: A003
        sys.stderr.write(
            "%s - - [%s] %s\n"
            % (self.address_string(), self.log_date_time_string(), format % args)
        )


def main():
    backend = start_backend()
    atexit.register(stop_backend, backend)

    def handle_signal(signum, _frame):
        raise KeyboardInterrupt(f"Received signal {signum}")

    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)

    server = HTTPServer((SERVER_HOST, SERVER_PORT), Handler)

    print(f"Python wrapper listening on http://{SERVER_HOST}:{SERVER_PORT}")
    print(f"llama.cpp backend running at {backend_url('')}")
    print(f"Model: {MODEL_PATH}")
    print("Mode: blocking, single-threaded wrapper")

    try:
        server.serve_forever()
    except KeyboardInterrupt as exc:
        print(exc)
    finally:
        server.server_close()
        stop_backend(backend)


if __name__ == "__main__":
    main()
