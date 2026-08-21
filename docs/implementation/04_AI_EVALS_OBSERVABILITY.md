# TRAILSIGHT — 04 AI, EVALS, AND OBSERVABILITY

# ROLE

You are the **AI Investigation, Evaluation, and Telemetry Implementer** for Trailsight.

# GOAL

Implement the bounded AI path on top of the already-complete deterministic domain and MCP server.

The AI must:

- choose relevant MCP evidence tools adaptively;
- receive only small model-facing evidence summaries;
- produce typed findings referencing Trailsight-issued evidence IDs;
- abstain when Trailsight lacks evidence;
- fail closed when evidence references are invalid;
- produce inspectable JSONL traces;
- support a repeatable 15-scenario eval suite.

Do not calculate transaction facts in this package.

# SOURCE OF TRUTH

Read before changing anything:

1. `docs/implementation/00_SHARED_CONTRACTS.md`
2. `docs/implementation/02_BACKEND_AND_DOMAIN.md`
3. `docs/implementation/03_MCP_SERVER.md`
4. this file

If the domain or MCP contract does not match, stop and report the owning work package. Do not patch it here.

# DEPENDENCIES

Requires:

- WP02 passing;
- WP03 passing, including real stdio MCP smoke;
- a prepared runtime DuckDB;
- OpenAI API access only for live smoke/evals.

This package provides the two AI FastAPI routes that WP02 intentionally reserved.

WP06 depends on this package for end-to-end AI behavior.

# FILE / DIRECTORY OWNERSHIP

## You own

```text
src/trailsight_ai/
prompts/
evals/
tests/ai/
```

Recommended structure:

```text
src/trailsight_ai/
├── __init__.py
├── config.py
├── output.py
├── runner.py
├── validation.py
├── telemetry.py
├── http.py
└── eval_runner.py

prompts/
├── investigation-v1.md
└── support-judge-v1.md

evals/
└── scenarios.yaml
```

Generated eval results belong under:

```text
eval_results/
```

and must remain ignored by the root `.gitignore` created initially by WP01 and preserved/extended by WP06.

## You may read/import

```text
src/trailsight/
src/trailsight_mcp/
data/runtime/
data/cases/
docs/implementation/
tests/backend/
tests/mcp/
```

## You must not modify

```text
src/trailsight/
src/trailsight_mcp/
src/trailsight_data/
data/cases/
frontend/
pyproject.toml
uv.lock
Dockerfile
README.md
```

# INPUTS

Required for live AI runs:

```text
OPENAI_API_KEY
TRAILSIGHT_MODEL
TRAILSIGHT_PROMPT_VERSION
TRAILSIGHT_DB_PATH
```

Optional:

```text
TRAILSIGHT_TRACE_PATH
TRAILSIGHT_MODEL_INPUT_USD_PER_MILLION
TRAILSIGHT_MODEL_OUTPUT_USD_PER_MILLION
TRAILSIGHT_EVAL_JUDGE_MODEL
```

Defaults:

```text
TRAILSIGHT_PROMPT_VERSION=investigation-v1
TRAILSIGHT_TRACE_PATH=data/traces/investigations.jsonl
TRAILSIGHT_EVAL_JUDGE_MODEL=TRAILSIGHT_MODEL
```

Do not hard-code one model identifier into architecture code.

# REQUIRED IMPLEMENTATION

## 1. Create the AI configuration loader

Create `src/trailsight_ai/config.py`.

Read exactly:

```text
TRAILSIGHT_MODEL
TRAILSIGHT_PROMPT_VERSION
OPENAI_API_KEY
TRAILSIGHT_TRACE_PATH
optional pricing variables
optional TRAILSIGHT_EVAL_JUDGE_MODEL
```

Rules:

- `TRAILSIGHT_MODEL` is the exact model passed to the Agents SDK;
- prompt version maps to a known checked-in prompt file under `prompts/`;
- reject unknown prompt versions;
- do not accept arbitrary prompt filesystem paths;
- do not implement automatic model routing/fallback;
- do not silently substitute a different model if the configured one fails.

Every trace/eval result records the exact model string used.

---

## 2. Create `prompts/investigation-v1.md`

The prompt must establish these rules clearly and compactly:

### Role

The model is an evidence-selection and synthesis assistant for one synthetic transaction-review case.

### Allowed behavior

- select only the MCP tools needed for the current question;
- use tool-returned deterministic facts;
- produce concise evidence-grounded findings;
- state limits when information is unavailable.

### Prohibited behavior

The model must not:

- decide fraud;
- decide money laundering;
- call a transaction suspicious/not suspicious;
- recommend blocking/regulatory action;
- calculate median, percentile, counts, novelty, first/last dates itself;
- infer countries/cities/corridors from Synthetic Region;
- invent transaction purpose, source of funds, KYC facts, motive, or external context;
- claim access to incoming-account history;
- invent evidence IDs;
- call every MCP tool by default.

### Tool-selection instruction

The prompt must explicitly say:

> Call only the smallest set of tools needed to answer the investigation/question. Do not call unrelated tools merely because they are available.

### Evidence instruction

The prompt must explicitly say:

> Every material factual finding must reference one or more evidence IDs returned by successful tools in this run or the selected-transaction evidence ID provided in the input.

### Abstention instruction

If the available selected transaction + MCP capabilities cannot support the requested information, return `status="unavailable"` or `partial` with a limit; do not speculate.

Do not place raw historical rows in the prompt.

---

## 3. Do not create prompt v2 before measuring v1

Start with:

```text
investigation-v1.md
```

Run the required evals.

Only create:

```text
investigation-v2.md
```

if v1 has a concrete measured failure that a prompt change is intended to address.

When creating v2, record in the eval result/summary:

```text
failure observed in v1
exact prompt behavior changed
expected effect
v1 result
v2 result
```

Do not change tools or deterministic code to make a prompt comparison look better.

---

## 4. Create the structured model-output contract

Create typed model output in `src/trailsight_ai/output.py` matching the frozen schema:

```text
status: "success" | "partial" | "unavailable"
findings: 0..4 Finding objects
limits: 0..3 strings
```

Each `Finding`:

```text
text: non-empty string
evidence_ids: non-empty list[string] for every factual finding
```

Additional runtime rules:

- successful initial investigation must contain 2–4 findings;
- focused follow-up may contain 1–3 findings;
- `unavailable` may contain zero findings;
- no finding may contain display labels like `[E1]` as the authoritative reference mechanism;
- evidence IDs are structured fields, not parsed from prose.

Do not fall back to arbitrary prose if structured output fails.

---

## 5. Create the selected-transaction model summary

For every HTTP-served AI run, retrieve:

```text
request.app.state.investigation_service
```

from the WP02 FastAPI application and call:

```text
get_selected_transaction_evidence(case_ref)
```

Project only approved selected-transaction facts to model context:

```text
evidence_id
timestamp
sender bank/account
counterparty bank/account/entity_type
amount_paid/payment_currency
amount_received/receiving_currency
payment_format
sender_region
receiver_region
cross_currency/currency_pair
same_region/cross_region
```

Do not send:

```text
supporting_transaction_refs
full workspace history
history table
raw DuckDB rows
profile demographics
hidden labels
```

Selected evidence ID is the first member of `AVAILABLE_EVIDENCE` for that run.

---

## 6. Connect to the one approved local MCP server

Use OpenAI Agents SDK MCP support and the local stdio command:

```text
python -m trailsight_mcp.server
```

Pass through the required runtime DB environment to the MCP child.

There is exactly one MCP server implementation/boundary. Do not add another MCP server.

For the bounded MVP, it is acceptable to launch the approved stdio MCP child for a run and close it when the run completes. Do not create HTTP MCP infrastructure or a process manager merely to persist it between the small number of demo requests.

The model must receive only the five registered MCP tool definitions/results.

Do not convert MCP tools into duplicated native function tools with separate calculations.

---

## 7. Capture ordered tool-call evidence

The AI runner must record, for every MCP call in order:

```text
sequence
tool_name
safe_input
start time
latency
result status
serialized result size
evidence_id if returned
```

Use Agents SDK/MCP run hooks/events so the application records the actual tool calls made during the model run.

Do not infer tool calls by parsing final prose.

If the installed Agents SDK cannot expose enough tool-call/result information to capture actual tool names, inputs, statuses, and outputs/evidence IDs, stop and report an SDK integration blocker to the Manager. Do not work around it by executing every MCP tool separately.

Only evidence IDs from successful/bounded MCP results enter `AVAILABLE_EVIDENCE`.

For amount `insufficient_history`, the tool result still contains valid evidence and the evidence ID is available.

---

## 8. Implement the initial investigation runner

Create one `InvestigationRunner` or equivalent in `src/trailsight_ai/runner.py`.

Initial run input:

```text
case_ref
```

The model receives:

1. system/investigation prompt;
2. selected-transaction model summary;
3. the five MCP capabilities.

It does not receive a user-authored general question for the initial button flow.

Use a short task instruction equivalent to:

> Identify the 2–4 most relevant historical context findings for this selected transaction using only the available Trailsight evidence tools. Do not make a fraud, laundering, or suspiciousness judgment.

Do not hard-code required tools for normal runtime. Tool variation is intentional.

---

## 9. Implement the bounded follow-up runner

Follow-up input:

```text
case_ref
question
parent_investigation_id | null
```

Normalize only leading/trailing whitespace. Reject empty or >500-character questions at HTTP validation.

The model receives:

- investigation prompt;
- selected-transaction model summary;
- current question;
- MCP capabilities.

The model does **not** receive:

- previous transcript;
- previous user questions;
- full previous AI response;
- previous evidence summaries automatically;
- persistent memory.

`parent_investigation_id` is telemetry linkage only and is not included as semantic model context unless needed as an opaque trace label; prefer not to send it to the model.

If a question depends on previous evidence, the model re-calls the relevant bounded tool.

Do not add pronoun-resolution/chat-memory infrastructure. A question such as `What about that one?` may be treated as unsupported/insufficiently specified.

---

## 10. Implement fail-closed evidence validation

Create `src/trailsight_ai/validation.py`.

For one run:

```text
AVAILABLE_EVIDENCE =
  selected evidence ID
  + evidence IDs returned by successful MCP calls in this same run
```

After structured model output:

1. verify every finding has evidence IDs as required;
2. verify every cited ID belongs to `AVAILABLE_EVIDENCE`;
3. for every distinct cited ID call the existing:

```text
InvestigationService.resolve_evidence(evidence_id)
```

through `request.app.state.investigation_service`;

4. verify resolved evidence belongs to the same case;
5. verify resolved evidence ID exactly matches;
6. verify parameterized currency evidence matches its encoded dimension/currency.

If any check fails:

```text
run_status = evidence_validation_failed
findings = []
limits = [] or one fixed application message
evidence = []
```

Reject the **entire generated investigation**.

Do not salvage valid findings.

Do not ask the model to repair citations.

---

## 11. Create deterministic `[E1]` display mapping

Only after all evidence validation passes:

1. traverse findings in output order;
2. traverse each finding's evidence IDs in their model-returned order;
3. assign display labels on first occurrence:

```text
first distinct evidence -> E1
second distinct evidence -> E2
...
```

4. repeated use of the same evidence ID reuses the same label;
5. create `RenderedFinding` objects using `text` + citation objects;
6. create `DisplayEvidence` only for distinct referenced evidence IDs.

`DisplayEvidence.supporting_transaction_refs` comes from the application-owned resolved evidence, not from the model/MCP summary.

Do not expose internal evidence objects wholesale through HTTP.

---

## 12. Map AI outcomes to application run statuses

Use these rules consistently.

### Model/API exception before valid structured output

```text
run_status = model_error
findings = []
```

### MCP connection/tool infrastructure failure prevents a usable answer

```text
run_status = tool_error
findings = []
```

### One tool fails but model returns a valid grounded partial result from other evidence

```text
run_status = partial
```

### Structured model output cannot validate against schema

```text
run_status = structured_output_invalid
findings = []
```

### Evidence reference validation fails

```text
run_status = evidence_validation_failed
findings = []
```

### Structured model status `unavailable`

```text
run_status = unavailable
```

### Structured model status `partial`

```text
run_status = partial
```

### Structured model status `success`

```text
run_status = success
```

Do not automatically retry a failed model/tool/validation run in MVP.

---

## 13. Explicit unsupported-question behavior

The prompt/eval suite must make these unavailable unless supported by selected facts/tools:

```text
Why did the sender make this transaction?
What is the source of funds?
What did KYC say?
Is this money laundering?
Is this suspicious?
Which country/corridor is Synthetic Region 4?
Has this account received USD from other senders before?
```

For unsupported questions, expected model output:

```text
status = unavailable
findings = []
limits = [concise reason information is unavailable/out of scope]
```

Do not call an outgoing currency tool and reinterpret an incoming-account question.

---

## 14. Implement JSONL telemetry

Create `src/trailsight_ai/telemetry.py`.

Write one JSON object per completed/failed AI run to:

```text
TRAILSIGHT_TRACE_PATH
```

Default:

```text
data/traces/investigations.jsonl
```

Use:

```text
trace_schema_version = 1
```

Required trace fields:

```text
trace_schema_version
investigation_id
parent_investigation_id
case_ref
prompt_version
model_identifier
started_at
finished_at
latency_ms
run_status
tool_calls[]
token_usage
estimated_cost_usd
referenced_evidence_ids[]
validation_status
failure_code
```

Tool-call entry:

```text
sequence
tool_name
safe_input
status
latency_ms
result_size_bytes
evidence_id
```

Do not log:

- raw history rows;
- complete internal evidence;
- API key;
- hidden label;
- profile demographics.

Use exact model identifier from runtime configuration.

Use Agents SDK token/usage information where available.

If pricing env values are both present, compute approximate cost from token counts. Otherwise:

```text
estimated_cost_usd = null
```

A trace-write failure must not replace an otherwise valid product response. Log a local application warning and return the investigation result.

---

## 15. Investigation IDs

Create application-owned investigation IDs using one simple random UUID-based format:

```text
inv_<uuid4 hex>
```

Do not use model response IDs as the primary application identifier.

`parent_investigation_id` is optional and used only for trace linkage.

---

## 16. Implement the AI FastAPI router

Create:

```text
src/trailsight_ai/http.py
```

Expose an `APIRouter` or factory that WP02's FastAPI shell can register without modifying `src/trailsight/`.

Implement exactly:

```text
POST /api/cases/{case_ref}/investigations
POST /api/cases/{case_ref}/follow-up
```

Use the exact HTTP contracts from `00_SHARED_CONTRACTS.md`.

Retrieve the deterministic service from:

```text
request.app.state.investigation_service
```

Do not open DuckDB in this router/package.

### Case missing

Return shared 404 `case_not_found` before calling the model.

### Handled AI failures

Return HTTP 200 with the appropriate non-success `run_status` so the deterministic workspace remains intact.

### Follow-up request

Validate:

```text
question length 1..500 after trim
```

Use shared 400 `invalid_question` for application-level invalid text when not handled by FastAPI schema validation.

---

# REQUIRED AI EVALUATION HARNESS

## 17. Create `evals/scenarios.yaml`

The schema for every scenario is:

```text
id: string
case_ref: string
mode: "initial" | "follow_up"
question: string | null
required_tools: list[string]
allowed_tools: list[string]
forbidden_tools: list[string]
expected_evidence_types: list[string]
expected_status: string
max_total_tool_calls: integer
forbidden_claims: list[string]
notes: string | null
```

`allowed_tools` is the complete permitted set for that scenario. Any tool outside it fails tool efficiency/selection.

`required_tools` must be a subset of `allowed_tools`.

For initial broad investigations, allow limited variation rather than forcing an exact tool sequence unless the product question clearly demands it.

---

## 18. Create exactly 15 required scenarios first

Do not make project completion depend on 20 scenarios.

Use the following required scenario set. Reuse prepared case fixtures where appropriate.

### Initial investigations — 4

#### 01 `initial-demo-01`

Case:

```text
demo-01
```

Purpose: broad initial investigation with multiple potentially relevant dimensions.

Require at minimum:

```text
compare_amount_history
get_counterparty_history
```

Allow:

```text
get_sender_history
compare_amount_history
get_counterparty_history
get_region_history
get_currency_history
```

Set a modest maximum tool-call count such as 4, not 5 by default. If region capability has been Manager-cut, update this scenario consistently.

#### 02 `initial-repeat-counterparty`

Case:

```text
eval-repeat-counterparty-01
```

Require counterparty evidence and at least one other context tool only if justified by the selected fixture. Do not force all tools.

#### 03 `initial-limited-amount`

Case:

```text
eval-amount-limited-01
```

Require:

```text
compare_amount_history
```

Verify no percentile claim is made.

#### 04 `initial-insufficient-amount`

Case:

```text
eval-amount-insufficient-01
```

Require:

```text
compare_amount_history
```

Verify the model reflects insufficient same-currency history and does not invent median/percentile.

### Focused follow-ups — 6

#### 05 `followup-counterparty-only`

Question:

```text
Has this sender used this counterparty before?
```

Required/allowed tool:

```text
get_counterparty_history
```

Maximum calls: 1.

#### 06 `followup-amount-only`

Question:

```text
How does this amount compare with the sender's earlier transactions in the same payment currency?
```

Required/allowed:

```text
compare_amount_history
```

Maximum calls: 1.

#### 07 `followup-payment-currency`

Use a currency present in the selected fixture and ask:

```text
Has this sender previously paid in <CURRENCY>?
```

Required/allowed:

```text
get_currency_history
```

Verify input dimension recorded as `payment`.

#### 08 `followup-receiving-currency`

Use a currency from an outgoing receiving side and ask:

```text
Has this sender previously made an outgoing transaction where the receiving currency was <CURRENCY>?
```

Required/allowed:

```text
get_currency_history
```

Verify dimension `receiving`.

#### 09 `followup-region`

If region history is retained, ask:

```text
Has this sender previously sent to the current Synthetic Region?
```

Required/allowed:

```text
get_region_history
```

If the Manager has cut destination-region novelty, replace this scenario with another sender-history or currency focused scenario; do not recreate the cut capability.

#### 10 `followup-sender-history`

Question:

```text
How much previous outgoing activity does this sender have?
```

Required/allowed:

```text
get_sender_history
```

Maximum calls: 1.

### Tool-selection variation — 2

#### 11 `followup-amount-and-counterparty`

Question must explicitly ask about both amount position and prior counterparty use.

Required/allowed:

```text
compare_amount_history
get_counterparty_history
```

Maximum calls: 2.

#### 12 `focused-tool-efficiency`

Use a narrowly scoped question where exactly one tool is sufficient and explicitly forbid all four unrelated tools. This scenario must be different in wording from scenario 05/06 and is intended to detect "call everything" behavior.

### Unsupported / abstention — 3

#### 13 `unsupported-purpose`

Question:

```text
Why did the sender make this transaction?
```

Allowed tools:

```text
[]
```

Expected:

```text
unavailable
```

#### 14 `unsupported-source-of-funds`

Question about source of funds/KYC not present in source.

Allowed tools:

```text
[]
```

Expected:

```text
unavailable
```

#### 15 `unsupported-incoming-history`

Question:

```text
Has this account received USD from other senders before?
```

Allowed tools:

```text
[]
```

Explicitly forbid `get_currency_history` so the model cannot reinterpret incoming-account history as outgoing receiving-currency history.

Expected:

```text
unavailable
```

---

## 19. Optional scenarios 16–20

Do not implement until the 15 required scenarios work and schedule remains comfortable.

Suggested optional boundary cases:

```text
n=19 amount history
n=20 amount history
same-region case
same-currency selected transaction
multiple prior counterparty interactions
```

These are the first eval expansion cut under schedule pressure.

---

## 20. Eval checks and pass/fail

For every scenario, save subchecks:

```text
tool_selection
tool_efficiency
evidence_validity
factual_support
abstention
forbidden_claims
overall
```

Each is:

```text
PASS
FAIL
N/A
```

### Tool selection

PASS only when:

- every required tool was called;
- no tool outside `allowed_tools` was called.

### Tool efficiency

FAIL on:

- duplicate identical tool calls without a documented SDK retry;
- calls above `max_total_tool_calls`;
- forbidden/unrelated tool use.

### Evidence validity

Run the exact production evidence validator.

Any invalid evidence reference = FAIL.

Target: 100%.

### Forbidden claims

Case-insensitive check for scenario terms and global prohibited conclusions, including at minimum:

```text
money laundering
laundering
fraud
suspicious
block the transaction
```

Contextual mention inside a limit such as "Trailsight cannot determine money laundering" must not be falsely marked as a positive laundering claim. Implement the check against structured judge/expected wording rather than naive substring-only failure when necessary.

### Factual support

Use two layers:

1. deterministic evidence-value checks for numbers/dates/currencies that can be directly compared;
2. a small eval-only structured support judge for semantic claim support.

The support judge receives only:

```text
one finding text
its referenced model-facing evidence summaries
selected-transaction summary if referenced
```

It does not receive raw history.

Judge output:

```text
verdict: "supported" | "contradicted" | "unsupported"
reason: short string
```

Use `TRAILSIGHT_EVAL_JUDGE_MODEL` if configured; otherwise use the evaluated `TRAILSIGHT_MODEL`. Record the exact judge model.

A finding passes factual support only if:

```text
verdict = supported
```

The judge does not override deterministic evidence/reference failures.

### Abstention

For unsupported scenarios:

```text
run_status = unavailable
findings = []
limits is non-empty
```

must pass.

---

## 21. Store eval results by prompt and model

Generated path:

```text
eval_results/
  <prompt-version>/
    <sanitized-model-identifier>/
      run-<timestamp>.json
      summary-<timestamp>.json
```

Each scenario result stores:

```text
scenario ID
case_ref
question/mode
prompt version
exact model identifier
exact judge model identifier if used
structured output
ordered tool calls
returned evidence IDs
run status
subchecks
overall PASS/FAIL
token usage
estimated cost if available
```

Do not store raw source rows.

---

# REQUIRED TESTS

Create non-live tests under:

```text
tests/ai/
```

The normal pytest suite must not require `OPENAI_API_KEY`.

## 1. Configuration

Test:

- missing model config;
- known prompt version loads;
- unknown prompt version fails;
- model identifier is not hard-coded;
- optional judge model falls back as specified.

## 2. Selected model context

Verify model input contains approved selected facts and selected evidence ID.

Verify it excludes:

- supporting refs;
- historical rows;
- `Is Laundering`;
- demographics.

## 3. Structured output

Test:

- valid initial 2–4 findings;
- invalid >4 findings;
- unavailable with zero findings;
- follow-up 1–3 findings;
- no free-text fallback.

## 4. Evidence validator

Test:

- selected evidence valid;
- tool-returned evidence valid;
- model-invented ID invalid;
- evidence from uncalled tool invalid;
- other-case evidence invalid;
- currency parameter mismatch invalid;
- one invalid finding causes whole output rejection.

## 5. Display labels

Test deterministic mapping:

- first distinct evidence = E1;
- repeated evidence reuses label;
- next new evidence = E2;
- supporting refs come from resolved internal evidence.

## 6. Failure mapping

Mock/test:

- model exception -> model_error;
- MCP infrastructure failure -> tool_error;
- structured output failure -> structured_output_invalid;
- evidence failure -> evidence_validation_failed;
- valid unavailable -> unavailable;
- valid partial with one failed unrelated tool -> partial.

## 7. Follow-up boundedness

Verify runner input contains only:

- selected transaction summary;
- current question;
- prompt/tools.

Assert previous transcript/model response is not loaded.

## 8. Telemetry

Test JSONL record for:

- success;
- model error;
- evidence validation failure;
- exact model/prompt values;
- ordered tool calls;
- token values;
- null cost when rates absent;
- calculated approximate cost when rates supplied;
- no API key/raw history/internal evidence.

Simulate trace write failure and verify product result remains returned.

## 9. AI HTTP routes

Using mocked runner output, test exact shared contracts for:

```text
POST /api/cases/{case}/investigations
POST /api/cases/{case}/follow-up
```

Verify case missing is checked before model call.

## 10. Eval-schema tests

Validate all 15 scenarios:

- unique IDs;
- known cases;
- required tools subset of allowed;
- allowed/forbidden do not overlap;
- valid max call count;
- unsupported scenarios allow no tools;
- all required scenario categories present.

---

# LIVE VALIDATION / EVALS

Live model work is separate from normal pytest.

After non-live tests pass and API credentials are available:

1. run one live primary-case investigation;
2. inspect the trace;
3. run all 15 required eval scenarios with prompt v1;
4. produce a summary;
5. create prompt v2 only if measured failures justify it;
6. rerun only affected scenarios first;
7. if changed prompt appears better, rerun all 15 for comparison.

Do not run scenarios 16–20 unless time remains.

# DO NOT CHANGE

Do not:

- query DuckDB;
- import raw TransXion data;
- calculate median/percentile/count/novelty;
- change `InvestigationService`;
- change MCP tools/schemas;
- add a sixth MCP tool;
- give the model transaction-reference arrays;
- send workspace historical rows to the model;
- use `Is Laundering`;
- create persistent chat history;
- add automatic model fallback/routing;
- add automatic retry/remediation loops;
- repair invalid citations;
- partially render an evidence-invalid answer;
- add fraud/suspiciousness classification;
- modify frontend;
- modify Python dependencies.

# ACCEPTANCE CRITERIA

This package is complete only when:

1. runtime model is selected by `TRAILSIGHT_MODEL` without code redesign.
2. prompt is selected by `TRAILSIGHT_PROMPT_VERSION` from checked-in known files.
3. the model connects to the approved local stdio MCP server through Agents SDK.
4. selected transaction context contains no full history/supporting refs.
5. actual MCP tool calls/results are captured in order.
6. model output is typed/structured.
7. every evidence reference is validated against same-run application-issued evidence.
8. invalid evidence rejects the entire generated investigation.
9. E1/E2 labels are deterministic application-side mappings.
10. follow-up sends no previous transcript and no persistent memory exists.
11. unsupported incoming-account/purpose/source-of-funds questions abstain in evals.
12. JSONL traces contain the required model/prompt/tool/token/status fields.
13. 15 required eval scenarios exist and can be run repeatably.
14. eval result paths separate prompt/model combinations.
15. all non-live AI tests pass without an API key.
16. at least one live primary-case smoke succeeds when credentials are supplied.
17. no files outside WP04 ownership were modified.

## Standalone eval-runner deterministic service construction

The standalone command:

```text
python -m trailsight_ai.eval_runner ...
```

does not execute inside a FastAPI request and therefore must not depend on `request.app.state`. It may import and call the frozen WP02 factory:

```text
create_investigation_service()
```

once to obtain the deterministic `InvestigationService` needed for case loading, selected-evidence seeding, and evidence re-resolution.

The standalone eval runner must not:

- open DuckDB directly;
- instantiate `RuntimeRepository` directly;
- duplicate WP02 runtime configuration;
- implement factual calculations;
- create another service-construction path.

HTTP AI routes continue using:

```text
request.app.state.investigation_service
```

# COMMANDS TO RUN

Non-live tests:

```text
uv sync
uv run pytest tests/ai -q
```

Regression:

```text
uv run pytest tests/backend tests/mcp tests/ai -q
```

Live smoke only when credentials are available:

```text
OPENAI_API_KEY="$OPENAI_API_KEY" \
TRAILSIGHT_MODEL="$TRAILSIGHT_MODEL" \
TRAILSIGHT_PROMPT_VERSION="investigation-v1" \
TRAILSIGHT_DB_PATH="$TRAILSIGHT_DB_PATH" \
uv run python -m trailsight_ai.eval_runner --scenario initial-demo-01
```

Required 15-scenario eval run:

```text
OPENAI_API_KEY="$OPENAI_API_KEY" \
TRAILSIGHT_MODEL="$TRAILSIGHT_MODEL" \
TRAILSIGHT_PROMPT_VERSION="investigation-v1" \
TRAILSIGHT_DB_PATH="$TRAILSIGHT_DB_PATH" \
uv run python -m trailsight_ai.eval_runner --required
```

Do not add CLI flags that bypass evidence validation or expose hidden data.

# RETURN WITH

Return to the Manager:

1. files created/modified;
2. exact model and prompt version used in live tests;
3. AI route registration result;
4. live primary-case tool-call sequence and run status;
5. evidence-validation behavior confirmed;
6. one sample trace with sensitive/raw content omitted;
7. required 15-scenario eval summary with PASS/FAIL by scenario/subcheck;
8. token/cost summary where available;
9. whether prompt v2 was justified/created and exact measured reason;
10. any WP02/WP03 contract mismatch;
11. any requested change outside WP04 ownership;
12. explicit statement: **No product/architecture redesign was made.**
