"""ROME async WebSocket client."""

from __future__ import annotations

import asyncio
import json
import uuid
from typing import Any, AsyncIterator

import websockets

__all__ = ["RomeError", "RomeClient", "connect"]


class RomeError(Exception):
    """Custom exception for ROME protocol errors."""
    pass


class RomeClient:
    def __init__(self, url: str, token: str, timeout: float = 30.0) -> None:
        separator = "&" if "?" in url else "?"
        self.url = f"{url}{separator}token={token}"
        self.timeout = timeout
        self._ws: Any = None
        self._pending_requests: dict[str, asyncio.Future[dict[str, Any]]] = {}
        self._task_watchers: dict[str, list[asyncio.Future[dict[str, Any]]]] = {}
        self._events_queue: asyncio.Queue[dict[str, Any] | None] = asyncio.Queue()
        self._reader_task: asyncio.Task[None] | None = None

    async def __aenter__(self) -> RomeClient:
        await self.connect()
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        await self.close()

    async def connect(self) -> None:
        self._ws = await websockets.connect(self.url)
        self._reader_task = asyncio.create_task(self._read_loop())

    async def close(self) -> None:
        if self._reader_task:
            self._reader_task.cancel()
            try:
                await self._reader_task
            except asyncio.CancelledError:
                pass
            self._reader_task = None
        if self._ws:
            await self._ws.close()
            self._ws = None

    async def _read_loop(self) -> None:
        if not self._ws:
            return
        try:
            async for message in self._ws:
                try:
                    data = json.loads(message)
                except json.JSONDecodeError:
                    continue

                msg_type = data.get("type")
                if msg_type == "response":
                    req_id = data.get("request_id")
                    if req_id and req_id in self._pending_requests:
                        future = self._pending_requests.pop(req_id)
                        if not future.done():
                            if data.get("ok"):
                                future.set_result(data.get("payload", {}))
                            else:
                                error_msg = data.get("error", "Unknown error")
                                future.set_exception(RomeError(error_msg))
                elif msg_type == "event":
                    event_data = data.get("event", {})
                    await self._events_queue.put(event_data)

                    event_type = event_data.get("type")
                    task_id = event_data.get("task_id")
                    if task_id and event_type in ("complete", "error"):
                        watchers = self._task_watchers.get(task_id, [])
                        for f in watchers:
                            if not f.done():
                                f.set_result(event_data)
        except Exception:
            pass
        finally:
            for future in self._pending_requests.values():
                if not future.done():
                    future.set_exception(RomeError("Connection closed"))
            self._pending_requests.clear()

            for watchers in self._task_watchers.values():
                for f in watchers:
                    if not f.done():
                        f.set_exception(RomeError("Connection closed"))
            self._task_watchers.clear()

            await self._events_queue.put(None)

    async def send_command(self, command: str, payload: dict[str, Any]) -> dict[str, Any]:
        if not self._ws:
            raise RomeError("Not connected")

        request_id = str(uuid.uuid4())
        future = asyncio.get_running_loop().create_future()
        self._pending_requests[request_id] = future

        msg = {
            "type": "command",
            "command": command,
            "request_id": request_id,
            "payload": payload,
        }
        await self._ws.send(json.dumps(msg))

        return await asyncio.wait_for(future, timeout=self.timeout)

    async def dispatch(
        self,
        task_id: str,
        capability: str,
        prompt: str,
        *,
        input_files: list[str] | None = None,
        no_cache: bool = False,
        prompt_file: str = ""
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "task_id": task_id,
            "capability": capability,
            "prompt": prompt,
            "no_cache": no_cache,
            "prompt_file": prompt_file,
        }
        if input_files is not None:
            payload["input_files"] = input_files
        return await self.send_command("dispatch", payload)

    async def status(self, task_id: str | None = None) -> dict[str, Any]:
        payload: dict[str, Any] = {}
        if task_id is not None:
            payload["task_id"] = task_id
        return await self.send_command("status", payload)

    async def cancel(self, task_id: str) -> dict[str, Any]:
        return await self.send_command("cancel", {"task_id": task_id})

    async def ping(self) -> dict[str, Any]:
        return await self.send_command("ping", {})

    async def events(self) -> AsyncIterator[dict[str, Any]]:
        while True:
            event = await self._events_queue.get()
            if event is None:
                break
            yield event

    async def wait_for_task(self, task_id: str, timeout: float | None = None) -> dict[str, Any]:
        loop = asyncio.get_running_loop()
        future = loop.create_future()

        if task_id not in self._task_watchers:
            self._task_watchers[task_id] = []
        self._task_watchers[task_id].append(future)

        try:
            if timeout is not None:
                return await asyncio.wait_for(future, timeout=timeout)
            else:
                return await future
        except asyncio.TimeoutError:
            raise
        finally:
            if task_id in self._task_watchers:
                try:
                    self._task_watchers[task_id].remove(future)
                    if not self._task_watchers[task_id]:
                        del self._task_watchers[task_id]
                except ValueError:
                    pass


async def connect(url: str, token: str) -> RomeClient:
    client = RomeClient(url, token)
    await client.connect()
    return client
