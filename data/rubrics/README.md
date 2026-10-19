# DiagSafe Rubrics

`DiagSafe_rubrics_3489.jsonl` contains one prompt-level rubric for every benchmark prompt. Each line is one UTF-8 JSON object.

## Record Format

```json
{
  "id": "DiagAttack-000003",
  "rubric": "..."
}
```

## Fields

| Field | Type | Description |
|---|---|---|
| `id` | string | Prompt identifier; matches exactly one record in the prompt file |
| `rubric` | string | Complete judge prompt with criteria, scoring rules, and output schema |

## Rubric Structure

Each rubric contains:

1. `{question}`, `{answer}`, and `{safety_categories}` placeholders.
2. Two to six prompt-specific safety items (`S1`–`S6`).
3. An exemption scope for every safety item.
4. Eight usefulness items: instruction following (`U1.1`–`U1.3`), information quality (`U2.1`–`U2.3`), and response pattern (`U3.1`–`U3.2`).
5. A 0–3 usefulness scoring rule.
6. A structured JSON output contract for evidence, exemptions, reasoning, verdict, and score.

Rubrics are written in the language of their prompt.

### Safety Item Distribution

| Safety items per rubric | Rubrics |
|---:|---:|
| 2 | 4 |
| 3 | 95 |
| 4 | 1,464 |
| 5 | 1,908 |
| 6 | 18 |

## Rendering a Rubric

The rubric includes JSON braces in its output template, so replace the three named placeholders directly rather than with `str.format`:

```python
import json
from typing import Any, Dict


def render_rubric(
    template: str,
    prompt: Dict[str, Any],
    answer: str,
) -> str:
    """Render one rubric for an evaluated response."""
    question = json.dumps(prompt["messages"], ensure_ascii=False)
    categories = json.dumps(prompt["category"], ensure_ascii=False)
    return (
        template
        .replace("{question}", question)
        .replace("{answer}", answer)
        .replace("{safety_categories}", categories)
    )
```

For multi-turn prompts, `scripts/run_eval.py` renders the rubric once per turn with that turn's user message as `{question}`, and appends the earlier question–answer pairs after the rendered rubric as a conversation history block (see [`src/rubric/render.py`](../../src/rubric/render.py)).

The structural definition is available in [`schema.json`](schema.json).
