"""Evaluate complaint analysis. Run: python eval_ai.py
Uses the REAL LLM when LLM_API_KEY is set, otherwise the fallback rules (the floor, not the product).
Labels follow a written policy in evaluation/complaints.json. Hand-labelled, small, not real campus data."""
import json
import os
import pathlib
import time
from ai_service import analyze_complaint
from schemas import Category

ROOT = pathlib.Path(__file__).parent / "evaluation"
ORD = {"Low": 0, "Medium": 1, "High": 2}


def run():
    items = json.loads((ROOT / "complaints.json").read_text())["items"]
    live = bool(os.getenv("LLM_API_KEY"))
    rows = []
    for it in items:
        out = analyze_complaint(it["text"])
        r = out.result
        ok = r.category.value in it.get("accept", [it["category"]])
        rows.append({"text": it["text"], "tag": it.get("tag", ""), "gold_cat": it["category"], "pred_cat": r.category.value, "cat_ok": ok,
                     "gold_pri": it["priority"], "pred_pri": r.priority.value, "mode": out.mode, "review": r.review_required})
        if live:
            time.sleep(0.4)  # stay under free-tier rate limits
    n = len(rows)
    f1s = {}
    for c in Category:
        tp = sum(1 for x in rows if x["pred_cat"] == c.value and x["cat_ok"])
        fp = sum(1 for x in rows if x["pred_cat"] == c.value and not x["cat_ok"])
        fn = sum(1 for x in rows if x["gold_cat"] == c.value and not x["cat_ok"])
        sup = sum(1 for x in rows if x["gold_cat"] == c.value)
        p, r_ = tp / (tp + fp) if tp + fp else 0.0, tp / (tp + fn) if tp + fn else 0.0
        f1s[c.value] = {"precision": p, "recall": r_, "f1": 2 * p * r_ / (p + r_) if p + r_ else 0.0, "support": sup}
    inj = [x for x in rows if x["tag"] == "prompt-injection"][0]
    return {"mode": "llm" if live else "fallback-rules", "n": n,
            "category_accuracy": sum(x["cat_ok"] for x in rows) / n,
            "macro_f1": sum(v["f1"] for v in f1s.values() if v["support"]) / sum(1 for v in f1s.values() if v["support"]),
            "per_class": f1s,
            "priority_exact": sum(x["gold_pri"] == x["pred_pri"] for x in rows) / n,
            "priority_within_one": sum(abs(ORD[x["gold_pri"]] - ORD[x["pred_pri"]]) <= 1 for x in rows) / n,
            "llm_structured_output_rate": sum(x["mode"] == "llm" for x in rows) / n,
            "flagged_for_review": sum(x["review"] for x in rows) / n,
            "injection_case": {"pred_priority": inj["pred_pri"], "mode": inj["mode"], "marked_low": inj["pred_pri"] == "Low"},
            "misses": [x for x in rows if not x["cat_ok"] or x["gold_pri"] != x["pred_pri"]]}


if __name__ == "__main__":
    r = run()
    print(f"mode={r['mode']}  n={r['n']}")
    print(f"category accuracy {r['category_accuracy']:.2f} | macro-F1 {r['macro_f1']:.2f} | priority exact {r['priority_exact']:.2f} | within one level {r['priority_within_one']:.2f}")
    print(f"LLM structured-output rate {r['llm_structured_output_rate']:.2f} | flagged for staff review {r['flagged_for_review']:.2f}")
    for c, v in r["per_class"].items():
        print(f"  {c:20s} P={v['precision']:.2f} R={v['recall']:.2f} F1={v['f1']:.2f} (n={v['support']})")
    print("prompt-injection case:", r["injection_case"])
    print(f"{len(r['misses'])} items with a category or priority miss (see evaluation/ai_results.json)")
    (ROOT / "ai_results.json").write_text(json.dumps(r, indent=1))
