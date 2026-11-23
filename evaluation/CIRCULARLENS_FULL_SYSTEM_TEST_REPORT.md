# CircularLens AI full system demo report

## Executive summary

The isolated demo seed and API/FAISS verification completed. Live Gemini quality and browser automation were not claimed.

## Environment

- Demo-only storage: `backend/data/demo/`
- Embeddings: `deterministic-demo` (offline fixture, not Gemini)
- Dataset: 60 fully fictional Demo University circulars
- Accounts: two member accounts; no administrator created because no supported admin-provisioning workflow exists.

## Verification results

| Component | Status | Actual result |
|---|---|---|
| Demo authentication and dashboard | **PASS** | Both demo members logged in; main dashboard reports 60 circulars. |
| Circular Library data | **PASS** | Main demo workspace lists 60 fictional circulars from SQLite. |
| Workspace isolation | **PASS** | Second demo workspace cannot enumerate or open main demo documents. |
| FAISS persistence and retrieval | **PASS** | Index exists and semantic query returned 3 grounded chunk(s): DU-FEE-501.txt p.1. |
| Action and notification fixtures | **PASS** | Actions: {'pending': 30, 'in_progress': 2, 'completed': 3, 'dismissed': 1}; in-app notifications: 8. |
| Live Gemini classification/summaries/drafts | **BLOCKED** | No live Gemini request was made by the demo seeder. Fixture labels are human-authored and explicitly not model predictions. |
| Gemini accuracy, precision, recall and F1 | **NOT TESTED** | A live labeled evaluation requires Gemini network access and a separately recorded prediction run. |
| Browser click-through automation | **BLOCKED** | The available automation surface cannot reach the host loopback server; API integration checks ran in-process. |

## Dataset distribution

| Category | Count |
|---|---:|
| Scholarship applications | 8 |
| Examination notices | 8 |
| Payment and fee circulars | 8 |
| Academic submissions | 7 |
| Placement/internship opportunities | 6 |
| Events and workshops | 5 |
| Informational notices | 5 |
| Policy amendments and deadline extensions | 7 |
| Cancelled/superseded notices | 3 |
| Ambiguous/incomplete notices | 3 |
| **Total** | **60** |

## Safety and limitations

- Demo storage is rejected at startup if any configured database, index, or upload path lies outside `backend/data/demo`.
- Fixture analysis is clearly tagged `human_authored_demo_fixture_not_gemini` and remains unverified.
- The app's live Gemini endpoints were not run because network availability was not established in this execution environment.
- The existing frontend is built separately; browser click-through must be manually checked using the commands in `backend/demo/README.md`.

## Reproduce

```powershell
$env:CIRCULARLENS_DEMO_MODE='1'
$env:CIRCULARLENS_EMBEDDING_PROVIDER='deterministic-demo'
.\backend\venv\Scripts\python.exe -m backend.demo.seed_demo
.\backend\venv\Scripts\python.exe -m backend.demo.evaluate_demo
```

## Final end-to-end live verification — 2026-11-23

| Area | Status | Actual evidence |
|---|---|---|
| Dummy login and Action Center API | PASS | Normal port-8000 login succeeded; dashboard contains 60 circulars, applications, payments, and notifications. |
| Circular Library and evidence | PASS | API search, source preview, and Evidence Viewer data succeeded for seeded documents. |
| Gemini embeddings / FAISS | PASS | 71 live Gemini vectors indexed; query retrieved the expected tuition source and extension. |
| Live classification / short summary | PARTIAL | One `DU-FEE-501.txt` live JSON classification succeeded with `gemini-3.5-flash-lite`: payment category, one deadline, one required-document field, fee present, 64-character summary. |
| Live RAG answer | PASS | Normal API returned HTTP 200 with two source passages; generation model `gemini-3.5-flash-lite`. |
| Live application draft | PASS | Normal API returned HTTP 200; generation model `gemini-3.5-flash-lite`; draft length 990 characters. |
| Action lifecycle/reminder/privacy | PASS | Isolated backend suite covers completion/reminder cancellation, tenancy and role restrictions: 9/9 passed. |
| Amendments and cancellation | PARTIAL | Ten unverified relationship candidates are retained and lineage is visible; no authorized administrator workflow exists to approve a live amendment. |
| Academic-rule verification | BLOCKED | No legitimate administrator account/provisioning route exists. The member was not elevated or used to bypass the admin-only endpoint. |
| Browser automation | BLOCKED | The available browser automation surface cannot reach the host-local Vite service. No click-through claim is made. |
| Multi-document live Gemini metrics | BLOCKED | Seven-document balanced evaluation was attempted but repeated bounded provider calls encountered transient 503 capacity failures before a complete results artifact could be saved. No aggregate accuracy/F1 is claimed. |

### One-sample live measurement (not a dataset-wide metric)

- Reference: `DU-FEE-501.txt` is a payment circular with one deadline and one required document.
- Live prediction: category `payment`, one deadline, one required-document field, fee present.
- On this single completed sample, classification, deadline presence, fee presence, and required-document count matched the reference. This is **n=1** and must not be read as an overall accuracy, precision, recall, or F1 score.

### Remaining issues

1. **Medium — Gemini generation capacity is intermittent.** Primary and fallback models can return provider 503 under high demand. Bounded retries/fallback are implemented and successful calls record their model.
2. **Medium — No legitimate administrator provisioning workflow.** This blocks production-style approval testing of academic clauses/relationships without violating role controls.
3. **Low — Browser automation isolation.** Use the manual cases below in a local browser: login; Library search; Evidence Viewer; RAG question; draft; mark action in progress/completed; check notification disappearance; Settings save; Profile save; Analytics; logout.

## Closure verification — administrator and workflows — 2026-11-23

| Feature | Status | Evidence |
|---|---|---|
| CLI-only admin provisioning | PASS | No HTTP route was added. Provisioner requires an existing admin bearer token or explicit local bootstrap secret, uses the existing PBKDF2 hash, refuses member elevation, records `admin_provisioned` audit activity, and does not create a workspace. |
| Member admin denial | PASS | Demo member received HTTP 403 from admin-only structured extraction. |
| Admin extraction/review | PASS | Separate CLI-provisioned admin ran source-verified extraction (4 suggestions) and explicitly approved one clause. No clause was automatically approved. |
| Amendment review | PASS | Separate admin explicitly verified one relationship with the new admin-only review endpoint. |
| Scholarship / fee / information / amendment actions | PASS | Scholarship and fee documents have actions; extension, information-only, and cancellation documents have none. Eight payment actions exist; extension did not duplicate payment obligation. |
| Completion/reminders/history | PASS | Existing isolated integration coverage verifies status transitions, completed history, reminder cancellation and scheduler persistence. |
| Live Gemini structured extraction | PARTIAL | Authorized endpoint reached Gemini but received an upstream 503 after the bounded attempts. Deterministic source-verified extraction and manual review passed. |
| Browser interaction | BLOCKED | Local automation surface remains isolated from host Vite. |

### Legitimate administrator setup

The provisioner is deliberately local-only: `backend/tools/provision_admin.py`. For a first administrator, an operator must set a non-empty `CIRCULARLENS_ADMIN_BOOTSTRAP_SECRET`, supply the matching secret interactively (or process-locally using `CIRCULARLENS_ADMIN_BOOTSTRAP_INPUT`), and choose a new identity. Later provisioning requires an existing admin bearer token. Example:

```powershell
$env:CIRCULARLENS_ADMIN_BOOTSTRAP_SECRET = '<operator-controlled-secret>'
python -m backend.tools.provision_admin --bootstrap --email admin@example.test --workspace 'Demo University — Data Science'
Remove-Item Env:CIRCULARLENS_ADMIN_BOOTSTRAP_SECRET
```

Never use this CLI to elevate an existing member; it rejects that case.

### Manual local-browser demonstration checklist

1. Open `http://127.0.0.1:5173/login`; sign in as `demo.data.science@demo-university.example`.
2. At `/app`, confirm 60 circulars and action/payment cards appear.
3. Open `/library`, search `Tuition`, open `DU-FEE-501.txt`, and verify the source/evidence view.
4. Use the RAG assistant to ask for its fee/deadline; confirm source citations.
5. Generate an editable draft from the tuition circular; confirm no automatic submission occurs.
6. Open `/deadlines`, start and complete a safe demo action; verify it moves to history and its reminder disappears.
7. Open `/analytics` and confirm healthy retrieval diagnostics; check `/settings` and `/profile` persist after reload.
8. Log out; sign in as the test admin only to inspect/review suggestions. Do not approve clauses unless demonstrating the explicit review step.
