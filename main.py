"""Local entry point: `uv run python main.py` starts the API on http://localhost:8000."""

import os

import uvicorn

SOURCE_DIRS = ["agents", "api", "guardrails", "Models", "utils"]


def main():
    reload = os.getenv("RELOAD", "false").lower() == "true"
    uvicorn.run(
        "api.main:app",
        host=os.getenv("HOST", "0.0.0.0"),
        port=int(os.getenv("PORT", "8000")),
        reload=reload,
        # Watch only source code - not .venv, frontend/node_modules or evals/results.
        reload_dirs=SOURCE_DIRS if reload else None,
    )


if __name__ == "__main__":
    main()
