# Cloud Run CI/CD Setup Guide

## Overview

This repository contains **shared CI/CD infrastructure** for deploying Python-based MCP servers to Google Cloud Run. It supports multiple agencies (NORIVO, EXLYAR, JOM) from a single codebase.

## Architecture

```
GitHub Push (main branch)
    ↓
Cloud Build Trigger (per agency)
    ↓
Build Docker Image (linux/amd64)
    ↓
Push to Artifact Registry
    ↓
Deploy to Cloud Run (specific service)
    ↓
Live Service (norivo.agency-mcp.jom.services)
```

### Supported Services

| Service | Agency | Region | Auto-Deploy |
|---------|--------|--------|-------------|
| `norivo-agency-mcp-prod` | NORIVO LLC | us-central1 | ✅ main branch |
| `exlyar-agency-mcp-prod` | EXLYAR LLC | us-central1 | ✅ main branch |
| `jom-agency-mcp-prod` | JOM Services | us-central1 | ⏸️ (optional) |

## Files

- **`cloudbuild.yaml`** - Cloud Build configuration (shared by all services)
- **`Dockerfile.template`** - Multi-stage Docker build for Python MCP servers
- **`requirements.txt`** - Python dependencies (boto3, fastmcp, starlette, httpx)
- **`server_template.py`** - FastMCP server with OAuth 2.0 PKCE support
- **`oauth/`** - OAuth provider module
- **`setup-cloud-build-triggers.sh`** - Automated trigger creation

## Setup Instructions

### Prerequisites

1. **GCP Project Access**
   ```bash
   gcloud auth login
   gcloud config set project ghlpest-controlv2
   ```

2. **GitHub Repository Connected**
   ```bash
   # Cloud Build needs GitHub App authorization
   # Visit: https://console.cloud.google.com/cloud-build/triggers
   # Click "Connect Repository" → Authorize GitHub
   ```

3. **Service Account Permissions**
   ```bash
   # Ensure Cloud Build service account has:
   # - Cloud Run Admin
   # - Service Account User
   # - Artifact Registry Writer
   # - Secret Manager Secret Accessor
   ```

### Step 1: Create Cloud Build Triggers

```bash
# Run the automated setup script
cd /home/user/jom-mcp-hub
./setup-cloud-build-triggers.sh
```

This creates triggers for:
- `norivo-agency-mcp-prod-deploy`
- `exlyar-agency-mcp-prod-deploy`

### Step 2: Verify Triggers

```bash
# List all triggers
gcloud builds triggers list --project=ghlpest-controlv2

# Should show:
# NAME                          TRIGGER_TYPE  REPO_NAME     BRANCH_PATTERN
# norivo-agency-mcp-prod-deploy github        jom-mcp-hub   ^main$
# exlyar-agency-mcp-prod-deploy github        jom-mcp-hub   ^main$
```

### Step 3: Test Deployment

#### Manual Trigger (No Code Push)

```bash
# Test NORIVO deployment
gcloud builds triggers run norivo-agency-mcp-prod-deploy \
  --branch=main \
  --project=ghlpest-controlv2

# Test EXLYAR deployment
gcloud builds triggers run exlyar-agency-mcp-prod-deploy \
  --branch=main \
  --project=ghlpest-controlv2
```

#### Automatic Trigger (Push to Main)

```bash
# Make a no-op change
git checkout main
echo "# $(date)" >> .cloud-build-test
git add .cloud-build-test
git commit -m "chore: test cloud build trigger"
git push origin main

# Watch the build
gcloud builds list --ongoing --project=ghlpest-controlv2
```

### Step 4: Monitor Build

```bash
# Get build ID from trigger output
BUILD_ID="<build-id-from-trigger>"

# Stream logs
gcloud builds log ${BUILD_ID} --stream

# Check build status
gcloud builds describe ${BUILD_ID}
```

## Environment Variables

Each Cloud Run service is configured with:

### NORIVO
```yaml
AGENCY_ID: norivo
AGENCY_LABEL: NORIVO LLC
SECRET_PATH: pestpro/integrations/norivo-agency
SECRET_REGION: us-east-2
MCP_SERVER_BASE_URL: https://norivo.agency-mcp.jom.services
PORT: 8001
```

### EXLYAR
```yaml
AGENCY_ID: exlyar
AGENCY_LABEL: EXLYAR LLC
SECRET_PATH: pestpro/integrations/exlyar-agency
SECRET_REGION: us-east-2
MCP_SERVER_BASE_URL: https://exlyar.agency-mcp.jom.services
PORT: 8001
```

## Rollback Procedure

If a deployment breaks production:

```bash
# List recent revisions
gcloud run revisions list \
  --service=norivo-agency-mcp-prod \
  --region=us-central1 \
  --limit=5

# Rollback to previous revision
gcloud run services update-traffic norivo-agency-mcp-prod \
  --region=us-central1 \
  --to-revisions=norivo-agency-mcp-prod-00042-abc=100

# Verify rollback
curl https://norivo.agency-mcp.jom.services/.well-known/oauth-authorization-server
```

## Troubleshooting

### Build Fails: "No module named 'boto3'"

**Problem:** `requirements.txt` missing or incomplete

**Fix:**
```bash
# Verify requirements.txt exists
cat requirements.txt | grep boto3

# Should show:
# boto3>=1.34.0
# botocore>=1.34.0
```

### Build Fails: "Permission denied"

**Problem:** Cloud Build service account lacks permissions

**Fix:**
```bash
# Grant Cloud Run Admin role
gcloud projects add-iam-policy-binding ghlpest-controlv2 \
  --member=serviceAccount:<project-number>@cloudbuild.gserviceaccount.com \
  --role=roles/run.admin

# Grant Service Account User role
gcloud projects add-iam-policy-binding ghlpest-controlv2 \
  --member=serviceAccount:<project-number>@cloudbuild.gserviceaccount.com \
  --role=roles/iam.serviceAccountUser
```

### Deployment Succeeds but Service Returns 500

**Problem:** Missing GCP secrets or incorrect SECRET_PATH

**Fix:**
```bash
# Verify secret exists
gcloud secrets describe pestpro-integrations-norivo-agency \
  --project=ghlpest-controlv2

# Check service logs
gcloud run services logs read norivo-agency-mcp-prod \
  --region=us-central1 \
  --limit=50
```

## Adding New Services

To add a new agency:

1. **Create GCP Secret**
   ```bash
   gcloud secrets create pestpro-integrations-newagency-agency \
     --data-file=secrets/newagency.json \
     --project=ghlpest-controlv2
   ```

2. **Deploy Cloud Run Service**
   ```bash
   gcloud run services create newagency-agency-mcp-prod \
     --image=us-central1-docker.pkg.dev/ghlpest-controlv2/openclaw-mcp-repo/agency-mcp:latest \
     --region=us-central1 \
     --set-env-vars=AGENCY_ID=newagency,SECRET_PATH=pestpro/integrations/newagency-agency \
     --service-account=mcp-server-sa@ghlpest-controlv2.iam.gserviceaccount.com
   ```

3. **Create Build Trigger**
   ```bash
   # Edit setup-cloud-build-triggers.sh and add:
   create_trigger "newagency-agency-mcp-prod" "newagency" "main"
   
   # Run setup script
   ./setup-cloud-build-triggers.sh
   ```

## Cost Optimization

**Current Setup:**
- Cloud Build: First 120 build-minutes/day free, then $0.003/build-minute
- Cloud Run: Pay only when handling requests (~$6-16/month per service)
- Artifact Registry: $0.10/GB/month storage

**Tips:**
- Use `--quiet` flag to skip interactive prompts (faster builds)
- Enable `CLOUD_LOGGING_ONLY` to reduce log costs
- Use `machineType: N1_HIGHCPU_8` for faster builds (same cost)

## Security Best Practices

✅ **No hardcoded secrets** - All credentials in Secret Manager  
✅ **Workload Identity** - No long-lived service account keys  
✅ **Least privilege IAM** - Cloud Build SA has minimal required roles  
✅ **Immutable deployments** - Every push creates new revision  
✅ **Audit logging** - All builds tracked in Cloud Build history  

## Monitoring

### Build Success Rate

```bash
# Last 10 builds
gcloud builds list --limit=10 --format="table(id,status,createTime,duration)"
```

### Service Health

```bash
# NORIVO health check
curl https://norivo.agency-mcp.jom.services/

# EXLYAR health check
curl https://exlyar.agency-mcp.jom.services/

# OAuth discovery
curl https://norivo.agency-mcp.jom.services/.well-known/oauth-authorization-server
```

### Cloud Run Metrics

```bash
# Request count
gcloud run services describe norivo-agency-mcp-prod \
  --region=us-central1 \
  --format="value(status.traffic)"

# Latest revision
gcloud run revisions list \
  --service=norivo-agency-mcp-prod \
  --region=us-central1 \
  --limit=1
```

## Next Steps

1. ✅ Push to `main` branch to trigger first deployment
2. ✅ Verify services are healthy at their URLs
3. ✅ Test OAuth flow from Claude.ai
4. ✅ Configure DNS (if not already done)
5. ✅ Share access credentials with agency teams
6. ✅ Set up monitoring alerts (optional)

---

**Questions?** Check Cloud Build logs: `gcloud builds list --ongoing`
