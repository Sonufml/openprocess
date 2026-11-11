"""Classify a ProcessSpec against the process framework and ITIL 4.

Scoring is deliberately transparent rather than clever: a reviewer has to be
able to see why a process landed where it did, and overrule it. A black-box
classifier would be worse than none, because nobody would trust the register.
"""

from __future__ import annotations

import re
from functools import lru_cache

from .schema import ProcessSpec
from .frameworks import ITIL4_PRACTICES, load_pcf, PcfEntry

STOPWORDS = {
    "the", "and", "for", "with", "from", "into", "manage", "management",
    "process", "processes", "it", "of", "to", "a", "an", "is", "are", "on",
}


def _tokens(text: str) -> set[str]:
    words = re.findall(r"[a-z]+", (text or "").lower())
    return {w for w in words if len(w) > 2 and w not in STOPWORDS}


def process_text(spec: ProcessSpec) -> str:
    """All the free text in a model, for keyword matching."""
    parts = [spec.name, spec.purpose, spec.scope, spec.trigger]
    parts += [n.name for n in spec.nodes]
    parts += [n.description for n in spec.nodes]
    parts += [n.system for n in spec.nodes]
    parts += [n.control for n in spec.nodes]
    parts += [l.name for l in spec.lanes]
    parts += [f.name for f in spec.flows]
    return " ".join(p for p in parts if p)


@lru_cache(maxsize=1)
def _pcf():
    return load_pcf()


def classify_pcf(spec: ProcessSpec) -> tuple[PcfEntry | None, float]:
    entries, _ = _pcf()
    # only leaf-ish elements are useful targets; skip the bare category row
    candidates = [e for e in entries if e.level >= 2]
    if not candidates:
        return None, 0.0

    haystack = _tokens(process_text(spec))
    title_tokens = _tokens(spec.name)

    best, best_score = None, 0.0
    for entry in candidates:
        entry_tokens = _tokens(entry.name)
        if not entry_tokens:
            continue
        overlap = entry_tokens & haystack
        if not overlap:
            continue
        # base: share of the framework element's own words that appear
        score = len(overlap) / len(entry_tokens)
        # a hit in the process title counts double — it is the strongest signal
        score += 0.5 * len(entry_tokens & title_tokens) / len(entry_tokens)
        score = min(1.0, score)
        if score > best_score:
            best, best_score = entry, score

    return best, round(best_score, 3)


def classify_itil(spec: ProcessSpec) -> tuple[str, float, list[str]]:
    haystack = process_text(spec).lower()
    title = (spec.name or "").lower()

    best_name, best_score, best_hits = "", 0.0, []
    for practice in ITIL4_PRACTICES:
        hits = [k for k in practice["keywords"] if k in haystack]
        if not hits:
            continue
        score = len(hits) / len(practice["keywords"])
        score += 0.6 * sum(1 for k in practice["keywords"] if k in title)
        if score > best_score:
            best_name, best_score, best_hits = practice["name"], score, hits

    return best_name, round(min(1.0, best_score), 3), best_hits


def classify(spec: ProcessSpec) -> dict:
    """Annotate the spec in place and return an explanation for the UI."""
    entry, confidence = classify_pcf(spec)
    practice, practice_conf, hits = classify_itil(spec)

    spec.pcf_id = entry.id if entry else ""
    spec.pcf_name = entry.name if entry else ""
    spec.pcf_confidence = confidence
    spec.itil_practice = practice

    _, source_label = _pcf()
    return {
        "pcf_id": spec.pcf_id,
        "pcf_name": spec.pcf_name,
        "pcf_confidence": confidence,
        "pcf_source": source_label,
        "pcf_official": bool(entry and entry.is_official),
        "itil_practice": practice,
        "itil_confidence": practice_conf,
        "itil_evidence": hits[:6],
    }
