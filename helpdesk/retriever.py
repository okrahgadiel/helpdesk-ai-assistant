"""Knowledge-base loading, section chunking, and BM25 retrieval (no external dependencies)."""
from __future__ import annotations

import math
import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Tuple

STOPWORDS = set("""a an and are as at be but by can do does for from has have how i if in into is it its my
me no not of on or our so that the their them then there these this to was we what when where which who
why will with you your yours am get got im ive dont cant wont""".split())

# Light synonym expansion so user phrasing matches KB phrasing.
SYNONYMS = {
    "locked": ["lockout"], "lock": ["lockout"], "forgot": ["reset", "password"], "pw": ["password"],
    "authenticator": ["mfa"], "2fa": ["mfa"], "phone": ["mfa"], "prompts": ["prompt"],
    "email": ["outlook", "mail"], "inbox": ["outlook", "mail"], "wifi": ["wi-fi", "wireless"],
    "internet": ["wi-fi", "network"], "laggy": ["slow"], "sluggish": ["slow"], "printing": ["printer", "print"],
    "camera": ["video", "teams"], "mic": ["microphone", "audio"], "folder": ["drive", "shared"],
    "permission": ["access"], "phish": ["phishing"], "scam": ["phishing"], "suspicious": ["phishing"],
    "bitlocker": ["recovery", "key"], "onboarding": ["new", "hire"],
}


def tokenize(text: str, expand: bool = False) -> List[str]:
    tokens = [t for t in re.findall(r"[a-z0-9][a-z0-9\-]*", text.lower()) if t not in STOPWORDS]
    tokens = [_stem(t) for t in tokens]
    if expand:
        tokens += [_stem(s) for t in list(tokens) for s in SYNONYMS.get(t, [])]
    return tokens


def _stem(t: str) -> str:
    for suffix in ("ing", "ed", "es", "s"):
        if len(t) > 4 and t.endswith(suffix):
            return t[: -len(suffix)]
    return t


@dataclass
class Chunk:
    doc_id: str
    title: str
    section: str
    text: str

    @property
    def citation(self) -> str:
        return f"{self.title} > {self.section}"


def load_kb(folder: Path) -> List[Chunk]:
    """Split each markdown article into one chunk per '## ' section, keeping the article title."""
    chunks: List[Chunk] = []
    for path in sorted(Path(folder).glob("*.md")):
        title, section, buf = path.stem, "Overview", []
        for line in path.read_text().splitlines():
            if line.startswith("# "):
                title = line[2:].strip()
            elif line.startswith("## "):
                if any(b.strip() for b in buf):
                    chunks.append(Chunk(path.stem, title, section, "\n".join(buf).strip()))
                section, buf = line[3:].strip(), []
            else:
                buf.append(line)
        if any(b.strip() for b in buf):
            chunks.append(Chunk(path.stem, title, section, "\n".join(buf).strip()))
    return chunks


class BM25:
    """Okapi BM25 ranking over chunks. Title and section are indexed with extra weight."""

    def __init__(self, chunks: List[Chunk], k1: float = 1.5, b: float = 0.75, title_boost: int = 3):
        self.chunks, self.k1, self.b = chunks, k1, b
        self.docs: List[Counter] = []
        for c in chunks:
            tokens = tokenize(c.text) + tokenize(f"{c.title} {c.section}") * title_boost
            self.docs.append(Counter(tokens))
        self.lengths = [sum(d.values()) for d in self.docs]
        self.avgdl = sum(self.lengths) / max(len(self.lengths), 1)
        df: Dict[str, int] = Counter(term for d in self.docs for term in d)
        n = len(self.docs)
        self.idf = {t: math.log(1 + (n - f + 0.5) / (f + 0.5)) for t, f in df.items()}

    def search(self, query: str, k: int = 3) -> List[Tuple[Chunk, float]]:
        terms = tokenize(query, expand=True)
        scored = []
        for i, doc in enumerate(self.docs):
            score = 0.0
            for t in terms:
                if t not in doc:
                    continue
                tf = doc[t]
                norm = tf * (self.k1 + 1) / (tf + self.k1 * (1 - self.b + self.b * self.lengths[i] / self.avgdl))
                score += self.idf[t] * norm
            if score > 0:
                scored.append((self.chunks[i], score))
        scored.sort(key=lambda x: -x[1])
        return scored[:k]
