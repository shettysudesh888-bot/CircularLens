# Hybrid extraction error analysis and held-out comparison

## Error analysis of the original four-circular evaluation

The reference set had 15 categories. Both methods recovered all five categories in the simple original and revision notices (eligibility, attendance, fee, deadline, required documents), yielding 10 true positives. The missing categories came from the exception circular: `backlog`, `approval`, and `exception` were missed by both methods; the pattern baseline additionally found only `attendance` there. This is category detection, not complete rule correctness.

Gemini false positives came from the ambiguous circular: it emitted an `eligibility` clause merely from “Eligibility for special cases…” even though no measurable eligibility predicate exists. Earlier runs also emitted `instruction`. Exact-source matching passed, which demonstrates that evidence matching alone does not establish semantic correctness.

The first hybrid-slice condition audit exposed a deterministic parsing bug: “Semester 2 and Semester 4” was normalized to `[2]`, not `[2,4]`. The parser now scans repeated `Semester <number>` forms. A post-fix local verification returns exactly `[2,4]`; the full Gemini slice has not been re-scored after this correction because the bounded API run did not return a result before the execution window ended.

## Hybrid design

1. Deterministic extraction creates source-validated suggestions for straightforward dates, fees, attendance, documents, and semester wording.
2. Gemini is invoked only when the document contains complex signals such as exceptions, condonation, approval, backlog, `unless`, or AND/OR language.
3. All outputs use the existing `RuleClause` model and source validation. Gemini condition fields/operators are constrained to the deterministic evaluator's whitelist.
4. Equivalent category/condition clauses are deduplicated. Same-category/condition suggestions with conflicting rule values are marked `conflict` for review rather than accepted silently.
5. Clauses remain unverified; neither hybrid nor Gemini outputs enter active-rule or eligibility resolution without administrator approval.

## Measured bounded held-out slice (pre multi-semester parser correction)

Two held-out circulars were executed: a simple notice with five reference categories and a complex exception notice with five reference categories. Development examples were not executed. The result is stored in `hybrid-results.json`.

| Method | Precision | Recall | F1 | TP | FP | FN | Mean latency |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Pattern | 1.0000 | 0.6000 | 0.7500 | 6 | 0 | 4 | 0.034s |
| Gemini | 1.0000 | 0.6000 | 0.7500 | 6 | 0 | 4 | 4.814s |
| Hybrid | 1.0000 | 0.7000 | 0.8235 | 7 | 0 | 3 | 2.796s |

All accepted Gemini evidence was exact-source validated: Gemini `6/6`; hybrid `7/7`. Hybrid's extra true positive was the union of deterministic `attendance` and Gemini `required_documents` for the complex notice. It still missed backlog, approval, and exception categories; it does not yet demonstrate robust complex-rule understanding.

The earlier condition metric should not be interpreted as a hybrid improvement: it was based on the discovered multi-semester parser defect. Gemini achieved `2/2` exact labeled conditions in that slice, while pattern/hybrid were `1/2`; the parser correction was verified after that run but has not been fully re-evaluated with Gemini.

## Complex-rule safety regression

The refinement adds source-bound suggestions for three missing structures:

- `backlog`: a `disqualify_if` predicate, for example `backlog_count > 2`.
- `approval` and `exception`: an attendance-condonation condition group, `attendance_percentage < 75 AND condonation_approved == true`, retained as review-required rather than flattened into an eligibility requirement.
- `required_documents`: a named approval-letter requirement when an attachment instruction is explicit.

Direct extractor verification confirmed all four categories (`exception`, `approval`, `backlog`, `required_documents`) for the prior exception sentence. A deterministic eligibility regression also confirmed backlog outcomes: count `1` → `ELIGIBLE`, `3` → `NOT ELIGIBLE`, missing count → `NEEDS VERIFICATION`.

An isolated safety regression confirmed that an unverified backlog rule has no operational effect (`NEEDS VERIFICATION` with no active verified rules); after it was marked verified, the same profile correctly became `NOT ELIGIBLE`.

## Reproduce

```powershell
cd 'C:\GenAI Project\CircularLens AI\backend'
$env:CIRCULARLENS_DB_PATH = Join-Path (Get-Location) 'evaluation\hybrid-evaluation.db'
$env:EVAL_HELD_OUT_LIMIT = '2'
.\venv\Scripts\python.exe -m evaluation.run_hybrid_evaluation
```

Set `EVAL_RUN_DEV=1` and omit `EVAL_HELD_OUT_LIMIT` for the longer full run. All databases created by the command are evaluation-only.
