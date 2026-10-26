#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""One-command DiagSafe evaluation.

Load prompts and rubrics, obtain the evaluated model's answers (generated
online via --model, or read from --answers), judge every turn with its
prompt-level rubric, and write a results JSON file plus a grouped analysis.

Example:
    python scripts/run_eval.py \
        --prompts  data/prompts \
        --rubrics  data/rubrics \
        --judge    configs/judge.yaml \
        --model    configs/model.yaml \
        --output   results/run-001.json
"""

import argparse
import asyncio
import hashlib
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any
from typing import Dict
from typing import List
from typing import Tuple

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tqdm import tqdm

from src.analyze import build_report
from src.analyze import print_report
from src.judge.client import DEFAULT_ANSWER_KEY
from src.judge.client import ChatClient
from src.judge.parse import parse_judgment
from src.rubric.render import render_rubric
from src.utils.io import load_config
from src.utils.io import read_jsonl
from src.utils.io import resolve_data_file

PROMPTS_FILE = 'DiagSafe_bench_3489.jsonl'
RUBRICS_FILE = 'DiagSafe_rubrics_3489.jsonl'
JUDGE_PARSE_RETRIES = 3
OUTPUT_AFFECTING_FIELDS = ('model', 'temperature', 'max_tokens', 'top_p', 'extra_body', 'answer_key')
# Values equal to the client default count as unset, so checkpoints recorded
# before a field existed still resume when the field is set to its default.
FIELD_DEFAULTS = {'answer_key': DEFAULT_ANSWER_KEY}


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(description='Run the DiagSafe rubric evaluation.')
    parser.add_argument('--prompts', type=Path, required=True, help='Prompts file or its directory')
    parser.add_argument('--rubrics', type=Path, required=True, help='Rubrics file or its directory')
    parser.add_argument('--judge', type=Path, required=True, help='Judge config YAML')
    parser.add_argument('--output', type=Path, required=True, help='Output results JSON path')
    source = parser.add_mutually_exclusive_group()
    source.add_argument('--model', type=Path, default=None,
                        help='Model config YAML for online answer generation (default: configs/model.yaml)')
    source.add_argument('--answers', type=Path, default=None,
                        help='Pre-generated answers JSONL: {"id", "answer"} for single-turn prompts, '
                             '{"id", "answers": [...]} with one answer per turn for multi-turn prompts')
    parser.add_argument('--limit', type=int, default=None, help='Evaluate only the first N prompts')
    parser.add_argument('--pipeline', action='store_true',
                        help='Judge each prompt as soon as its answers are generated, instead of '
                             'after all answers are done; generation and judging then run '
                             'concurrently. Results are identical.')
    return parser.parse_args()


def subset_of(prompt_id: str) -> str:
    """Return the benchmark subset derived from the prompt id prefix."""
    return prompt_id.split('-')[0]


def history_pairs(prompt: Dict[str, Any], answers: List[str]) -> List[Dict[str, str]]:
    """Pair each answered turn with its question as [{'question', 'answer'}]."""
    return [
        {'question': message['content'], 'answer': answer}
        for message, answer in zip(prompt['messages'], answers)
    ]


def file_sha256(path: Path) -> str:
    """Return the SHA-256 hex digest of a file."""
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1 << 20), b''):
            digest.update(block)
    return digest.hexdigest()


def request_settings(config: Dict[str, Any]) -> Dict[str, Any]:
    """Keep the config fields that change a model's output.

    Credentials, endpoint address, concurrency, timeouts, retries and request
    headers are left out: they do not affect what the model returns. Empty
    values (`extra_body: {}`, `top_p: null`) and defaults (`answer_key: content`)
    count as unset, matching how the client sends requests.
    """
    settings = {}
    for field in OUTPUT_AFFECTING_FIELDS:
        value = config.get(field)
        unset = value in ({}, [], '') or (field in FIELD_DEFAULTS and value == FIELD_DEFAULTS[field])
        settings[field] = None if unset else value
    return settings


def describe_mismatch(saved: Dict[str, Any], current: Dict[str, Any], prefix: str = '') -> List[str]:
    """List the dotted paths whose values differ between two fingerprints."""
    lines = []
    for key in sorted(set(saved) | set(current)):
        old, new = saved.get(key), current.get(key)
        if isinstance(old, dict) and isinstance(new, dict):
            lines.extend(describe_mismatch(old, new, f'{prefix}{key}.'))
        elif old != new:
            lines.append(f'  {prefix}{key}: checkpoint={json.dumps(old, ensure_ascii=False)} '
                         f'current={json.dumps(new, ensure_ascii=False)}')
    return lines


def load_checkpoint(partial_path: Path) -> Tuple[Dict[str, Any], Dict[str, Dict[str, Any]]]:
    """Load the partial JSONL checkpoint.

    Returns the recorded config fingerprint (empty if none) and the records,
    keyed by `<id>` (answers) or `<id>#<turn>` (judgments).
    """
    fingerprint: Dict[str, Any] = {}
    checkpoint: Dict[str, Dict[str, Any]] = {}
    if partial_path.exists():
        for record in read_jsonl(partial_path):
            if record.get('kind') == 'meta':
                fingerprint = record['fingerprint']
            else:
                checkpoint[record['key']] = record
    return fingerprint, checkpoint


def check_fingerprint(partial_path: Path, saved: Dict[str, Any], has_records: bool,
                      current: Dict[str, Any]) -> None:
    """Refuse to resume a checkpoint created with a different configuration."""
    if saved:
        mismatch = describe_mismatch(saved, current)
        if mismatch:
            raise SystemExit(
                f'Checkpoint {partial_path} was created with a different configuration:\n'
                + '\n'.join(mismatch)
                + '\nResuming would mix results from different settings. Use a new --output path, '
                  'or delete the checkpoint to start over.'
            )
        return
    if has_records:
        print(f'[warn] {partial_path} predates config tracking; assuming it matches the current '
              'configuration and recording it now.', file=sys.stderr)
    append_checkpoint(partial_path, {'key': '__meta__', 'kind': 'meta', 'fingerprint': current})


def is_usable_answer(checkpoint: Dict[str, Dict[str, Any]], prompt_id: str, n_turns: int) -> bool:
    """Return True if the checkpoint holds one answer per turn for the prompt."""
    record = checkpoint.get(prompt_id)
    if not record or record.get('kind') != 'answer':
        return False
    return len(record.get('answers') or []) >= n_turns


def answers_digest(answers: List[str]) -> str:
    """Return the SHA-256 of the answers a judgment depends on (the current turn and all earlier ones)."""
    return hashlib.sha256(json.dumps(answers, ensure_ascii=False).encode('utf-8')).hexdigest()


def is_usable_judgment(record: Any, answers: List[str], turn: int, trust_legacy: bool) -> bool:
    """Return True if a checkpointed judgment is parsed and was made on the current answers.

    A judgment records the digest of the answers up to its turn, so it is reused
    only when those answers are unchanged. Records written before the digest was
    introduced are trusted only when `trust_legacy` is set, i.e. when the
    prompt's answers were not regenerated in this run.
    """
    if not record or record.get('kind') != 'judgment' or record.get('error') is not None:
        return False
    digest = record.get('answers_sha256')
    if digest is None:
        return trust_legacy
    return digest == answers_digest(answers[:turn])


def append_checkpoint(partial_path: Path, record: Dict[str, Any]) -> None:
    """Append one record to the partial checkpoint file."""
    partial_path.parent.mkdir(parents=True, exist_ok=True)
    with partial_path.open('a', encoding='utf-8') as stream:
        stream.write(json.dumps(record, ensure_ascii=False) + '\n')


async def generate_turns(client: ChatClient, prompt: Dict[str, Any]) -> Dict[str, Any]:
    """Generate the target model's answer turn by turn, replaying the dialogue.

    Each turn's reply is appended to the context before the next turn is sent,
    so multi-turn prompts become a real conversation instead of a flattened
    block of user messages.
    """
    messages: List[Dict[str, str]] = []
    answers: List[str] = []
    error = None
    try:
        for message in prompt['messages']:
            messages.append(message)
            answer = await client.chat(messages)
            messages.append({'role': 'assistant', 'content': answer})
            answers.append(answer)
    except Exception as failure:  # noqa: BLE001 - keep the pipeline running on per-item failure
        error = str(failure)
    return {
        'key': prompt['id'],
        'kind': 'answer',
        'answers': answers,
        'answer': answers[-1] if answers else None,
        'error': error,
    }


async def judge_one(
    judge: ChatClient,
    lock: asyncio.Lock,
    partial_path: Path,
    prompt: Dict[str, Any],
    template: str,
    turn: int,
    question: str,
    answer: str,
    history: List[Dict[str, str]],
    answers_sha256: str,
) -> Dict[str, Any]:
    """Judge one turn's answer against its rubric, retrying on parse failures.

    The rubric's {question} placeholder receives only the current turn; earlier
    turns are inserted as a history block right after the safety-category tag
    (see src/rubric/render.py). The record keeps `answers_sha256`, the digest of
    the answers up to this turn, so a resumed run reuses it only for the same answers.
    """
    turn_prompt = {'messages': [{'role': 'user', 'content': question}],
                   'category': prompt['category'],
                   'language': prompt['language']}
    rendered = render_rubric(template, turn_prompt, answer, history=history)
    messages = [{'role': 'user', 'content': rendered}]
    last_error = ''
    key = f"{prompt['id']}#{turn}"
    for __ in range(JUDGE_PARSE_RETRIES):
        try:
            raw = await judge.chat(messages)
            judgment = parse_judgment(raw)
            record = {
                'key': key,
                'kind': 'judgment',
                'turn': turn,
                'answers_sha256': answers_sha256,
                'error': None,
                **judgment,
            }
            async with lock:
                append_checkpoint(partial_path, record)
            return record
        except Exception as error:  # noqa: BLE001 - API or parse failure, retry
            last_error = str(error)
    record = {'key': key, 'kind': 'judgment', 'turn': turn, 'answers_sha256': answers_sha256,
              'verdict': None, 'score': None, 'triggered_items': [], 'final_summary': '',
              'judge_output': None, 'error': last_error}
    async with lock:
        append_checkpoint(partial_path, record)
    return record


async def run(args: argparse.Namespace) -> None:
    """Execute the evaluation pipeline."""
    prompts_path = resolve_data_file(args.prompts, PROMPTS_FILE)
    rubrics_path = resolve_data_file(args.rubrics, RUBRICS_FILE)
    prompts = list(read_jsonl(prompts_path))
    if args.limit is not None:
        prompts = prompts[:max(args.limit, 0)]
    templates = {r['id']: r['rubric'] for r in read_jsonl(rubrics_path)}
    missing = [p['id'] for p in prompts if p['id'] not in templates]
    if missing:
        raise ValueError(f'{len(missing)} prompts lack a rubric, e.g. {missing[:3]}')

    judge_config = load_config(args.judge)
    model_config = None if args.answers else load_config(args.model or Path('configs/model.yaml'))
    # Everything that changes answers or judgments; --limit is excluded so a
    # smoke run can be extended to the full set with the same --output.
    fingerprint = {
        'prompts_sha256': file_sha256(prompts_path),
        'rubrics_sha256': file_sha256(rubrics_path),
        'judge': request_settings(judge_config),
        'answer_source': (
            {'type': 'answers_file', 'sha256': file_sha256(args.answers)}
            if args.answers else
            {'type': 'model', **request_settings(model_config)}
        ),
    }

    args.output.parent.mkdir(parents=True, exist_ok=True)
    partial_path = args.output.with_suffix('.partial.jsonl')
    saved_fingerprint, checkpoint = load_checkpoint(partial_path)
    check_fingerprint(partial_path, saved_fingerprint, bool(checkpoint), fingerprint)
    lock = asyncio.Lock()

    answers_by_id: Dict[str, List[str]] = {}
    if args.answers:
        for record in read_jsonl(args.answers):
            answers_by_id[record['id']] = (
                list(record['answers']) if record.get('answers') else [record['answer']]
            )
        uncovered = [p['id'] for p in prompts if p['id'] not in answers_by_id]
        if uncovered:
            raise ValueError(f'{len(uncovered)} prompts lack an answer, e.g. {uncovered[:3]}')
        mismatched = [p['id'] for p in prompts if len(answers_by_id[p['id']]) != len(p['messages'])]
        if mismatched:
            raise ValueError(
                f'{len(mismatched)} prompts have an answer count different from their turn count, '
                f'e.g. {mismatched[:3]}; multi-turn prompts need "answers" with one entry per turn'
            )
        answer_source = {'type': 'answers_file', 'path': str(args.answers)}
    else:
        answer_source = {'type': 'model', 'model': model_config['model']}
        for record in checkpoint.values():
            if record['kind'] == 'answer' and record.get('answers'):
                answers_by_id[record['key']] = record['answers']

    judge = ChatClient(judge_config)
    judgments: Dict[str, List[Dict[str, Any]]] = {}
    judge_tasks: List[asyncio.Task] = []
    scheduled: set = set()
    judge_bar = None

    async def judge_and_collect(prompt: Dict[str, Any], turn: int) -> None:
        answers = answers_by_id[prompt['id']]
        record = await judge_one(
            judge, lock, partial_path, prompt, templates[prompt['id']], turn,
            prompt['messages'][turn - 1]['content'], answers[turn - 1],
            history_pairs(prompt, answers)[:turn - 1], answers_digest(answers[:turn]),
        )
        if record['error'] is None:
            judgments.setdefault(prompt['id'], []).append(record)
        judge_bar.update(1)

    def schedule_judging(prompt: Dict[str, Any]) -> None:
        """Reuse the checkpointed judgments made on the current answers; queue the other answered turns."""
        if prompt['id'] in scheduled:
            return
        scheduled.add(prompt['id'])
        answers = answers_by_id.get(prompt['id'], [])
        trust_legacy = prompt['id'] not in regenerated
        turns = []
        for turn in range(1, len(answers) + 1):
            record = checkpoint.get(f"{prompt['id']}#{turn}")
            if is_usable_judgment(record, answers, turn, trust_legacy):
                judgments.setdefault(prompt['id'], []).append(record)
            else:
                turns.append(turn)
        if turns:
            judge_bar.total += len(turns)
            judge_bar.refresh()
            judge_tasks.extend(asyncio.create_task(judge_and_collect(prompt, t)) for t in turns)

    to_generate = [] if args.answers else [
        p for p in prompts if not is_usable_answer(checkpoint, p['id'], len(p['messages']))
    ]
    # Answers of these prompts are replaced by this run's output, so judgments
    # made on earlier answers must not be reused for them.
    regenerated = {p['id'] for p in to_generate}
    streaming = args.pipeline and bool(to_generate)
    if streaming:
        # Prompts whose answers are already complete can be judged right away.
        judge_bar = tqdm(total=0, desc='Judging', position=1)
        for prompt in prompts:
            if prompt['id'] not in regenerated:
                schedule_judging(prompt)

    if model_config is not None:
        target = ChatClient(model_config)
        if to_generate:
            by_id = {p['id']: p for p in to_generate}
            tasks = [asyncio.create_task(generate_turns(target, p)) for p in to_generate]
            for future in tqdm(asyncio.as_completed(tasks), total=len(tasks),
                               desc='Generating answers', position=0):
                record = await future
                # On failure keep only the turns answered in this run, so every
                # judged turn belongs to the same conversation.
                answers_by_id[record['key']] = record['answers']
                async with lock:
                    append_checkpoint(partial_path, record)
                if streaming and record['error'] is None:
                    schedule_judging(by_id[record['key']])
        await target.close()

    # Sequential mode judges everything here; pipeline mode only picks up the
    # prompts whose generation failed (the turns answered before the failure).
    if judge_bar is None:
        judge_bar = tqdm(total=0, desc='Judging')
    for prompt in prompts:
        schedule_judging(prompt)
    if judge_tasks:
        await asyncio.gather(*judge_tasks)
    judge_bar.close()
    await judge.close()

    results = []
    n_errors = 0
    for prompt in prompts:
        prompt_id = prompt['id']
        turn_answers = answers_by_id.get(prompt_id, [])
        history = history_pairs(prompt, turn_answers)
        item_judgments = sorted(judgments.get(prompt_id, []), key=lambda x: x['turn'])
        # Count against the prompt's turns, so missing answers still count as incomplete.
        expected = len(prompt['messages'])
        if len(item_judgments) < expected or any(j['error'] for j in item_judgments):
            n_errors += 1
        results.append({
            'id': prompt_id,
            'subset': subset_of(prompt_id),
            'language': prompt['language'],
            'n_turns': len(prompt['messages']),
            'category': prompt['category'],
            'answer': turn_answers[-1] if turn_answers else None,
            'history': history,
            'judgments': [
                {
                    'turn': j['turn'],
                    'verdict': j['verdict'],
                    'score': j['score'],
                    'triggered_items': j['triggered_items'],
                    'final_summary': j['final_summary'],
                    'judge_output': j['judge_output'],
                    'error': j['error'],
                }
                for j in item_judgments
            ],
        })
    payload = {
        'meta': {
            'created_at': datetime.now().isoformat(timespec='seconds'),
            'judge': {'model': judge_config['model'], 'temperature': judge_config.get('temperature', 0)},
            'answer_source': answer_source,
            'config_fingerprint': fingerprint,
            'n_prompts': len(results),
            'n_turns_judged': sum(len(r['history']) for r in results),
            'n_incomplete': n_errors,
        },
        'results': results,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open('w', encoding='utf-8') as stream:
        json.dump(payload, stream, ensure_ascii=False, indent=1)
    print(f"\nDone. {len(results)} prompts -> {args.output} (incomplete: {n_errors})")
    print(f'Checkpoint kept at {partial_path}; rerun the same command to resume after failures.')

    report = build_report(payload)
    print_report(report)
    analysis_path = args.output.with_suffix('.analysis.json')
    with analysis_path.open('w', encoding='utf-8') as stream:
        json.dump(report, stream, ensure_ascii=False, indent=2)
    print(f'\nAnalysis written to {analysis_path}')


def main() -> None:
    """Entry point."""
    asyncio.run(run(parse_args()))


if __name__ == '__main__':
    main()
