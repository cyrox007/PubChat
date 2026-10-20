"""Bounded, deterministic moderation text simulation.

No arbitrary user-submitted regex, model calls or text persistence. Matches are
preview-only until the separate server-side write-path enforcement project ships.
"""
from __future__ import annotations

import re
import unicodedata

MAX_TEXT_CHARS = 4000
MAX_RULES = 200
MAX_RULE_CHARS = 120
MAX_MATCHES = 100
# Convert Latin lookalikes ONLY in words that also contain Cyrillic.
_LOOKALIKES = str.maketrans({
    "a": "а", "e": "е", "o": "о", "p": "р", "c": "с", "x": "х",
    "y": "у", "k": "к", "m": "м", "t": "т", "h": "н", "b": "в",
})
_LEET_RU = str.maketrans({"0": "о", "3": "з", "4": "ч", "6": "б"})
_RU_SUFFIXES = frozenset({
    "", "а", "я", "у", "ю", "е", "и", "ы", "о", "ом", "ем", "ой",
    "ый", "ий", "ая", "ое", "ые", "ого", "ему", "ому", "ыми",
    "ыми", "ых", "их", "ую", "ют", "ет", "ал", "ала", "али",
    "или", "ит", "ать", "ять", "ов", "ам", "ям", "ами", "ями",
})
_EN_SUFFIXES = frozenset({"", "s", "es", "ed", "ing", "er", "ers", "ly"})


def _canonical(word: str) -> str:
    word = unicodedata.normalize("NFKC", word).casefold().replace("ё", "е")
    if any("а" <= char <= "я" for char in word):
        word = word.translate(_LOOKALIKES).translate(_LEET_RU)
    return word


def _word_tokens(text: str) -> list[tuple[str, int, int]]:
    # No \w with unbounded regexes. Preserve original offsets and allow only
    # Unicode letters/marks/numbers. Invisible format chars never become words.
    words: list[tuple[str, int, int]] = []
    start = -1
    for index, char in enumerate(text + " "):
        kind = unicodedata.category(char)[0]
        valid = kind in ("L", "N", "M") and kind != "C"
        if valid and start < 0:
            start = index
        if not valid and start >= 0:
            token = _canonical(text[start:index])
            if token:
                words.append((token, start, index))
            start = -1
    return words


def _with_split_obfuscation(text: str, tokens: list[tuple[str, int, int]]) -> list[tuple[str, int, int]]:
    """Join isolated letters separated by short punctuation into a single candidate.

    Whitespace is NOT collapsed (prevents normal multi-word phrases from turning
    into accidental profanities). Span offsets always point into original text.
    """
    extra: list[tuple[str, int, int]] = []
    i = 0
    while i < len(tokens):
        j = i + 1
        while j < len(tokens) and j - i < 24:
            prev, end = tokens[j - 1][0], tokens[j - 1][2]
            current, start = tokens[j][0], tokens[j][1]
            separator = text[end:start]
            if (len(prev) != 1 or len(current) != 1 or not separator
                or len(separator) > 2 or any(ch.isspace() for ch in separator)
                or any(ch.isalnum() for ch in separator)):
                break
            j += 1
        if j - i >= 3:
            extra.append((
                _canonical("".join(v[0] for v in tokens[i:j])),
                tokens[i][1], tokens[j - 1][2],
            ))
            i = j
        else:
            i += 1
    return tokens + extra


def _same_or_stem(candidate: str, target: str, mode: str, language: str) -> bool:
    if mode != "stem":
        return candidate == target
    if len(target) < 4 or not candidate.startswith(target):
        return False
    endings = _RU_SUFFIXES if language == "ru" else _EN_SUFFIXES
    return candidate[len(target):] in endings


def simulate_rules(text: str, rules: list[dict], *, revision: int, mode: str) -> dict:
    """Pure preview, no mutation: stable, bounded matches and mask projection."""
    if len(text) > MAX_TEXT_CHARS:
        raise ValueError("simulation_text_too_long")
    if len(rules) > MAX_RULES:
        raise ValueError("too_many_moderation_rules")
    tokens = _word_tokens(text)
    candidate_tokens = _with_split_obfuscation(text, tokens)
    found: list[dict] = []
    for rule in rules:
        if not rule.get("enabled", True):
            continue
        match_mode = rule["match_mode"]
        forms = (rule["term"], *rule.get("variants", []))
        exceptions = {
            tuple(token[0] for token in _word_tokens(v)) for v in rule.get("exceptions", [])
        }
        for form in forms:
            phrase = [_canonical(token[0]) for token in _word_tokens(form)]
            if not phrase:
                continue
            if len(phrase) == 1:
                candidates = candidate_tokens
                for candidate, start, end in candidates:
                    if _same_or_stem(candidate, phrase[0], match_mode, rule["language"]) and (candidate,) not in exceptions:
                        found.append({
                            "rule_uid": str(rule["uid"]), "category": rule["category"],
                            "action": rule["action"], "start": start, "end": end,
                            "match_kind": "obfuscated" if (candidate, start, end) not in tokens else match_mode,
                        })
            elif match_mode == "phrase":
                for j in range(len(tokens) - len(phrase) + 1):
                    current = tuple(tok[0] for tok in tokens[j:j + len(phrase)])
                    if current == tuple(phrase) and current not in exceptions:
                        found.append({
                            "rule_uid": str(rule["uid"]), "category": rule["category"],
                            "action": rule["action"], "start": tokens[j][1],
                            "end": tokens[j + len(phrase) - 1][2],
                            "match_kind": "phrase",
                        })
    found.sort(key=lambda m: (m["start"], -(m["end"] - m["start"]), m["rule_uid"]))
    unique: list[dict] = []
    seen: set[tuple[str, int, int]] = set()
    for item in found:
        key = (item["rule_uid"], item["start"], item["end"])
        if key not in seen:
            seen.add(key)
            unique.append(item)
        if len(unique) == MAX_MATCHES:
            break
    # Use span-based masking, no raw matched text in events or stored decisions.
    masked = list(text)
    for item in unique:
        if item["action"] in {"mask", "reject", "hold"}:
            for pos in range(item["start"], item["end"]):
                if not masked[pos].isspace():
                    masked[pos] = "•"
    return {
        "revision": revision, "mode": mode,
        "enforced": False,  # No runtime content preflight yet: #146.
        "matches": unique,
        "preview": "".join(masked),
        "would_block": any(m["action"] in ("reject", "hold") for m in unique),
    }
