"""
Aris Brain — Local LLM Integration (本地推理引擎)
===================================================

Connects ArisBrain to llama.cpp server for local inference
on the RTX 4070 SUPER. No cloud dependency.

Architecture:
  ┌──────────────────────────────────────────────┐
  │  LocalLLM (language cortex backend)          │
  │  ├── llama-server → localhost:8080           │
  │  │   └── Qwen2.5-7B-Instruct Q4_K_M          │
  │  ├── OpenAI-compatible API client            │
  │  └── Fallback: template mode if server down  │
  ├──────────────────────────────────────────────┤
  │  Start/stop lifecycle managed by BodyLauncher │
  └──────────────────────────────────────────────┘

Usage:
    llm = LocalLLM()
    llm.start()           # launches llama-server subprocess
    response = llm.chat(prompt)  # synchronous inference
    llm.stop()            # graceful shutdown
"""

from __future__ import annotations

import logging

from typing import Any, Dict, List, Optional, Callable
import json, logging, os, subprocess, time, threading, urllib.request, urllib.error
from pathlib import Path

logger = logging.getLogger("aris.local_llm")

LLAMA_DIR = Path("D:/user/Documents/llama")
MODELS_DIR = LLAMA_DIR / "models"
SERVER_EXE = Path("C:/Users/user/.docker/bin/inference/llama-server.exe")
DEFAULT_MODEL = "Qwythos-9B-Claude-Mythos-5-1M-MTP-Q6_K.gguf"
SERVER_PORT = 8089
SERVER_URL = f"http://127.0.0.1:{SERVER_PORT}"


class LocalLLM:
    """
    Manages llama.cpp server subprocess and provides
    an OpenAI-compatible chat interface.

    Runs the model on the RTX 4070 SUPER via CUDA.
    """

    def __init__(self, model_name: str = DEFAULT_MODEL, port: int = SERVER_PORT):
        self.model_name = model_name
        self.model_path = MODELS_DIR / model_name
        self.port = port
        self.server_url = f"http://127.0.0.1:{port}"

        self._process: Optional[subprocess.Popen] = None
        self._ready = False
        self._start_time = 0.0
        self._lock = threading.Lock()

        # Stats
        self.total_requests = 0
        self.total_tokens = 0
        self.last_response_time = 0.0

    # ══════════════════════════════════════════════
    # Lifecycle
    # ══════════════════════════════════════════════

    def is_available(self) -> bool:
        """Check if model file exists."""
        return self.model_path.exists()

    def start(self, timeout: float = 60.0) -> bool:
        """
        Launch llama-server as a subprocess with CUDA acceleration.

        Args:
            timeout: Max seconds to wait for server to be ready

        Returns:
            True if server started successfully
        """
        if self._ready:
            return True

        if not SERVER_EXE.exists():
            logger.error(f"llama-server not found at {SERVER_EXE}")
            return False

        if not self.model_path.exists():
            logger.warning(f"Model not found at {self.model_path}")
            logger.warning(f"Available: {[p.name for p in MODELS_DIR.glob('*.gguf')]}")
            return False

        # Build command with optimal settings for RTX 4070 SUPER
        # ctx-size=524288 (512K) + Q4_0 KV + ngl=35 = 12GB 显存可行
        cmd = [
            str(SERVER_EXE),
            "--model", str(self.model_path),
            "--host", "127.0.0.1",
            "--port", str(self.port),
            "--n-gpu-layers", "35",           # 35 层全 GPU
            "--ctx-size", "524288",          # 512K context
            "--batch-size", "512",
            "--ubatch-size", "512",
            "--flash-attn", "1",              # faster attention + 节省 KV cache
            "--no-mmap",                      # better for CUDA
            "--parallel", "1",                # single user
            "--threads", "8",                 # CPU 线程数
            "--cache-type-k", "q4_0",         # KV cache 量化: Q4_0 (1/4 显存)
            "--cache-type-v", "q4_0",         # 512K fp16 会 OOM, Q4_0 可行
        ]

        logger.info(f"Starting llama-server: {' '.join(str(c) for c in cmd)}")
        self._start_time = time.time()

        try:
            self._process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, 'CREATE_NO_WINDOW') else 0,
            )
        except Exception as e:
            logger.error(f"Failed to start llama-server: {e}")
            return False

        # Wait for server to be ready
        start = time.time()
        while time.time() - start < timeout:
            if self._check_health():
                self._ready = True
                elapsed = time.time() - self._start_time
                logger.info(f"llama-server ready in {elapsed:.1f}s on port {self.port}")
                return True
            time.sleep(1)

        logger.error(f"llama-server failed to become ready within {timeout}s")
        self.stop()
        return False

    def stop(self):
        """Gracefully stop llama-server."""
        self._ready = False
        if self._process:
            logger.info("Stopping llama-server...")
            try:
                self._process.terminate()
                self._process.wait(timeout=10)
            except Exception:
                try:
                    self._process.kill()
                except Exception as e:
                    logger.debug(f"操作失败: {e}")
            self._process = None
            logger.info("llama-server stopped")

    # ══════════════════════════════════════════════
    # Health Check
    # ══════════════════════════════════════════════

    def _check_health(self) -> bool:
        """Ping the server health endpoint."""
        try:
            req = urllib.request.Request(f"{self.server_url}/health", method="GET")
            with urllib.request.urlopen(req, timeout=2) as resp:
                return resp.status == 200
        except Exception:
            return False

    def status(self) -> Dict[str, Any]:
        """Get server status."""
        return {
            "ready": self._ready,
            "model": self.model_name,
            "port": self.port,
            "uptime": round(time.time() - self._start_time) if self._start_time else 0,
            "requests": self.total_requests,
            "tokens": self.total_tokens,
            "running": self._process is not None and self._process.poll() is None,
        }

    # ══════════════════════════════════════════════
    # Chat / Completion (OpenAI-compatible API)
    # ══════════════════════════════════════════════

    def chat(self, messages: List[Dict[str, str]],
             temperature: float = 0.7,
             max_tokens: int = 2048,
             timeout: float = 60.0) -> str:
        """
        Send a chat completion request to llama-server.

        Args:
            messages: [{"role": "system"|"user"|"assistant", "content": "..."}]
            temperature: 0.0-1.0, higher = more creative
            max_tokens: max tokens to generate
            timeout: request timeout in seconds

        Returns:
            Generated text response
        """
        if not self._ready:
            return "[LocalLLM not ready]"

        payload = {
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": False,
        }

        data = json.dumps(payload).encode()
        req = urllib.request.Request(
            f"{self.server_url}/v1/chat/completions",
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        try:
            t0 = time.time()
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                result = json.loads(resp.read().decode())
            elapsed = time.time() - t0

            content = result.get("choices", [{}])[0].get("message", {}).get("content", "")
            tokens_used = result.get("usage", {}).get("total_tokens", 0)

            self.total_requests += 1
            self.total_tokens += tokens_used
            self.last_response_time = elapsed

            logger.debug(f"LLM chat: {tokens_used} tokens in {elapsed:.2f}s")
            return content

        except urllib.error.HTTPError as e:
            logger.error(f"LLM HTTP error: {e.code} {e.reason}")
            return f"[LLM error: {e.code}]"
        except urllib.error.URLError as e:
            logger.error(f"LLM connection error: {e.reason}")
            return "[LLM not available — is llama-server running?]"
        except json.JSONDecodeError as e:
            logger.error(f"LLM parse error: {e}")
            return "[LLM response parse error]"
        except Exception as e:
            logger.error(f"LLM unexpected error: {e}")
            return "[LLM error]"

    # ══════════════════════════════════════════════
    # Completion (simple prompt → text)
    # ══════════════════════════════════════════════

    def complete(self, prompt: str, temperature: float = 0.7,
                 max_tokens: int = 2048) -> str:
        """Simple prompt completion via chat API."""
        return self.chat([
            {"role": "user", "content": prompt}
        ], temperature=temperature, max_tokens=max_tokens)
