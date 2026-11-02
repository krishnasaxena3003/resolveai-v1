# Evaluation results (reproducible)

Regenerate: `python eval_duplicates.py` and `python eval_ai.py`. All data is hand-written by the project assistant, small, and not real campus data. Treat numbers as indicative, not as accuracy claims.

## Duplicate detection (48 labelled pairs: 24 duplicate, 24 not)
Hard negatives are included on purpose (same place, different problem; same problem, different place).
Design and tuning used 32 `dev` pairs. 16 `test` pairs were written after the design was frozen.
An earlier version of the test pairs was seen during diagnosis and was folded into `dev`.

| Method | Test P / R / F1 / false-alarm rate |
|---|---|
| First version, RapidFuzz token_set_ratio, tuned on dev (t=55) | 0.57 / 1.00 / 0.73 / 0.75 |
| Shipped: issue-word Dice + place penalty, tuned on dev (t=35) | 0.64 / 0.88 / 0.74 / 0.50 |

The two methods are statistically indistinguishable on 16 pairs. The shipped one gives better precision at higher thresholds and produces an explanation ("same problem wording, different place, shared terms").

Shipped threshold sweep over all 48 pairs (optimistic, tuned and scored on the same data):

| Threshold | Precision | Recall | False-alarm rate |
|---|---|---|---|
| 35 | 0.68 | 0.88 | 0.42 |
| 40 | 0.64 | 0.75 | 0.42 (dominated, avoid) |
| **45 (default)** | **0.83** | **0.62** | **0.12** |
| 55 | 0.83 | 0.42 | 0.08 |

Why 45: at 35 about 4 in 10 unrelated reports would trigger a "possible duplicate" prompt, which trains users to ignore it. At 45 most real duplicates are still surfaced, and staff can link the rest manually.

Known weakness: near-identical wording about different things (e.g. "sink blocked in girls washroom" vs "boys washroom") cannot be separated by text overlap. This is why the app asks a person to confirm and never merges or deletes automatically.

## Complaint analysis (32 labelled complaints, policy in complaints.json)
Fallback rules only (no LLM key in the build environment): category accuracy 0.91, macro-F1 0.90, priority exact 0.59, within one level 1.00.
These numbers are inflated: the rules and the test complaints were written by the same author. They are a floor and a pipeline check, not evidence about the real model.
**Not yet measured: the Groq model. Run `python eval_ai.py` with LLM_API_KEY set and record the output here.**
