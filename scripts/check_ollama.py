# /// script
# requires-python = ">=3.10"
# dependencies = [
#   "requests",
#   "rich>=13.7",
# ]
# ///

"""
Check Ollama server status and required models readiness.

Usage examples:
  uv run scripts/check_ollama.py
  uv run scripts/check_ollama.py --models gpt-oss,bge-m3 --probe
  uv run scripts/check_ollama.py --host 127.0.0.1 --port 11434 --json

Environment variables (defaults):
  OLLAMA_HOST=localhost
  OLLAMA_PORT=11434

Exit codes:
  0 = server reachable and all required models present (and probes ok if enabled)
  1 = server not reachable
  2 = some models missing
  3 = probe failed for at least one model
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from typing import List, Dict, Any

import requests
from requests.exceptions import RequestException
from rich.console import Console
from rich.table import Table
from rich import box


def load_dotenv_if_exists(filename: str = ".env.local") -> None:
    """Load simple KEY=VALUE lines from a dotenv-style file into os.environ.

    Ignores blank lines, comments starting with '#', and fenced code markers like ```.
    Expands ${VAR} using existing environment (or earlier keys in the file if ordered).
    """
    # search likely locations: cwd and script parent dir
    candidates = [os.path.join(os.getcwd(), filename), os.path.join(os.path.dirname(__file__), "..", filename)]
    for path in candidates:
        try:
            full = os.path.abspath(path)
            if not os.path.exists(full):
                continue
            with open(full, "r", encoding="utf-8") as fh:
                for raw in fh:
                    line = raw.strip()
                    if not line or line.startswith("#") or line.startswith("```"):
                        continue
                    if "=" not in line:
                        continue
                    k, v = line.split("=", 1)
                    k = k.strip()
                    v = v.strip()
                    # strip surrounding quotes if present
                    if (v.startswith('"') and v.endswith('"')) or (v.startswith("'") and v.endswith("'")):
                        v = v[1:-1]
                    # expand environment variables using any already-loaded env
                    v = os.path.expandvars(v)
                    # don't override existing env unless not set
                    if k not in os.environ:
                        os.environ[k] = v
            # stop after first found file
            return
        except Exception:
            # best-effort loader; ignore errors
            return

# Load .env.local early so parse_args can read defaults from it
load_dotenv_if_exists()


def get_base_url(host: str, port: int) -> str:
    scheme = "http"  # Ollama typically runs without TLS locally
    return f"{scheme}://{host}:{port}"


def resolve_urls(host: str, port: int) -> Dict[str, str]:
    """Resolve effective URLs for tags/generate/embeddings from env or host/port."""
    base_env = os.environ.get("OLLAMA_BASE_URL")
    if base_env:
        base = base_env
    else:
        base = get_base_url(host, port)

    return {
        "base": base,
        "tags": os.environ.get("OLLAMA_TAGS_URL", f"{base}/api/tags"),
        "generate": os.environ.get("OLLAMA_GENERATE_URL", f"{base}/api/generate"),
        "embeddings": os.environ.get("OLLAMA_EMBEDDING_URL", f"{base}/api/embeddings"),
    }


def check_server(base_url: str, timeout: float = 3.0) -> Dict[str, Any]:
    url = f"{base_url}/api/tags"
    try:
        resp = requests.get(url, timeout=timeout)
        resp.raise_for_status()
        data = resp.json()
        # Normalize model names
        models = [m.get("name", "") for m in data.get("models", [])]
        return {"ok": True, "models": models, "error": None}
    except RequestException as e:
        return {"ok": False, "models": [], "error": str(e)}
    except ValueError:
        # Non-JSON response
        return {"ok": False, "models": [], "error": "Invalid response from /api/tags"}


def model_present(installed: List[str], name: str) -> bool:
    target = name.strip()
    for m in installed:
        base = m.split(":")[0]
        if m == target or base == target:
            return True
    return False


def probe_embedding(base_url: str, model: str, timeout: float = 10.0) -> bool:
    url = f"{base_url}/api/embeddings"
    payload = {"model": model, "prompt": "ping"}
    try:
        resp = requests.post(url, json=payload, timeout=timeout)
        resp.raise_for_status()
        data = resp.json()
        emb = data.get("embedding")
        return isinstance(emb, list) and len(emb) > 0
    except RequestException:
        return False
    except ValueError:
        return False


def probe_generate(base_url: str, model: str, timeout: float = 20.0) -> bool:
    url = f"{base_url}/api/generate"
    payload = {"model": model, "prompt": "ping", "stream": False}
    try:
        resp = requests.post(url, json=payload, timeout=timeout)
        resp.raise_for_status()
        data = resp.json()
        return bool(data.get("response"))
    except RequestException:
        return False
    except ValueError:
        return False


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Check Ollama server and model readiness.")
    parser.add_argument(
        "--host",
        default=os.environ.get("OLLAMA_HOST", "localhost"),
        help="Ollama host (default from OLLAMA_HOST or 'localhost')",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=int(os.environ.get("OLLAMA_PORT", 11434)),
        help="Ollama port (default from OLLAMA_PORT or 11434)",
    )
    parser.add_argument(
        "--models",
        default="gpt-oss,bge-m3",
        help="Comma-separated list of required models to check",
    )
    parser.add_argument(
        "--probe",
        action="store_true",
        help="Additionally probe minimal generate/embedding calls to verify runtime",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output machine-readable JSON instead of pretty table",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=3.0,
        help="HTTP timeout seconds for server check (default 3.0)",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    console = Console()
    base_url = get_base_url(args.host, args.port)
    urls = resolve_urls(args.host, args.port)
    required = [m.strip() for m in args.models.split(",") if m.strip()]

    server = check_server(urls["base"], timeout=args.timeout)
    if not server["ok"]:
        if args.json:
            print(json.dumps({
                "server": {"ok": False, "base_url": urls["base"], "error": server["error"]},
                "models": [],
                "summary": {"all_present": False, "all_probes_ok": False},
            }))
        else:
            console.print(f"[red]Ollama UNREACHABLE[/red] at {urls['base']}: {server['error']}")
        return 1

    installed = server["models"]
    results: List[Dict[str, Any]] = []
    all_present = True
    all_probes_ok = True

    for name in required:
        present = model_present(installed, name)
        probe_ok = None
        if not present:
            all_present = False
            probe_ok = False if args.probe else None
        elif args.probe:
            # Heuristic: treat bge models as embedding-capable, others as generate-capable
            if name.lower().startswith("bge"):
                probe_ok = probe_embedding(urls["embeddings"], name)
            else:
                probe_ok = probe_generate(urls["generate"], name)
            if not probe_ok:
                all_probes_ok = False

        results.append({
            "model": name,
            "present": present,
            "probe": probe_ok,
        })

    if args.json:
        print(json.dumps({
            "server": {"ok": True, "base_url": base_url},
            "installed": installed,
            "models": results,
            "summary": {"all_present": all_present, "all_probes_ok": (all_probes_ok if args.probe else None)},
        }, ensure_ascii=False))
    else:
        console.print(f"[green]Ollama reachable[/green] at {base_url}")
        table = Table(title="Model readiness", box=box.SIMPLE_HEAVY)
        table.add_column("Model", justify="left")
        table.add_column("Installed", justify="center")
        if args.probe:
            table.add_column("Probe OK", justify="center")
        for r in results:
            present = "[green]yes[/green]" if r["present"] else "[red]no[/red]"
            row = [r["model"], present]
            if args.probe:
                if r["probe"] is None:
                    cell = "-"
                else:
                    cell = "[green]yes[/green]" if r["probe"] else "[red]no[/red]"
                row.append(cell)
            table.add_row(*row)
        console.print(table)

        if not all_present:
            missing = [r["model"] for r in results if not r["present"]]
            console.print("[yellow]Missing models:[/yellow] " + ", ".join(missing))
            console.print("Hint: pull models with e.g. 'ollama pull MODEL_NAME'")

    if not all_present:
        return 2
    if args.probe and not all_probes_ok:
        return 3
    return 0


if __name__ == "__main__":
    sys.exit(main())
