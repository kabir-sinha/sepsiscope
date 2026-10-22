"""Mask personal values before anything is printed."""

from __future__ import annotations

import re


def mask(value: str) -> str:
    """Keep the first character of each word: "Jane Doe" -> "J**** D****"."""
    return " ".join(word[:1] + "****" for word in value.split()) or "****"


def mask_email(address: str) -> str:
    """Hide the local part, keep the domain: "jane@example.org" -> "j****@example.org"."""
    local, _, domain = address.partition("@")
    return f"{local[:1]}****@{domain}"


def mask_offset(offset: str) -> str:
    """A timezone offset reveals location: "+0100" -> "+0***"."""
    return offset[:2] + "***"


def mask_values(text: str, values: tuple[str, ...]) -> str:
    """Replace every listed value (case-insensitive) in ``text`` by its masked form."""
    for value in sorted(values, key=len, reverse=True):
        text = re.sub(re.escape(value), mask(value), text, flags=re.IGNORECASE)
    return text
