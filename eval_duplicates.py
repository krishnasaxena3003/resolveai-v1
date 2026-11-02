"""Tune and report duplicate detection. Run: python eval_duplicates.py
Tunes scorer + threshold on the 'dev' pairs only, then reports on the untouched 'test' pairs."""
import json
import pathlib

DATA = json.loads((pathlib.Path(__file__).parent / "evaluation" / "duplicate_pairs.json").read_text())["pairs"]
from duplicate_service import legacy_similarity, similarity

SCORERS = {"legacy_token_set_ratio": lambda p: legacy_similarity(p["a"], p["loc_a"], p["b"], p["loc_b"]),
           "dice_issue_words+place_penalty": lambda p: similarity(p["a"], p["loc_a"], p["b"], p["loc_b"])}


def metrics(scorer, rows, t):
    tp = fp = fn = tn = 0
    for p in rows:
        pred, y = scorer(p) >= t, bool(p["duplicate"])
        tp += pred and y; fp += pred and not y; fn += (not pred) and y; tn += (not pred) and not y
    pr = tp / (tp + fp) if tp + fp else 0.0
    rc = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * pr * rc / (pr + rc) if pr + rc else 0.0
    return {"precision": pr, "recall": rc, "f1": f1, "fpr": fp / (fp + tn) if fp + tn else 0.0, "tp": tp, "fp": fp, "fn": fn, "tn": tn}


def run():
    dev = [p for p in DATA if p["split"] == "dev"]
    test = [p for p in DATA if p["split"] == "test"]
    best = None
    for name, sc in [("dice_issue_words+place_penalty", SCORERS["dice_issue_words+place_penalty"])]:
        for t in range(30, 100, 5):
            m = metrics(sc, dev, t)
            key = (round(m["f1"], 6), m["precision"], t)
            if best is None or key > best[0]:
                best = (key, name, t, m)
    _, name, t, dev_m = best
    return {"n_dev": len(dev), "n_test": len(test), "chosen": {"scorer": name, "threshold": t},
            "dev_at_chosen": dev_m, "test_at_chosen": metrics(SCORERS[name], test, t),
            "baseline_test_current_default": metrics(SCORERS["legacy_token_set_ratio"], test, 70),
            "baseline_dev_current_default": metrics(SCORERS["legacy_token_set_ratio"], dev, 70)}


if __name__ == "__main__":
    r = run()
    f = lambda m: f"P={m['precision']:.2f} R={m['recall']:.2f} F1={m['f1']:.2f} FPR={m['fpr']:.2f} (TP{m['tp']} FP{m['fp']} FN{m['fn']} TN{m['tn']})"
    print(f"pairs: dev={r['n_dev']} test={r['n_test']}")
    print("first version (RapidFuzz token_set_ratio @70)  dev :", f(r["baseline_dev_current_default"]))
    print("first version (RapidFuzz token_set_ratio @70)  test:", f(r["baseline_test_current_default"]))
    print(f"chosen on dev: {r['chosen']['scorer']} @ {r['chosen']['threshold']}")
    print("  dev :", f(r["dev_at_chosen"]))
    print("  test:", f(r["test_at_chosen"]))
    sc = SCORERS["dice_issue_words+place_penalty"]
    print("\nThreshold sweep for the shipped matcher, all pairs (tuning + test, optimistic):")
    for t in range(30, 80, 5):
        print(f"  @{t}: ", f(metrics(sc, DATA, t)))
