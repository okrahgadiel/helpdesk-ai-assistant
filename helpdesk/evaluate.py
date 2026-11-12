"""Offline evaluation: retrieval hit@1 / hit@3 / MRR, out-of-scope refusal rate, and triage accuracy."""
from __future__ import annotations

import json
from pathlib import Path

from .assistant import MIN_SCORE, ROOT, HelpdeskAssistant


def evaluate(eval_path: Path = ROOT / "data" / "eval_set.json", verbose: bool = True) -> dict:
    data = json.loads(Path(eval_path).read_text())
    bot = HelpdeskAssistant()

    hit1 = hit3 = rr = 0.0
    misses = []
    for item in data["questions"]:
        ranked = [c.doc_id for c, _ in bot.index.search(item["q"], k=3)]
        if ranked[:1] == [item["doc"]]:
            hit1 += 1
        if item["doc"] in ranked:
            hit3 += 1
            rr += 1 / (ranked.index(item["doc"]) + 1)
        else:
            misses.append((item["q"], item["doc"], ranked))
    n = len(data["questions"])

    refused = sum(1 for q in data["out_of_scope"] if bot.ask(q).mode == "handoff")

    cat_ok = pri_ok = 0
    for t in data["triage"]:
        r = bot.triager.triage(t["text"])
        cat_ok += r.category == t["category"]
        pri_ok += r.priority == t["priority"]
    m = len(data["triage"])

    results = {
        "retrieval_hit@1": round(hit1 / n, 3),
        "retrieval_hit@3": round(hit3 / n, 3),
        "retrieval_mrr": round(rr / n, 3),
        "out_of_scope_handoff_rate": round(refused / len(data["out_of_scope"]), 3),
        "triage_category_accuracy": round(cat_ok / m, 3),
        "triage_priority_accuracy": round(pri_ok / m, 3),
        "confidence_threshold": MIN_SCORE,
    }
    if verbose:
        for k, v in results.items():
            print(f"{k:<28} {v}")
        for q, want, got in misses:
            print(f"  MISS: {q!r} expected {want}, got {got}")
    return results
