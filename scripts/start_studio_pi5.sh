#!/usr/bin/env bash
# Optimal launch script for Lumio Voice Studio on Raspberry Pi 5 (8GB RAM)
# Uses CPU device mapping, restricts thread count to avoid core thrashing, and binds to loopback.
set -euo pipefail
cd "$(dirname "$0")/.."

export HF_HUB_OFFLINE=1
export TRANSFORMERS_OFFLINE=1
export HF_HUB_DISABLE_TELEMETRY=1
export GRADIO_ANALYTICS_ENABLED=False

# Limit OpenMP / PyTorch to the Pi 5's 4 physical Cortex-A76 cores
export OMP_NUM_THREADS=4
export MKL_NUM_THREADS=4
export TORCH_NUM_THREADS=4

PYTHON=".venv/bin/python"
if [ ! -f "$PYTHON" ]; then
  PYTHON=".venv-offline/bin/python"
fi
if [ ! -f "$PYTHON" ]; then
  PYTHON="python3"
fi

printf "Starting Lumio Voice Studio in Raspberry Pi 5 (CPU) mode on port 7860...\n"
exec "$PYTHON" studio/server.py --device cpu --port 7860 "$@"

