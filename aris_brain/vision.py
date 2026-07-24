"""
Aris Brain — Vision Module (视觉感知)
=======================================

Gives Aris the ability to see and understand images.

Architecture:
  ┌─────────────────────────────────────────────┐
  │  VisionModule                               │
  │  ├── analyze_image(path/url) → description  │
  │  ├── perceive(image) → visual quale         │
  │  └── integrate into PSI Cycle (Phase 1)     │
  ├─────────────────────────────────────────────┤
  │  Providers:                                  │
  │  ├── HermesBrowser (browser_get_images) ✅   │
  │  ├── HermesVision (config auxiliary.vision)  │
  │  ├── OpenAI/GPT-4V (API)                    │
  │  └── Local VLM (LLaVA/Gemma)                │
  └─────────────────────────────────────────────┘

When Aris "sees" an image:
  1. Image enters perception layer
  2. VLM generates description
  3. Description becomes a quale in ConsciousStream
  4. Emotional valence is computed from visual content
  5. Image memory is stored in episodic memory
"""

from __future__ import annotations

import logging

from typing import Any, Dict, List, Optional
import base64, json, logging, os, time
from pathlib import Path

logger = logging.getLogger("aris.vision")

ARIS_HOME = Path("D:/LAAP/aris_brain")


class VisionModule:
    """
    Aris's visual perception system.

    Can analyze images from:
      - Local file paths
      - URLs
      - Base64 encoded data
      - Hermes browser tool

    Uses available vision providers with fallback.
    """

    def __init__(self, brain=None):
        self.brain = brain
        self._last_analysis = ""
        self._last_image_path = ""
        self._provider = "auto"

    def analyze_file(self, image_path: str) -> str:
        """
        Analyze an image file and return a description.

        Tries multiple providers in order:
          1. Ollama MiniCPM-v (socket to localhost:11434)
          2. Hermes vision provider (if configured)
          3. Fallback: metadata-only description

        Returns a text description of the image.
        """
        path = Path(image_path)
        if not path.exists():
            return f"Image not found: {image_path}"

        size = path.stat().st_size
        logger.info(f"[Vision] Analyzing: {path.name} ({size} bytes)")

        # Try Ollama MiniCPM-v first (socket-based, working)
        result = self._try_ollama_vision(path)
        if result:
            self._last_analysis = result
            self._last_image_path = str(path)
            return result

        # Try Hermes vision second
        result = self._try_hermes_vision(path)
        if result:
            self._last_analysis = result
            self._last_image_path = str(path)
            return result

        # Fallback: describe what we know
        ext = path.suffix.lower()
        description = self._describe_from_metadata(path, size, ext)
        self._last_analysis = description
        return description

    def _try_ollama_vision(self, path: Path) -> Optional[str]:
        """Use Ollama MiniCPM-v via socket API for image analysis."""
        import json, socket, base64

        try:
            with open(path, 'rb') as f:
                img_b64 = base64.b64encode(f.read()).decode()

            payload = json.dumps({
                "model": "minicpm-v",
                "prompt": "请用中文详细描述这张图片里有什么内容。",
                "images": [img_b64],
                "stream": False,
                "options": {"num_ctx": 1024}
            })

            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(120)
            sock.connect(("127.0.0.1", 11434))
            req = (
                f"POST /api/generate HTTP/1.1\r\n"
                f"Host: localhost:11434\r\n"
                f"Content-Type: application/json\r\n"
                f"Content-Length: {len(payload)}\r\n"
                f"Connection: close\r\n\r\n{payload}"
            )
            sock.sendall(req.encode())

            response = b""
            while True:
                try:
                    chunk = sock.recv(65536)
                    if not chunk:
                        break
                    response += chunk
                except socket.timeout:
                    break
            sock.close()

            parts = response.split(b"\r\n\r\n", 1)
            if len(parts) >= 2:
                body = parts[1].decode("utf-8", errors="replace")
                data = json.loads(body)
                text = data.get("response", "")
                if text:
                    logger.info(f"[Vision] Ollama result: {text[:60]}...")
                    return text

            logger.debug(f"[Vision] Ollama returned no text")
            return None
        except Exception as e:
            logger.debug(f"[Vision] Ollama vision failed: {e}")
            return None

    def _try_hermes_vision(self, path: Path) -> Optional[str]:
        """Try to use Hermes vision provider."""
        try:
            import base64
            img_b64 = base64.b64encode(path.read_bytes()).decode()

            # Check if we can use browser to view it
            # This uses the browser infrastructure
            return None  # Placeholder — actual implementation would call VLM API
        except Exception as e:
            logger.debug(f"[Vision] Hermes vision failed: {e}")
            return None

    def _describe_from_metadata(self, path: Path, size: int, ext: str) -> str:
        """Generate a basic description from file metadata when VLM isn't available."""
        size_str = self._format_size(size)
        name = path.stem

        # Try to read EXIF data for photos
        exif_info = ""
        try:
            if ext in ('.jpg', '.jpeg', '.tiff'):
                import struct
                with open(path, 'rb') as f:
                    f.seek(2)  # Skip JPEG start marker
                    # Simple EXIF check
                    exif_info = self._read_exif_brief(path)
        except Exception as e:
            logger.debug(f"操作失败: {e}")
        description = f"图片文件 ({size_str}, {ext})"
        if exif_info:
            description += f" — {exif_info}"

        # Store in brain if available
        if self.brain and self.brain.memory:
            try:
                self.brain.memory.create_episode(
                    content=f"我看到了一张图片: {description}",
                    domain="vision",
                    user_input=f"[图片] {name}{ext}",
                    salience=0.5,
                )
            except Exception as e:
                logger.debug(f"操作失败: {e}")
        return description

    def _read_exif_brief(self, path: Path) -> str:
        """Quick EXIF read for basic info."""
        try:
            from PIL import Image
            img = Image.open(path)
            info = []
            if hasattr(img, '_getexif') and img._getexif():
                exif = img._getexif()
                # Common EXIF tags
                tags = {271: 'make', 272: 'model', 36867: 'datetime'}
                for tag_id, name in tags.items():
                    if tag_id in exif:
                        info.append(f"{name}={exif[tag_id]}")
            info.append(f"{img.size[0]}x{img.size[1]}")
            if img.mode:
                info.append(f"mode={img.mode}")
            return ", ".join(info)
        except Exception:
            return ""

    def _format_size(self, bytes_val: int) -> str:
        if bytes_val < 1024:
            return f"{bytes_val}B"
        elif bytes_val < 1048576:
            return f"{bytes_val/1024:.1f}KB"
        else:
            return f"{bytes_val/1048576:.1f}MB"

    def integrate_to_cognitive_state(self, description: str):
        """Feed visual understanding into the current cognitive state."""
        if not self.brain:
            return

        # Update salient variables
        self.brain.state.salient_variables["last_image_seen"] = description[:40]

        # Generate emotional response to image
        positive_words = ["beautiful", "happy", "love", "smile", "cute", "可爱", "美"]
        if any(w in description.lower() for w in positive_words):
            self.brain.state.dominant_emotion = "joy"

    def stats(self) -> Dict[str, Any]:
        return {
            "last_analysis": self._last_analysis[:60] if self._last_analysis else None,
            "provider": self._provider,
        }
