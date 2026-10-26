# -*- coding: utf-8 -*-
"""Async OpenAI-compatible chat client with concurrency limiting and retries."""

import asyncio
import random
from typing import Any
from typing import Dict
from typing import List

from openai import AsyncOpenAI

from src.utils.io import resolve_api_key

# Message fields the answer can be read from: the final reply, or the reasoning
# trace returned separately by some servers (e.g. vLLM with a reasoning parser).
ANSWER_KEYS = ('content', 'reasoning_content')
DEFAULT_ANSWER_KEY = 'content'


class ChatClient:
    """Thin async wrapper around an OpenAI-compatible /chat/completions endpoint."""

    def __init__(self, config: Dict[str, Any]) -> None:
        self.model = config['model']
        self.temperature = float(config.get('temperature', 0))
        self.max_tokens = int(config.get('max_tokens', 4096))
        self.max_retries = int(config.get('max_retries', 5))
        self._semaphore = asyncio.Semaphore(int(config.get('concurrency', 16)))
        # Optional parameters; sent only when configured (e.g. vLLM's
        # chat_template_kwargs via extra_body).
        self.top_p = config.get('top_p')
        self.extra_body = config.get('extra_body') or None
        self.extra_headers = config.get('extra_headers') or None
        self._client = AsyncOpenAI(
            base_url=config.get('base_url'),
            api_key=resolve_api_key(config),
            timeout=float(config.get('timeout', 120)),
            max_retries=0,
        )
        self.answer_key = config.get('answer_key') or DEFAULT_ANSWER_KEY
        if self.answer_key not in ANSWER_KEYS:
            raise ValueError(f"Unsupported answer_key {self.answer_key!r}; choose one of {', '.join(ANSWER_KEYS)}")

    def _request_options(self) -> Dict[str, Any]:
        """Build the optional request options; empty when nothing is configured."""
        options: Dict[str, Any] = {}
        if self.top_p is not None:
            options['top_p'] = float(self.top_p)
        if self.extra_body:
            options['extra_body'] = self.extra_body
        if self.extra_headers:
            options['extra_headers'] = self.extra_headers
        return options

    async def chat(self, messages: List[Dict[str, str]]) -> str:
        """Send one chat request and return the content; retry with exponential backoff."""
        async with self._semaphore:
            last_error: Exception = RuntimeError('unreachable')
            for attempt in range(self.max_retries):
                try:
                    response = await self._client.chat.completions.create(
                        model=self.model,
                        messages=messages,
                        temperature=self.temperature,
                        max_tokens=self.max_tokens,
                        **self._request_options(),
                    )
                    # Fields outside the OpenAI schema (reasoning_content) are kept
                    # as extra attributes, absent when the server does not send them.
                    content = getattr(response.choices[0].message, self.answer_key, None)
                    if content is None:
                        raise ValueError(f'Response has no {self.answer_key!r} field or it is empty')
                    return content
                except Exception as error:  # noqa: BLE001 - retry any API/network error
                    last_error = error
                    if attempt + 1 < self.max_retries:
                        await asyncio.sleep(min(2 ** attempt + random.random(), 30))
            raise RuntimeError(f'Request failed after {self.max_retries} retries: {last_error}') from last_error

    async def close(self) -> None:
        """Close the underlying HTTP client."""
        await self._client.close()
