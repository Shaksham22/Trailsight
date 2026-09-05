# Trailsight V2

Trailsight is a local analyst workspace for investigating review-prioritized activity in the synthetic IBM AMLworld HI-Small benchmark. It combines reproducible graph-based prioritization, deterministic historical context, Evidence V2, bounded REST/MCP interfaces, and an optional grounded LLM investigation. The analyst retains judgment.

Trailsight does **not** decide that an account or transaction is money laundering, assign laundering probabilities, block transactions, or recommend regulatory action.

## Architecture

```text
IBM HI-Small transactions
  -> prepared runtime-safe DuckDB
  -> GARG detector snapshots, review bands, priorities, and alerts
  -> deterministic investigation domain + Evidence V2
  -> FastAPI /api/v2 + bounded local stdio MCP
  -> optional grounded LLM investigation
  -> React analyst workspace
```

FastAPI, MCP, and the React client consume the same deterministic domain contracts. The model receives bounded application-owned context and can cite only Evidence V2 IDs made available during that run.

## Ground-truth firewall

IBM's `Is Laundering` label and hidden pattern annotations are offline-evaluation inputs only. They are excluded from the runtime DuckDB, API, frontend, Evidence, MCP, prompts, AI context, and runtime telemetry. Detector outputs are produced before any separate offline comparison with benchmark truth.

Bank Country is deterministic synthetic **bank metadata**. It is not customer residence, nationality, physical location, domicile, or country risk.

## Product screenshots

### Analyst workspaces

**Network Pattern Alerts.** Review-prioritized accounts are presented with their Bank Country metadata, detector cutoff, entry reason, and human workflow status.

![Trailsight Network Pattern Alerts queue](docs/assets/alerts-queue.png)

**Transaction browser.** Server-driven search and filters provide a bounded view of transaction facts, endpoint identities, currencies, formats, and review priorities.

![Trailsight transaction browser](docs/assets/transactions-browser.png)

**Account directory.** Canonical Bank and Account identities appear alongside the latest completed network-review context and directional activity counts.

![Trailsight account directory](docs/assets/accounts-directory.png)

### Account investigation

**Account overview.** The primary investigation view brings together identity, detector standing, directional transaction activity, counterparties, and same-currency comparisons.

![Trailsight Account Investigation overview](docs/assets/account-investigation-overview.png)

**Bounded AI assessment.** The optional structured assessment summarizes supplied facts, observations, patterns, and material limits while preserving a single bounded follow-up.

![Trailsight Account Investigation AI assessment](docs/assets/account-ai-assessment.png)

**Network and Bank-Country flows.** A world-context flow map and bounded one-hop account graph show international bank metadata and transaction direction side by side.

![Trailsight Account Investigation network and Bank-Country flows](docs/assets/account-network-and-bank-country-flows.png)

**Flow and relationship detail.** Bank-Country aggregates, per-currency activity, and direct counterparty counts retain their separate deterministic measures.

![Trailsight Account Investigation flow summary and direct counterparties](docs/assets/account-flow-summary-and-counterparties.png)

**Historical investigation context.** Alert history and bounded transaction records connect the account’s review state to the underlying activity.

![Trailsight Account Investigation alert history and transactions](docs/assets/account-alert-history-and-transactions.png)

### Transaction investigation

**Transaction overview.** Review priority and its endpoint-band derivation sit above the transfer summary and synthetic Bank-Country route.

![Trailsight Transaction Investigation overview](docs/assets/transaction-investigation-overview.png)

**Structured transaction assessment.** The shared AI investigation surface describes the transaction, key observations, cross-fact patterns, and meaningful limits.

![Trailsight Transaction Investigation AI assessment](docs/assets/transaction-ai-assessment.png)

**Facts and endpoint context.** Exact transfer facts are followed by sender and receiver account state at the applicable historical cutoff.

![Trailsight Transaction Investigation facts and endpoint accounts](docs/assets/transaction-facts-and-endpoints.png)

**Deterministic indicators.** Endpoint bands, amount-history comparisons, relationship history, recent velocity, and currency-route facts remain directly inspectable.

![Trailsight Transaction Investigation endpoint accounts and deterministic indicators](docs/assets/transaction-endpoints-and-indicators.png)

**Activity and local network.** A sender-rooted 30-day activity view and bounded one-hop graph provide temporal and relationship context without cross-currency aggregation.

![Trailsight Transaction Investigation activity and local network](docs/assets/transaction-activity-and-network.png)

**Supporting evidence.** Evidence categories and their bounded supporting transaction rows remain visible beneath the investigation narrative.

![Trailsight Transaction Investigation supporting evidence](docs/assets/transaction-supporting-evidence.png)

## Prerequisites

- Python 3.12 or newer
- [uv](https://docs.astral.sh/uv/)
- Node.js `20.19+` or `22.12+` and npm
- an externally obtained IBM AMLworld HI-Small transaction CSV when preparing the database
- optionally, an OpenAI API key and an API model available to your project

Raw IBM data and generated DuckDB files are intentionally not committed.

## One-time setup

```bash
cp .env.example .env
uv sync --frozen
npm --prefix frontend ci
```

The checked-in `.env.example` contains no secret. Edit only the untracked `.env` file for local paths and optional AI settings.

## Prepare the database when it is absent

Point `--source` at the external HI-Small transaction CSV. Preparation strips hidden truth from the product path and creates the runtime-safe database:

```bash
uv run python scripts/v2_data_prepare.py \
  --source /absolute/path/to/HI-Small_Trans.csv \
  --output data/v2/runtime/trailsight_v2.duckdb
```

Then materialize detector snapshots, account review bands, transaction priorities, and alerts:

```bash
uv run python scripts/v2_detector_prepare.py \
  --database data/v2/runtime/trailsight_v2.duckdb
```

These are offline preparation commands, not backend startup behavior. Full detector preparation can be long-running; the web app never regenerates it on request. See [Data and detector](docs/02_DATA_AND_DETECTOR.md) for the data contract and offline-evaluation isolation.

## Start Trailsight

Start the backend from the repository root. `--env-file` loads the documented local paths without repeated shell exports:

```bash
uv run uvicorn trailsight_v2.api.app:create_app \
  --factory \
  --env-file .env \
  --host 127.0.0.1 \
  --port 8000
```

In another terminal, start the normal real-API frontend:

```bash
cd frontend
npm run dev
```

Open [http://127.0.0.1:5173](http://127.0.0.1:5173). Vite proxies `/api` to FastAPI on port 8000. There is no silent fixture fallback.

Check backend readiness at [http://127.0.0.1:8000/api/v2/health](http://127.0.0.1:8000/api/v2/health). Startup fails safely if the prepared database is missing or invalid.

Fixture development is explicit and isolated from normal builds:

```bash
cd frontend
npm run dev:fixture
```

## Optional AI configuration

Set these only in the untracked root `.env`:

```text
OPENAI_API_KEY=<local secret>
TRAILSIGHT_MODEL=<exact API model identifier available to your project>
TRAILSIGHT_PROMPT_VERSION=investigation-v2
```

`GET /api/v2/health` reports `ai_configured: true` when both `OPENAI_API_KEY` and `TRAILSIGHT_MODEL` are non-empty. Prompt/provider validation occurs when an investigation starts. When AI is unconfigured or unavailable, every deterministic list, detail, workflow, visualization, and Evidence V2 path remains usable.

Start a real investigation from an Account or Transaction detail page using **Investigate**. A successful initial investigation permits exactly one successful follow-up. Configuration, infrastructure, or provider failure does not consume that follow-up; a request after successful consumption returns `FOLLOW_UP_ALREADY_USED`.

One sanitized JSONL record per handled AI run is written to `TRAILSIGHT_TRACE_PATH` (default `data/traces/investigations-v2.jsonl`). The file records model/prompt provenance, bounded MCP call metadata, timing, usage, tool-returned evidence IDs, structural-validation state, and failure code. It does not store API keys, chat transcripts, model reasoning, generated prose, full evidence payloads, or hidden benchmark truth.

OpenAI recommends keeping API keys server-side in environment variables; never place the key in `frontend/.env*` or browser code. See the [official OpenAI API documentation](https://developers.openai.com/api/docs/quickstart).

## Validation

The final deterministic validation sequence is:

```bash
uv run pytest tests/v2
uv run python evals/v2/run_non_live.py

cd frontend
npm ci
npm run test:contracts
npm run build
```

The non-live eval harness is credential-free and makes no paid model call. It validates the frozen scenario contract through an independent mocked execution path. A real-model investigation remains a separate manual acceptance step.

## Important V2 limitations

- Local single-process MVP; `runtime_state.json` is not a multi-worker state service.
- No authentication, user accounts, production deployment, or cloud control plane.
- Review workflow is `NOT_REVIEWED -> IN_REVIEW -> REVIEWED`; `REVIEWED` is terminal.
- GARG review bands prioritize analyst attention; they are not laundering probabilities.
- Transaction activity context is fixed to **Sender Activity — Prior 30 Days**.
- Account Network shows at most 24 counterparties plus the root; truncation is explicit.
- Model/MCP network context remains capped at 12; Evidence samples remain bounded.
- Account Detail Bank-Country Flows include all aggregated connections for the resolved context and have no arbitrary top-12 limit.
- Alert History returns the latest 100 rows with explicit total/truncation metadata.
- AI is a bounded investigation aid, not a generic chatbot, and permits one successful follow-up.

## Authoritative documentation

- [Product contract](docs/00_PRODUCT_CONTRACT.md)
- [System architecture](docs/01_SYSTEM_ARCHITECTURE.md)
- [Data and detector](docs/02_DATA_AND_DETECTOR.md)
- [Investigation domain and Evidence V2](docs/03_DOMAIN_AND_EVIDENCE.md)
- [REST API and MCP](docs/04_API_AND_MCP.md)
- [AI and evaluation](docs/05_AI_AND_EVALUATION.md)
- [Frontend UX](docs/06_FRONTEND_UX.md)
- [Runtime and configuration](docs/07_RUNTIME_AND_DEPLOYMENT.md)
- [Testing and acceptance](docs/08_TESTING_AND_ACCEPTANCE.md)

`docs/09_IMPLEMENTATION_ROADMAP.md` and `docs/implementation/` preserve implementation history; they are not startup or release runbooks.
