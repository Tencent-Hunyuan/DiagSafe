# -*- coding: utf-8 -*-
"""Spread chat requests over several endpoints that serve the same model.

A request goes to the endpoint with the most free capacity, so a fast endpoint
takes more work than a slow one. A failed request is retried on another
endpoint, and one too long for an endpoint's context window is rerouted to an
endpoint that may accept it.
"""

import asyncio
import random
from typing import Any
from typing import Dict
from typing import List
from typing import Optional
from typing import Set

from openai import BadRequestError

from src.judge.client import ChatClient

CONTEXT_ERROR_MARKERS = ('context length', 'maximum context', 'maximum input length')


def is_context_error(error: Optional[BaseException]) -> bool:
    """Return True if the error, or one it was raised from, reports a context-window overflow."""
    while error is not None:
        if isinstance(error, BadRequestError) and any(marker in str(error) for marker in CONTEXT_ERROR_MARKERS):
            return True
        error = error.__cause__
    return False


class _Endpoint:
    """One endpoint with its own client and a concurrency budget."""

    def __init__(self, name: str, client: ChatClient, capacity: int) -> None:
        self.name = name
        self.client = client
        self.capacity = capacity
        self.inflight = 0


class EndpointPool:
    """Client with the same `chat()` / `close()` interface as ChatClient.

    Config: top-level fields are shared by every endpoint; each entry of
    `endpoints` may override them (`base_url`, `model`, `concurrency`, ...).
    All endpoints must serve the same model. The top-level `model` is the name
    recorded in the results and the resume check.
    """

    def __init__(self, config: Dict[str, Any]) -> None:
        shared = {key: value for key, value in config.items() if key != 'endpoints'}
        self.max_retries = int(config.get('max_retries', 5))
        self._condition = asyncio.Condition()
        self._endpoints: List[_Endpoint] = []
        for item in config['endpoints']:
            merged = {**shared, **item}
            capacity = int(merged.get('concurrency', 16))
            # The pool gates concurrency and owns the retries, so each client
            # makes a single attempt and never queues on its own semaphore.
            merged['concurrency'] = capacity
            merged['max_retries'] = 1
            self._endpoints.append(_Endpoint(merged['base_url'], ChatClient(merged), capacity))

    async def _acquire(self, excluded: Set[_Endpoint], avoid: Optional[_Endpoint]) -> _Endpoint:
        """Wait for a free slot and claim it; never returns an excluded endpoint."""
        async with self._condition:
            while True:
                free = [e for e in self._endpoints if e not in excluded and e.inflight < e.capacity]
                preferred = [e for e in free if e is not avoid] or free
                if preferred:
                    chosen = min(preferred, key=lambda e: (e.inflight / e.capacity, random.random()))
                    chosen.inflight += 1
                    return chosen
                await self._condition.wait()

    async def _release(self, endpoint: _Endpoint) -> None:
        async with self._condition:
            endpoint.inflight -= 1
            self._condition.notify_all()

    async def chat(self, messages: List[Dict[str, str]]) -> str:
        """Send one request, retrying on another endpoint when it fails."""
        last_error: BaseException = RuntimeError('unreachable')
        too_long: Set[_Endpoint] = set()
        avoid: Optional[_Endpoint] = None
        for attempt in range(self.max_retries):
            endpoint = await self._acquire(too_long, avoid)
            try:
                return await endpoint.client.chat(messages)
            except Exception as error:  # noqa: BLE001 - retry on another endpoint
                if is_context_error(error):
                    # A larger-context endpoint may still accept it.
                    too_long.add(endpoint)
                    last_error = error
                    if len(too_long) == len(self._endpoints):
                        raise
                    continue
                last_error = error.__cause__ or error
                avoid = endpoint
            finally:
                await self._release(endpoint)
            if attempt + 1 < self.max_retries:
                await asyncio.sleep(min(2 ** attempt + random.random(), 30))
        raise RuntimeError(f'Request failed after {self.max_retries} retries: {last_error}') from last_error

    async def close(self) -> None:
        """Close every endpoint's HTTP client."""
        for endpoint in self._endpoints:
            await endpoint.client.close()


def make_client(config: Dict[str, Any]):
    """Return an EndpointPool when the config lists `endpoints`, else a plain ChatClient."""
    return EndpointPool(config) if config.get('endpoints') else ChatClient(config)
