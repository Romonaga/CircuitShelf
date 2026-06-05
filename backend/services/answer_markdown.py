from __future__ import annotations

import re
from typing import Any, Iterable


_HORIZONTAL_RULE_RE = re.compile(r"\s+---\s+")
_HEADING_RE = re.compile(r"(?<!\n)\s+(#{1,6}\s+)")
_HEADING_TABLE_RE = re.compile(r"^(#{1,6}\s+[^|\n]+?)\s+(\|)", re.MULTILINE)
_NUMBERED_RE = re.compile(r"(?<=[.:;])\s+(\d+\.\s+)")
_BULLET_RE = re.compile(r"(?<=[.:;])\s+-\s+")
_EXCESSIVE_BLANKS_RE = re.compile(r"\n{3,}")
_TABLE_SEPARATOR_RE = re.compile(r"^\|?\s*:?-{3,}:?\s*(?:\|\s*:?-{3,}:?\s*)+\|?$")


def normalize_answer_markdown(answer: Any) -> str:
    """Return display-oriented Markdown without changing the technical content.

    The local and cloud finalizers sometimes preserve Markdown markers but flatten
    the whole answer into one line. That is usable as LLM context but unreadable
    for people, and GFM tables/headings only render when markers start on lines.
    """

    text = str(answer or "").replace("\r\n", "\n").replace("\r", "\n").strip()
    if not text:
        return ""

    text = _HORIZONTAL_RULE_RE.sub("\n\n---\n\n", text)
    text = _HEADING_RE.sub(r"\n\n\1", text)
    text = _NUMBERED_RE.sub(r"\n\1", text)
    text = _BULLET_RE.sub("\n- ", text)
    text = _HEADING_TABLE_RE.sub(r"\1\n\n\2", text)
    text = _normalize_repeated_inline_bullets(text)
    text = _normalize_pipe_tables(text)
    text = "\n".join(line.rstrip() for line in text.splitlines())
    return _EXCESSIVE_BLANKS_RE.sub("\n\n", text).strip()


def display_chat_history_from_turns(turns: Iterable[dict[str, Any]] | None) -> list[list[str]]:
    history: list[list[str]] = []
    for turn in turns or []:
        question = str(turn.get("question") or "").strip()
        answer = normalize_answer_markdown(turn.get("answer"))
        if question and answer:
            history.append([question, answer])
    return history


def _normalize_pipe_tables(text: str) -> str:
    normalized_lines: list[str] = []
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.count("|") < 4:
            normalized_lines.append(line)
            continue

        if "\n" not in line and _looks_like_flat_table(stripped):
            normalized_lines.extend(_split_flat_table(stripped))
        else:
            normalized_lines.append(line)
    return "\n".join(normalized_lines)


def _normalize_repeated_inline_bullets(text: str) -> str:
    lines = []
    for line in text.splitlines():
        if line.count(" - ") >= 2:
            lines.append(line.replace(" - ", "\n- "))
        else:
            lines.append(line)
    return "\n".join(lines)


def _looks_like_flat_table(line: str) -> bool:
    return "|---" in line or "---|" in line


def _split_flat_table(line: str) -> list[str]:
    cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
    cells = [cell for cell in cells if cell]
    separator_index = next((index for index, cell in enumerate(cells) if re.fullmatch(r":?-{3,}:?", cell)), -1)
    if separator_index <= 0:
        return [line]

    column_count = separator_index
    if column_count < 2:
        return [line]

    rows: list[list[str]] = []
    prefix = cells[:separator_index]
    rows.append(prefix)
    rows.append(cells[separator_index:separator_index + column_count])
    remaining = cells[separator_index + column_count:]
    while remaining:
        row = remaining[:column_count]
        remaining = remaining[column_count:]
        if len(row) < column_count:
            row.extend([""] * (column_count - len(row)))
        rows.append(row)

    rendered = [_render_table_row(row) for row in rows]
    if len(rendered) >= 2 and not _TABLE_SEPARATOR_RE.match(rendered[1]):
        return [line]
    return rendered


def _render_table_row(cells: list[str]) -> str:
    return "| " + " | ".join(cells) + " |"
