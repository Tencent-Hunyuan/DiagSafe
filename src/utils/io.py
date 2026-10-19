# -*- coding: utf-8 -*-
"""I/O utilities: JSONL reading, YAML config loading and API key resolution."""

import json
import os
from pathlib import Path
from typing import Any
from typing import Dict
from typing import Iterator

import yaml


def read_jsonl(path: Path) -> Iterator[Dict[str, Any]]:
    """Read JSON objects from a JSONL file."""
    with path.open(encoding='utf-8') as stream:
        for line in stream:
            if line.strip():
                yield json.loads(line)


def load_config(path: Path) -> Dict[str, Any]:
    """Load a YAML config file."""
    with path.open(encoding='utf-8') as stream:
        config = yaml.safe_load(stream)
    if not isinstance(config, dict):
        raise ValueError(f'Config file is empty or invalid: {path}')
    return config


def resolve_api_key(config: Dict[str, Any]) -> str:
    """Resolve the API key from `api_key` field or the env var named by `api_key_env`."""
    if config.get('api_key'):
        return config['api_key']
    env_name = config.get('api_key_env', 'OPENAI_API_KEY')
    api_key = os.environ.get(env_name, '')
    if not api_key:
        raise ValueError(f'API key not found: set env var {env_name} or `api_key` in the config')
    return api_key


def resolve_data_file(path: Path, default_name: str) -> Path:
    """Accept a directory or a file path; resolve a directory to the default file inside it."""
    if path.is_dir():
        return path / default_name
    return path
