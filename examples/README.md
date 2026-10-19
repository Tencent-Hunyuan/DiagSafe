# DiagSafe Examples

[`joined_sample.json`](joined_sample.json) demonstrates how one prompt connects to its prompt-level rubric and taxonomy specification.

## Relationship

```text
prompt.id ─────────── rubric.id
prompt.category.l3 ── taxonomy.类目名称.三级类目
```

The joined representation is provided for documentation and integration examples. The released benchmark preserves prompts, rubrics, and taxonomy entries in their dedicated files under [`data/`](../data/).
