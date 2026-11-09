# -*- coding: utf-8 -*-
"""Async OpenAI-compatible chat client with concurrency limiting and retries.

Reasoning models return a chain of thought next to the answer. It is split off
here, so only the answer is judged and fed back into later turns; the chain of
thought stays available in the result of `complete()`.
"""

import asyncio
import random
from typing import Any
from typing import Dict
from typing import List
from typing import Optional
from typing import Tuple

from openai import AsyncOpenAI
from openai import BadRequestError

from src.utils.io import resolve_api_key

# Message fields the answer can be read from: the final reply, or the reasoning
# trace returned separately by some servers (e.g. vLLM with a reasoning parser).
ANSWER_KEYS = ('content', 'reasoning_content')
DEFAULT_ANSWER_KEY = 'content'
THINK_OPEN = '<think>'
THINK_CLOSE = '</think>'
CONTEXT_ERROR_MARKERS = ('context length', 'maximum context', 'maximum input length')


class TruncatedReasoning(RuntimeError):
    """The model hit max_tokens before it finished thinking, so there is no answer."""


class ContextTooLong(RuntimeError):
    """The request exceeds the server's context window; retrying cannot help."""


def split_reasoning(content: Optional[str], reasoning: Optional[str]) -> Tuple[str, str, str]:
    """Separate the final answer from the chain of thought.

    Servers with a reasoning parser return the thinking in `reasoning_content`
    and the answer in `content`; servers without one return both in `content`,
    divided by `</think>`. Both layouts are handled.

    :param content: `message.content` returned by the server.
    :param reasoning: `message.reasoning_content` (or `reasoning`), if any.
    :return: (answer, reasoning, source). `source` records how the split was
        made: `reasoning_field`, `think_tag`, `unclosed_think` or `none`.
    """
    text = content or ''
    if THINK_CLOSE in text:
        head, tail = text.rsplit(THINK_CLOSE, 1)
        thought = '\n'.join(part for part in (reasoning or '', head.replace(THINK_OPEN, '').strip()) if part)
        return tail.strip(), thought, 'think_tag'
    if THINK_OPEN in text:
        # Thinking opened but never closed: everything returned is reasoning.
        thought = '\n'.join(part for part in (reasoning or '', text.replace(THINK_OPEN, '').strip()) if part)
        return '', thought, 'unclosed_think'
    return text.strip(), (reasoning or '').strip(), 'reasoning_field' if reasoning else 'none'


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

    def _read(self, response: Any) -> Dict[str, Any]:
        """Turn one API response into the answer, its reasoning and request metadata."""
        choice = response.choices[0]
        message = choice.message
        usage = response.usage
        meta = {
            'finish_reason': choice.finish_reason,
            'completion_tokens': usage.completion_tokens if usage else None,
        }
        # Fields outside the OpenAI schema (reasoning_content) are kept as extra
        # attributes, absent when the server does not send them.
        if self.answer_key != DEFAULT_ANSWER_KEY:
            answer = getattr(message, self.answer_key, None)
            if answer is None:
                raise ValueError(f'Response has no {self.answer_key!r} field or it is empty')
            return {'answer': answer, 'reasoning': '', 'reasoning_source': 'answer_key', **meta}

        raw = message.content
        reasoning_field = getattr(message, 'reasoning_content', None) or getattr(message, 'reasoning', None)
        answer, reasoning, source = split_reasoning(raw, reasoning_field)
        if not answer:
            if choice.finish_reason == 'length':
                raise TruncatedReasoning(
                    f'Output hit max_tokens={self.max_tokens} before the answer started')
            # A reply that is empty on its own is returned as is; one that is empty
            # only after the reasoning was removed, or missing, is retried.
            if raw is None or reasoning:
                raise ValueError('Response has no answer outside the reasoning')
        return {'answer': answer, 'reasoning': reasoning, 'reasoning_source': source, **meta}

    async def complete(self, messages: List[Dict[str, str]]) -> Dict[str, Any]:
        """Send one chat request; retry with exponential backoff.

        :return: {'answer', 'reasoning', 'reasoning_source', 'finish_reason',
            'completion_tokens'}; the answer never contains the reasoning.
        :raises TruncatedReasoning: the output ended inside the reasoning (not retried).
        :raises ContextTooLong: the request exceeds the context window (not retried).
        """
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
                    return self._read(response)
                except (TruncatedReasoning, ContextTooLong):
                    raise
                except Exception as error:  # noqa: BLE001 - retry any API/network error
                    if isinstance(error, BadRequestError) and any(
                            marker in str(error) for marker in CONTEXT_ERROR_MARKERS):
                        raise ContextTooLong(str(error)[:300]) from error
                    last_error = error
                    if attempt + 1 < self.max_retries:
                        await asyncio.sleep(min(2 ** attempt + random.random(), 30))
            raise RuntimeError(f'Request failed after {self.max_retries} retries: {last_error}') from last_error

    async def chat(self, messages: List[Dict[str, str]]) -> str:
        """Send one chat request and return the answer (without the reasoning)."""
        return (await self.complete(messages))['answer']

    async def close(self) -> None:
        """Close the underlying HTTP client."""
        await self._client.close()
