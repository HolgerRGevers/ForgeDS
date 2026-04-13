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
    handle_export_api,
    handle_generate_api_code,
    handle_get_api_list,
    handle_get_schema,
    handle_get_status,
    handle_inspect_element,
    handle_lint_check,
    handle_mock_upload,
    handle_parse_ds,
    handle_read_file,
    handle_run_validation,
    handle_search_files,
    handle_write_file,
)

HOST = "localhost"
PORT = 9876

# Origins allowed to connect via WebSocket.  Restricting this prevents
# cross-site WebSocket hijacking (CSWSH) from arbitrary websites.
_ALLOWED_WS_ORIGINS = [
    "http://localhost:5173",    # Vite dev server
    "http://localhost:4173",    # Vite preview
    "http://127.0.0.1:5173",
    "http://127.0.0.1:4173",
]

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
        if msg_type == "lint_check":
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

        elif msg_type == "write_file":
            result = await handle_write_file(data)
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

        elif msg_type == "generate_api_code":
            result = await handle_generate_api_code(data)
            await _send_json(ws, {"id": msg_id, "type": "response", "data": result})

        elif msg_type == "get_api_list":
            result = await handle_get_api_list(data)
            await _send_json(ws, {"id": msg_id, "type": "response", "data": result})

        elif msg_type == "export_api":
            result = await handle_export_api(data)
            await _send_json(ws, {"id": msg_id, "type": "response", "data": result})

        elif msg_type == "search_files":
            result = await handle_search_files(data)
            await _send_json(ws, {"id": msg_id, "type": "response", "data": result})

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
        origins=_ALLOWED_WS_ORIGINS,
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
