# JOM MCP Hub

**Live:** [mcp.jom.services](https://mcp.jom.services)

MCP (Model Context Protocol) server registry for JOM Services / Pest Pro Rid All. Three production streamable-http servers spanning field operations, payments, and CRM.

---

## Servers

| Server | Transport | Status | Tools |
|--------|-----------|--------|-------|
| BrioStack Operations | streamable-http | production | 32 |
| CardPointe Payments | streamable-http | production | 15 |
| Agency / GHL Operations | streamable-http | production | 98 |

---

## Quick Connect

### Claude Desktop — Remote MCP servers

Add to `~/Library/Application Support/Claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "briostack-ops": {
      "type": "streamable-http",
      "url": "https://briostack-mcp-prod-138839186214.us-central1.run.app/mcp",
      "headers": { "Authorization": "Bearer <MCP_API_KEY>" }
    },
    "cardpointe-mcp": {
      "type": "streamable-http",
      "url": "https://cardpointe-mcp-prod-138839186214.us-central1.run.app/mcp",
      "headers": { "Authorization": "Bearer <MCP_API_KEY>" }
    },
    "agency-mcp": {
      "type": "streamable-http",
      "url": "https://agency-mcp-prod-138839186214.us-central1.run.app/mcp",
      "headers": { "Authorization": "Bearer <MCP_API_KEY>" }
    }
  }
}
```

> Replace `<MCP_API_KEY>` with the shared API key. `claude_desktop_config.json` is local to your machine — do not commit it to any repository.

### Cursor

Add to `.cursor/mcp.json` in your project root:

```json
{
  "mcpServers": {
    "briostack-ops": {
      "url": "https://briostack-mcp-prod-138839186214.us-central1.run.app/mcp",
      "headers": { "Authorization": "Bearer <MCP_API_KEY>" }
    },
    "cardpointe-mcp": {
      "url": "https://cardpointe-mcp-prod-138839186214.us-central1.run.app/mcp",
      "headers": { "Authorization": "Bearer <MCP_API_KEY>" }
    },
    "agency-mcp": {
      "url": "https://agency-mcp-prod-138839186214.us-central1.run.app/mcp",
      "headers": { "Authorization": "Bearer <MCP_API_KEY>" }
    }
  }
}
```

> Replace `<MCP_API_KEY>` with the shared API key. Do not commit this file if it contains the live token.

---

## Discovery Endpoints

| Endpoint | Format | Purpose |
|----------|--------|---------|
| `https://mcp.jom.services/.well-known/mcp.json` | JSON | Standard server discovery |
| `https://mcp.jom.services/mcp-catalog.json` | JSON | Full catalog with tools, hosting, credentials |
| `https://briostack-mcp-prod-138839186214.us-central1.run.app/` | HTTP | BrioStack health check |
| `https://briostack-mcp-prod-138839186214.us-central1.run.app/mcp` | MCP/SSE | BrioStack MCP endpoint |
| `https://cardpointe-mcp-prod-138839186214.us-central1.run.app/mcp` | MCP/SSE | CardPointe MCP endpoint |
| `https://agency-mcp-prod-138839186214.us-central1.run.app/mcp` | MCP/SSE | Agency MCP endpoint |

---

## Deployment (BrioStack MCP)

### Prerequisites

- Google Cloud SDK (`gcloud`) configured
- Docker with `--platform linux/amd64` support
- Artifact Registry repo: `us-central1-docker.pkg.dev/ghlpest-controlv2/openclaw-mcp-repo/briostack-mcp`
- GCP Secret Manager: `pestpro/integrations/briostack`

### Build & Push

```bash
# Authenticate to Artifact Registry
gcloud auth configure-docker us-central1-docker.pkg.dev

# Build for amd64 (REQUIRED for Cloud Run)
docker build --platform linux/amd64 \
  -t us-central1-docker.pkg.dev/ghlpest-controlv2/openclaw-mcp-repo/briostack-mcp:latest \
  hosted/

# Push
docker push us-central1-docker.pkg.dev/ghlpest-controlv2/openclaw-mcp-repo/briostack-mcp:latest
```

### Cloud Run Service

- **Service name:** `briostack-mcp-prod`
- **Region:** `us-central1`
- **Port:** `8001`
- **Service Account Role Required:** `roles/secretmanager.secretAccessor` on the Secret Manager secret `pestpro/integrations/briostack`.

### Server Configuration

The FastMCP server **must** bind to `0.0.0.0` (not `127.0.0.1`) for Cloud Run container access:

```python
mcp = FastMCP("BrioStack Operations", host="0.0.0.0", port=8001, stateless_http=True)
```

Entry point selects transport via argv:
```python
transport = "streamable-http" if "--http" in sys.argv else "stdio"
mcp.run(transport=transport)
```

Dockerfile `CMD`:
```dockerfile
CMD ["python3", "server.py", "--http"]
```

### Health Check

```bash
# Should return the SSE connection or a text stream
curl -H "Accept: text/event-stream" https://briostack-mcp-prod-138839186214.us-central1.run.app/sse

# Actual health/root endpoint
curl https://briostack-mcp-prod-138839186214.us-central1.run.app/
```

---

## DNS Setup (mcp.jom.services)

### DNSimple

1. Log in to [DNSimple](https://dnsimple.com)
2. Select domain `jom.services`
3. Add record:
   - **Type:** CNAME
   - **Name:** `mcp`
   - **Content:** `moemeyer.github.io`
   - **TTL:** 3600

### GitHub Pages

1. Repo: `github.com/moemeyer/jom-mcp-hub`
2. Settings → Pages → Source: Deploy from branch `main` / `/ (root)`
3. Custom domain: `mcp.jom.services`
4. Enable "Enforce HTTPS"

The `CNAME` file in this repo root tells GitHub Pages which domain to serve.

---

## Credentials

All credentials are stored in GCP Secret Manager (`us-central1`):

| Server | Secret Path |
|--------|------------|
| BrioStack | `pestpro/integrations/briostack` |
| CardPointe | `pestpro/integrations/cardpointe` |
| Agency / GHL | `pestpro/integrations/ghl` |

CardPointe merchant IDs:
- Credit card: `496354430886`
- ACH (BlueChex): `BCX101329844815`

---

## Publisher

**JOM Services / Pest Pro Rid All**  
Domain: `jom.services`  
Contact: moemeyer@gmail.com  
Protocol: MCP 2025-03-26
