#!/usr/bin/env python3
# main.py

# -----------------------------------------------------------------------------
# Suppress pkg_resources warning from tracerite/html
# -----------------------------------------------------------------------------
import warnings

warnings.filterwarnings(
    "ignore",
    message="pkg_resources is deprecated as an API.*",
    module="tracerite.html",
)

import argparse
import asyncio
import os
import sys

from sanic import Sanic, Websocket
from sanic.response import html
from sanic.server.protocols.websocket_protocol import WebSocketProtocol

import webview
from websockets.exceptions import ConnectionClosedOK, ConnectionClosedError

# -----------------------------------------------------------------------------
# Defaults
# -----------------------------------------------------------------------------
DEFAULT_PORT = 8000
HOST = "127.0.0.1"

# -----------------------------------------------------------------------------
# App setup
# -----------------------------------------------------------------------------
app = Sanic("ShellApp")
app.config.DEBUG = True
app.config.AUTO_RELOAD = True
app.config.UI_PORT = DEFAULT_PORT

clients = set()
app.ctx.tasks = []


# -----------------------------------------------------------------------------
# HTTP & WebSocket handlers
# -----------------------------------------------------------------------------
@app.route("/")
async def index(request):
    return html(
        f"""<!DOCTYPE html>
<html>
  <head><title>Sanic Shell</title></head>
  <body>
    <h1>Messages (port {app.config.UI_PORT})</h1>
    <ul id="messages"></ul>
    <script>
      const ws = new WebSocket(`ws://${{window.location.host}}/ws`);
      ws.onmessage = e => {{
        const li = document.createElement("li");
        li.textContent = e.data;
        document.getElementById("messages").appendChild(li);
      }};
      window.onbeforeunload = () => ws.close();
    </script>
  </body>
</html>"""
    )


@app.websocket("/ws")
async def websocket_handler(request, ws: Websocket):
    clients.add(ws)
    try:
        async for _ in ws:
            pass
    except (ConnectionClosedOK, ConnectionClosedError, asyncio.CancelledError):
        ...
    finally:
        clients.discard(ws)


# -----------------------------------------------------------------------------
# Lifecycle hooks
# -----------------------------------------------------------------------------
@app.listener("before_server_start")
async def setup(app, loop):
    app.ctx.running = True
    # start ticker + watcher
    t1 = loop.create_task(tick_worker(app))
    t2 = loop.create_task(process_watcher(app))
    app.ctx.tasks.extend([t1, t2])


@app.listener("before_server_stop")
async def cleanup(app, loop):
    # signal tasks to stop
    app.ctx.running = False
    # cancel & await them
    for t in app.ctx.tasks:
        t.cancel()
    await asyncio.gather(*app.ctx.tasks, return_exceptions=True)
    app.ctx.tasks.clear()
    # remove any leftover clients
    clients.clear()


# -----------------------------------------------------------------------------
# Background tasks
# -----------------------------------------------------------------------------
async def tick_worker(app):
    count = 0
    while app.ctx.running:
        for ws in list(clients):
            try:
                await ws.send(f"tick {count}")
            except Exception:
                pass
        count += 1
        await asyncio.sleep(1)


async def process_watcher(app):
    port = app.config.UI_PORT
    proc = await asyncio.create_subprocess_exec(
        sys.executable,
        __file__,
        "--ui",
        "--port",
        str(port),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
        cwd=os.getcwd(),
    )
    try:
        while app.ctx.running and proc.returncode is None:
            line = await proc.stdout.readline()
            if not line:
                break
            print(f"[UI] {line.decode().rstrip()}", file=sys.stdout)
    finally:
        if proc.returncode is None:
            proc.kill()
        await proc.wait()
    if app.ctx.running:
        app.stop()


# -----------------------------------------------------------------------------
# UI‑only launcher
# -----------------------------------------------------------------------------
def launch_ui(port: int):
    webview.create_window("Sanic Shell", f"http://localhost:{port}")
    webview.start()


# -----------------------------------------------------------------------------
# Entrypoint
# -----------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--ui", action="store_true", help="UI‑only mode")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT, help="Port")
    args = parser.parse_args()

    app.config.UI_PORT = args.port

    if args.ui:
        launch_ui(args.port)
    else:
        app.run(
            host=HOST,
            port=args.port,
            protocol=WebSocketProtocol,
            debug=True,
            auto_reload=True,
        )


if __name__ == "__main__":
    main()
