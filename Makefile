LLAMA_DIR := llama.cpp
VENV_DIR := .venv
MODEL_DIR := models
LOG_DIR := results/logs
PYTHON_VERSION ?= 3.11
SDK_CXX_HEADERS := /Library/Developer/CommandLineTools/SDKs/MacOSX.sdk/usr/include/c++/v1
JOBS ?= $(shell sysctl -n hw.ncpu 2>/dev/null || echo 8)
LLAMA_REPO := https://github.com/ggerganov/llama.cpp.git
MODEL_REPO := QuantFactory/Mistral-7B-Instruct-v0.2-GGUF
MODEL_PATTERN := *Q4_K_M.gguf
MODEL_FILE := Mistral-7B-Instruct-v0.2.Q4_K_M.gguf
MODEL_PATH := $(MODEL_DIR)/$(MODEL_FILE)
CLI_BIN := $(LLAMA_DIR)/build/bin/llama-completion
CLI_CTX ?= 4096
CLI_N_PREDICT ?= 128
CLI_SEED ?= 42
CLI_GPU_LAYERS ?= auto
CLI_PROMPT ?= Explain in one short paragraph what unified memory means on Apple Silicon.
CLI_LOG ?= $(LOG_DIR)/cli-baseline.txt

.DEFAULT_GOAL := help

.PHONY: help add-submodule submodule venv install download-model model-path cli-baseline cli-all-metal cli-cpu-only build-llama clean-llama run-server

help: ## Show every available target and what it does
	@echo "Available targets:"
	@awk 'BEGIN {FS = ":.*## "}; /^[a-zA-Z0-9_.-]+:.*## / {printf "  %-14s %s\n", $$1, $$2}' $(MAKEFILE_LIST)

add-submodule: ## Add llama.cpp as a git submodule at the repo root
	git submodule add $(LLAMA_REPO) $(LLAMA_DIR)

submodule: ## Initialize or update the pinned llama.cpp submodule
	git submodule update --init --recursive

venv: ## Create the local uv-managed virtual environment in .venv
	uv venv --python $(PYTHON_VERSION) $(VENV_DIR)

install: ## Install Python dependencies into the local .venv
	uv pip install --python $(VENV_DIR)/bin/python -r requirements.txt

download-model: ## Download Mistral 7B Instruct v0.2 GGUF in Q4_K_M into models/
	uvx hf download $(MODEL_REPO) --include "$(MODEL_PATTERN)" --local-dir $(MODEL_DIR)

model-path: ## Print the expected local path for the benchmark model
	@echo $(MODEL_PATH)

cli-baseline: ## Run the raw llama-completion baseline and save a benchmark log
	mkdir -p $(LOG_DIR)
	/usr/bin/time -l $(CLI_BIN) \
		-m $(MODEL_PATH) \
		-c $(CLI_CTX) \
		-n $(CLI_N_PREDICT) \
		-ngl $(CLI_GPU_LAYERS) \
		-no-cnv \
		--temp 0 \
		--seed $(CLI_SEED) \
		--perf \
		-p "$(CLI_PROMPT)" \
		2>&1 | tee $(CLI_LOG)

cli-all-metal: CLI_GPU_LAYERS = all
cli-all-metal: CLI_LOG = $(if $(filter $(LOG_DIR)/cli-baseline.txt,$(CLI_LOG)),$(LOG_DIR)/cli-all-metal.txt,$(CLI_LOG))
cli-all-metal: ## Run the raw llama-completion baseline with all 33 layers forced to Metal
	$(MAKE) cli-baseline CLI_GPU_LAYERS="$(CLI_GPU_LAYERS)" CLI_LOG="$(CLI_LOG)"

cli-cpu-only: CLI_GPU_LAYERS = 0
cli-cpu-only: CLI_LOG = $(if $(filter $(LOG_DIR)/cli-baseline.txt,$(CLI_LOG)),$(LOG_DIR)/cli-cpu-only.txt,$(CLI_LOG))
cli-cpu-only: ## Run the raw llama-completion baseline with CPU-only inference and zero GPU layers
	$(MAKE) cli-baseline CLI_GPU_LAYERS="$(CLI_GPU_LAYERS)" CLI_LOG="$(CLI_LOG)"

build-llama: ## Configure and build llama.cpp with the macOS SDK libc++ workaround
	cmake -S $(LLAMA_DIR) -B $(LLAMA_DIR)/build -DCMAKE_CXX_FLAGS='-isystem $(SDK_CXX_HEADERS)'
	cmake --build $(LLAMA_DIR)/build --config Release -j $(JOBS)

clean-llama: ## Remove the llama.cpp build directory
	rm -rf $(LLAMA_DIR)/build

run-server: ## Start the Python server entrypoint using the local .venv
	$(VENV_DIR)/bin/python server/server.py
