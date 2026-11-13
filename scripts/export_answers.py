#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Export the answers and chains of thought of an existing results file.

The output is an answers JSONL for `scripts/run_eval.py --answers`, so a run
can be judged again in another mode without generating the answers again:

    python scripts/export_answers.py --results results/<model>.json --output answers/<model>.jsonl
    python scripts/run_eval.py --prompts data/prompts --rubrics data/rubrics --judge configs/judge.yaml \\
        --answers answers/<model>.jsonl --answer-key content+reasoning_content

Each line is {"id", "answers": [...], "reasonings": [...]} with one entry per
turn. Prompts whose answers are incomplete are skipped. "reasonings" is written
only when the results file stored the chain of thought (`generation`).
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Any
from typing import Dict
from typing import Optional


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(description='Export answers and reasoning for run_eval.py --answers.')
    parser.add_argument('--results', type=Path, required=True, help='Results JSON written by run_eval.py')
    parser.add_argument('--output', type=Path, required=True, help='Answers JSONL to write')
    return parser.parse_args()


def export_record(result: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Return the answers record of one prompt, or None if its answers are incomplete."""
    answers = [pair.get('answer') for pair in result.get('history') or []]
    if len(answers) != result['n_turns'] or any(answer is None for answer in answers):
        return None
    record: Dict[str, Any] = {'id': result['id'], 'answers': answers}
    generation = result.get('generation') or []
    if len(generation) == len(answers):
        record['reasonings'] = [(item or {}).get('reasoning') or '' for item in generation]
    return record


def main() -> int:
    """Entry point."""
    args = parse_args()
    with args.results.open(encoding='utf-8') as stream:
        payload = json.load(stream)
    written = skipped = with_reasoning = 0
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open('w', encoding='utf-8') as stream:
        for result in payload['results']:
            record = export_record(result)
            if record is None:
                skipped += 1
                continue
            with_reasoning += int('reasonings' in record)
            stream.write(json.dumps(record, ensure_ascii=False) + '\n')
            written += 1
    print(f'Wrote {written} prompts to {args.output} ({with_reasoning} with reasoning); '
          f'skipped {skipped} with incomplete answers.')
    if skipped:
        print('[info] Pass --allow-missing-answers to run_eval.py to count the skipped prompts as incomplete.',
              file=sys.stderr)
    if written and not with_reasoning:
        print('[warn] The results file has no chain of thought; only answer_key content can be judged.',
              file=sys.stderr)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
