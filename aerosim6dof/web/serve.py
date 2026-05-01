"""Local development server entry point for the browser simulator."""

from __future__ import annotations

import argparse


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Serve the AeroSim 6DOF browser API.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--reload", action="store_true")
    args = parser.parse_args(argv)

    import uvicorn

    uvicorn.run("aerosim6dof.web.api:app", host=args.host, port=args.port, reload=args.reload)


if __name__ == "__main__":
    main()
