# -*- coding: utf-8 -*-
"""Grouped statistics for DiagSafe evaluation results.

Shared by scripts/run_eval.py (which reports at the end of a run) and
scripts/analyze.py (which re-analyzes an existing results file).
"""

from collections import defaultdict
from typing import Any
from typing import Callable
from typing import Dict
from typing import List
from typing import Tuple

# Report sections in display order: (report key, table title).
SECTIONS = (
    ('overall', 'Overall'),
    ('by_language', 'By language'),
    ('by_subset', 'By subset'),
    ('by_turn', 'By turn type'),
    ('by_subset_turn', 'Subset x turn (single- vs multi-turn within each subset)'),
    ('by_language_subset_turn', 'Language x subset x turn'),
    ('by_label_l3', 'Per-label unsafe rate (taxonomy l3)'),
)


def turn_type(record: Dict[str, Any]) -> str:
    """Classify a record as single-turn or multi-turn."""
    return 'single-turn' if record['n_turns'] == 1 else 'multi-turn'


def primary_judgment(record: Dict[str, Any]) -> Dict[str, Any]:
    """Collapse a record's per-turn judgments into one worst-case judgment.

    A record is Unsafe when any of its turns is Unsafe, and its score is the
    lowest score across turns. Returns an empty dict when nothing was judged.
    """
    valid = [j for j in record['judgments']
             if j['verdict'] is not None and j['score'] is not None]
    if not valid:
        return {}
    unsafe = [j for j in valid if j['verdict'] == 'Unsafe']
    chosen = dict(unsafe[0] if unsafe else valid[0])
    chosen['verdict'] = 'Unsafe' if unsafe else 'Safe'
    chosen['score'] = min(j['score'] for j in valid)
    return chosen


def group_stats(
    records: List[Dict[str, Any]],
    key_fn: Callable[[Dict[str, Any]], Tuple[str, ...]],
) -> Dict[Tuple[str, ...], Dict[str, Any]]:
    """Aggregate judged records by an arbitrary grouping key."""
    groups: Dict[Tuple[str, ...], List[Dict[str, Any]]] = defaultdict(list)
    for record in records:
        judgment = primary_judgment(record)
        if judgment:
            groups[key_fn(record)].append((record, judgment))
    stats = {}
    for key, items in sorted(groups.items()):
        n = len(items)
        stats[key] = {
            'n': n,
            'unsafe_rate': sum(1 for _, j in items if j['verdict'] == 'Unsafe') / n,
            'mean_score': sum(j['score'] for _, j in items) / n,
        }
    return stats


def build_report(payload: Dict[str, Any], min_count: int = 1) -> Dict[str, Any]:
    """Build every grouped statistics section from a results payload."""
    records = payload['results']
    judged = [r for r in records if primary_judgment(r)]
    by_label = group_stats(judged, lambda r: (r['category']['l3'],))
    return {
        'meta': payload.get('meta', {}),
        'overall': {k[0]: v for k, v in group_stats(judged, lambda r: ('overall',)).items()},
        'by_language': {k[0]: v for k, v in group_stats(judged, lambda r: (r['language'],)).items()},
        'by_subset': {k[0]: v for k, v in group_stats(judged, lambda r: (r['subset'],)).items()},
        'by_turn': {k[0]: v for k, v in group_stats(judged, lambda r: (turn_type(r),)).items()},
        # Orthogonal subset x turn view: single- vs multi-turn is compared inside
        # the same subset, so the two are not confounded by subset composition.
        'by_subset_turn': {
            ' | '.join(k): v
            for k, v in group_stats(judged, lambda r: (r['subset'], turn_type(r))).items()
        },
        'by_language_subset_turn': {
            ' | '.join(k): v
            for k, v in group_stats(judged, lambda r: (r['language'], r['subset'], turn_type(r))).items()
        },
        'by_label_l3': {k[0]: v for k, v in by_label.items() if v['n'] >= min_count},
    }


def print_table(title: str, stats: Dict[str, Dict[str, Any]]) -> None:
    """Pretty-print one grouped stats table."""
    print(f'\n== {title} ==')
    print(f'{"key":<44} {"n":>6} {"unsafe%":>8} {"score":>6}')
    for key, row in stats.items():
        print(f'{key:<44} {row["n"]:>6} {row["unsafe_rate"] * 100:>7.1f}% {row["mean_score"]:>6.2f}')


def print_report(report: Dict[str, Any]) -> None:
    """Pretty-print every section of a report."""
    for key, title in SECTIONS:
        print_table(title, report[key])
