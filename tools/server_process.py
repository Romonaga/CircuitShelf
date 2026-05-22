#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from process_lock import process_exists, read_pid_file, terminate_pid_file_process  # noqa: E402


def configured_pid_file() -> Path:
    config_path = PROJECT_ROOT / "config" / "config.yaml"
    configured = None
    if config_path.exists():
        with config_path.open("r", encoding="utf-8") as handle:
            config = yaml.safe_load(handle) or {}
        configured = config.get("SERVER_PID_FILE")
    return PROJECT_ROOT / str(configured or "data/circuitshelf.pid")


def main() -> int:
    parser = argparse.ArgumentParser(description="Inspect or stop the CircuitShelf server process.")
    parser.add_argument("action", choices=["status", "stop"], help="Action to run against the configured PID file.")
    parser.add_argument("--pid-file", default=None, help="Override the configured PID file path.")
    parser.add_argument("--timeout", type=float, default=20.0, help="Seconds to wait before force-killing on stop.")
    args = parser.parse_args()

    pid_file = Path(args.pid_file) if args.pid_file else configured_pid_file()
    if not pid_file.is_absolute():
        pid_file = PROJECT_ROOT / pid_file

    data = read_pid_file(pid_file)
    pid = int(data.get("pid") or 0) if data else 0
    running = bool(pid and process_exists(pid))

    if args.action == "status":
        if running:
            print(f"CircuitShelf is running as PID {pid}.")
            print(f"PID file: {pid_file}")
            return 0
        if pid_file.exists():
            print(f"CircuitShelf is not running; stale PID file found at {pid_file}.")
            return 1
        print("CircuitShelf is not running.")
        return 3

    stopped = terminate_pid_file_process(pid_file, timeout_seconds=args.timeout)
    if stopped:
        print(f"Stopped CircuitShelf PID {pid}.")
        return 0
    print("CircuitShelf was not running.")
    return 3


if __name__ == "__main__":
    raise SystemExit(main())
