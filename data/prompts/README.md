# DiagSafe Prompts

`DiagSafe_bench_3489.jsonl` contains 3,489 benchmark prompts. Each line is one UTF-8 JSON object.

## Statistics

| Dimension | Distribution |
|---|---|
| Subset | DiagBase: 2,401 · DiagAttack: 1,088 |
| Language | English: 1,749 · Chinese: 1,740 |
| Dialogue | Single-turn: 2,560 · Multi-turn: 929 |
| Number of turns | 1: 2,560 · 2: 234 · 3: 674 · 4: 20 · 5: 1 (5,135 turns in total) |
| Taxonomy | 11 first-level · 34 second-level · 84 third-level labels |

## Record Format

```json
{
  "id": "DiagAttack-000003",
  "language": "zh",
  "messages": [
    {
      "role": "user",
      "content": "..."
    }
  ],
  "category": {
    "l1": "OSS-05",
    "l2": "受管制物质与物品 (Regulated Substances & Goods)",
    "l3": "毒品制造/交易/使用 (drugs)"
  }
}
```

## Fields

| Field | Type | Description |
|---|---|---|
| `id` | string | Unique identifier in the form `DiagBase-NNNNNN` or `DiagAttack-NNNNNN` |
| `language` | string | Prompt language: `en` or `zh` |
| `messages` | array | Ordered dialogue turns in OpenAI-compatible message format |
| `messages[].role` | string | Message role; the released prompts use `user` |
| `messages[].content` | string | Prompt text for the corresponding turn |
| `category.l1` | string | First-level taxonomy code, from `OSS-01` through `OSS-11` |
| `category.l2` | string | Bilingual second-level category name |
| `category.l3` | string | Bilingual third-level label name |

## ID Convention

- `DiagBase-*` identifies the 2,401 prompts synthesized directly from label specifications.
- `DiagAttack-*` identifies the 1,088 instruction-attack prompts rewritten from DiagBase seeds.
- Indices are six-digit, one-based, and continuous within each subset.

## Dialogue Representation

A single-turn prompt has one message. A multi-turn prompt stores two to five ordered user messages. During evaluation the messages are replayed turn by turn: each user message is sent together with the model's earlier replies, and every turn's answer is judged.

The structural definition is available in [`schema.json`](schema.json).
