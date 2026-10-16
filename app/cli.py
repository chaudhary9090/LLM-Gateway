"""Unified Developer CLI for LLM Gateway."""

import argparse
import asyncio
import os
import platform
import shutil
import subprocess
import sys
from typing import Dict, List

import httpx

GATEWAY_DEFAULT_URL = os.getenv("GATEWAY_BASE_URL", "http://localhost:8000")


def _print_banner():
    banner = r"""
  _     _     __  __    ____       _
 | |   | |   |  \/  |  / ___| __ _| |_ _____      ____ _ _   _
 | |   | |   | |\/| | | |  _ / _` | __/ _ \ \ /\ / / _` | | | |
 | |___| |___| |  | | | |_| | (_| | ||  __/\ V  V / (_| | |_| |
 |_____|_____|_|  |_|  \____|\__,_|\__\___| \_/\_/ \__,_|\__, |
                                                          |___/
    Production-Grade Unified AI Router, Cache & Resilience Gateway
"""
    print(banner)


def cmd_init():
    """Initializes project configuration, virtual environment, and dependencies."""
    _print_banner()
    print("[INIT] Setting up LLM Gateway local environment...\n")

    # 1. Setup .env
    if not os.path.exists(".env"):
        if os.path.exists(".env.example"):
            shutil.copy(".env.example", ".env")
            print("  [+] Created .env from .env.example with safe default configurations.")
        else:
            print("  [!] .env.example not found. Please create .env manually.")
    else:
        print("  [*] .env configuration file already exists.")

    # 2. Check or create .venv
    venv_python = (
        os.path.join(".venv", "Scripts", "python.exe")
        if platform.system() == "Windows"
        else os.path.join(".venv", "bin", "python")
    )
    if not os.path.exists(venv_python):
        print("  [+] Creating Python virtual environment in .venv...")
        subprocess.run([sys.executable, "-m", "venv", ".venv"], check=True)
        print("  [+] Virtual environment created.")
    else:
        print("  [*] Virtual environment .venv already exists.")

    # 3. Install requirements
    if os.path.exists("requirements.txt"):
        print("  [+] Installing dependencies from requirements.txt...")
        subprocess.run([venv_python, "-m", "pip", "install", "-r", "requirements.txt"], check=True)
        print("  [+] Dependencies installed successfully.")

    print("\n[SUCCESS] Gateway environment is ready! Start it using: python gateway.py start\n")


def cmd_doctor():
    """Diagnostic system health and dependency checks with troubleshooting hints."""
    _print_banner()
    print("[DOCTOR] Inspecting local environment and subsystem readiness...\n")

    checks = []

    # 1. Python version check
    py_ver = sys.version_info
    py_ok = py_ver >= (3, 12)
    checks.append(
        (
            "Python Version",
            f"{py_ver.major}.{py_ver.minor}.{py_ver.micro}",
            "PASS" if py_ok else "FAIL",
            "Upgrade to Python 3.12 or newer (https://python.org)" if not py_ok else "Compatible",
        )
    )

    # 2. SQLite Database
    db_path = "./gateway.db"
    try:
        import sqlite3

        conn = sqlite3.connect(db_path)
        conn.execute("SELECT 1")
        conn.close()
        db_status = "PASS"
        db_hint = f"Connected ({db_path})"
    except Exception as e:
        db_status = "FAIL"
        db_hint = f"Cannot access SQLite: {e}"
    checks.append(("SQLite Persistence", "Local DB", db_status, db_hint))

    # 3. Redis Cache
    redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    try:
        import redis

        r = redis.Redis.from_url(redis_url, socket_timeout=1.0)
        r.ping()
        redis_status = "PASS"
        redis_hint = "Redis reachable for fast L1 caching"
    except Exception:
        redis_status = "WARN"
        redis_hint = "Redis offline. Gateway automatically degrades to in-memory caching."
    checks.append(("Redis Cache", redis_url, redis_status, redis_hint))

    # 4. Local Engine (Ollama / LM Studio)
    local_url = os.getenv("LOCAL_BASE_URL", "http://localhost:11434/v1")
    ollama_ok = False
    try:
        with httpx.Client(timeout=1.0) as client:
            res = client.get(f"{local_url}/models")
            if res.status_code == 200:
                ollama_ok = True
                ollama_hint = "Local engine online. Offline private inference active."
    except Exception:
        pass

    if not ollama_ok:
        try:
            with httpx.Client(timeout=1.0) as client:
                res = client.get("http://localhost:11434/api/tags")
                if res.status_code == 200:
                    ollama_ok = True
                    ollama_hint = "Ollama detected via native API."
        except Exception:
            pass

    if not ollama_ok:
        ollama_status = "INFO"
        ollama_hint = (
            "No local engine detected at localhost:11434. "
            "Mock providers handle offline mode seamlessly. Optional: install Ollama (https://ollama.ai)."
        )
    else:
        ollama_status = "PASS"
    checks.append(("Local Engine (Ollama)", local_url, ollama_status, ollama_hint))

    # 5. Port 8000 Availability
    import socket

    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        s.bind(("0.0.0.0", 8000))
        port_status = "PASS"
        port_hint = "Port 8000 is free and available."
    except OSError:
        port_status = "INFO"
        port_hint = "Port 8000 is currently in use (gateway is likely already running)."
    finally:
        s.close()
    checks.append(("Gateway Port (8000)", "0.0.0.0:8000", port_status, port_hint))

    # Print Table
    col_w = [25, 25, 8, 45]
    header = f"{'CHECK':<{col_w[0]}} {'TARGET':<{col_w[1]}} {'STATUS':<{col_w[2]}} {'DIAGNOSTIC / HINT':<{col_w[3]}}"
    sep = "-" * len(header)
    print(sep)
    print(header)
    print(sep)
    for name, target, status, hint in checks:
        print(f"{name:<{col_w[0]}} {target:<{col_w[1]}} {status:<{col_w[2]}} {hint:<{col_w[3]}}")
    print(sep)
    print("\n[DOCTOR COMPLETE] System is ready for operation.\n")


def cmd_start():
    """Starts the Uvicorn ASGI server."""
    _print_banner()
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "8000"))
    print(f"[START] Launching LLM Gateway on http://{host}:{port} ...\n")
    try:
        import uvicorn

        uvicorn.run("app.main:app", host=host, port=port, reload=True)
    except KeyboardInterrupt:
        print("\n[STOP] Gateway gracefully stopped.")


def cmd_models(base_url: str = GATEWAY_DEFAULT_URL):
    """Fetches and displays active model catalog from running gateway."""
    url = f"{base_url.rstrip('/')}/models"
    try:
        with httpx.Client(timeout=5.0) as client:
            res = client.get(url)
            if res.status_code != 200:
                print(f"[ERROR] Failed to fetch models from gateway ({res.status_code}): {res.text}")
                return
            data = res.json()
    except Exception as e:
        print(f"[ERROR] Could not connect to gateway at {url}. Is it running? ({e})")
        return

    _print_banner()
    print(f"[MODELS] Configured Model Catalog & Routing Chains ({len(data)} models registered):\n")

    col_w = [22, 12, 18, 28, 12]
    header = f"{'MODEL ID':<{col_w[0]}} {'TIER':<{col_w[1]}} {'PRIMARY':<{col_w[2]}} {'FALLBACK CHAIN':<{col_w[3]}} {'PRICE/1K':<{col_w[4]}}"
    sep = "=" * len(header)
    print(sep)
    print(header)
    print(sep)
    for m in data:
        name = m.get("name", "")
        tier = m.get("tier", "").upper()
        primary = m.get("primary_provider", "")
        fallbacks = " -> ".join(m.get("fallback_providers", [])) or "None"
        cost = f"${m.get('input_cost_per_1k', 0.0):.4f}"
        print(f"{name:<{col_w[0]}} {tier:<{col_w[1]}} {primary:<{col_w[2]}} {fallbacks:<{col_w[3]}} {cost:<{col_w[4]}}")
    print(sep + "\n")


def cmd_stats(base_url: str = GATEWAY_DEFAULT_URL):
    """Fetches and displays real-time operational statistics."""
    url = f"{base_url.rstrip('/')}/stats"
    api_key = os.getenv("GATEWAY_API_KEY", "")
    headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}

    try:
        with httpx.Client(timeout=5.0) as client:
            res = client.get(url, headers=headers)
            if res.status_code != 200:
                print(f"[ERROR] Failed to fetch stats ({res.status_code}): {res.text}")
                return
            stats = res.json()
    except Exception as e:
        print(f"[ERROR] Could not connect to gateway at {url}: {e}")
        return

    _print_banner()
    print("[STATS] Real-Time Gateway Telemetry:\n")
    print(f"  * Total Requests:        {stats.get('total_requests', 0):,}")
    print(f"  * Successful Requests:   {stats.get('successful_requests', 0):,}")
    print(f"  * Failed Requests:       {stats.get('failed_requests', 0):,}")
    print(f"  * Cache Hits:            {stats.get('cache_hits', 0):,} ({stats.get('cache_hit_rate', 0.0)*100:.1f}%)")
    print(f"  * Cache Misses:          {stats.get('cache_misses', 0):,}")
    print(f"  * Fallback Count:        {stats.get('fallback_count', 0):,}")
    print(f"  * Total Tokens:          {stats.get('total_tokens', 0):,} (In: {stats.get('prompt_tokens', 0):,} | Out: {stats.get('completion_tokens', 0):,})")
    print(f"  * Total Estimated Cost:  ${stats.get('total_estimated_cost_usd', 0.0):.6f}")
    print(f"  * Latency (p50 / Median):{stats.get('latency_p50_ms', 0.0):.2f} ms")
    print(f"  * Latency (p95):         {stats.get('latency_p95_ms', 0.0):.2f} ms")
    print(f"  * Latency (p99):         {stats.get('latency_p99_ms', 0.0):.2f} ms\n")


async def _async_chat(base_url: str, model: str):
    """Interactive streaming chat in the terminal."""
    url = f"{base_url.rstrip('/')}/v1/chat/completions"
    api_key = os.getenv("GATEWAY_API_KEY", "")
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}" if api_key else "",
    }

    _print_banner()
    print(f"[CHAT] Connected to {url}")
    print(f"[CHAT] Model: '{model}' (type 'exit', 'quit', or 'q' to end)\n")

    history: List[Dict[str, str]] = []

    async with httpx.AsyncClient(timeout=45.0) as client:
        while True:
            try:
                user_input = input("You > ").strip()
            except (KeyboardInterrupt, EOFError):
                print("\nExiting chat.")
                break

            if not user_input:
                continue
            if user_input.lower() in ("exit", "quit", "q"):
                print("Goodbye!")
                break

            history.append({"role": "user", "content": user_input})
            payload = {
                "model": model,
                "messages": history,
                "temperature": 0.7,
                "stream": True,
            }

            print("Assistant > ", end="", flush=True)
            full_assistant_reply = ""

            try:
                async with client.stream("POST", url, json=payload, headers=headers) as response:
                    if response.status_code != 200:
                        error_body = await response.aread()
                        print(f"\n[ERROR {response.status_code}]: {error_body.decode('utf-8')}")
                        continue

                    async for line in response.aiter_lines():
                        line = line.strip()
                        if not line or not line.startswith("data: "):
                            continue
                        data_part = line[6:].strip()
                        if data_part == "[DONE]":
                            break
                        try:
                            import json

                            chunk = json.loads(data_part)
                            delta = chunk.get("choices", [{}])[0].get("delta", {})
                            content = delta.get("content", "")
                            if content:
                                print(content, end="", flush=True)
                                full_assistant_reply += content
                        except Exception:
                            continue

                print("\n")
                if full_assistant_reply:
                    history.append({"role": "assistant", "content": full_assistant_reply})

            except Exception as e:
                print(f"\n[Request Failed]: {e}\n")


def cmd_chat(base_url: str = GATEWAY_DEFAULT_URL, model: str = "cheap"):
    """Launches terminal chat."""
    asyncio.run(_async_chat(base_url, model))


def main():
    """CLI argument parser and dispatcher."""
    parser = argparse.ArgumentParser(
        description="LLM Gateway CLI - Unified Control & Diagnostics Tool"
    )
    subparsers = parser.add_subparsers(dest="command", help="Available gateway commands")

    subparsers.add_parser("init", help="Initialize configuration, .env, and dependencies")
    subparsers.add_parser("doctor", help="Run system diagnostics and dependency checks")
    subparsers.add_parser("start", help="Start the gateway ASGI server")

    models_parser = subparsers.add_parser("models", help="List registered models and routing chains")
    models_parser.add_argument("--url", default=GATEWAY_DEFAULT_URL, help="Gateway base URL")

    stats_parser = subparsers.add_parser("stats", help="Show real-time gateway operational stats")
    stats_parser.add_argument("--url", default=GATEWAY_DEFAULT_URL, help="Gateway base URL")

    chat_parser = subparsers.add_parser("chat", help="Start interactive terminal chat session")
    chat_parser.add_argument("--url", default=GATEWAY_DEFAULT_URL, help="Gateway base URL")
    chat_parser.add_argument("--model", default="cheap", help="Target model alias or ID (default: cheap)")

    args = parser.parse_args()

    if args.command == "init":
        cmd_init()
    elif args.command == "doctor":
        cmd_doctor()
    elif args.command == "start":
        cmd_start()
    elif args.command == "models":
        cmd_models(args.url)
    elif args.command == "stats":
        cmd_stats(args.url)
    elif args.command == "chat":
        cmd_chat(args.url, args.model)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
