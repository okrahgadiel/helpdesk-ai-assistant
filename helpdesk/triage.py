"""Ticket triage: Naive Bayes category classifier + explainable priority rules."""
from __future__ import annotations

import csv
import math
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Tuple

from .retriever import tokenize


class NaiveBayes:
    """Multinomial Naive Bayes with Laplace smoothing, implemented from scratch."""

    def __init__(self, alpha: float = 1.0):
        self.alpha = alpha
        self.class_counts: Counter = Counter()
        self.word_counts: Dict[str, Counter] = defaultdict(Counter)
        self.vocab: set = set()

    def fit(self, texts: List[str], labels: List[str]) -> "NaiveBayes":
        for text, label in zip(texts, labels):
            self.class_counts[label] += 1
            for tok in tokenize(text, expand=True):
                self.word_counts[label][tok] += 1
                self.vocab.add(tok)
        return self

    def predict_proba(self, text: str) -> Dict[str, float]:
        tokens = tokenize(text, expand=True)
        total = sum(self.class_counts.values())
        v = len(self.vocab)
        logp = {}
        for label, n in self.class_counts.items():
            denom = sum(self.word_counts[label].values()) + self.alpha * v
            lp = math.log(n / total)
            for tok in tokens:
                lp += math.log((self.word_counts[label][tok] + self.alpha) / denom)
            logp[label] = lp
        m = max(logp.values())
        exp = {k: math.exp(val - m) for k, val in logp.items()}
        z = sum(exp.values())
        return {k: val / z for k, val in sorted(exp.items(), key=lambda kv: -kv[1])}

    def predict(self, text: str) -> Tuple[str, float]:
        label, p = next(iter(self.predict_proba(text).items()))
        return label, p


# Priority is rule-based on purpose: service desks need decisions they can explain and audit.
PRIORITY_RULES: List[Tuple[str, List[str], str]] = [
    ("P1", ["clicked", "entered my password", "ransomware", "breach", "hacked", "compromised",
            "everyone", "whole floor", "entire", "outage", "all users", "down for"], "security incident or widespread outage"),
    ("P2", ["can't work", "cannot work", "locked out", "can't sign in", "cannot sign in", "deadline",
            "customer", "store", "payroll", "urgent"], "single user blocked from working"),
    ("P3", ["slow", "not syncing", "intermittent", "sometimes", "keeps"], "degraded but workable"),
]


def priority(text: str) -> Tuple[str, str]:
    lower = text.lower()
    for level, phrases, reason in PRIORITY_RULES:
        hit = next((p for p in phrases if p in lower), None)
        if hit:
            return level, f"{reason} (matched '{hit}')"
    return "P4", "request or minor issue"


@dataclass
class Triage:
    category: str
    confidence: float
    priority: str
    priority_reason: str


class Triager:
    def __init__(self, tickets_csv: Path):
        rows = list(csv.DictReader(open(tickets_csv)))
        self.model = NaiveBayes().fit([r["text"] for r in rows], [r["category"] for r in rows])

    def triage(self, text: str) -> Triage:
        cat, conf = self.model.predict(text)
        pri, why = priority(text)
        return Triage(cat, round(conf, 2), pri, why)
