"""Export the dashboard as a static site for any static web host.

    python dashboard/export.py --out docs

The output needs no server at runtime. Prompts and standards load up front;
rubrics are split into chunks fetched only when a sample is opened.
.github/workflows/pages.yml runs this export and deploys it to GitHub Pages.
"""

import argparse
import json
import shutil
import sys
from pathlib import Path
from typing import Any
from typing import Dict
from typing import List

HERE = Path(__file__).resolve().parent
STATIC = HERE / 'static'
sys.path.insert(0, str(HERE))

from app import Dataset  # noqa: E402  (path set above)
from app import default_data_root  # noqa: E402

RUBRICS_PER_CHUNK = 400
PREVIEW_LENGTH = 140


def write_json(path: Path, payload: Any) -> None:
    """Write compact JSON with parent directories created."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, separators=(',', ':')),
        encoding='utf-8',
    )


def build_prompts(dataset: Dataset) -> List[Dict[str, Any]]:
    """Flatten prompts into the shape the front-end filters and renders."""
    rows = []
    for prompt in dataset.by_id.values():
        messages = prompt['messages']
        rows.append({
            'id': prompt['id'],
            'subset': prompt['subset'],
            'language': prompt['language'],
            'n_turns': prompt['n_turns'],
            'category': prompt['category'],
            'l1': prompt['category'].get('l1', ''),
            'l3': prompt['category'].get('l3', ''),
            'has_rubric': prompt['has_rubric'],
            'preview': messages[0].get('content', '')[:PREVIEW_LENGTH] if messages else '',
            'messages': messages,
        })
    rows.sort(key=lambda row: row['id'])
    return rows


def build_rubrics(dataset: Dataset, out: Path) -> Dict[str, str]:
    """Split rubrics into chunks and return an id -> chunk-file index."""
    identifiers = sorted(dataset.rubrics)
    index: Dict[str, str] = {}
    for start in range(0, len(identifiers), RUBRICS_PER_CHUNK):
        batch = identifiers[start:start + RUBRICS_PER_CHUNK]
        name = f'chunk-{start // RUBRICS_PER_CHUNK:02d}.json'
        write_json(out / 'data/rubrics' / name,
                   {key: dataset.rubrics[key] for key in batch})
        for key in batch:
            index[key] = name
    write_json(out / 'data/rubrics/index.json', {'map': index})
    return index


def copy_frontend(out: Path) -> None:
    """Copy static assets and switch index.html to relative, static-mode paths."""
    for name in ('styles.css', 'app.js'):
        shutil.copyfile(STATIC / name, out / name)
    html = (STATIC / 'index.html').read_text(encoding='utf-8')
    html = html.replace('href="/static/styles.css"', 'href="styles.css"')
    html = html.replace('src="/static/app.js"', 'src="app.js"')
    html = html.replace('<head>', '<head>\n  <script>window.DIAGSAFE_STATIC = true;</script>', 1)
    (out / 'index.html').write_text(html, encoding='utf-8')


def export(data_root: Path, out: Path) -> None:
    """Generate the whole static site."""
    dataset = Dataset(data_root)
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)

    copy_frontend(out)
    write_json(out / 'data/prompts.json', build_prompts(dataset))
    write_json(out / 'data/standards.json', dataset.standards_list())
    write_json(out / 'data/meta.json', {
        'summary': dataset.summary(),
        'stats': dataset.stats(),
        'labels': dataset.labels(),
    })
    index = build_rubrics(dataset, out)

    print(f'Wrote {out}')
    print(f'  prompts   : {len(dataset.by_id)}')
    print(f'  standards : {len(dataset.standards)}')
    print(f'  rubrics   : {len(index)} in {len(set(index.values()))} chunks')


def main() -> None:
    """CLI entry point."""
    parser = argparse.ArgumentParser(description='Export the dashboard as a static site')
    parser.add_argument('--out', type=Path, default=HERE.parent / 'docs')
    parser.add_argument('--data', type=Path, default=None, help='Path to the data/ directory')
    args = parser.parse_args()
    export(Path(args.data) if args.data else default_data_root(), args.out)


if __name__ == '__main__':
    main()
