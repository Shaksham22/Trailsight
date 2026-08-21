# Trailsight

Trailsight is a one-screen, evidence-backed assistant for reviewing synthetic TransXion transactions. It presents deterministic historical context first, then lets an analyst request concise AI findings tied to application-owned evidence. The analyst retains judgment.

Trailsight does not decide whether a transaction is fraudulent, money laundering, suspicious, should be blocked, or requires regulatory action.

## Architecture

```text
React -> FastAPI -> deterministic Python -> read-only DuckDB
                         ^
                         |
LLM -> local stdio MCP --+
```

FastAPI and the five-tool MCP adapter reuse the same `InvestigationService`; factual calculations are not implemented in the model, MCP, or React. The application retains complete internal evidence, while the model receives bounded aggregate summaries with no transaction references or historical rows. Generated citations are validated and re-resolved before FastAPI returns display evidence.

## Source data and provenance

Trailsight uses the synthetic [TransXion dataset](https://github.com/chaos-max/TransXion) from an external source checkout pinned to commit:

```text
53932595c37c23b9f55ea5ddf5984e4d57b88369
```

The source repository uses Git LFS for `data/tx.csv`. Install Git LFS before cloning and verify the checkout:

```bash
git lfs install
git clone https://github.com/chaos-max/TransXion.git /absolute/path/to/TransXion
git -C /absolute/path/to/TransXion checkout 53932595c37c23b9f55ea5ddf5984e4d57b88369
git -C /absolute/path/to/TransXion lfs pull
git -C /absolute/path/to/TransXion rev-parse HEAD
```

Raw TransXion CSVs are not committed to or redistributed with Trailsight, and the generated runtime DuckDB is also excluded. Trailsight does not assert a right to redistribute those CSVs; obtaining source data externally is a project-governance constraint, not legal advice.

`Synthetic Region` is derived as the numeric account suffix modulo 20. It is a source-derived grouping only—not a real country, city, province, geography, or transaction corridor.

## Host setup

Requirements: Python 3.12+, [uv](https://docs.astral.sh/uv/), Node.js/npm, Git LFS, and Docker for the container path.

```bash
cp .env.example .env
uv sync --frozen
```

Configure `.env` locally; it is Git-ignored. Use paths for your machine and keep `OPENAI_API_KEY` only in the local environment. The approved final AI configuration is:

```text
TRAILSIGHT_MODEL=gpt-5.6-luna
TRAILSIGHT_PROMPT_VERSION=investigation-v2
```

Prepare the source-derived database on the host:

```bash
set -a
source .env
set +a
uv run python scripts/prepare_runtime_data.py \
  --source-root "$TRANSXION_SOURCE_DIR" \
  --case-catalog data/cases/cases.yaml \
  --output "$TRAILSIGHT_DB_PATH"
```

For local development, build the frontend and start the single FastAPI app:

```bash
npm --prefix frontend install
npm --prefix frontend run build
uv run uvicorn trailsight.api.app:create_app --factory --host 127.0.0.1 --port 8000
```

Open [http://127.0.0.1:8000](http://127.0.0.1:8000). Vite development is also available with `npm --prefix frontend run dev`; it proxies `/api` to port 8000.

## Tests and AI evals

The normal test suite is deterministic and does not need an API key:

```bash
uv sync --frozen
uv run pytest tests/data tests/backend tests/mcp tests/ai tests/integration -q
npm --prefix frontend install
npm --prefix frontend run build
```

The AI eval harness defines 15 required scenarios covering initial investigations, focused tool selection, factual/evidence validity, and abstention. Each result records the exact model, prompt version, judge model, tool sequence, status, usage, and optional estimated cost under `eval_results/<prompt>/<model>/`; generated results remain local and Git-ignored.

With `.env` loaded, run one scenario or the required suite:

```bash
uv run python -m trailsight_ai.eval_runner --scenario initial-demo-01
uv run python -m trailsight_ai.eval_runner --required
```

## Docker

Build the single deployment image; the build context excludes `.env`, raw source data, runtime DuckDB files, traces, and eval results:

```bash
docker build -t trailsight:local .
mkdir -p data/traces
```

Run with the host-prepared database mounted read-only and traces mounted separately as writable. `-e OPENAI_API_KEY` forwards the current shell variable without putting its value in this command or image:

```bash
docker run --rm --name trailsight -p 8000:8000 \
  --mount type=bind,src="$(pwd)/data/runtime/trailsight.duckdb",dst=/app/data/runtime/trailsight.duckdb,readonly \
  --mount type=bind,src="$(pwd)/data/traces",dst=/app/data/traces \
  -e OPENAI_API_KEY \
  -e TRAILSIGHT_MODEL=gpt-5.6-luna \
  -e TRAILSIGHT_PROMPT_VERSION=investigation-v2 \
  trailsight:local
```

The image defaults to `TRAILSIGHT_DB_PATH=/app/data/runtime/trailsight.duckdb`, `TRAILSIGHT_STATIC_DIR=/app/frontend/dist`, and `TRAILSIGHT_TRACE_PATH=/app/data/traces/investigations.jsonl`. The DuckDB is never baked into the image.

## Demo 01

1. Open Trailsight; `demo-01` loads its deterministic workspace before any AI request.
2. Review `A016568 -> A013644`, `69.54 CNY -> 9.40 USD`, Cash, Synthetic Region `8 -> 4`.
3. Confirm 74 previous outgoing transactions, 70 prior CNY transactions, median `15.095`, historical position about `95.71%`, and zero previous interactions with the current counterparty.
4. Select **Investigate transaction**, then click an `[E#]` citation to focus the corresponding deterministic section and applicable rows without making another AI request.
5. Ask one supported question such as “Has this sender used this counterparty before?”
6. In a fresh case UI state, ask “Why did the sender make this transaction?” and confirm an explicit limit/abstention. A second follow-up is unavailable in the same selected-case state.

## Observability

Each completed or handled AI run appends one JSON object to `TRAILSIGHT_TRACE_PATH` (default `data/traces/investigations.jsonl`). Records include the investigation/case linkage, exact model and prompt, timing, ordered safe MCP calls, result sizes/statuses, token usage, referenced evidence IDs, validation result, and optional cost estimate. They exclude the API key, raw historical rows, complete internal evidence, profile demographics, and the hidden source label.
