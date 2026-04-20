import asyncio
import base64
import json
import logging
import os
import shutil
import subprocess
import tempfile
import threading
import time
from pathlib import Path
import httpx
import websockets

logger = logging.getLogger(__name__)

REMOTE_DEBUGGING_PORT = int(os.getenv("UNITY_BROADCAST_DEBUG_PORT", "9223"))

def _find_edge_executable() -> str | None:
    candidates = [
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    ]
    for candidate in candidates:
        if Path(candidate).exists():
            return candidate
    return None

class UnityBroadcastMirror:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._condition = threading.Condition(self._lock)
        self._thread: threading.Thread | None = None
        self._running = False
        self._stop_requested = False
        self._edge_process: subprocess.Popen | None = None
        self._source_url: str | None = None
        self._latest_frame: bytes | None = None
        self._latest_frame_id = 0
        self._last_error = ""
        self._last_frame_at = 0.0
        self._user_data_dir = Path(tempfile.gettempdir()) / "stoneodds-unity-broadcast"

    def ensure_started(self, source_url: str) -> None:
        with self._lock:
            self._source_url = source_url
            if self._thread and self._thread.is_alive():
                return
            self._stop_requested = False
            self._thread = threading.Thread(
                target=self._thread_main,
                name="unity-broadcast-mirror",
                daemon=True,
            )
            self._thread.start()

    def latest_frame(self) -> tuple[bytes | None, int, float, str]:
        with self._lock:
            return self._latest_frame, self._latest_frame_id, self._last_frame_at, self._last_error

    def wait_for_next_frame(self, last_seen_id: int, timeout: float = 5.0) -> tuple[bytes | None, int]:
        deadline = time.time() + timeout
        with self._condition:
            while self._latest_frame_id <= last_seen_id and time.time() < deadline:
                remaining = deadline - time.time()
                if remaining <= 0:
                    break
                self._condition.wait(timeout=remaining)
            return self._latest_frame, self._latest_frame_id

    def status(self) -> dict:
        with self._lock:
            return {
                "running": self._running,
                "has_frame": self._latest_frame is not None,
                "frame_id": self._latest_frame_id,
                "last_frame_at": self._last_frame_at,
                "last_error": self._last_error,
            }

    def _thread_main(self) -> None:
        self._running = True
        try:
            asyncio.run(self._capture_loop())
        except Exception as e:
            logger.exception("Broadcast capture loop crashed")
        finally:
            self._running = False
            self._shutdown_edge()

    async def _capture_loop(self) -> None:
        # Reuse HTTP client for DevTools API calls (connection pooling)
        async with httpx.AsyncClient(timeout=5.0) as http_client:
            while not self._stop_requested:
                try:
                    await self._ensure_edge_running()
                    websocket_url = await self._resolve_page_websocket(http_client)
                    if not websocket_url:
                        raise RuntimeError("Could not find Edge DevTools page websocket")
                    await self._capture_frames(websocket_url)
                except Exception as exc:
                    with self._lock:
                        self._last_error = str(exc)
                    logger.warning(f"Broadcast capture error: {exc}")
                    await asyncio.sleep(1.0)

    async def _ensure_edge_running(self) -> None:
        if self._edge_process and self._edge_process.poll() is None:
            return

        edge_executable = _find_edge_executable()
        if not edge_executable:
            raise RuntimeError("Microsoft Edge or Chrome is required for Unity broadcast mirroring")

        self._shutdown_edge()
        self._user_data_dir.mkdir(parents=True, exist_ok=True)
        source_url = self._source_url or "http://127.0.0.1:8001/broadcast/source/"
        args = [
            edge_executable,
            "--headless=new",
            "--disable-gpu",
            "--mute-audio",
            "--hide-scrollbars",
            "--autoplay-policy=no-user-gesture-required",
            f"--remote-debugging-port={REMOTE_DEBUGGING_PORT}",
            f"--user-data-dir={self._user_data_dir}",
            "--window-size=1280,720",
            source_url,
        ]
        self._edge_process = subprocess.Popen(
            args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
        )
        await asyncio.sleep(2.5)

    async def _resolve_page_websocket(self, client: httpx.AsyncClient) -> str | None:
        url = f"http://127.0.0.1:{REMOTE_DEBUGGING_PORT}/json/list"
        for _ in range(20):
            try:
                response = await client.get(url)
                response.raise_for_status()
                pages = response.json()
                for page in pages:
                    if page.get("type") == "page" and page.get("webSocketDebuggerUrl"):
                        return page["webSocketDebuggerUrl"]
            except Exception:
                pass
            await asyncio.sleep(0.5)
        return None

    async def _capture_frames(self, websocket_url: str) -> None:
        async with websockets.connect(websocket_url, max_size=None) as websocket:
            client = _DevToolsClient(websocket)
            await client.send("Page.enable")
            await client.send("Runtime.enable")
            await client.send("Emulation.setDeviceMetricsOverride", {
                "width": 1280, "height": 720, "deviceScaleFactor": 1, "mobile": False
            })
            await client.send("Page.navigate", {"url": self._source_url or "http://127.0.0.1:8001/broadcast/source/"})
            await asyncio.sleep(4.0)
            await client.send("Page.startScreencast", {
                "format": "jpeg", "quality": 78, "maxWidth": 1280, "maxHeight": 720, "everyNthFrame": 1
            })

            while not self._stop_requested:
                message = await client.next_event("Page.screencastFrame")
                session_id = message.get("params", {}).get("sessionId")
                data = message.get("params", {}).get("data")
                if session_id is not None:
                    await client.send("Page.screencastFrameAck", {"sessionId": session_id})
                if not data:
                    continue
                frame = base64.b64decode(data)
                with self._condition:
                    self._latest_frame = frame
                    self._latest_frame_id += 1
                    self._last_frame_at = time.time()
                    self._last_error = ""
                    self._condition.notify_all()

    def _shutdown_edge(self) -> None:
        process = self._edge_process
        self._edge_process = None
        if process and process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                process.kill()
        if self._user_data_dir.exists():
            shutil.rmtree(self._user_data_dir, ignore_errors=True)


class _DevToolsClient:
    def __init__(self, websocket) -> None:
        self.websocket = websocket
        self._message_id = 0
        self._pending_events: list[dict] = []

    async def _recv_message(self) -> dict:
        raw = await self.websocket.recv()
        return json.loads(raw)

    async def send(self, method: str, params: dict | None = None) -> dict:
        self._message_id += 1
        message_id = self._message_id
        payload = {"id": message_id, "method": method}
        if params:
            payload["params"] = params
        await self.websocket.send(json.dumps(payload))
        while True:
            message = await self._recv_message()
            if "id" not in message:
                self._pending_events.append(message)
                continue
            if message.get("id") != message_id:
                continue
            if "error" in message:
                raise RuntimeError(f"DevTools error for {method}: {message['error']}")
            return message.get("result", {})

    async def next_event(self, method: str) -> dict:
        while True:
            for index, message in enumerate(self._pending_events):
                if message.get("method") == method:
                    return self._pending_events.pop(index)
            message = await self._recv_message()
            if message.get("method") == method:
                return message
            if "id" not in message:
                self._pending_events.append(message)

# Singleton instance for app-wide access
broadcast_mirror = UnityBroadcastMirror()