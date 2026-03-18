#!/usr/bin/env python3
"""
Launch llama-server with an embedding model.
"""

import subprocess
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent

# Default model
DEFAULT_MODEL = SCRIPT_DIR / "Qwen3-Embedding-0.6B-f16.gguf"

# llama-server path
LLAMA_SERVER_PATH = Path.home() / "Downloads/llama-b7971-bin-ubuntu-vulkan-x64/llama-b7971/llama-server"

# Server settings
DEFAULT_PORT = 8080
DEFAULT_HOST = "0.0.0.0"


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Launch llama-server with an embedding model")
    parser.add_argument(
        "-m", "--model",
        type=Path,
        default=DEFAULT_MODEL,
        help=f"Path to GGUF model file (default: {DEFAULT_MODEL})"
    )
    parser.add_argument(
        "-p", "--port",
        type=int,
        default=DEFAULT_PORT,
        help=f"Server port (default: {DEFAULT_PORT})"
    )
    parser.add_argument(
        "--host",
        type=str,
        default=DEFAULT_HOST,
        help=f"Server host (default: {DEFAULT_HOST})"
    )
    parser.add_argument(
        "-c", "--ctx-size",
        type=int,
        default=512,
        help="Context size (default: 512)"
    )
    parser.add_argument(
        "-t", "--threads",
        type=int,
        default=None,
        help="Number of threads (default: auto)"
    )
    parser.add_argument(
        "--gpu-layers",
        type=int,
        default=-1,
        help="Number of layers to offload to GPU (-1 = all, default: -1)"
    )

    args = parser.parse_args()

    if not args.model.exists():
        print(f"Error: Model file not found: {args.model}")
        sys.exit(1)

    if not LLAMA_SERVER_PATH.exists():
        print(f"Error: llama-server not found at: {LLAMA_SERVER_PATH}")
        sys.exit(1)

    cmd = [
        str(LLAMA_SERVER_PATH),
        "-m", str(args.model),
        "--port", str(args.port),
        "--host", args.host,
        "--ctx-size", str(args.ctx_size),
        "--embedding"
    ]

    if args.threads:
        cmd.extend(["-t", str(args.threads)])

    if args.gpu_layers >= 0:
        cmd.extend(["-ngl", str(args.gpu_layers)])

    print(f"Starting llama-server...")
    print(f"  Binary: {LLAMA_SERVER_PATH}")
    print(f"  Model: {args.model}")
    print(f"  URL: http://{args.host}:{args.port}")
    print(f"  Embeddings: enabled")
    print()

    try:
        subprocess.run(cmd)
    except KeyboardInterrupt:
        print("\nShutting down...")
    except FileNotFoundError:
        print(f"Error: llama-server not found at: {LLAMA_SERVER_PATH}")
        sys.exit(1)


if __name__ == "__main__":
    main()
