"""DiagSafe dataset dashboard — browse prompts, rubrics and the safety taxonomy.

Run:
    pip install -r dashboard/requirements.txt
    python dashboard/app.py --port 8765

The server reads the benchmark files under data/ and serves them read-only.
"""

import argparse
import json
import re
from pathlib import Path
from typing import Any
from typing import Dict
from typing import Iterator
from typing import List
from typing import Optional

import uvicorn
from fastapi import FastAPI
from fastapi import HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

HERE = Path(__file__).resolve().parent
STATIC = HERE / 'static'

PAGE_SIZE = 60


def default_data_root() -> Path:
    """Locate data/ next to the dashboard directory, falling back to the CWD."""
    for candidate in (HERE.parent / 'data', Path.cwd() / 'data'):
        if candidate.is_dir():
            return candidate
    return HERE.parent / 'data'


def read_jsonl(path: Path) -> Iterator[Dict[str, Any]]:
    """Yield JSON objects from a JSONL file."""
    with path.open(encoding='utf-8') as stream:
        for line in stream:
            if line.strip():
                yield json.loads(line)


def english_of(bilingual: str) -> str:
    """Extract the English part of a `中文 (English)` string."""
    match = re.search(r'\(([^()]*)\)\s*$', bilingual or '')
    return match.group(1).strip() if match else (bilingual or '').strip()


def chinese_of(bilingual: str) -> str:
    """Extract the Chinese part of a `中文 (English)` string."""
    return re.sub(r'\s*\([^()]*\)\s*$', '', bilingual or '').strip()


class Dataset:
    """In-memory index over prompts, rubrics and the taxonomy."""

    def __init__(self, data_root: Path) -> None:
        self.root = Path(data_root)
        self.prompts_path = self._first('prompts', '*.jsonl')
        self.rubrics_path = self._first('rubrics', '*.jsonl')
        self.standards_en_path = self._first('taxonomy', '*84_en.json')
        self.standards_zh_path = self._first('taxonomy', '*84.json')

        self.prompts: List[Dict[str, Any]] = list(read_jsonl(self.prompts_path))
        self.rubrics: Dict[str, str] = {
            row['id']: (row.get('rubric') or '') for row in read_jsonl(self.rubrics_path)
        }
        self.standards = self._load_standards()

        self.by_id: Dict[str, Dict[str, Any]] = {}
        for row in self.prompts:
            category = row.get('category') or {}
            messages = row.get('messages') or []
            self.by_id[row['id']] = {
                'id': row['id'],
                'subset': row['id'].split('-')[0],
                'language': row.get('language', ''),
                'messages': messages,
                'n_turns': len(messages),
                'category': category,
                'standard': self.standards.get((category.get('l2', ''), category.get('l3', ''))),
                'has_rubric': bool(self.rubrics.get(row['id'], '').strip()),
            }

    def _first(self, folder: str, pattern: str) -> Path:
        """Resolve a data file, raising a clear error when it is missing."""
        matches = sorted((self.root / folder).glob(pattern))
        if not matches:
            raise FileNotFoundError(f'No {pattern} found under {self.root / folder}')
        return matches[0]

    def _load_standards(self) -> Dict[Any, Dict[str, Any]]:
        """Index taxonomy entries by the bilingual (l2, l3) pair used in prompts."""
        english: List[Dict[str, Any]] = json.loads(self.standards_en_path.read_text(encoding='utf-8'))
        chinese: List[Dict[str, Any]] = json.loads(self.standards_zh_path.read_text(encoding='utf-8'))
        by_label: Dict[Any, Dict[str, Any]] = {}
        for row in english:
            names = row.get('category_name') or {}
            by_label[(row.get('category_code', ''), names.get('l3', ''))] = {
                'definition': row.get('definition', ''),
                'general_standard': row.get('general_standard', ''),
                'detailed_rules': row.get('detailed_rules', ''),
            }
        index: Dict[Any, Dict[str, Any]] = {}
        for order, row in enumerate(chinese):
            names = row.get('类目名称') or {}
            l1 = names.get('一级类目', '')
            l2 = names.get('二级类目', '')
            l3 = names.get('三级类目', '')
            code = row.get('类目编号', '')
            # English names come from the bilingual strings; the English file is
            # matched per label, because one code covers several third-level labels.
            entry = by_label.get((code, english_of(l3)), {})
            index[(l2, l3)] = {
                'code': code,
                'l1': l1,
                'l2': l2,
                'l3': l3,
                'l1_en': english_of(l1),
                'l2_en': english_of(l2),
                'l3_en': english_of(l3),
                'l1_zh': chinese_of(l1),
                'l2_zh': chinese_of(l2),
                'l3_zh': chinese_of(l3),
                'order': order,
                'definition': entry.get('definition', ''),
                'general_standard': entry.get('general_standard', ''),
                'detailed_rules': entry.get('detailed_rules', ''),
                'definition_zh': row.get('定义', ''),
                'general_standard_zh': row.get('标准总则', ''),
                'detailed_rules_zh': row.get('标准细则', ''),
            }
        return index

    # -- queries ----------------------------------------------------------

    def summary(self) -> Dict[str, Any]:
        """Headline counts for the whole benchmark."""
        items = self.by_id.values()
        return {
            'prompts': len(self.by_id),
            'rubrics': sum(1 for row in self.rubrics.values() if row.strip()),
            'taxonomy': {
                'l1': len({p['category'].get('l1', '') for p in items}),
                'l2': len({p['category'].get('l2', '') for p in items}),
                'l3': len({p['category'].get('l3', '') for p in items}),
            },
            'languages': {
                name: sum(1 for p in items if p['language'] == name) for name in ('en', 'zh')
            },
            'subsets': {
                name: sum(1 for p in items if p['subset'] == name)
                for name in ('DiagBase', 'DiagAttack')
            },
            'turns': {
                'single': sum(1 for p in items if p['n_turns'] == 1),
                'multi': sum(1 for p in items if p['n_turns'] > 1),
            },
            'files': {
                'prompts': self.prompts_path.name,
                'rubrics': self.rubrics_path.name,
                'taxonomy': self.standards_zh_path.name,
            },
        }

    def stats(self) -> Dict[str, Any]:
        """Distribution tables for the overview charts."""
        by_l1: Dict[str, Dict[str, Any]] = {}
        by_turns: Dict[int, int] = {}
        for prompt in self.by_id.values():
            code = prompt['category'].get('l1', '')
            entry = by_l1.setdefault(code, {'code': code, 'name': code, 'count': 0})
            if prompt['standard']:
                entry['name'] = prompt['standard']['l1_en'] or english_of(prompt['standard']['l1'])
            entry['count'] += 1
            turns = prompt['n_turns']
            by_turns[turns] = by_turns.get(turns, 0) + 1
        return {
            'by_l1': sorted(by_l1.values(), key=lambda item: item['code']),
            'by_turns': [{'turns': key, 'count': by_turns[key]} for key in sorted(by_turns)],
        }

    def taxonomy(self) -> List[Dict[str, Any]]:
        """Three-level tree with per-label prompt counts."""
        tree: Dict[str, Dict[str, Any]] = {}
        for prompt in self.by_id.values():
            category = prompt['category']
            standard = prompt['standard'] or {}
            node = tree.setdefault(category.get('l1', ''), {
                'code': category.get('l1', ''),
                'name': standard.get('l1_en') or english_of(standard.get('l1', '')),
                'name_zh': standard.get('l1', ''),
                'count': 0,
                'children': {},
            })
            node['count'] += 1
            l2 = node['children'].setdefault(category.get('l2', ''), {
                'name': standard.get('l2_en') or english_of(category.get('l2', '')),
                'name_zh': category.get('l2', ''),
                'count': 0,
                'children': {},
            })
            l2['count'] += 1
            l3 = l2['children'].setdefault(category.get('l3', ''), {
                'name': standard.get('l3_en') or english_of(category.get('l3', '')),
                'name_zh': category.get('l3', ''),
                'count': 0,
            })
            l3['count'] += 1
        return [
            {
                'code': code,
                'name': node['name'],
                'name_zh': node['name_zh'],
                'count': node['count'],
                'children': [
                    {
                        'name': child['name'],
                        'name_zh': child['name_zh'],
                        'count': child['count'],
                        'children': sorted(child['children'].values(), key=lambda x: -x['count']),
                    }
                    for child in sorted(node['children'].values(), key=lambda x: -x['count'])
                ],
            }
            for code, node in sorted(tree.items())
        ]

    def standards_list(self) -> List[Dict[str, Any]]:
        """Every taxonomy entry with its full standard text and prompt count."""
        counts: Dict[str, int] = {}
        for prompt in self.by_id.values():
            l3 = prompt['category'].get('l3', '')
            counts[l3] = counts.get(l3, 0) + 1
        entries = []
        for (_l2, l3), entry in self.standards.items():
            entries.append({
                'key': l3,
                'code': entry['code'],
                'l1': entry['l1'],
                'l2': entry['l2'],
                'l3': l3,
                'l1_en': entry['l1_en'],
                'l2_en': entry['l2_en'],
                'l3_en': entry['l3_en'],
                'l1_zh': entry['l1_zh'],
                'l2_zh': entry['l2_zh'],
                'l3_zh': entry['l3_zh'],
                'order': entry['order'],
                'count': counts.get(l3, 0),
                'definition': entry['definition'],
                'general_standard': entry['general_standard'],
                'detailed_rules': entry['detailed_rules'],
                'definition_zh': entry['definition_zh'],
                'general_standard_zh': entry['general_standard_zh'],
                'detailed_rules_zh': entry['detailed_rules_zh'],
            })
        # Taxonomy-file order keeps each L2 group contiguous under its L1.
        return sorted(entries, key=lambda item: (item['code'], item['order']))

    def samples(
        self,
        query: str = '',
        language: str = '',
        subset: str = '',
        turns: str = '',
        label: str = '',
        offset: int = 0,
        limit: int = PAGE_SIZE,
    ) -> Dict[str, Any]:
        """Filtered, paginated sample list."""
        needle = query.strip().lower()
        matched: List[Dict[str, Any]] = []
        for prompt in self.by_id.values():
            if language and prompt['language'] != language:
                continue
            if subset and prompt['subset'] != subset:
                continue
            if turns == 'single' and prompt['n_turns'] != 1:
                continue
            if turns == 'multi' and prompt['n_turns'] <= 1:
                continue
            if label and prompt['category'].get('l3', '') != label:
                continue
            if needle:
                haystack = prompt['id'].lower() + ' ' + ' '.join(
                    message.get('content', '') for message in prompt['messages']
                ).lower()
                if needle not in haystack:
                    continue
            matched.append(prompt)
        matched.sort(key=lambda item: item['id'])
        page = matched[offset:offset + limit]
        return {
            'total': len(matched),
            'offset': offset,
            'items': [
                {
                    'id': item['id'],
                    'language': item['language'],
                    'subset': item['subset'],
                    'n_turns': item['n_turns'],
                    'l1': item['category'].get('l1', ''),
                    'l3': item['category'].get('l3', ''),
                    'has_rubric': item['has_rubric'],
                    'preview': item['messages'][0].get('content', '')[:140] if item['messages'] else '',
                }
                for item in page
            ],
        }

    def sample(self, sample_id: str) -> Dict[str, Any]:
        """Full record for one prompt: messages, rubric and taxonomy entry."""
        prompt = self.by_id.get(sample_id)
        if prompt is None:
            raise HTTPException(404, f'Unknown sample: {sample_id}')
        return {**prompt, 'rubric': self.rubrics.get(sample_id, '')}

    def labels(self) -> List[Dict[str, str]]:
        """Every third-level label that appears in the prompt set."""
        seen: Dict[str, Dict[str, str]] = {}
        for prompt in self.by_id.values():
            l3 = prompt['category'].get('l3', '')
            if l3 not in seen:
                standard = prompt['standard'] or {}
                seen[l3] = {
                    'l3': l3,
                    'l3_en': standard.get('l3_en') or english_of(l3),
                    'l1': prompt['category'].get('l1', ''),
                }
        return sorted(seen.values(), key=lambda item: item['l3_en'])


def create_app(data_root: Optional[Path] = None) -> FastAPI:
    """Build the FastAPI application."""
    dataset = Dataset(Path(data_root) if data_root else default_data_root())
    application = FastAPI(title='DiagSafe Dataset Dashboard', docs_url=None, redoc_url=None)
    application.state.dataset = dataset

    @application.get('/')
    def home() -> FileResponse:
        return FileResponse(STATIC / 'index.html')

    @application.get('/api/summary')
    def api_summary() -> Dict[str, Any]:
        return dataset.summary()

    @application.get('/api/stats')
    def api_stats() -> Dict[str, Any]:
        return dataset.stats()

    @application.get('/api/taxonomy')
    def api_taxonomy() -> List[Dict[str, Any]]:
        return dataset.taxonomy()

    @application.get('/api/standards')
    def api_standards() -> List[Dict[str, Any]]:
        return dataset.standards_list()

    @application.get('/api/labels')
    def api_labels() -> List[Dict[str, str]]:
        return dataset.labels()

    @application.get('/api/samples')
    def api_samples(
        q: str = '',
        language: str = '',
        subset: str = '',
        turns: str = '',
        label: str = '',
        offset: int = 0,
        limit: int = PAGE_SIZE,
    ) -> Dict[str, Any]:
        return dataset.samples(q, language, subset, turns, label, offset, min(limit, 300))

    @application.get('/api/samples/{sample_id}')
    def api_sample(sample_id: str) -> Dict[str, Any]:
        return dataset.sample(sample_id)

    application.mount('/static', StaticFiles(directory=STATIC), name='static')
    return application


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='DiagSafe dataset dashboard')
    parser.add_argument('--host', default='127.0.0.1',
                        help='Interface to bind (use 0.0.0.0 to serve other machines)')
    parser.add_argument('--port', type=int, default=8765)
    parser.add_argument('--data', type=Path, default=None,
                        help='Path to the data/ directory (default: ../data)')
    args = parser.parse_args()
    uvicorn.run(create_app(args.data), host=args.host, port=args.port)
