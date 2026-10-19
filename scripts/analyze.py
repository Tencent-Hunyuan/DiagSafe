#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Analyze DiagSafe evaluation results.

Standalone entry point for re-analyzing an existing results file.
scripts/run_eval.py performs the same analysis automatically at the end of a run.

Example:
    python scripts/analyze.py --results results/run-001.json
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.analyze import build_report
from src.analyze import print_report


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(description='Analyze DiagSafe evaluation results.')
    parser.add_argument('--results', type=Path, required=True, help='Results JSON produced by run_eval.py')
    parser.add_argument('--report', type=Path, default=None,
                        help='Where to write the analysis JSON (default: <results>.analysis.json)')
    parser.add_argument('--min-count', type=int, default=1,
                        help='Hide per-label rows with fewer judged prompts')
    return parser.parse_args()


def main() -> None:
    """Entry point."""
    args = parse_args()
    with args.results.open(encoding='utf-8') as stream:
        payload = json.load(stream)
    report = build_report(payload, args.min_count)
    judged = report['overall'].get('overall', {}).get('n', 0)
    print(f"Results: {args.results} | prompts: {len(payload['results'])} | judged: {judged}")
    print(f"Meta: {json.dumps(payload.get('meta', {}), ensure_ascii=False)}")
    print_report(report)
    report_path = args.report or args.results.with_suffix('.analysis.json')
    with report_path.open('w', encoding='utf-8') as stream:
        json.dump(report, stream, ensure_ascii=False, indent=2)
    print(f'\nReport written to {report_path}')


if __name__ == '__main__':
    main()
