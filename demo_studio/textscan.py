"""Text checks shared by the validator and the gate: banned terms, contact details, dashes, hype."""
from __future__ import annotations

import re
from dataclasses import dataclass

DASHES = {"\u2014": "em dash", "\u2013": "en dash"}

EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
# a phone number stays on one line: a column of figures, one per line, is not one
PHONE_CANDIDATE = re.compile(r"(?<![\w/])\+?\(?\d[\d \t().-]{7,}\d(?![\w/])")
ISO_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
URL = re.compile(
    r"\bhttps?://[^\s\"'<>]+|\bwww\.[^\s\"'<>]+|"
    r"\b[a-z0-9][a-z0-9-]*(?:\.[a-z0-9-]+)*\.(?:com|net|org|io|co|ai|app|dev|us|uk|biz|info|me|xyz|cloud)\b",
    re.IGNORECASE,
)
# Words that read as sales copy. A warning, not a failure.
HYPE = [
    "revolutionary", "seamless", "seamlessly", "cutting-edge", "game-changer", "game changer",
    "effortless", "effortlessly", "supercharge", "unlock", "best-in-class", "world-class",
    "next-gen", "next generation", "magic", "magical", "powerful", "robust", "leverage",
    "skyrocket", "blazing", "unleash", "transformative", "state-of-the-art",
]


@dataclass
class Hit:
    kind: str       # banned | email | phone | url | dash | hype
    match: str
    where: str

    def safe(self) -> str:
        """A description that is safe to print (banned-term hits are shown, they are our own list)."""
        return f"{self.kind}: {self.match!r} in {self.where}"


def find_dashes(text: str, where: str) -> list[Hit]:
    return [Hit("dash", name, where) for ch, name in DASHES.items() if ch in text]


def find_hype(text: str, where: str) -> list[Hit]:
    low = text.lower()
    return [Hit("hype", w, where) for w in HYPE if re.search(rf"(?<![\w-]){re.escape(w)}(?![\w-])", low)]


def find_banned(text: str, terms: list[str], where: str) -> list[Hit]:
    hits = []
    low = text.lower()
    for t in terms:
        if t and t.lower() in low:
            hits.append(Hit("banned", t, where))
    return hits


def find_contacts(text: str, where: str, allowed_hosts: list[str] | None = None) -> list[Hit]:
    allowed = [h.lower() for h in (allowed_hosts or [])] + ["localhost", "127.0.0.1"]
    hits = [Hit("email", m.group(0), where) for m in EMAIL.finditer(text)]
    for m in PHONE_CANDIDATE.finditer(text):
        s = m.group(0).strip()
        digits = re.sub(r"\D", "", s)
        if len(digits) < 9 or ISO_DATE.match(s):
            continue
        hits.append(Hit("phone", s, where))
    for m in URL.finditer(text):
        s = m.group(0)
        if any(a in s.lower() for a in allowed):
            continue
        if "@" in s:  # already counted as an email
            continue
        hits.append(Hit("url", s, where))
    return hits


def scan_public(text: str, where: str, banned: list[str], allowed_hosts: list[str] | None = None) -> list[Hit]:
    return find_banned(text, banned, where) + find_contacts(text, where, allowed_hosts) + find_dashes(text, where)
