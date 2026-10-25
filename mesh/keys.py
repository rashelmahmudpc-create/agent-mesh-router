"""API key ঘোরানো (rotation) — একটা key শেষ হলে পরেরটায় যায়।

নাম দেওয়ার নিয়ম:
    OPENROUTER_API_KEY
    OPENROUTER_API_KEY_2
    OPENROUTER_API_KEY_3
    ... (২০ নম্বর পর্যন্ত)

সতর্কতা: হাজার হাজার অ্যাকাউন্ট ঘোরানো ঠিক নয় — দরকার হলে ২-৩টা key যথেষ্ট।
"""

from __future__ import annotations

import os

MAX_SLOTS = 20


def collect_keys(names: list[str], environ: dict[str, str] | None = None) -> list[tuple[str, str]]:
    """['OPENROUTER_API_KEY'] → [('OPENROUTER_API_KEY', 'sk-or-...'), ('OPENROUTER_API_KEY_2', 'sk-or-...')]"""
    env = environ if environ is not None else os.environ
    found: list[tuple[str, str]] = []
    for base in names:
        for slot in range(1, MAX_SLOTS + 1):
            var = base if slot == 1 else f"{base}_{slot}"
            value = (env.get(var) or "").strip()
            if value:
                found.append((var, value))
    return found


def expand_env_value(value: str, environ: dict[str, str] | None = None) -> str:
    """'$OPENROUTER_API_KEY' → আসল key। না থাকলে খালি স্ট্রিং।"""
    env = environ if environ is not None else os.environ
    value = value or ""
    if value.startswith("$"):
        return (env.get(value[1:]) or "").strip()
    return value
