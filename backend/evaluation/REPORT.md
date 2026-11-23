# Academic rule intelligence evaluation

Run date: 22 November 2026. This was run against the isolated SQLite file `evaluation/academic-evaluation-run-2.db`; production data and FAISS assets were not opened or changed.

## Method

`run_academic_evaluation.py` creates separate documents for pattern and Gemini extraction, preventing duplicate suppression from influencing either method. Four manually labeled synthetic circulars cover baseline rules, a revision, attendance/approval/backlog exceptions, and intentionally ambiguous guidance. Exact category labels are the reference truth; Gemini predictions are never used as labels. Each run writes machine-readable output to `evaluation/latest-results.json`.

The evaluator validates Gemini evidence by requiring each saved source excerpt to be an exact substring of the source circular. It then constructs administrator-verified clauses plus a verified partial `AMENDS` relationship and calls the authenticated profile/eligibility APIs for five student profiles.

## Results

| Measure | Pattern baseline | Gemini structured |
| --- | ---: | ---: |
| Reference categories | 15 | 15 |
| Predicted categories | 11 | 13 |
| True positives | 11 | 11 |
| Precision | 1.0000 | 0.8462 |
| Recall | 0.7333 | 0.7333 |
| F1 | 0.8462 | 0.7857 |

- Gemini source-evidence correctness: `13 / 13` accepted predictions.
- Verified partial-amendment resolution: `1 / 1` correct.
- End-to-end deterministic eligibility: `5 / 5` correct.
- Appropriate `NEEDS VERIFICATION` outcomes: `2 / 2`.
- Mean real Gemini extraction latency: `3.9166 seconds` across four calls.
- Token usage/cost: not exposed by the observed SDK responses; no estimate is reported.

## Additional isolated end-to-end workflow

After adding bounded retry/backoff for temporary Gemini `503 UNAVAILABLE` responses, a separate isolated SQLite database and separate FAISS directory were used to test the actual application path: upload original and revised text circulars, semantic index creation, Gemini extraction, unverified-clause inspection, administrator approval, verified partial `AMENDS` record, student profile creation, and eligibility request. The result was `E2E_WORKFLOW_OK {'gemini_clauses': 4, 'eligibility': 'ELIGIBLE', 'index_chunks': 2}`.

One initial end-to-end attempt received a real Gemini `503 UNAVAILABLE` during demand spike; no rule was saved from that failed call. The retry implementation makes up to three bounded attempts before returning a clear error.

## Observed failure cases

The Gemini method returned `required_documents` for the exception circular where the reference label expected attendance, backlog, approval, exception, and required documents; it did not recover all of those categories. It also emitted `eligibility` and `instruction` for ambiguous guidance whose reference label was intentionally empty. These are the reason its precision and F1 are lower than the pattern baseline in this small labeled set.

The result is not a production-quality generalization claim: this is a four-circular synthetic evaluation. Gemini findings remain unverified and cannot affect active-rule or eligibility resolution until administrator approval.

## Reproduce

```powershell
cd 'C:\GenAI Project\CircularLens AI\backend'
$env:CIRCULARLENS_DB_PATH = Join-Path (Get-Location) 'evaluation\academic-evaluation-run.db'
.\venv\Scripts\python.exe -m evaluation.run_academic_evaluation
```
