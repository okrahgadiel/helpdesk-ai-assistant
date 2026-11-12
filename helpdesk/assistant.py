"""Retrieval-augmented helpdesk assistant with guardrails.

Pipeline: redact PII -> retrieve KB sections (BM25) -> confidence gate -> generate a grounded answer
(Azure OpenAI / OpenAI when configured, otherwise extractive) -> cite sources -> triage if unresolved.
"""
from __future__ import annotations

import json
import os
import re
import urllib.request
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import List, Optional

from .retriever import BM25, Chunk, load_kb
from .triage import Triager

ROOT = Path(__file__).resolve().parent.parent
MIN_SCORE = 4.0  # below this, the KB does not cover the question -> hand off to a human

PII_PATTERNS = [
    (re.compile(r"\b\d{3}-\d{2}-\d{4}\b"), "[SSN]"),
    (re.compile(r"\b(?:\d[ -]?){13,16}\b"), "[CARD]"),
    (re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+"), "[EMAIL]"),
    (re.compile(r"\(?\b\d{3}\)?[ .-]?\d{3}[ .-]?\d{4}\b"), "[PHONE]"),
    (re.compile(r"(?i)(password\s*(?:is|:|=)\s*)\S+"), r"\1[REDACTED]"),
]

SYSTEM_PROMPT = """You are an IT service desk assistant. Answer ONLY using the numbered knowledge base
excerpts provided. Give short numbered steps. Cite sources like [1]. If the excerpts do not answer the
question, say you don't know and recommend opening a ticket. Never ask for or repeat passwords."""


def redact(text: str) -> str:
    for pattern, repl in PII_PATTERNS:
        text = pattern.sub(repl, text)
    return text


def _search_text(text: str) -> str:
    """Drop redaction placeholders so e.g. [EMAIL] doesn't match the Outlook article."""
    return re.sub(r"\[[A-Z_]+\]", " ", text)


@dataclass
class Answer:
    question: str
    answer: str
    sources: List[str]
    grounded: bool
    mode: str  # azure-openai | openai | extractive | handoff
    triage: Optional[dict] = None
    scores: List[float] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


class HelpdeskAssistant:
    def __init__(self, kb_dir: Path = ROOT / "knowledge_base", tickets: Path = ROOT / "data" / "tickets.csv"):
        self.chunks = load_kb(kb_dir)
        self.index = BM25(self.chunks)
        self.triager = Triager(tickets)

    def ask(self, question: str, k: int = 3) -> Answer:
        clean = redact(question)
        query = _search_text(clean)
        hits = self.index.search(query, k=k)
        scores = [round(s, 2) for _, s in hits]
        if not hits or hits[0][1] < MIN_SCORE:
            t = self.triager.triage(query)
            return Answer(clean, "I couldn't find this in the knowledge base, so I've drafted a ticket for "
                                 f"the service desk: category **{t.category}**, priority **{t.priority}** "
                                 f"({t.priority_reason}).", [], False, "handoff", asdict(t), scores)
        # keep sections that are close to the best match
        context = [c for c, s in hits if s >= hits[0][1] * 0.6]
        sources = list(dict.fromkeys(c.citation for c in context))
        mode, text = self._generate(clean, context)
        triage = asdict(self.triager.triage(query))
        return Answer(clean, text, sources, True, mode, triage, scores)

    # ---- generation -------------------------------------------------------------------------
    def _generate(self, question: str, context: List[Chunk]):
        prompt = "\n\n".join(f"[{i}] {c.citation}\n{c.text}" for i, c in enumerate(context, 1))
        messages = [{"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": f"Knowledge base excerpts:\n{prompt}\n\nQuestion: {question}"}]
        try:
            if os.getenv("AZURE_OPENAI_ENDPOINT") and os.getenv("AZURE_OPENAI_API_KEY"):
                return "azure-openai", self._azure(messages)
            if os.getenv("OPENAI_API_KEY"):
                return "openai", self._openai(messages)
        except Exception as exc:  # fall back rather than fail the user
            print(f"LLM call failed ({exc}); using extractive answer")
        return "extractive", self._extractive(context)

    @staticmethod
    def _extractive(context: List[Chunk]) -> str:
        best = context[0]
        return f"**{best.title} — {best.section}**\n{best.text}\n\nSource: [1] {best.citation}"

    @staticmethod
    def _post(url: str, headers: dict, body: dict) -> str:
        req = urllib.request.Request(url, data=json.dumps(body).encode(), headers={"Content-Type": "application/json", **headers})
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read())["choices"][0]["message"]["content"]

    def _azure(self, messages) -> str:
        endpoint = os.environ["AZURE_OPENAI_ENDPOINT"].rstrip("/")
        deployment = os.getenv("AZURE_OPENAI_DEPLOYMENT", "gpt-4o-mini")
        version = os.getenv("AZURE_OPENAI_API_VERSION", "2024-06-01")
        url = f"{endpoint}/openai/deployments/{deployment}/chat/completions?api-version={version}"
        return self._post(url, {"api-key": os.environ["AZURE_OPENAI_API_KEY"]},
                          {"messages": messages, "temperature": 0.1, "max_tokens": 400})

    def _openai(self, messages) -> str:
        return self._post("https://api.openai.com/v1/chat/completions",
                          {"Authorization": f"Bearer {os.environ['OPENAI_API_KEY']}"},
                          {"model": os.getenv("OPENAI_MODEL", "gpt-4o-mini"), "messages": messages, "temperature": 0.1})
