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
      "url": "https://vnf9mp2vik.us-east-2.awsapprunner.com/mcp",
      "headers": { "Authorization": "Bearer <MCP_API_KEY>" }
    },
    "cardpointe-mcp": {
      "type": "streamable-http",
      "url": "https://qwnm3rvm8m.us-east-2.awsapprunner.com/mcp",
      "headers": { "Authorization": "Bearer <MCP_API_KEY>" }
    },
    "agency-mcp": {
      "type": "streamable-http",
      "url": "https://gdip7vymuh.us-west-2.awsapprunner.com/mcp",
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
      "url": "https://vnf9mp2vik.us-east-2.awsapprunner.com/mcp",
      "headers": { "Authorization": "Bearer <MCP_API_KEY>" }
    },
    "cardpointe-mcp": {
      "url": "https://qwnm3rvm8m.us-east-2.awsapprunner.com/mcp",
      "headers": { "Authorization": "Bearer <MCP_API_KEY>" }
    },
    "agency-mcp": {
      "url": "https://gdip7vymuh.us-west-2.awsapprunner.com/mcp",
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
| `https://vnf9mp2vik.us-east-2.awsapprunner.com/` | HTTP | BrioStack health check |
| `https://vnf9mp2vik.us-east-2.awsapprunner.com/mcp` | MCP/SSE | BrioStack MCP endpoint |
| `https://qwnm3rvm8m.us-east-2.awsapprunner.com/mcp` | MCP/SSE | CardPointe MCP endpoint |
| `https://gdip7vymuh.us-west-2.awsapprunner.com/mcp` | MCP/SSE | Agency MCP endpoint |

---

## Deployment (BrioStack MCP)

### Prerequisites

- AWS CLI configured (`us-east-2`)
- Docker with `--platform linux/amd64` support
- ECR repo: `us-central1-docker.pkg.dev/ghlpest-controlv2/openclaw-mcp-repo/briostack-mcp`
- GCP Secret Manager: `pestpro/integrations/briostack`

### Build & Push

```bash
# Authenticate to ECR
aws ecr get-login-password --region us-east-2 | \
  docker login --username AWS --password-stdin \
  767397993913.dkr.ecr.us-east-2.amazonaws.com

# Build for amd64 (REQUIRED — App Runner is x86_64)
docker build --platform linux/amd64 \
  -t us-central1-docker.pkg.dev/ghlpest-controlv2/openclaw-mcp-repo/briostack-mcp:latest \
  hosted/

# Push
docker push us-central1-docker.pkg.dev/ghlpest-controlv2/openclaw-mcp-repo/briostack-mcp:latest
```

### App Runner Service

- **Service name:** `briostack-mcp-prod`
- **ARN:** `arn:aws:apprunner:us-east-2:767397993913:service/briostack-mcp-prod/4eda73f27c634148ba4bb7505971926e`
- **Region:** `us-east-2`
- **Port:** `8001`
- **Health check:** TCP on port 8001

#### IAM Roles Required

**ECR access role** (trust: `build.apprunner.amazonaws.com`):
- `AmazonEC2ContainerRegistryReadOnly`

**Instance role** (trust: `tasks.apprunner.amazonaws.com`):
- `AmazonSSMReadOnlyAccess`
- Inline policy for `secretsmanager:GetSecretValue` on `arn:aws:secretsmanager:us-east-2:767397993913:secret:pestpro/*`
- CloudWatch Logs write permissions

### Server Configuration

The FastMCP server **must** bind to `0.0.0.0` (not `127.0.0.1`) for App Runner container access:

```python
mcp = FastMCP("BrioStack Operations", host="0.0.0.0", port=8001)
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
# Should return {"error":"Not Acceptable: Client must accept text/event-stream"}
# This is CORRECT — the server is healthy, it just requires SSE accept header
curl https://vnf9mp2vik.us-east-2.awsapprunner.com/mcp

# Actual health endpoint
curl https://vnf9mp2vik.us-east-2.awsapprunner.com/
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

All credentials are stored in GCP Secret Manager (`us-east-2`):

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
