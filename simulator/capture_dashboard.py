"""Capture screenshots of the Streamlit dashboard for the report (needs Microsoft Edge or Chrome).

Usage:  python simulator/capture_dashboard.py
Starts the dashboard on a free port, drives a headless browser over the DevTools protocol, waits until
each tab has finished rendering and writes outputs/figures/fig_dashboard_*.png.
"""
from __future__ import annotations

import asyncio
import base64
import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import urllib.parse
import urllib.request
from pathlib import Path

from tornado.websocket import websocket_connect

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
FIG = ROOT / "outputs" / "figures"

WIDTH, SCALE = 1600, 1.5
SHOTS = [  # (tab, file, viewport height in CSS px, crop to the tab panel)
    ("Telemetry", "fig_dashboard_telemetry.png", 1000, False),
    ("Energy flow", "fig_dashboard_energy.png", 1500, True),
    ("Track map", "fig_dashboard_map.png", 1500, True),
    ("Braking zones", "fig_dashboard_zones.png", 1500, True),
    ("Strategy", "fig_dashboard_strategy.png", 1400, True),
    ("Utilisation", "fig_dashboard_utilisation.png", 1400, True),
]

PANEL_JS = """(() => {
  const r = document.querySelector('[role="tabpanel"]:not([hidden])').getBoundingClientRect();
  return JSON.stringify({x: r.left, y: r.top, w: r.width, h: r.height});
})()"""

READY_JS = """(() => {
  const metrics = document.querySelectorAll('[data-testid="stMetricValue"]').length;
  const panel = document.querySelector('[role="tabpanel"]:not([hidden])');
  const plots = panel ? panel.querySelectorAll('.js-plotly-plot .main-svg').length : 0;
  const running = !!document.querySelector('[data-testid="stStatusWidget"] img, [data-testid="stStatusWidget"] svg');
  return JSON.stringify({metrics, plots, running, size: document.body.innerHTML.length});
})()"""


def find_browser() -> str | None:
    candidates = [
        Path(os.environ.get("ProgramFiles(x86)", "")) / "Microsoft/Edge/Application/msedge.exe",
        Path(os.environ.get("ProgramFiles", "")) / "Microsoft/Edge/Application/msedge.exe",
        Path(os.environ.get("ProgramFiles", "")) / "Google/Chrome/Application/chrome.exe",
        Path(os.environ.get("LOCALAPPDATA", "")) / "Google/Chrome/Application/chrome.exe",
    ]
    for c in candidates:
        if c.is_file():
            return str(c)
    return shutil.which("msedge") or shutil.which("chrome")


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def get_json(url: str, timeout: float = 60.0):
    t0 = time.time()
    while True:
        try:
            with urllib.request.urlopen(url, timeout=2) as r:
                return json.loads(r.read().decode() or "null") if r.status == 200 else None
        except (OSError, ValueError):
            if time.time() - t0 > timeout:
                return None
            time.sleep(0.5)


class DevTools:
    def __init__(self, ws):
        self.ws, self.next_id = ws, 0

    @classmethod
    async def connect(cls, url: str) -> "DevTools":
        return cls(await websocket_connect(url, max_message_size=512 * 1024 * 1024))

    async def call(self, method: str, **params):
        self.next_id += 1
        mid = self.next_id
        await self.ws.write_message(json.dumps({"id": mid, "method": method, "params": params}))
        while True:
            msg = await self.ws.read_message()
            if msg is None:
                raise RuntimeError("DevTools connection closed")
            data = json.loads(msg)
            if data.get("id") == mid:
                if "error" in data:
                    raise RuntimeError(f"{method}: {data['error']}")
                return data.get("result", {})

    async def wait_rendered(self, timeout: float = 240.0) -> bool:
        t0, last, stable = time.time(), None, 0
        while time.time() - t0 < timeout:
            res = await self.call("Runtime.evaluate", expression=READY_JS, returnByValue=True)
            state = json.loads(res["result"]["value"])
            done = state["metrics"] >= 7 and state["plots"] >= 1 and not state["running"]
            stable = stable + 1 if done and last == state["size"] else 0
            if stable >= 3:
                return True
            last = state["size"]
            await asyncio.sleep(1.0)
        return False


async def capture(debug_port: int, app_port: int) -> None:
    targets = get_json(f"http://127.0.0.1:{debug_port}/json/list") or []
    page = next(t for t in targets if t.get("type") == "page")
    tab = await DevTools.connect(page["webSocketDebuggerUrl"])
    for name, file, height, crop in SHOTS:
        await tab.call("Emulation.setDeviceMetricsOverride", width=WIDTH, height=height,
                       deviceScaleFactor=SCALE, mobile=False)
        await tab.call("Page.navigate", url=f"http://127.0.0.1:{app_port}/?tab={urllib.parse.quote(name)}")
        await asyncio.sleep(2.0)
        ok = await tab.wait_rendered()
        await asyncio.sleep(1.5)
        params = {"format": "png"}
        if crop:
            res = await tab.call("Runtime.evaluate", expression=PANEL_JS, returnByValue=True)
            r = json.loads(res["result"]["value"])
            pad = 12
            params["clip"] = {"x": max(0.0, r["x"] - pad), "y": r["y"] + 2, "width": r["w"] + 2 * pad,
                              "height": min(r["h"] + pad, height - r["y"] - 2), "scale": 1}
        shot = await tab.call("Page.captureScreenshot", **params)
        (FIG / file).write_bytes(base64.b64decode(shot["data"]))
        print(f"  {file}: {'ok' if ok else 'saved, but the page may not have finished rendering'}")
    version = get_json(f"http://127.0.0.1:{debug_port}/json/version") or {}
    if version.get("webSocketDebuggerUrl"):
        browser = await DevTools.connect(version["webSocketDebuggerUrl"])
        try:
            await browser.call("Browser.close")
        except RuntimeError:
            pass


def main() -> int:
    exe = find_browser()
    if not exe:
        print("No Edge/Chrome found - dashboard screenshots skipped.")
        return 0
    FIG.mkdir(parents=True, exist_ok=True)
    app_port, debug_port = free_port(), free_port()
    server = subprocess.Popen(
        [sys.executable, "-m", "streamlit", "run", str(HERE / "app.py"), "--server.headless", "true",
         "--server.port", str(app_port), "--browser.gatherUsageStats", "false"],
        cwd=ROOT, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    profile = tempfile.mkdtemp(prefix="dash_shot_")
    browser = None
    try:
        if get_json(f"http://127.0.0.1:{app_port}/_stcore/health") is None and server.poll() is not None:
            print("Streamlit did not start - screenshots skipped.")
            return 1
        browser = subprocess.Popen(
            [exe, "--headless=new", "--disable-gpu", "--hide-scrollbars", "--no-first-run",
             f"--remote-debugging-port={debug_port}", "--remote-allow-origins=*",
             f"--user-data-dir={profile}", "about:blank"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        if get_json(f"http://127.0.0.1:{debug_port}/json/version") is None:
            print("Browser DevTools endpoint did not come up - screenshots skipped.")
            return 1
        asyncio.run(capture(debug_port, app_port))
    finally:
        for proc in (browser, server):
            if proc is not None and proc.poll() is None:
                proc.terminate()
                try:
                    proc.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    proc.kill()
        shutil.rmtree(profile, ignore_errors=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
