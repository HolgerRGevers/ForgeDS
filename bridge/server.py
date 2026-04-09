"""WebSocket bridge server — routes browser SPA messages to ForgeDS CLI tools."""

from __future__ import annotations

import asyncio
import json
import logging
import traceback

import websockets
from websockets.asyncio.server import ServerConnection

from bridge.handlers import (
    handle_ai_chat,
    handle_build_project,
    handle_get_schema,
    handle_get_status,
    handle_inspect_element,
    handle_lint_check,
    handle_mock_upload,
    handle_parse_ds,
    handle_read_file,
    handle_refine_prompt,
    handle_run_validation,
)

HOST = "localhost"
PORT = 9876

logger = logging.getLogger("bridge")


async def _send_json(ws: ServerConnection, payload: dict) -> None:
    """Serialise *payload* and send over *ws*."""
    await ws.send(json.dumps(payload))


async def _handle_message(ws: ServerConnection, raw: str) -> None:
    """Parse a single JSON message and dispatch to the appropriate handler."""
    try:
        msg = json.loads(raw)
    except json.JSONDecodeError:
        await _send_json(ws, {
            "id": None,
            "type": "error",
            "data": {"message": "Invalid JSON"},
        })
        return

    msg_id = msg.get("id")
    msg_type = msg.get("type")
    data = msg.get("data", {})

    try:
        if msg_type == "refine_prompt":
            result = await handle_refine_prompt(data)
            await _send_json(ws, {"id": msg_id, "type": "response", "data": result})

        elif msg_type == "build_project":
            # Streaming: send chunks, then a final stream_end
            async def send_stream(chunk_data: dict) -> None:
                await _send_json(ws, {"id": msg_id, "type": "stream", "data": chunk_data})

            result = await handle_build_project(data, send_stream)
            await _send_json(ws, {"id": msg_id, "type": "stream_end", "data": {"result": result}})

        elif msg_type == "lint_check":
            result = await handle_lint_check(data)
            await _send_json(ws, {"id": msg_id, "type": "response", "data": result})

        elif msg_type == "get_status":
            result = await handle_get_status()
            await _send_json(ws, {"id": msg_id, "type": "response", "data": result})

        elif msg_type == "parse_ds":
            result = await handle_parse_ds(data)
            await _send_json(ws, {"id": msg_id, "type": "response", "data": result})

        elif msg_type == "read_file":
            result = await handle_read_file(data)
            await _send_json(ws, {"id": msg_id, "type": "response", "data": result})

        elif msg_type == "inspect_element":
            result = await handle_inspect_element(data)
            await _send_json(ws, {"id": msg_id, "type": "response", "data": result})

        elif msg_type == "ai_chat":
            result = await handle_ai_chat(data)
            await _send_json(ws, {"id": msg_id, "type": "response", "data": result})

        elif msg_type == "get_schema":
            result = await handle_get_schema(data)
            await _send_json(ws, {"id": msg_id, "type": "response", "data": result})

        elif msg_type == "run_validation":
            result = await handle_run_validation(data)
            await _send_json(ws, {"id": msg_id, "type": "response", "data": result})

        elif msg_type == "mock_upload":
            # Streaming: send chunks, then a final stream_end
            async def send_upload_stream(chunk_data: dict) -> None:
                await _send_json(ws, {"id": msg_id, "type": "stream", "data": chunk_data})

            result = await handle_mock_upload(data, send_upload_stream)
            await _send_json(ws, {"id": msg_id, "type": "stream_end", "data": {"result": result}})

        else:
            await _send_json(ws, {
                "id": msg_id,
                "type": "error",
                "data": {"message": f"Unknown message type: {msg_type}"},
            })

    except Exception:
        tb = traceback.format_exc()
        logger.error("Handler error for %s: %s", msg_type, tb)
        await _send_json(ws, {
            "id": msg_id,
            "type": "error",
            "data": {"message": f"Internal error handling {msg_type}"},
        })


async def _handler(ws: ServerConnection) -> None:
    """Per-connection handler — reads messages until the client disconnects."""
    remote = ws.remote_address
    logger.info("Client connected: %s", remote)
    try:
        async for raw in ws:
            await _handle_message(ws, raw)
    except websockets.ConnectionClosed:
        pass
    finally:
        logger.info("Client disconnected: %s", remote)


async def run_server() -> None:
    """Start the WebSocket server and run forever."""
    logger.info("Starting ForgeDS bridge on ws://%s:%s", HOST, PORT)
    async with websockets.serve(
        _handler,
        HOST,
        PORT,
        origins=None,  # Allow connections from any origin (localhost only)
    ):
        await asyncio.Future()  # run forever


def main() -> None:
    """CLI entry point."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s %(message)s",
    )
    try:
        asyncio.run(run_server())
    except KeyboardInterrupt:
        logger.info("Bridge server stopped.")


if __name__ == "__main__":
    main()
