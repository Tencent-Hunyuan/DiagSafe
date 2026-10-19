# -*- coding: utf-8 -*-
"""Render a per-prompt rubric template into a complete judge prompt.

Follows the protocol documented in data/rubrics/README.md: the rubric
template contains JSON braces in its output contract, so the three named
placeholders are replaced directly with str.replace().
"""

import json
from typing import Any
from typing import Dict
from typing import List


def render_rubric(template: str, prompt: Dict[str, Any], answer: str,
                  history: 'List[Dict[str, str]] | None' = None) -> str:
    """Render one rubric for an evaluated response.

    :param template: Rubric template with {question}, {answer} and
        {safety_categories} placeholders.
    :param prompt: Prompt record from DiagSafe_bench_3489.jsonl.
    :param answer: The evaluated model's answer text.
    :param history: Ordered [{'question', 'answer'}] pairs for earlier turns.
        When given, the block is inserted into the *template* right after the
        safety-category tag, before the answer is substituted, so its position
        cannot be confused with the same string inside the answer.
    :return: The complete judge prompt.
    """
    question = json.dumps(prompt['messages'], ensure_ascii=False)
    categories = json.dumps(prompt['category'], ensure_ascii=False)
    if history:
        template = insert_history(template, history, prompt.get('language', 'en'))
    return (
        template
        .replace('{question}', question)
        .replace('{answer}', answer)
        .replace('{safety_categories}', categories)
    )


_HISTORY_LABELS = {
    'zh': {
        'anchor': '</安全类目>',
        'tag': '历史对话',
        'note': '以下为历史对话，可以作为理解本轮的上下文',
        'turn': '第{}轮',
        'user': '用户',
        'assistant': '助手',
    },
    'en': {
        'anchor': '</safety_categories>',
        'tag': 'conversation_history',
        'note': 'The following is the conversation history, which can be used as context '
                'for understanding the current turn',
        'turn': 'Turn {}',
        'user': 'User',
        'assistant': 'Assistant',
    },
}


def build_history_block(history: List[Dict[str, str]], language: str) -> str:
    """Build the `<conversation_history>` block for the earlier turns."""
    labels = _HISTORY_LABELS.get(language, _HISTORY_LABELS['en'])
    lines = [f'<{labels["tag"]}>', labels['note']]
    for index, pair in enumerate(history, 1):
        lines.extend([
            f'[{labels["turn"].format(index)}]',
            f'{labels["user"]}: {pair["question"]}',
            f'{labels["assistant"]}: {pair["answer"]}',
        ])
    lines.append(f'</{labels["tag"]}>')
    return '\n'.join(lines)


def insert_history(template: str, history: List[Dict[str, str]], language: str) -> str:
    """Insert earlier turns into a rubric template, right after the safety-category tag.

    The judge then reads the dialogue before the safety and usefulness items.
    Prefer the `history` argument of render_rubric(): inserting into the
    template before the answer is substituted keeps the anchor unambiguous even
    when the model's answer contains the tag itself.

    :param template: Rubric template, before or after rendering.
    :param history: Ordered [{'question', 'answer'}] pairs for earlier turns.
    :param language: Prompt language (`en` or `zh`); selects the block labels
        and the anchor tag.
    :return: The template with the history block inserted.
    """
    if not history:
        return template
    labels = _HISTORY_LABELS.get(language, _HISTORY_LABELS['en'])
    block = build_history_block(history, language)
    # The anchor occurs once in every released rubric, ahead of the answer
    # placeholder. Searching the template keeps it unambiguous.
    position = template.find(labels['anchor'])
    if position < 0:
        return template.rstrip() + '\n\n' + block + '\n'
    cut = position + len(labels['anchor'])
    return template[:cut] + '\n\n' + block + template[cut:]


def append_history(rendered: str, history: List[Dict[str, str]], language: str) -> str:
    """Insert earlier turns into a rendered rubric; kept for backwards compatibility.

    Prefer the `history` argument of render_rubric(), which inserts into the
    template before the answer is substituted.
    """
    return insert_history(rendered, history, language)
