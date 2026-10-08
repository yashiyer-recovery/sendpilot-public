"""Extraction eval harness (PRD §15.5).

Field-level precision/recall over a labeled corpus, gated in CI so an extraction
regression fails the build before it can reach the review UI. Runs the
deterministic tabular path (no API key required).

    python tests/eval/run_eval.py [dataset.jsonl]
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from sendpilot.extraction.orchestrator import _extract_pipeline

FIELDS = ["recipient_email", "subject", "body"]
THRESHOLD = 0.9


def evaluate(path: str) -> tuple[float, float, dict[str, int]]:
    cases = [json.loads(line) for line in Path(path).read_text().splitlines() if line.strip()]
    tp = {f: 0 for f in FIELDS}
    pred_total = gold_total = 0
    for case in cases:
        _, _, records, _, _ = _extract_pipeline(case["content"].encode(), case["mime"], "doc")
        pred = {(r.recipient_email or "").lower(): r for r in records}
        gold = {g["recipient_email"].lower(): g for g in case["gold"]}
        pred_total += len(records) * len(FIELDS)
        gold_total += len(case["gold"]) * len(FIELDS)
        for email, g in gold.items():
            p = pred.get(email)
            if p is None:
                continue
            for f in FIELDS:
                if (getattr(p, f) or "").strip() == (g[f] or "").strip():
                    tp[f] += 1
    matched = sum(tp.values())
    precision = matched / pred_total if pred_total else 0.0
    recall = matched / gold_total if gold_total else 0.0
    return precision, recall, tp


def main() -> int:
    path = sys.argv[1] if len(sys.argv) > 1 else str(
        Path(__file__).parent / "datasets" / "extraction_eval.jsonl"
    )
    precision, recall, tp = evaluate(path)
    print(f"precision={precision:.3f} recall={recall:.3f} field_tp={tp}")
    if precision < THRESHOLD or recall < THRESHOLD:
        print(f"EVAL FAILED (threshold {THRESHOLD})")
        return 1
    print("EVAL OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
