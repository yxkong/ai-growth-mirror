"""Shared JSON repair utilities for LLM responses."""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from enum import IntEnum
from typing import Any


def _strip_fences(raw: str) -> str:
    text = raw.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        text = "\n".join(lines[1:-1] if lines and lines[-1].strip() == "```" else lines[1:])
    return text.strip()


def _escape_newlines_in_strings(text: str) -> str:
    result: list[str] = []
    in_string = False
    escape_next = False
    for char in text:
        if escape_next:
            result.append(char)
            escape_next = False
            continue
        if char == "\\" and in_string:
            result.append(char)
            escape_next = True
            continue
        if char == '"':
            in_string = not in_string
            result.append(char)
            continue
        if in_string:
            if char == "\n":
                result.append("\\n")
                continue
            if char == "\r":
                result.append("\\r")
                continue
            if char == "\t":
                result.append("\\t")
                continue
        result.append(char)
    return "".join(result)


def _fix_unescaped_quotes(text: str) -> str:
    for _ in range(20):
        try:
            json.loads(text)
            return text
        except json.JSONDecodeError as exc:
            if exc.pos is None or exc.pos == 0:
                break
            repaired = False
            for index in range(exc.pos - 1, -1, -1):
                if text[index] == '"' and (index == 0 or text[index - 1] != "\\"):
                    text = text[:index] + '\\"' + text[index + 1 :]
                    repaired = True
                    break
            if not repaired:
                break
    return text


def _close_truncated_json(text: str) -> str:
    in_string = False
    escape_next = False
    stack: list[str] = []
    last_complete = 0
    stack_at_last_complete: list[str] = []
    for index, char in enumerate(text):
        if escape_next:
            escape_next = False
            continue
        if char == "\\" and in_string:
            escape_next = True
            continue
        if char == '"':
            in_string = not in_string
            continue
        if in_string:
            continue
        if char in ("{", "["):
            stack.append(char)
        elif char in ("}", "]"):
            if stack:
                stack.pop()
            if not stack:
                last_complete = index + 1
                stack_at_last_complete = []
                break
        elif char == "," and len(stack) == 1:
            last_complete = index + 1
            stack_at_last_complete = list(stack)
    truncated = text[:last_complete].rstrip().rstrip(",")
    for opener in stack_at_last_complete:
        truncated += "}" if opener == "{" else "]"
    return truncated


def _repair_strip_fences(text: str) -> str:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```[a-zA-Z0-9]*\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned)
    return cleaned.strip()


def _repair_trailing_commas(blob: str) -> str:
    return re.sub(r",(\s*[}\]])", r"\1", blob)


def _repair_extract_object(blob: str) -> str | None:
    match = re.search(r"(\{.*\}|\[.*\])", blob, re.DOTALL)
    return match.group(1) if match else None


def _fix_json(text: str) -> str:
    start = text.find("{")
    if start == -1:
        return text
    text = _escape_newlines_in_strings(text[start:])
    text = re.sub(r"//[^\n]*", "", text)
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.DOTALL)
    text = re.sub(r",\s*([}\]])", r"\1", text)
    text = re.sub(r"\bTrue\b", "true", text)
    text = re.sub(r"\bFalse\b", "false", text)
    text = re.sub(r"\bNone\b", "null", text)
    try:
        json.loads(text)
        return text
    except json.JSONDecodeError:
        pass
    end = text.rfind("}")
    if end != -1:
        candidate = text[: end + 1]
        try:
            json.loads(candidate)
            return candidate
        except json.JSONDecodeError:
            pass
    return _close_truncated_json(text)


def decode_json_payload(raw: str) -> Any:
    text = _strip_fences(raw)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    object_start = text.find("{")
    if object_start != -1:
        try:
            value, _ = json.JSONDecoder().raw_decode(text, object_start)
            return value
        except json.JSONDecodeError:
            pass
    fixed = _fix_json(text)
    try:
        return json.loads(fixed)
    except json.JSONDecodeError:
        return json.loads(_fix_unescaped_quotes(fixed))


class JSONRepairLevel(IntEnum):
    L1_STRIP_MARKDOWN = 1
    L2_TRAILING_COMMA = 2
    L3_EXTRACT_OBJECT = 3
    L4_HEURISTIC_WRAPPER = 4


@dataclass
class LLMResponse:
    text: str
    parsed_json: Any | None = None
    repair_levels_used: list[JSONRepairLevel] | None = None


def repair_json(text: str) -> tuple[Any, list[JSONRepairLevel]]:
    levels: list[JSONRepairLevel] = []
    current = text

    def attempt(candidate: str) -> Any | None:
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            return None

    stripped = _repair_strip_fences(current)
    if stripped != current:
        levels.append(JSONRepairLevel.L1_STRIP_MARKDOWN)
    current = stripped
    parsed = attempt(current)
    if parsed is not None:
        return parsed, levels

    trimmed = _repair_trailing_commas(current)
    if trimmed != current:
        levels.append(JSONRepairLevel.L2_TRAILING_COMMA)
        current = trimmed
        parsed = attempt(current)
        if parsed is not None:
            return parsed, levels

    extracted = _repair_extract_object(current)
    if extracted:
        levels.append(JSONRepairLevel.L3_EXTRACT_OBJECT)
        current = _repair_trailing_commas(extracted)
        parsed = attempt(current)
        if parsed is not None:
            return parsed, levels

    wrapped = _fix_json(current)
    if wrapped != current:
        levels.append(JSONRepairLevel.L4_HEURISTIC_WRAPPER)
        parsed = attempt(wrapped)
        if parsed is not None:
            return parsed, levels

    raise json.JSONDecodeError("Unable to repair JSON", text, 0)
