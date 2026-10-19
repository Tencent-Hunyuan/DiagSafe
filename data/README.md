# DiagSafe Data

This directory contains the three components of the DiagSafe benchmark: prompts, prompt-level rubrics, and the safety taxonomy that grounds them.

## Composition

| Component | File | Records | Description |
|---|---|---:|---|
| Prompts | [`prompts/DiagSafe_bench_3489.jsonl`](prompts/DiagSafe_bench_3489.jsonl) | 3,489 | Bilingual single- and multi-turn evaluation prompts |
| Rubrics | [`rubrics/DiagSafe_rubrics_3489.jsonl`](rubrics/DiagSafe_rubrics_3489.jsonl) | 3,489 | One prompt-level judge rubric for every prompt |
| Taxonomy | [`taxonomy/DiagSafe_standards_84.json`](taxonomy/DiagSafe_standards_84.json) | 84 | Three-level safety taxonomy and label specifications |
| Taxonomy (English) | [`taxonomy/DiagSafe_standards_84_en.json`](taxonomy/DiagSafe_standards_84_en.json) | 84 | English definitions, general standards, and detailed rules |

The taxonomy files cover the same 84 labels and preserve category codes and record order.
The English file uses English field names, category names, and standard text.
Schemas: [Chinese](taxonomy/schema.json) · [English](taxonomy/schema_en.json).
Both versions are distributed under the [CC BY 4.0 License](../LICENSE).

### Prompt Distribution

| Dimension | Distribution |
|---|---|
| Subset | DiagBase: 2,401 · DiagAttack: 1,088 |
| Language | English: 1,749 · Chinese: 1,740 |
| Dialogue | Single-turn: 2,560 · Multi-turn: 929 |
| Number of turns | 1: 2,560 · 2: 234 · 3: 674 · 4: 20 · 5: 1 |
| Taxonomy coverage | 11 first-level · 34 second-level · 84 third-level labels |

## Data Relationships

```text
prompts/DiagSafe_bench_3489.jsonl
    │ id
    ├───────────────────────────────┐
    │                               ▼
    │                    rubrics/DiagSafe_rubrics_3489.jsonl
    │ category.l1/l2/l3             │ rubric
    ▼                               ▼
taxonomy/DiagSafe_standards_84.json ──► LLM judge
```

- Prompt and rubric records form a one-to-one mapping through `id`.
- `category.l1`, `category.l2`, and `category.l3` connect each prompt to its taxonomy entry.
- Every third-level taxonomy label is represented in the prompt set.

## Loading and Joining

```python
import json
from pathlib import Path
from typing import Any, Dict, Iterator


def read_jsonl(path: Path) -> Iterator[Dict[str, Any]]:
    """Read JSON objects from a JSONL file."""
    with path.open(encoding="utf-8") as stream:
        for line in stream:
            if line.strip():
                yield json.loads(line)


prompts = list(read_jsonl(Path("data/prompts/DiagSafe_bench_3489.jsonl")))
rubrics = {
    item["id"]: item["rubric"]
    for item in read_jsonl(Path("data/rubrics/DiagSafe_rubrics_3489.jsonl"))
}

for prompt in prompts:
    prompt_id = prompt["id"]
    rubric = rubrics[prompt_id]
```

## Schemas and Documentation

- [Prompt format](prompts/README.md) · [Prompt JSON Schema](prompts/schema.json)
- [Rubric format](rubrics/README.md) · [Rubric JSON Schema](rubrics/schema.json)
- [Taxonomy format](taxonomy/README.md) · [Chinese JSON Schema](taxonomy/schema.json) · [English JSON Schema](taxonomy/schema_en.json)
- [Joined example](../examples/README.md)

## File Integrity

| File | SHA-256 |
|---|---|
| `DiagSafe_bench_3489.jsonl` | `befa1cae314fc0faceed1a077e823d04b9e207a39111794e3e70e71cbd3e1733` |
| `DiagSafe_rubrics_3489.jsonl` | `811b71a6a864ba8245b92994a8510aa55fcad98c22124c917dec3eb3d722ad9e` |
| `DiagSafe_standards_84.json` | `d7e66c37ee9b55b7bb984b4dfd70740908f390b3a6743dfd579a84c055bcaca4` |
| `DiagSafe_standards_84_en.json` | `356b638bda1f9ca090f117ea9876cfbf44f486c3cd17a9508fe55144a9760204` |
