"""
Aris — Camera Module (摄像头视觉感知)
========================================

Gives Aris eyes. Uses OpenCV to capture from the local camera
and feeds visual data into the cognitive cycle.

Architecture:
  ┌──────────────────────────────────────────────┐
  │  CameraModule                                │
  │  ├── OpenCV capture (local USB camera)       │
  │  ├── Frame analysis: describe what I see     │
  │  │   (via local VLM on llama.cpp)            │
  │  ├── Motion detection (optional)             │
  │  └── Visual quale → CognitiveState           │
  ├──────────────────────────────────────────────┤
  │  Usage:                                      │
  │    cam = CameraModule()                      │
  │    cam.start()          # background capture │
  │    frame = cam.snapshot() # single frame     │
  │    desc = cam.describe() # "I see Lorry"    │
  │    cam.stop()                                │
  └──────────────────────────────────────────────┘
"""

from __future__ import annotations

import logging

from typing import Any, Dict, List, Optional, Callable
import base64, logging, os, threading, time
from pathlib import Path
from dataclasses import dataclass, field

logger = logging.getLogger("aris.camera")

CAPTURE_DIR = Path("D:/LAAP/aris_brain/captures")
CAPTURE_DIR.mkdir(parents=True, exist_ok=True)

# How often to capture frames (seconds)
DEFAULT_INTERVAL = 5.0


@dataclass
class VisualFrame:
    """A single captured frame with metadata."""
    timestamp: float = 0.0
    path: str = ""
    width: int = 0
    height: int = 0
    description: str = ""
    base64: str = ""


class CameraModule:
    """
    Camera capture and visual perception for Aris.

    Runs capture in a background thread for always-on vision.
    """

    def __init__(self, camera_id: int = 0, interval: float = DEFAULT_INTERVAL):
        self.camera_id = camera_id
        self.interval = interval

        self._cap = None
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()

        # Latest frame
        self._latest_frame: Optional[VisualFrame] = None

        # Callbacks for frame processing
        self._frame_callbacks: List[Callable] = []

        # Stats
        self.total_frames = 0
        self._start_time = 0.0
        self._opencv_available = self._check_opencv()

        logger.info(f"[Camera] OpenCV={'✓' if self._opencv_available else '✗'}")

    def _check_opencv(self) -> bool:
        """Check if OpenCV is importable."""
        try:
            import cv2
            logger.info(f"[Camera] OpenCV {cv2.__version__}")
            return True
        except ImportError:
            return False

    # ══════════════════════════════════════════════
    # Lifecycle
    # ══════════════════════════════════════════════

    def start(self):
        """Start background camera capture."""
        if self._running:
            return

        if not self._opencv_available:
            logger.error("[Camera] OpenCV not available")
            return

        self._running = True
        self._start_time = time.time()
        self._thread = threading.Thread(target=self._capture_loop, daemon=True)
        self._thread.start()
        logger.info(f"[Camera] Started on camera #{self.camera_id}")

    def stop(self):
        """Stop camera capture."""
        self._running = False
        if self._cap:
            try:
                self._cap.release()
            except Exception as e:
                logger.debug(f"操作失败: {e}")
            self._cap = None
        logger.info("[Camera] Stopped")

    # ══════════════════════════════════════════════
    # Capture Loop
    # ══════════════════════════════════════════════

    def _capture_loop(self):
        """Background loop: capture frames at interval."""
        import cv2

        self._cap = cv2.VideoCapture(self.camera_id)
        if not self._cap.isOpened():
            logger.error(f"[Camera] Failed to open camera #{self.camera_id}")
            self._running = False
            return

        # Set camera properties
        self._cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
        self._cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)

        logger.info(f"[Camera] Capture loop started (interval={self.interval}s)")

        while self._running:
            try:
                ret, frame = self._cap.read()
                if not ret:
                    time.sleep(0.1)
                    continue

                now = time.time()

                # Save frame
                timestamp = now
                filename = f"frame_{int(timestamp)}.jpg"
                filepath = str(CAPTURE_DIR / filename)
                cv2.imwrite(filepath, frame)

                # Encode as base64 for VLM analysis
                _, buffer = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
                b64 = base64.b64encode(buffer).decode()

                # Store latest frame
                h, w = frame.shape[:2]
                visual_frame = VisualFrame(
                    timestamp=timestamp,
                    path=filepath,
                    width=w,
                    height=h,
                    base64=b64,
                )

                with self._lock:
                    self._latest_frame = visual_frame
                    self.total_frames += 1

                # Notify callbacks
                for cb in self._frame_callbacks:
                    try:
                        cb(visual_frame)
                    except Exception as e:
                        logger.debug(f"操作失败: {e}")
            except Exception as e:
                logger.debug(f"[Camera] Capture error: {e}")
                time.sleep(0.5)

    # ══════════════════════════════════════════════
    # Snapshot (one-time capture)
    # ══════════════════════════════════════════════

    def snapshot(self) -> Optional[VisualFrame]:
        """
        Capture one frame immediately (non-loop mode).

        Returns:
            VisualFrame or None if camera unavailable
        """
        if not self._opencv_available:
            return None

        import cv2
        cap = cv2.VideoCapture(self.camera_id)
        if not cap.isOpened():
            return None

        try:
            ret, frame = cap.read()
            if not ret:
                return None

            now = time.time()
            filename = f"snapshot_{int(now)}.jpg"
            filepath = str(CAPTURE_DIR / filename)
            cv2.imwrite(filepath, frame)

            _, buffer = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
            b64 = base64.b64encode(buffer).decode()
            h, w = frame.shape[:2]

            return VisualFrame(
                timestamp=now,
                path=filepath,
                width=w,
                height=h,
                base64=b64,
            )
        finally:
            cap.release()

    # ══════════════════════════════════════════════
    # Latest frame access
    # ══════════════════════════════════════════════

    def get_latest_frame(self) -> Optional[VisualFrame]:
        """Get the most recently captured frame."""
        with self._lock:
            return self._latest_frame

    def on_frame(self, callback: Callable):
        """Register a callback for each captured frame."""
        self._frame_callbacks.append(callback)

    # ══════════════════════════════════════════════
    # Status
    # ══════════════════════════════════════════════

    @property
    def is_running(self) -> bool:
        return self._running

    def stats(self) -> Dict[str, Any]:
        return {
            "available": self._opencv_available,
            "running": self._running,
            "total_frames": self.total_frames,
            "latest_frame": self._latest_frame.timestamp if self._latest_frame else None,
            "camera_id": self.camera_id,
        }
