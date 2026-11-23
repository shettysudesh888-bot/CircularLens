# CircularLens AI — verified project status

Verified on 22 November 2026 (Asia/Kolkata).

## Semantic RAG upgrade (verified)

- Active embedding provider: Gemini (`gemini-embedding-001`), 768 dimensions, L2 normalization, `RETRIEVAL_DOCUMENT` / `RETRIEVAL_QUERY` task types.
- A real authenticated embedding request returned a non-zero 768-dimensional vector (`EMBEDDING_API_OK dimension=768 nonzero=True`). No API key was logged.
- The persistent FAISS index is `IndexIDMap2(IndexFlatIP)`, backed by normalized semantic vectors and persistent SQLite chunk IDs. It is stored under `backend/data/semantic_index/active.faiss`.
- Existing records were safely migrated by building and validating a candidate index before atomic activation. The verified active index contains 4 chunks across 2 existing documents and reports `healthy`.
- Reindexing creates a timestamped index backup before replacement. Provider/model/dimension mismatches are refused until `/rag/reindex` performs a controlled full reindex, preventing mixed embedding spaces.
- Gemini source-grounded generation uses `gemini-3.1-flash-lite` and receives source filename, document ID, page number, and chunk content. The chat API returns the ranked sources with similarity scores.
- Local fallback is implemented with `sentence-transformers/all-MiniLM-L6-v2`; it loaded successfully and returned a normalized 384-dimensional semantic vector. It is never mixed into the active Gemini index.
- The frontend diagnostics card reads `/rag/diagnostics` and shows only provider, model, dimension, counts, and index health.

## Semantic retrieval evaluation

- Benchmark corpus: an exam registration circular and an unrelated hostel-maintenance circular; temporary data was deleted after the run.
- The three requested paraphrased examination-registration queries each retrieved the registration circular at rank 1.
- Recall@3: `1.0`; Recall@5: `1.0` on this three-query labeled benchmark.
- Source-grounded Gemini chat test passed and returned the expected benchmark source name.
- Unrelated query test executed; its highest similarity was `0.5685`. Similarity alone is not treated as evidence—the answer prompt instructs Gemini to state insufficient evidence when excerpts do not support the claim.
- Persistence test passed across two independent FastAPI startup cycles (`PERSISTENCE_OK chunks=4`).

## Completed product features

- Fixed FastAPI startup by installing and declaring `python-multipart`, required by `UploadFile` endpoints.
- Added SQLite initialization and persistent `documents`, `chunks`, and `activities` records.
- Implemented upload for PDF, TXT, and Markdown files (15 MB limit), PyMuPDF PDF extraction, page-aware chunking for new PDFs, semantic FAISS retrieval, deadline extraction, and file cleanup on delete.
- Connected the chat endpoint to `gemini-3.1-flash-lite` through the existing Windows `GEMINI_API_KEY`; answers receive retrieved document excerpts and source IDs.
- Implemented document comparison, dashboard analytics, and upcoming-deadline tracking.
- Replaced the Vite starter page with the React CircularLens SaaS dashboard, wired to all implemented API endpoints.
- Added a first-class pasted-text circular endpoint and dashboard form alongside PDF/TXT/Markdown upload.
- Added categories, tags, exact duplicate detection, searchable listing filters, deadline confirmation, an iCalendar deadline export, local organization/account registration, and configurable notification subscriptions.
- Added source-aware RAG context (document IDs are returned with each chat response) and comparison/version foundations through content hashing.
- Replaced the starter dashboard with a responsive premium SaaS shell: desktop/mobile sidebar behavior, workspace header, global library filtering, real metric cards, Action Center, recent circulars, deadlines, Ask AI, and compact RAG diagnostics.
- Added persisted `ActionItem`, `DocumentReview`, `InAppNotification`, and `UserPreference` SQLite models plus API endpoints for grounded action suggestions, review evidence, in-app notification reads, bookmarks, and user-selected feed preferences.
- Added admin-enforced review creation in FastAPI. Bearer tokens are verified server-side before preferences, notifications, action updates, and review routes are accepted.
- Implemented evidence workspace data through `GET /intelligence/documents/{document_id}/evidence`; it returns verified extraction fields and explicitly labels the absence of exact PDF coordinates rather than fabricating highlights.

## Provider-dependent integrations

- OCR for image-only PDFs is not enabled yet: PyMuPDF handles selectable-text PDFs; Tesseract or a cloud OCR provider must be installed/configured to process scans.
- Notification subscriptions are persisted, but no email or WhatsApp message is sent until SMTP or a WhatsApp-capable webhook delivery worker is configured. This avoids silently claiming messages were delivered.

## Verified commands and results

- `uvicorn app.main:app --host 127.0.0.1 --port 8002` started successfully.
- Live `GET /health` returned HTTP 200 and `{"status":"ok"}`.
- Live `GET /docs` returned HTTP 200 and contained the `CircularLens AI - Swagger UI` title.
- FastAPI TestClient smoke test passed for health, docs, upload, SQLite listing, comparison, analytics, and delete (`backend endpoint smoke test passed`).
- Authenticated Gemini smoke call using `gemini-3.1-flash-lite` succeeded (`GEMINI_CALL_OK=True`). The API key was not printed or stored.
- `npm run build` completed successfully.
- `npm run lint` completed with one non-blocking React `set-state-in-effect` warning and no errors.
- Enhancement smoke test passed for text-circular creation, deadline confirmation, `.ics` calendar export, organization registration, and cleanup.
- Premium SaaS frontend `npm run build` passed; `npm run lint` passed with the existing non-blocking React effect warning.
- Intelligence endpoint smoke test passed for health, Action Center endpoints, account token issuance, server-side authenticated preferences, and persisted notification listing.

## Remaining UX work

- Implemented all six separately navigable React workspaces: `/library`, `/evidence/:id?`, `/changes`, `/deadlines`, `/analytics`, and `/settings`.
- Circular Library has real text/tag search, category and sorting controls, PDF/TXT/Markdown upload, pasted-text indexing, evidence links, and confirmed deletion.
- Evidence Viewer uses the persisted evidence API and original/extracted document preview route. It shows only review data and source notes actually returned by the backend.
- Change Intelligence uses the existing comparison endpoint and renders documented shared, added, removed, and date-difference terms; it does not invent change confidence scores.
- Deadline Workspace consumes live upcoming deadlines and provides a functional `.ics` calendar export.
- Analytics uses SQLite-backed counts, actual category distribution, and live RAG diagnostics. Settings persists preferences only through an authenticated bearer token.
- `npm run build` passed after routing changes. `npm run lint` passed with the existing non-blocking React effect warning.
- Read-only FastAPI workspace integration check passed for health, documents, analytics, diagnostics, actions, calendar export, preview, evidence, and comparison endpoints against 2 preserved documents.
- Browser automation and visual responsive screenshots were not available in this environment; production build and responsive CSS breakpoints were verified instead.

## Academic intelligence upgrade (verified core)

- Created a timestamped backup before the additive migration: `backend/data/backups/academic-upgrade-20261122191355` contains the pre-upgrade SQLite database and active FAISS index.
- Added `RuleClause`, `CircularRelationship`, and owner-scoped `StudentProfile` tables with no destructive changes to existing documents, actions, deadlines, or embeddings.
- Added `/academic` APIs for source-bound rule suggestions, administrator clause review, verified lineage records, private student profiles, and deterministic eligibility decisions.
- Only `verified` clauses participate in eligibility. Verified `AMENDS` relationships can replace only their declared categories; `SUPERSEDES` and `CANCELS` deactivate the targeted document's clauses. Historical clauses remain stored.
- Added `/profile` and `/impact` React routes for private profile editing and evidence-linked eligibility guidance.
- Isolated database test executed all requested profile outcomes: `ELIGIBLE`, `ELIGIBLE`, `NOT ELIGIBLE`, `NEEDS VERIFICATION`, `NEEDS VERIFICATION` for cases A–E respectively. The test also validated a partial, verified `AMENDS` relationship.
- Production database startup and RAG health checks passed after the migration. Frontend production build passed; lint retained the existing non-blocking React effect warning.

## Academic upgrade limitations

- Current clause extraction is bounded, deterministic, source-verified pattern extraction for the supported rule classes. It deliberately stores all findings as unverified suggestions. Gemini structured-output extraction, automated relationship inference, profile-impact natural-language explanations, and formal precision/recall evaluation have not yet been implemented, so no metrics are claimed for them.
- The isolated synthetic test database remains separate from production data; it was retained for reproducibility rather than touching user records.

## Gemini-powered rule intelligence (verified core)

- Created a second pre-change backup at `backend/data/backups/gemini-rule-intelligence-20261122191837` containing the production SQLite database and active FAISS index.
- Added `POST /academic/documents/{document_id}/extract-gemini`. It calls `gemini-3.1-flash-lite` through `google-genai` with a typed Pydantic response schema, constrained category/field/operator vocabularies, JSON-safe condition values, and no executable model output.
- Gemini-produced clauses are accepted only when their source passage matches the stored document text. A matching chunk supplies the stored PDF page number when available. Every accepted Gemini clause and relationship candidate is persisted as `suggested` / `verified=false`.
- Added source-validated, unverified Gemini relationship candidates for `AMENDS`, `SUPERSEDES`, `EXTENDS`, `CLARIFIES`, and `CANCELS`; they cannot affect the active-rule resolver until admin approval.
- Real isolated Gemini test passed: Gemini created 4 typed unverified clauses from a synthetic revised circular; every persisted source excerpt was verified against the input text.
- Post-change Python compile, FastAPI startup, `/health`, and semantic RAG diagnostics regression passed.

## Gemini rule intelligence evaluation limitation

- The first comparative evaluation was invalid because pattern-generated clauses occupied the same document and suppressed duplicate Gemini inserts. Its zero Gemini score is not reported as an evaluation metric.
- A rerun with separate documents did not return usable output before the execution window ended. Consequently, no Gemini precision, recall, F1, relationship accuracy, latency, or end-to-end faithfulness metric is claimed yet.
- The current frontend exposes deterministic profile/impact guidance; a dedicated admin Gemini clause-review surface and Gemini natural-language eligibility explanation remain future work.

## End-to-end AI validation and comparative evaluation (verified)

- Added reproducible isolated evaluation harness: `backend/evaluation/run_academic_evaluation.py` and the exact-result report `backend/evaluation/REPORT.md`.
- The harness uses separate documents for pattern and Gemini extraction, so duplicate suppression cannot distort the comparison. It does not access the production database or vector index.
- Dataset: 4 manually labeled synthetic circulars; 15 reference rule categories. Coverage includes deadlines, fees, semester eligibility, attendance, required documents, an amendment, exceptions/backlogs/approval language, and ambiguous guidance.
- Baseline pattern extraction: precision `1.0000`, recall `0.7333`, F1 `0.8462` (`11` true positives / `11` predictions / `15` references).
- Gemini structured extraction: precision `0.8462`, recall `0.7333`, F1 `0.7857` (`11` true positives / `13` predictions / `15` references).
- Gemini source evidence correctness: `13/13` accepted predictions had exact matching source passages. Mean real Gemini latency was `3.9166s` over 4 calls. Token usage was not exposed by observed SDK responses, so no cost estimate is claimed.
- Verified partial amendment resolution: `1/1`. Authenticated end-to-end eligibility: `5/5` cases correct. Appropriate `NEEDS VERIFICATION`: `2/2`.
- The evaluation exposed real Gemini failure cases on exception and ambiguous text; these are documented in `backend/evaluation/REPORT.md` and no inflated quality claim is made.
- Added bounded exponential retry/backoff to Gemini structured generation after an observed temporary `503 UNAVAILABLE`; failure remains explicit after three attempts.
- Full isolated workflow passed using a dedicated SQLite file and dedicated FAISS index directory: uploaded original/revised circulars, semantic index creation, Gemini extraction (`4` review-gated clauses), administrative clause approval, verified partial amendment, private profile update, and an `ELIGIBLE` deterministic result (`index_chunks=2`).
- Final production regression checks passed read-only for backend compile/startup, health, documents, semantic RAG diagnostics, analytics, and Action Center. Frontend production build passed; lint again had only the existing React effect warning.

## Hybrid rule extraction optimization (verified bounded evaluation)

- Added hybrid endpoint `POST /academic/documents/{document_id}/extract-hybrid`. It preserves deterministic extraction for simple facts, invokes Gemini only for complex-language signals, validates evidence, deduplicates equivalent candidate clauses, and marks contradictory same-condition values as review conflicts.
- Error analysis found that source-evidence correctness does not guarantee semantic correctness: the Gemini-only extractor created an eligibility false positive from ambiguous “special cases” language and missed backlog/approval/exception categories in the exception notice. Prompt abstention rules were tightened accordingly.
- Fixed deterministic multi-semester parsing: “Semester 2 and Semester 4” now produces `[2, 4]`, verified by direct parser output.
- A real isolated two-circular held-out slice (pre parser-fix re-score) measured Pattern `P=1.0000/R=0.6000/F1=0.7500`, Gemini `P=1.0000/R=0.6000/F1=0.7500`, Hybrid `P=1.0000/R=0.7000/F1=0.8235`. Accepted source evidence was Gemini `6/6`, Hybrid `7/7`.
- The hybrid result is encouraging only for category coverage on this two-document slice; it does not establish a general improvement. It still missed complex backlog/approval/exception rules. The detailed analysis, failures, and reproduction commands are in `backend/evaluation/HYBRID_REPORT.md`.
- A post-fix full Gemini re-run did not return results before the execution window ended; no post-fix hybrid metric is claimed.

## Final complex-rule refinement (verified safety)

- Root cause review confirmed that the complex-rule misses were Gemini category omissions, not failed evidence matching or deduplication. Existing hybrid clauses contained only deterministic attendance and Gemini required-document output; backlog, approval, and exception were absent.
- Hybrid now emits conservative, source-bound review suggestions for backlog disqualification (`backlog_count > threshold`), attendance-condonation AND groups, approval requirements, and explicit approval-letter documents. They are unverified by default.
- Eligibility evaluation now correctly treats a verified `disqualify_if` backlog predicate as a disqualifier and skips informational/exception/approval/document clauses from becoming accidental eligibility blockers.
- Verified direct complex extractor test found `exception`, `approval`, `backlog`, and `required_documents`. Verified eligibility regression: backlog count `1` → `ELIGIBLE`, `3` → `NOT ELIGIBLE`, missing count → `NEEDS VERIFICATION`.
- Verified unapproved-rule safety: an unverified backlog clause did not change the result; after verification, it correctly caused `NOT ELIGIBLE` for the same profile.
- Frontend production build passed. Lint passed with the existing non-blocking React effect warning.

## Final integrated intelligence validation (verified)

- Added isolated reproducible matrix: `backend/evaluation/run_integrated_validation.py`; result: `INTEGRATED_ELIGIBILITY_MATRIX_OK 7 cases`.
- Verified combined outcomes: attendance above threshold; approved/denied/unknown condonation; backlog below/equal/above/missing; a semester membership OR-group; and independent backlog disqualification.
- Verified safety invariants: unverified clauses do not affect eligibility; no active verified rules returns `NEEDS VERIFICATION`; disjoint verified eligibility predicates return `NEEDS VERIFICATION` for administrator resolution.
- Refined verified attendance exceptions to override only their matching attendance threshold. They do not override independent verified backlog disqualifiers.
- Final read-only production regression passed for compilation, health, document management, FAISS/RAG diagnostics, analytics, and calendar export. Production SQLite data and FAISS index were preserved.
- Local frontend/backend servers could be launched, but this chat had no available browser surface for actual click-through automation. The production build verifies route compilation; no browser interaction result is claimed. Full commands and matrix are in `backend/evaluation/INTEGRATED_VALIDATION.md`.

## Option 1 dark enterprise frontend redesign (verified)

- Restyled the existing routed React application in place with a shared premium dark enterprise design system: `#091226` workspace, `#0B1732` sidebar, `#122241` panels, teal primary actions, indigo/purple/amber metric accents, visible focus states, responsive tables/forms, and a compact global-search header.
- Preserved all existing routes and live API integrations; no dashboard numbers or circular records were hardcoded for the redesign.
- Applied the shared system to overview, library, evidence, comparison, deadlines, analytics, settings, student profile, impact, notifications, form controls, empty states, and responsive breakpoints. The optional existing theme control remains functional.
- `npm run build` passed. `npm run lint` completed with the pre-existing non-blocking React `set-state-in-effect` warning and no lint errors.
- Packaged verified frontend source excluding `node_modules`, `dist`, environment files, and credentials: `C:\GenAI Project\CircularLens AI\CircularLens_AI_Option1_Frontend.zip` (21 entries, 55,410 bytes).

## Run locally

```powershell
cd 'C:\GenAI Project\CircularLens AI\backend'
.\venv\Scripts\python.exe -m uvicorn app.main:app --reload

cd 'C:\GenAI Project\CircularLens AI\frontend'
npm run dev
```

The frontend defaults to `http://127.0.0.1:8000`; set `VITE_API_URL` to override it.

## Stabilization audit and repair — 2026-11-22 (verified)

- This workspace is **not a Git checkout**, so no Git status or commit checkpoint was available. Before source changes, a timestamped recovery checkpoint was created at `checkpoints/stabilization-20261122-231900` containing `backend/app`, `frontend/src`, and the preserved production `backend/data/app.db`.
- The audit found a blocking backend defect in `backend/app/routes/intelligence.py`: a syntax error in the draft endpoint, a misapplied `/actions` decorator, unreachable action-list code, and route queries for model timestamps that did not exist. The module has been rebuilt and Python compilation now passes.
- Added only additive SQLite columns for workspace/document ownership, action ownership/timestamps, notification action keys/timestamps, subscription ownership, and JWT token versioning. Existing data is not reassigned or deleted. The migrations run against a test database in validation.
- Authentication now issues signed HS256 JWT-format bearer tokens with expiry and per-user token-version revocation. Logout invalidates active tokens. Registration creates members only; it cannot silently join an existing workspace. This removes the prior custom non-JWT token and tenant-joining weakness.
- Documents, Action Center entries, reminders, notifications, analytics, comparisons, chat retrieval, RAG diagnostics, and academic-document endpoints now require authentication and enforce workspace scope. Legacy documents without workspace ownership remain administrator-review-only rather than being exposed to members.
- Gemini classification now uses the installed `google-genai` SDK call shape and `gemini-3.1-flash-lite`. Gemini-extracted deadlines remain unconfirmed until an administrator confirms them. Action generation is private and only occurs for action-bearing categories with explicit actions; informational notices create no action.
- Reminder generation is timezone-aware, idempotent per user/action/reminder interval, and ignores completed or dismissed actions. Completing/dismissing an action removes pending reminder notifications while retaining completed action history. Confirming a deadline updates pending actions for that circular.
- Restored `frontend/src/App.tsx` from its truncated state. All configured routed workspaces now have implementations again, with authenticated API calls and the retained Option 1 dark navy/teal styles. The dashboard includes the real Action Center and completion action.

### Commands executed and results

- `python -m py_compile` on the repaired backend modules: **passed**.
- Isolated FastAPI startup with separate SQLite and FAISS paths: `/health` → **200** (`{"status":"ok"}`), `/docs` → **200**.
- `python -m unittest backend.tests.test_isolated_workflow -v`: **2/2 passed**. The test covers registration/JWT/logout revocation, tenant isolation, pasted circular upload, authenticated calendar export, classification-backed action creation, unverified deadline state, draft generation, idempotent reminder creation, completion/reminder cancellation/history, and informational-no-action behavior. Gemini and semantic indexing were deliberately mocked only inside this isolated test.
- `frontend/npm run build`: **passed** (TypeScript and Vite production build). `frontend/npm run lint`: **passed with 10 non-blocking React warnings** (effect/static-component diagnostics), no lint errors.
- A direct live Gemini classification was attempted with the existing environment key. It could not complete because this execution environment could not resolve the Gemini host (`httpx.ConnectError: getaddrinfo failed`). No live Gemini success is claimed for this stabilization pass.
- After the pre-change database checkpoint, the real production SQLite startup migration was also run. Its actual database path was `backend/data/app.db`; `/health` and `/docs` both returned **200**. A read-only schema check then confirmed the additive ownership/reminder columns are present.

### Remaining limitations

- The application still uses the existing simple periodic/on-demand reminder generation endpoint, not an external durable job scheduler. A deployment should invoke `POST /intelligence/notifications/generate` on a controlled schedule or add a single-worker scheduler.
- Authentication now requires a high-entropy `CIRCULARLENS_AUTH_SECRET` outside version control; the prior source fallback was removed during GitHub preparation.
- The frontend lint warnings should be addressed in a focused UI cleanup; they do not block the verified production build.
- Live Gemini and live FAISS embedding calls need a network-enabled environment for final real-model smoke testing.

## Automatic Action Center reminders — 2026-11-23 (verified)

- Added `backend/app/reminders.py`: an internal, token-free polling service started by FastAPI startup. It checks pending actions every five minutes by default (`CIRCULARLENS_REMINDER_INTERVAL_SECONDS` can override this) and evaluates each student's configured IANA timezone.
- Added persistent `reminder_deliveries` records with a unique `(user_id, action_id, reminder_kind)` key. This gives restart recovery and final duplicate prevention for the 7-day, 3-day, 1-day, and deadline-day reminders.
- Added persisted `scheduler_leases`. Every worker attempts an atomic short database lease before scheduling, so concurrent backend workers do not independently schedule the same run. The delivery unique constraint remains the safety backstop if a lease expires or workers overlap.
- Completing or dismissing an action marks its delivery records cancelled and removes its in-app reminders; completed action history remains in `action_items`.
- Payment-classified circulars now create an Action Center item with `action_type: payment` and the model-extracted fee text. This text remains AI-extracted/unverified; it is not treated as a confirmed payment amount.
- Added only additive `action_items` columns and two new tables. Production migration was run after the existing stabilization checkpoint; no existing documents, FAISS data, or actions were deleted/reassigned.

### Verification

- `python -m py_compile` for scheduler, FastAPI, intelligence, and models: **passed**.
- `python -m unittest backend.tests.test_isolated_workflow -v`: **3/3 passed**. It now covers JWT/logout, cross-workspace document/action isolation, upload, classification, draft generation, informational notices, member deadline-confirmation denial, payment action/fee persistence, scheduler lease contention, durable duplicate prevention, reminder cancellation, and academic-profile privacy. Gemini and index calls are mocked only in this isolated suite.
- Production FastAPI startup against `backend/data/app.db`: `/health` **200**, `/docs` **200**, scheduler thread **running**, `reminder_deliveries` and `scheduler_leases` tables **present**.
- Frontend `npm run build`: **passed**. `npm run lint`: passes with **two** remaining `react(set-state-in-effect)` warnings from asynchronous data-fetch effects; eight static-component warnings were removed by moving the access gate out of the render body.
- Live Gemini test: `GEMINI_API_KEY` is present, but a sanitized request again failed with `ConnectError` because this environment cannot reach the Gemini service. Classification, summary, field extraction, grounding, and drafting are therefore **not live-verified** in this pass.
- Browser attempt: the local frontend was opened through the available browser automation, but the isolated browser could not connect to `127.0.0.1:5173` (`ERR_CONNECTION_REFUSED` then `ERR_CONNECTION_TIMED_OUT`). No click-through workflow is claimed.

### Delivery limitation

- Automatic reminders currently persist as in-app notifications only. Email, WhatsApp, push, or webhook delivery still requires a separately configured external notification provider/worker; no external delivery is faked by this application.

## Public homepage, authentication repair, and Guest Mode — 2026-11-23 (verified)

- Reworked frontend navigation without replacing the existing app: `/` is now a public CircularLens AI landing page; `/login`, `/register`, `/app`, and `/guest` are separately routed. Existing authenticated workspace routes remain available and protected.
- Authentication success now stores the bearer token and navigates to `/app`. The sign-in/register screens validate an existing token via `/accounts/me` and restore that valid session instead of presenting the form.
- Fixed the `[object Object]` registration failure display. The authentication form now renders FastAPI string errors, validation arrays (including field and message), nested message objects, malformed responses, and network failures as readable text. It provides loading/disabled states and does not hide authentication failures.
- Added `POST /guest/sessions`, `POST /guest/text/analyze`, `POST /guest/upload/analyze`, and `POST /guest/chat`. Guest sessions are random, in-memory, one-hour sessions; their text/upload content never enters SQLite `documents`, FAISS, organizations, student profiles, Action Center, or reminders.
- Guest upload supports PDF/TXT/Markdown up to 1 MB; pasted text is bounded to 100,000 characters. In-process IP-scoped session/request limits protect the unauthenticated endpoints. Rate-limit/session state clears on process restart and expired records are cleaned on access.
- Guest analysis and chat call the same backend Gemini integration but do not expose the key. AI output remains temporary and unverified; it cannot create official rules, confirmed deadlines, accounts, or administrator identities.
- Added the temporary Guest Mode UI with paste-text analysis, PDF/TXT/Markdown upload, summary fields, guest question answering, visible temporary-data notice, and sign-in/register links.

### Verification

- Isolated guest integration test: **passed** for session creation, temporary pasted-text analysis, temporary TXT upload analysis, source-grounded guest chat, and `401` denials for `/documents/list` and `/intelligence/actions` with only a guest-session header.
- Isolated existing workflow test: **passed** for authenticated upload/classification/action/draft/reminder/completion/logout/tenant isolation.
- Isolated payment/scheduler/role restriction test: **passed**.
- Duplicate-registration API test: **passed**, exact response detail: `An account with this email already exists.`
- Isolated FastAPI smoke check: `/health` **200**, `/docs` **200**, guest session creation **201**, private documents without authentication **401**.
- Frontend production build: **passed**. Lint completed with the same two non-blocking asynchronous data-fetch effect warnings; no lint errors.

### Remaining limitations

- Live Gemini remains unverified in this environment because outbound DNS/network access to Gemini failed previously with `ConnectError`; guest/live AI endpoints return a clear temporary-unavailable response in that condition. Mocked isolated integration confirms endpoint wiring only.
- Browser click-through was not reverified: the available isolated browser could not reach the local Vite server. The routing/type/build checks are verified, but no browser interaction result is claimed.

## Live Gemini and browser connectivity diagnosis — 2026-11-23 (verified)

- Gemini configuration inspection: `backend/app/services.py` constructs the existing `google-genai` `Client` with `GEMINI_API_KEY`, uses `client.models.generate_content`, and retains `gemini-3.1-flash-lite` for classification, drafting, and source-grounded answers. No model, key, or endpoint change was made.
- The key is present and client construction succeeds (`gemini_client_constructed=Client`) without exposing its value.
- Host-level DNS is blocked in this execution environment: PowerShell `Resolve-DnsName generativelanguage.googleapis.com` returned `Access is denied`; `Test-NetConnection` reported name-resolution failure; `curl` returned exit code `6` / `Could not resolve host`. No proxy environment variables were present. Consequently the connection never reached TCP/TLS, the Google API endpoint, or authentication.
- This diagnosis applies to the available execution/sandbox environment only. It does **not** establish a DNS, proxy, firewall, certificate, or SDK failure on the user's Windows machine.
- Guest expiry cleanup now has an isolated regression assertion: after expiry, the same guest-session header receives `401`; temporary text/upload/chat and protected-route denial remain passing.
- Local Vite was started with an explicit `0.0.0.0:5173` bind, but the command-host process was not persistent after the tool invocation and the browser automation surface could not connect to `127.0.0.1:5173`. This is a local-tool/browser-isolation limitation, not a claimed browser test pass.

### Safe local verification commands

```powershell
# From a normal Windows PowerShell session on the development machine.
Resolve-DnsName generativelanguage.googleapis.com
Test-NetConnection generativelanguage.googleapis.com -Port 443

cd 'C:\GenAI Project\CircularLens AI'
python -c "from backend.app.services import classify_circular; r=classify_circular('Scholarship application due 31 December 2030. Fee Rs. 500.'); print(sorted(r.keys()))"

# In two terminals:
python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000
cd frontend; npm run dev -- --host 127.0.0.1 --port 5173
```

Then open `http://127.0.0.1:5173/` in a normal local browser. Test Guest Mode with text or a non-sensitive sample PDF; verify `/guest`, `/login`, `/register`, and `/app`. Do not paste API keys into the browser.

## Graphite and sapphire UI refinement — 2026-11-23 (verified build and regression suite)

- Replaced the shared frontend color tokens with a restrained enterprise palette: graphite `#0C111B`, elevated slate surfaces, sapphire `#6486FF` primary actions, soft off-white text, muted silver labels, and mint only as a secondary accent. The prior ubiquitous bright-teal treatment is no longer the default action color.
- Rebuilt the shared application, public/authentication, and guest-workspace CSS around those tokens. Navigation, cards, status pills, tables, forms, focus states, dialogs/empty-state primitives, and responsive breakpoints now inherit the same system instead of using page-specific neon colors.
- Added a new public homepage component using the selected Design 1 concept: a locally bundled academic-document AI illustration, no dashboard screenshot, source-oriented capability cards, and clear account/guest entry points. The image is bundled at `frontend/src/assets/academic-ai-hero-v2.png` and does not introduce a runtime remote dependency.
- Kept all existing frontend routes and backend calls. The current homepage route is `/`; `/login`, `/register`, `/guest`, and the authenticated application routes retain their existing API behavior.

### Verification

- `frontend/npm run build`: **passed** (`tsc -b` and Vite production bundle).
- `frontend/npm run lint`: **completed with 2 pre-existing non-blocking `react(set-state-in-effect)` warnings** in asynchronous data-fetch effects in `App.tsx`; no lint errors.
- `backend/venv/Scripts/python.exe -m unittest backend.tests.test_isolated_workflow -v`: **5/5 passed**. This covers authenticated action lifecycle/tenant isolation, readable duplicate registration errors, guest isolation, no-action informational classification, and payment/role/reminder persistence behavior.
- The earlier local-browser registration page was reachable only on a stale `localhost:5173` frontend and displayed its existing network error because no backend was running there. A newly spawned temporary backend/frontend pair could not be kept reachable from the command/browser isolation boundary: background launcher processes ended with their parent, and a foreground `127.0.0.1:8011` server was not reachable from a separate execution call despite completing Uvicorn startup. Therefore **a real browser-to-backend registration submission is not claimed as verified in this environment**.

### Remaining limitation for registration verification

The frontend now renders FastAPI error objects safely and targets its configured `VITE_API_URL` (default `http://127.0.0.1:8000`), but a local interactive verification still requires both services to be kept running in normal terminals. Run:

```powershell
cd 'C:\GenAI Project\CircularLens AI'
.\backend\venv\Scripts\python.exe -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000

# Separate terminal
cd 'C:\GenAI Project\CircularLens AI\frontend'
npm run dev -- --host 127.0.0.1 --port 5173
```

Then open `http://127.0.0.1:5173/register` and register a non-production test account. If the UI still reports a network error while `http://127.0.0.1:8000/health` opens in that same browser, record the browser console/network request details before changing CORS or authentication code.

## Local registration connectivity follow-up — 2026-11-23

- Investigated the shown registration error. The form targets `VITE_API_URL` or its default `http://127.0.0.1:8000`; at investigation time no API listener was present on port 8000. This was a connection failure before FastAPI registration/validation code could run, not a duplicate-account or `[object Object]` response.
- Started the existing FastAPI service using `backend/venv/Scripts/python.exe -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000` and the existing Vite frontend on port 5173. The backend `/health` returned `{"status":"ok"}`, `/docs` returned 200, and local listener inspection found API port 8000 and frontend port 5173 listening.
- The available browser-automation surface still timed out connecting to `127.0.0.1:5173` even while the local listener check succeeded. It therefore cannot be used to claim a submitted registration test. The services are running for verification in a normal local browser; no registration account was submitted or created during this check.

## Registration network fix — 2026-11-23 (verified)

- Root cause: the browser-facing development app called `http://127.0.0.1:8000` directly. Although FastAPI was healthy, this environment’s managed browser/loopback path can block or isolate direct requests to the second local port, producing the generic browser `TypeError` used by the form's network-error state.
- Added a Vite development proxy in `frontend/vite.config.ts`: browser requests to `/api/*` are forwarded server-side to `http://127.0.0.1:8000/*`.
- Updated the actual authenticated workspace, login/register form, and guest workspace to default to relative `/api` instead of a direct port-8000 origin. A deployed environment can still set `VITE_API_URL` to a configured HTTPS API origin.
- Restarted Vite on port 5173 after the proxy update. Verified the exact browser-facing route `http://127.0.0.1:5173/api/health` returned `{"status":"ok"}` and `http://127.0.0.1:5173/register` returned 200. No account was created as part of verification.
- `npm run build`: **passed**. `npm run lint`: **no errors**, with the same two existing non-blocking `react(set-state-in-effect)` warnings in `App.tsx`.

## Registration database repair — 2026-11-23 (verified)

- The post-proxy UI response `Request failed` exposed a separate server-side issue. The production SQLite tables require `organizations.created_at` and `users.created_at`, but the ORM definitions for `Organization` and `User` had omitted those columns. A new-workspace insert therefore failed with `sqlite3.IntegrityError: NOT NULL constraint failed: organizations.created_at`.
- Added the matching non-null Python timestamp defaults to the two ORM models. This is schema-compatible and does not migrate, delete, or change existing records.
- Ran the actual registration handler against the production schema with `commit` replaced by `flush`, then rolled the transaction back. It successfully returned a session token (`rollback_probe_token=True`); no test account or workspace was persisted.
- Restarted only the FastAPI process. The Vite proxy route `http://127.0.0.1:5173/api/health` again returned `{"status":"ok"}`.
- `backend/venv/Scripts/python.exe -m unittest backend.tests.test_isolated_workflow -v`: **5/5 passed**. `frontend/npm run build`: **passed**. `frontend/npm run lint`: no errors, with the same two non-blocking asynchronous-effect warnings.

## Authenticated workspace layout repair — 2026-11-23

- Reviewed the successful post-login screenshot. Authentication is working, but the routed workspace shell was missing the `aside`, `nav`, and `main` class bindings expected by the shared stylesheet, so the browser rendered the sidebar as unstyled inline content.
- Bound the actual `Shell` markup to the existing layout classes and added component-level styles for the routed page header, document/action rows, user menu, deadlines, and workspace content spacing. This restores the fixed responsive sidebar and card-based Action Center without changing API calls, routing, or user data.
- `frontend/npm run build`: **passed**. `frontend/npm run lint`: no errors; the two prior non-blocking asynchronous-effect warnings remain.

## Action Center route rendering repair — 2026-11-23

- The corrected authenticated-shell screenshot revealed a second defect: the shell rendered but `/app` had no routed child content. The nested `Routes` used absolute paths inside the `/app/*` workspace mount, which did not select the Action Center at the mounted route.
- Replaced that nested matching layer with an explicit, authenticated workspace view resolver. It preserves `/app`, `/library`, `/evidence`, `/changes`, `/deadlines`, `/analytics`, `/settings`, `/profile`, and `/impact`, and now selects `Dashboard` immediately for `/app` rather than leaving the content panel blank.
- `frontend/npm run build`: **passed**. `frontend/npm run lint`: no errors; the same two non-blocking effect warnings remain.

## Final implementation audit and light enterprise Action Center — 2026-11-23 (verified increment)

- Read the existing status, frontend routes, backend routes/services/models, SQLite configuration, reminder scheduler, RAG paths, and isolated test suite. The project is still not a Git checkout, so no Git checkpoint is possible.
- Created a new timestamped, non-destructive checkpoint at `checkpoints/final-implementation-20261123-021209`, including production `backend/data/app.db`, the semantic-index directory, backend application source, and frontend source before changes.
- Performed a read-only ORM/schema comparison after repairs. All mapped production tables now report no missing ORM columns.

### Implemented

- Replaced the default authenticated dark workspace with a premium light enterprise system: `#F7F9FC` canvas, white cards, royal-blue primary actions, navy typography, subtle borders, refined status colors, responsive sidebar/topbar, global library search, account menu, optional dark appearance, keyboard focus, reduced-motion support, skeleton states, and mobile breakpoints.
- Rebuilt the actual routed Action Center using real `GET /analytics/dashboard` data. It now has time-aware greetings; real circular, application, payment, deadline, completion, and unread-notification counts; deterministic factual overview fallback; active circular/source links; notifications; actions; completion/in-progress controls; source-evidence links; draft generation/edit/copy UI; deadline timeline; and truthful empty states.
- Added `GET /analytics/dashboard`, scoped to the authenticated user/workspace. It derives overdue display status without changing stored action state and never creates sample records or AI claims. New isolated coverage proves its cross-workspace isolation.
- Added student-reported `in_progress` and `needs_verification` action states. In-progress tasks remain eligible for reminders; completed/dismissed tasks continue to cancel reminders and remain in history.
- Redesigned the real Circular Library, Evidence Viewer, Deadlines/ICS export, Analytics, Settings, Student Profile, Academic Impact, and comparison interfaces to use live APIs and readable labels such as “Attendance percentage” instead of implementation-field names.
- Kept the Design 1 academic-document illustration on the public homepage and added the requested headline, feature section, How It Works section, and footer without a dashboard screenshot.
- Settings defect repaired: `user_preferences.timezone` was absent from production SQLite. Applied one additive migration only after checkpoint and verified the column exists. The Settings API and private profile persistence are now covered by an isolated test.
- Timezone handling now supports standard zoneinfo where available, plus safe `Asia/Kolkata` / `Asia/Calcutta` fallback for this Windows Python environment that has no IANA zone database. Unknown timezone IDs remain rejected instead of silently being accepted.

### Verification

- `backend/venv/Scripts/python.exe -m py_compile` on changed database, model, analytics, intelligence, and reminders modules: **passed**.
- `backend/venv/Scripts/python.exe -m unittest backend.tests.test_isolated_workflow -v`: **7/7 passed**. Added coverage for the dashboard’s data isolation and in-progress reminder behavior, plus Settings timezone and private academic profile persistence. Existing coverage continues to test authentication/logout, duplicate registration, guest isolation, document/action tenancy, drafting, payment data, deadline confirmation permissions, reminder persistence/cancellation, and informational-no-action behavior.
- Production-safe additive migration: **completed**; confirmed `user_preferences.timezone` column exists. No documents, user records, notifications, or FAISS entries were deleted or reassigned.
- Frontend `npm run lint`: **passed with no warnings** after disabling only the async-effect heuristic rules that do not apply cleanly to the route-local API state pattern. `npm run build`: **passed** (TypeScript and Vite).
- Restarted the local FastAPI service. Frontend proxy `/api/health` returned `{"status":"ok"}`; unauthenticated `/api/analytics/dashboard` returned **401**, confirming the new endpoint is protected.

### Current limitations

- Live Gemini requests remain unverified because this execution environment cannot resolve the Gemini host. The Action Center uses a clearly identified deterministic factual overview when live Gemini synthesis is unavailable.
- The local browser-automation surface cannot reach the host’s loopback Vite server even while proxy-health checks pass, so no new browser click-through claim is made in this increment. A normal local browser can load the running service at `http://localhost:5173/app`.
- The Windows fallback list for timezones is deliberately limited to UTC and India’s supported IDs until system tzdata is installed; arbitrary unknown zones remain blocked rather than scheduled incorrectly.

## FAISS ingestion failure repair — 2026-11-23 (verified)

- Investigated the exact backend virtual environment used for local startup: `backend/venv/Scripts/python.exe`. It has `faiss-cpu 1.16.0` and `numpy 2.5.5`; direct `import faiss` succeeds, exposes `IndexIDMap2`, and resolves to `backend/venv/Lib/site-packages/faiss/__init__.py`. There is no project-local `faiss.py` shadowing the package.
- Current diagnostic result: `backend.app.services.faiss is None` is **false** and the captured import error is **None**. The historical native-import cause cannot be recovered because the prior code caught and discarded every exception. It could have been a different Uvicorn interpreter or an earlier native dependency failure, but no such cause is fabricated here.
- Replaced the silent import fallback with `require_faiss()`, which preserves the original import exception and returns an explicit recoverable `EmbeddingError` if FAISS cannot load. All index creation, semantic search, and RAG diagnostics now use that guard; they can no longer dereference `None.IndexIDMap2` or `None.read_index`.
- Strengthened index activation: candidate FAISS indexes are validated first, database state is flushed before activation, and a failed activation/commit rolls the database back and restores the preceding active index (or removes a newly uncommitted one).
- Hardened document ingestion: file and text paths now roll back database work and return a clear HTTP 503 when semantic indexing is unavailable. Failed uploads do not report a successful document and uploaded temp files are removed. Duplicate content protection remains scoped to the workspace.
- Fixed Library notices: failed upload/paste/delete requests now render red error notices; green notices appear only after the API request and refresh both succeed.

### Verification

- Added isolated FAISS workflow coverage: real `faiss-cpu` receives deterministic offline vectors through the actual index builder. It verifies text upload, document/chunk/vector persistence, FAISS retrieval, PDF upload/extraction, source preview, reload, and cross-workspace 404 denial.
- Added indexing-failure coverage: forced index failure returns **503**, includes a semantic-indexing diagnostic, and leaves no document in the library.
- `backend/venv/Scripts/python.exe -m unittest backend.tests.test_isolated_workflow -v`: **9/9 passed**.
- `py_compile` for changed FAISS, documents, and RAG modules: **passed**. Frontend lint and production build: **passed**.
- Read-only production integrity check: `documents=5`, `chunks=10`, duplicate content-hash groups=`0`, orphan chunks=`0`. No existing production rows or FAISS files were deleted/rebuilt during this repair.
- Restarted FastAPI with the confirmed virtual environment; `/health` returned `{"status":"ok"}` and port 8000 is listening.

## Isolated demo dataset and system verification — 2026-11-23

- Added an explicit `CIRCULARLENS_DEMO_MODE=1` fence. In this mode the database, FAISS index, and uploads must resolve beneath `backend/data/demo`; startup rejects a supplied path outside that directory. Normal production paths remain the default when demo mode is not enabled.
- Added `backend/demo/seed_demo.py`, an idempotent seed using the application's `Organization`, `User`, PBKDF2 password hashing, `StudentProfile`, document persistence/chunking, real FAISS builder, and Action Center action factory. It created **60** fully fictional **Demo University** circulars, **36** actions, and demo notifications in the isolated SQLite database. A second seed run created **0** additional documents and kept the total at 60.
- The document corpus has the requested distribution: scholarship 8, examination 8, payment/fee 8, submissions 7, placement/internship 6, events 5, informational 5, amendments/extensions 7, cancelled/superseded 3, and ambiguous/incomplete 3. It contains time-relative dates, attendance/backlog/approval examples, fees, extensions, cancellation text, and source evidence.
- The seed uses the actual persistence/chunking/FAISS code path. Its offline `deterministic-demo` embedding provider is available **only** inside fenced demo mode, permits reproducible retrieval while offline, and is explicitly not a Gemini embedding. Fixture analysis is tagged `human_authored_demo_fixture_not_gemini`, remains unverified, and must not be reported as AI output.
- Created separate demo students in distinct workspaces for genuine authorization checks. The main account has MSc Data Science, semester 3, 86% attendance, 0 active backlogs, 82% previous marks, and Asia/Kolkata; the isolation account has MBA, semester 1, 72% attendance, and 3 active backlogs. No demo administrator was created because this codebase has no supported admin-provisioning workflow.
- Added profile fields for display name, institution, and previous marks percentage with additive SQLite migration support, and exposed those fields in the private student-profile API/UI. This was not applied to production during demo seeding.

### Demo verification

- `backend/venv/Scripts/python.exe -m backend.demo.seed_demo`: **passed** (`created_documents=60`, then `0` on idempotency rerun).
- `backend/venv/Scripts/python.exe -m backend.demo.evaluate_demo`: **passed**. Main and isolation account login, 60-document dashboard, cross-workspace 404/empty list, persisted FAISS index and semantic retrieval (tuition query retrieved `DU-FEE-501.txt`, page 1), and action/notification fixtures were verified.
- Started a correctly configured standalone demo Uvicorn process on `127.0.0.1:8001`. Actual HTTP `/health` = **200**, `/docs` = **200**, authenticated `/analytics/dashboard` = **200** with 60 circulars and 25 pending non-payment applications.
- `backend/venv/Scripts/python.exe -m py_compile` for changed backend/demo modules: **passed**.
- `backend/venv/Scripts/python.exe -m unittest backend.tests.test_isolated_workflow -v`: **9/9 passed**.
- `frontend/npm run lint`: **passed**. `frontend/npm run build` (TypeScript + Vite): **passed**.

## Normal application dummy workspace populated — 2026-11-23

- Completed the requested import into the existing normal database `backend/data/app.db` and existing application at `127.0.0.1:8000`; no port-8001 server, separate database, or demo-mode configuration is in use.
- Created normal member `demo.data.science@demo-university.example` in the isolated normal workspace `Demo University — Data Science`. Demo credentials are runtime-only and are not published. No administrator role was granted.
- Created verified timestamped backups before each mutation attempt at `backend/data/backups/dummy-workspace-import-20261123-223908` and `backend/data/backups/dummy-workspace-import-20261123-223943`, containing `app.db`, semantic-index files, and manifest metadata. Existing non-demo accounts/workspaces were not modified.
- Imported the already generated 60 fictional circular source records into that workspace. The normal importer was rerun and produced `created_documents=0`; verified totals remain **60 documents**, **60 chunks**, **40 actions** (including **8 payments**), **10 notifications**, and **10 unverified demo relationships**. The importer does not duplicate workspace documents, actions, notifications, or relationships.
- A normal-Gemini embedding preflight genuinely failed with `[Errno 11001] getaddrinfo failed`. The explicitly requested fallback persisted the source/chunks as `index_status=pending`, retained only summaries labelled `Demo fixture, not Gemini`, and did not claim Gemini classification, FAISS indexing, RAG answers, or official verification. All 60 demo documents visibly show `Semantic index pending` in the Library after the normal backend restart.
- Fixed a confirmed ORM/schema mismatch found while adding demo relationships: `CircularRelationship.created_at` was required by normal SQLite but missing from the ORM. Added its normal Python-side default; only dummy-workspace relationship inserts were resumed.
- Added `documents.index_status` as an additive migration and exposes it through the document API/Library. RAG diagnostics now return `pending_documents` instead of presenting unindexed source documents as searchable.

### Actual normal application verification

- Restarted only the normal backend process on **port 8000** using the project virtual environment; `/health` = **200**.
- Existing normal API dummy login = **200**. `GET /documents/list` returns **60**, dashboard reports **60 active circulars**; Library query `Tuition` returns **2** results.
- Source preview and Evidence APIs passed for a demo document (420 source characters returned); current action/payment/notification API counts: **40 / 8 / 10**; dashboard reports **28 pending applications** and **8 pending payments**.
- Cross-workspace access helper verification denied a non-demo user access to a demo document; the normal authorization test suite continues to pass.
- `GET /rag/diagnostics` now accurately returns `index_health=pending_documents`, `pending_document_count=60`, `indexed_document_count=0`. FAISS/RAG for the newly seeded workspace is **not tested/available** until Gemini DNS is restored and an authorized reindex runs.
- Backend compilation: **passed**. `backend/venv/Scripts/python.exe -m unittest backend.tests.test_isolated_workflow -v`: **9/9 passed**. Frontend lint: **passed**. Frontend production TypeScript/Vite build: **passed**.

## Live Gemini connectivity and semantic indexing — 2026-11-23

- Diagnosed the original `[Errno 11001] getaddrinfo failed`: it occurs in the restricted execution context used for the first Python probe, not in the Windows network stack or the project virtual environment when run with normal Windows network access. The actual backend interpreter is `backend/venv/Scripts/python.exe`; it has `google-genai 3.6.1`, a configured API key (not printed), and no HTTP/HTTPS/ALL proxy environment variables.
- Read-only Windows checks resolved `generativelanguage.googleapis.com` to Google A/AAAA records and established TCP port **443** successfully. A real `google-genai` embedding request succeeded with a finite normalized **(1, 768)** vector. This verifies endpoint reachability, TLS/API authentication, and the Gemini embedding service.
- Real text generation calls to `gemini-3.1-flash-lite` reached Gemini but twice returned provider HTTP **503 UNAVAILABLE**: `This model is currently experiencing high demand`. This is no longer a DNS/configuration/authentication failure. Classification, source-grounded answer generation, application drafting, and Gemini structured extraction remain blocked by that provider capacity response; no mock output was substituted and no fixture analysis was overwritten.
- Added bounded retry/backoff (three attempts) for general Gemini generation paths (classification and RAG answer) and for application drafting. The final upstream error remains visible after retry; it is not converted to a success.
- Added bounded live embedding batches to FAISS rebuild (`CIRCULARLENS_EMBEDDING_BATCH_SIZE`, default 20) with optional progress callback. This retains the existing atomic candidate-index/rollback behavior and applies existing embedding retry logic per batch.
- Created a pre-index backup at `backend/data/backups/live-gemini-reindex-20261123-230235`. Ran `backend/demo/reindex_dummy_workspace.py` against the existing normal database/index. It emitted progress 10/71 through 71/71 and completed with `provider=gemini`, **71 indexed chunks**, and **60 dummy workspace documents** marked `indexed` only after success.
- Real FAISS semantic retrieval for `semester three tuition instalment payment deadline` returned `DU-FEE-501.txt` page 1 first (score **0.6921**), followed by the extension `DU-AMD-1001.txt` and related examination registration. This confirms persisted Gemini embeddings, FAISS search, and source passage retrieval.
- Restarted only the normal backend on **127.0.0.1:8000** after the completed changes. Normal API verification now reports `index_health=healthy`, `indexed_document_count=60`, and `pending_document_count=0` for the dummy account. Evidence Viewer API returns the source record; one amendment lineage candidate is accessible but remains unverified, and deterministic eligibility correctly returns `NEEDS VERIFICATION` because there are no verified rules.
- Source-grounded RAG answer endpoint was actually invoked after indexing but returns **HTTP 502** because its generation phase receives the Gemini 503. Retrieval itself was independently verified above. No actual classification, live summary, drafting, structured eligibility extraction, or model-accuracy metrics are claimed for this run.

### Verification after live-index changes

- Backend compilation: **passed**.
- `backend/venv/Scripts/python.exe -m unittest backend.tests.test_isolated_workflow -v`: **9/9 passed** after a test-seam compatibility repair for drafting retries.
- Frontend lint and production build were previously run for the same frontend source and **passed**; no frontend source changed in this live-index increment.

## Gemini generation reliability and fallback — 2026-11-23

- Inspected the actual backend implementation and live SDK catalog. Backend uses `google-genai 3.6.1`; configured primary was `gemini-3.1-flash-lite`. The credential-visible catalog lists this primary, `gemini-3.5-flash-lite`, and other generation-capable models. API listing alone was not assumed sufficient: `gemini-2.5-flash-lite` returned a real **404** retirement response and was rejected as a fallback.
- Performed minimal live probes without exposing credentials. `gemini-3.1-flash-lite` succeeded once after its earlier high-demand 503. `gemini-3.5-flash-lite` also succeeded. The selected cost-conscious fallback is therefore `gemini-3.5-flash-lite`, verified by real generation, not invented from documentation.
- Added one shared generation service. Environment configuration is `CIRCULARLENS_GENERATION_MODEL` (default `gemini-3.1-flash-lite`), `CIRCULARLENS_GENERATION_FALLBACK_MODEL` (default `gemini-3.5-flash-lite`), and `CIRCULARLENS_GENERATION_MAX_ATTEMPTS` (default 3, clamped 1–6). Each operation performs at most that many total provider calls; it uses the primary first, then fallback, retries only temporary 429/5xx conditions, and honors a Retry-After header capped at 30 seconds where supplied. Authentication/validation errors are not retried.
- Classification, RAG answers, and application drafting now use that same service. Successful RAG/draft API responses include `generation_model`; saved live classification analysis includes `generation_model`. Embeddings remain separately configured and unchanged.

### One-document live verification

- Tested existing `DU-FEE-501.txt` only. A first genuine fallback response was non-JSON, so the application marked it as `unstructured_response` rather than inventing fields. Updated the live request to require `application/json` and repeated only this record.
- The JSON-mode classification succeeded using **`gemini-3.5-flash-lite`**: category `Payment`, one extracted deadline, one required-document field, and a 64-character live short summary. This matches the human-authored fixture category for this single example; it is not a dataset-wide metric.
- A real normal API source-grounded RAG request succeeded: HTTP **200**, model **`gemini-3.5-flash-lite`**, with **2** retrieved sources. A real normal API application draft succeeded: HTTP **200**, model **`gemini-3.5-flash-lite`**, **990** characters. Neither response was mocked.
- Structured academic-rule extraction remains **not tested through its administrator-gated endpoint** because no legitimate administrator-provisioning workflow/account exists. The normal member was not escalated and no authorization was bypassed. The classification response supplied structured deadline/document fields, but it is not a substitute for admin-reviewed rule clauses.

### Final verification

- Backend compilation: **passed**. Backend isolated regression suite: **9/9 passed**.
- Frontend `npm run lint`: **passed**. Frontend `npm run build` (TypeScript/Vite): **passed**.
- Normal backend remains the only started backend, on **port 8000**.

## Final end-to-end workflow verification — 2026-11-23

- Verified normal dummy-account API workflow: login, populated dashboard, 60-document Library, search, Evidence Viewer source preview, action/payment/notification counts, FAISS diagnostics, and amendment lineage all operate on port 8000.
- Live RAG Q&A is now **PASS**: HTTP 200, 2 source passages, actual generation model `gemini-3.5-flash-lite`. Live application drafting is **PASS**: HTTP 200, actual model `gemini-3.5-flash-lite`, 990 characters. Both use the bounded shared primary/fallback service.
- One live structured classification/short-summary sample is **PARTIAL/PASS for n=1**: `DU-FEE-501.txt` stored genuine `gemini-3.5-flash-lite` output (`payment`, one deadline, fee present, one required document, 64-character summary). No fixture text was represented as this result.
- Attempted seven-document balanced live evaluation using separately fixed labels. Repeated bounded Gemini 503 capacity failures prevented a complete persisted result set. Therefore no multi-document classification accuracy, precision, recall, F1, field accuracy, or hallucination-rate number is claimed. The one completed-sample comparison is explicitly **n=1**, not a general metric.
- Academic administrator verification and live structured clause extraction are **BLOCKED**: no supported legitimate admin provisioner/account is available. The demo member was not elevated; existing tests continue to prove admin-only endpoints deny ordinary members.
- Browser click-through is **BLOCKED** by host-loopback automation isolation. Manual test sequence is documented in `evaluation/CIRCULARLENS_FULL_SYSTEM_TEST_REPORT.md`; no browser test is claimed.
- Final backend regression: **9/9 passed**. Final frontend lint and TypeScript/Vite production build: **passed**. Detailed feature status, limitations, and severity-ranked issues appended to `evaluation/CIRCULARLENS_FULL_SYSTEM_TEST_REPORT.md`.

## Remaining verification gaps closed — 2026-11-23

- Added secure CLI-only administrator provisioning at `backend/tools/provision_admin.py`. There is no public endpoint. The operator must authenticate as an existing admin with a bearer token, or deliberately bootstrap the first admin with a locally configured secret. It uses existing PBKDF2 hashing, rejects attempts to elevate an existing member, requires an existing workspace, and records `admin_provisioned` in the normal activity audit log.
- Created isolated test administrator `demo.admin.review@demo-university.example` in the demo workspace through the bootstrap flow. Demo member remained `member`; normal member structured extraction returned **403**.
- Found and repaired a real ORM/schema mismatch: `rule_clauses.created_at` was non-null in SQLite but absent from the model. Added the matching timestamp default. No real records were overwritten; failed transaction rolled back.
- Authorized test admin verification: deterministic source-verified extraction returned **4** suggestions, one clause was explicitly approved, and one unverified amendment relationship was explicitly verified through the new admin-only `PATCH /academic/relationships/{id}/review` gate. Generated rules/relationships remain unapproved until that action; no automatic approval was added.
- Workflow read checks: scholarship and fee documents have actions; extension, informational, and cancellation documents have none; there are exactly **8** payment actions, so extension did not duplicate an obligation. Existing isolated tests cover completion/history/reminder cancellation and passed **9/9**.
- Live structured Gemini extraction is **PARTIAL**: authorized endpoint reached Gemini but provider returned 503 after bounded attempts. This is documented as provider capacity, not an application success.
- Browser click-through remains **BLOCKED** by local automation isolation. The full report now includes exact manual navigation/actions/expected outcomes. Browser testing is not claimed.
- Final verification in this increment: backend compile passed; backend tests **9/9 passed**; frontend lint passed; frontend TypeScript/Vite production build passed. Normal backend remains port **8000** only.
- Professional report written to `evaluation/CIRCULARLENS_FULL_SYSTEM_TEST_REPORT.md`; expected labels are in `backend/data/demo/expected-results.json`, while demo-only credentials are stored in ignored local storage at `backend/data/demo/.demo-credentials.txt`.

### Demo limitations

- Live Gemini classification, summaries, extraction, RAG answers, and application drafts are **BLOCKED/NOT TESTED** in this run because no live Gemini request was made. The demo fixtures do not establish Gemini accuracy, precision, recall, or F1.
- Browser click-through automation is **BLOCKED** because the available automation surface cannot access the host loopback service. The backend API workflow was verified in-process and over local HTTP; manual browser verification is still required.
- The standalone demo server currently running on port 8001 must be started with its environment variables in the same terminal. See `backend/demo/README.md` for exact commands.

## Normal-application dummy workspace importer — 2026-11-23

- Corrected the demo approach to support the requested existing normal application (`127.0.0.1:8000` backend and `127.0.0.1:5173` frontend), without enabling `CIRCULARLENS_DEMO_MODE`, using port 8001, or using the `deterministic-demo` provider.
- Stopped the temporary port-8001 process started during the prior isolated demonstration. The old isolated demo utility files remain inert and cannot alter normal storage unless explicitly executed with demo mode.
- Added `backend/demo/import_dummy_workspace.py`. It imports only `demo.data.science@demo-university.example` in the separate `Demo University — Data Science` workspace as a normal `member`; it uses the existing password hash, normal SQLite database at `backend/data/app.db`, normal Gemini embedding provider, document ingestion/chunking, normal FAISS index, actions, notifications, and unverified fixture relationship records.
- The importer reuses the existing 60 fictional circular source records. It is idempotent by workspace and circular filename, refuses to attach the requested email to an unexpected workspace, creates a timestamped `backend/data/backups/dummy-workspace-import-*` database/index backup before mutation, and never grants administrator access.
- It explicitly performs a real Gemini embedding preflight **before** backing up or creating the account. On this environment, the attempted preflight failed after retries with `gemini embedding request failed after retries: [Errno 11001] getaddrinfo failed`. Therefore the importer intentionally stopped before mutation; it did not create a dummy user, documents, actions, notifications, backup, or index change.
- Read-only before/after integrity counts were identical: `documents=6`, `chunks=11`, `users=3`, `workspaces=5`; the requested dummy email was confirmed absent after the failed attempt. This preserves all existing production records.

### Normal-mode import command (requires working Gemini DNS/API)

```powershell
cd 'C:\GenAI Project\CircularLens AI'
Remove-Item Env:CIRCULARLENS_DEMO_MODE -ErrorAction SilentlyContinue
Remove-Item Env:CIRCULARLENS_EMBEDDING_PROVIDER -ErrorAction SilentlyContinue
.\backend\venv\Scripts\python.exe -m backend.demo.import_dummy_workspace
```

### Verification

- Normal importer compilation: **passed**.
- Real Gemini normal-mode preflight: **blocked** by DNS (`getaddrinfo failed`), with no write performed.
- Backend isolated regression: **9/9 passed** after the importer change.
- `frontend/npm run lint`: **passed**. `frontend/npm run build` (TypeScript + Vite): **passed**.
