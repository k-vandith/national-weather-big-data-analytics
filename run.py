"""Run the local HTML/CSS/JavaScript weather analytics console."""
from __future__ import annotations

import argparse

import uvicorn


def main() -> None:
    parser = argparse.ArgumentParser(description="Start the local National Weather Analytics web app.")
    parser.add_argument("--host", default="127.0.0.1", help="Bind address (default: loopback only)")
    parser.add_argument("--port", type=int, default=8501, help="HTTP port (default: 8501)")
    args = parser.parse_args()
    if not 1 <= args.port <= 65535:
        parser.error("--port must be between 1 and 65535")
    uvicorn.run("src.api:app", host=args.host, port=args.port, reload=False)


if __name__ == "__main__":
    main()
