LLAMA_DIR := llama.cpp
VENV_DIR := .venv
PYTHON_VERSION ?= 3.11
SDK_CXX_HEADERS := /Library/Developer/CommandLineTools/SDKs/MacOSX.sdk/usr/include/c++/v1
JOBS ?= $(shell sysctl -n hw.ncpu 2>/dev/null || echo 8)
LLAMA_REPO := https://github.com/ggerganov/llama.cpp.git

.DEFAULT_GOAL := help

.PHONY: help add-submodule submodule venv install build-llama clean-llama run-server

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

build-llama: ## Configure and build llama.cpp with the macOS SDK libc++ workaround
	cmake -S $(LLAMA_DIR) -B $(LLAMA_DIR)/build -DCMAKE_CXX_FLAGS='-isystem $(SDK_CXX_HEADERS)'
	cmake --build $(LLAMA_DIR)/build --config Release -j $(JOBS)

clean-llama: ## Remove the llama.cpp build directory
	rm -rf $(LLAMA_DIR)/build

run-server: ## Start the Python server entrypoint using the local .venv
	$(VENV_DIR)/bin/python server/server.py
