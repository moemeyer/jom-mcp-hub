# Justice Nexus MCP Server

Legal-adjacent **public records**, **open meetings**, **procurement**, and **judgments/liens** tooling for MCP clients. This server follows the JOM hub FastMCP + Cloud Run pattern (`streamable-http`).

> **Not legal advice.** Every tool response includes `not_legal_advice: true`. Draft requests and search stubs set `human_review_recommended: true` where applicable. Have a qualified attorney review filings before submission.

## Tools

| Tool | Purpose | Data status |
|------|---------|-------------|
| `generate_public_records_request` | Build a draft public-records request payload (Florida citations when detected) | Logic-only (no external fetch) |
| `search_open_meetings` | Meeting notices/minutes search | **Stub** — `status: not_implemented`, empty `records` |
| `search_procurement` | Government solicitations/awards | **Stub** — `status: not_implemented`, empty `records` |
| `search_judgments_and_liens` | Court judgments and recorded liens | **Stub** — empty `judgments`/`liens`, `status: not_implemented` |

Stub tools never invent placeholder rows (no fake creditors, confidence scores, or synthetic IDs).

## Authentication

- **Bearer token** (required): `Authorization: Bearer <MCP_API_KEY>`
- **OAuth 2.0 PKCE** (optional): Mounts the shared `oauth/oauth_provider.py` routes when the hub `oauth` package is present — same pattern as agency/briostack servers. Discovery at `/.well-known/oauth-authorization-server`.

Configure the key via:

1. `MCP_API_KEY` or `JUSTICE_NEXUS_MCP_API_KEY` environment variable (local dev / tests), or
2. GCP Secret Manager (`JUSTICE_NEXUS_SECRET_PATH`, default `justice-nexus-mcp-api-key`) with JSON `{"mcp_api_key": "..."}`.

Never commit secrets or `.env` files.

## Florida citations

- **Public records** (`request_type` default `public_records`): `Fla. Stat. ch. 119 (§119.07)` when jurisdiction matches Florida (`Florida`, `FL`, `Fla.`, or `, FL` / `, Florida`).
- **Open meetings** (`request_type` `open_meetings` / `sunshine`): `Fla. Stat. §286.011` only (no ch. 119 on that path).

## Run locally

```bash
export MCP_API_KEY="your-dev-key"
pip install -r justice-nexus/requirements.txt
python justice-nexus/server.py
```

## Tests

```bash
pip install -r justice-nexus/requirements.txt
pytest justice-nexus/tests -q
```

## Docker / Cloud Run (manual deploy only)

There is **no** `cloudbuild.yaml` or repo-managed Cloud Build trigger for this server — builds and deploys are **manual** so Justice Nexus stays isolated from other hub pipelines.

Build from repository root (includes `oauth/`):

```bash
docker build -f justice-nexus/Dockerfile -t us-central1-docker.pkg.dev/PROJECT_ID/openclaw-mcp-repo/justice-nexus-mcp:TAG .
docker push us-central1-docker.pkg.dev/PROJECT_ID/openclaw-mcp-repo/justice-nexus-mcp:TAG
```

Deploy to the isolated dev service **`justice-nexus-mcp-dev`**, require authentication at the edge, and load the bearer key **only from Secret Manager at runtime** (no plain `MCP_API_KEY` env var in production):

1. Create secret `justice-nexus-mcp-api-key` with payload `{"mcp_api_key": "<token>"}`.
2. Grant the Cloud Run runtime service account **`roles/secretmanager.secretAccessor` on that secret only** (not project-wide).
3. Deploy:

```bash
gcloud run deploy justice-nexus-mcp-dev \
  --image=us-central1-docker.pkg.dev/PROJECT_ID/openclaw-mcp-repo/justice-nexus-mcp:TAG \
  --region=us-central1 \
  --platform=managed \
  --no-allow-unauthenticated \
  --set-env-vars=GOOGLE_CLOUD_PROJECT=PROJECT_ID,JUSTICE_NEXUS_SECRET_PATH=justice-nexus-mcp-api-key,PORT=8002
```

`OAuthProvider` is wired with `secret_key='mcp_api_key'` and the same `JUSTICE_NEXUS_SECRET_PATH`. Use `MCP_API_KEY` / `JUSTICE_NEXUS_MCP_API_KEY` **only for local dev and CI**. The process **exits on startup** if production has no env override and Secret Manager cannot be read.

### Health check

- `GET /health` — **unauthenticated**, returns HTTP 200 with an empty body (for load balancers and Cloud Run probes).
- MCP traffic remains behind bearer auth on `/mcp`.

Runtime env (typical):

- `MCP_API_KEY` or `JUSTICE_NEXUS_MCP_API_KEY`, or Secret Manager via `JUSTICE_NEXUS_SECRET_PATH`
- `PORT` (default `8002`; Cloud Run sets this automatically)
- `GOOGLE_CLOUD_PROJECT`
- `MCP_SERVER_BASE_URL` (OAuth metadata)

## Planned data sources (not wired)

| Tool | Candidate sources |
|------|---------------------|
| `search_open_meetings` | Florida Sunbiz / county commission agendas, Granicus/Legistar APIs, state sunshine portals |
| `search_procurement` | VendorLink, MyFloridaMarketPlace, agency solicitation RSS/API |
| `search_judgments_and_liens` | County clerk recorded-instrument indexes, Florida e-Verify courts (where public) |

Until integrated, stubs return empty lists with `status: not_implemented` and `source: null`.