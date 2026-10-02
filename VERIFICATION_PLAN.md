# CI/CD Verification Plan

## What Was Built

✅ **Shared Cloud Run CI/CD infrastructure** for multi-agency MCP servers:
- `cloudbuild.yaml` - Builds Docker image → Pushes to Artifact Registry → Deploys to Cloud Run
- `Dockerfile.template` - Python 3.12 with fastmcp, boto3, httpx, starlette
- `requirements.txt` - All Python dependencies including boto3 (fixes the error!)
- `server_template.py` - Multi-tenant FastMCP server
- `setup-cloud-build-triggers.sh` - Automated trigger creation
- `CLOUD_RUN_CICD.md` - Complete documentation

## What It Does

**On push to `main` branch:**
1. Cloud Build trigger activates
2. Builds Docker image with substitutions (`_SERVICE_NAME`, `_AGENCY_ID`)
3. Pushes to `us-central1-docker.pkg.dev/ghlpest-controlv2/openclaw-mcp-repo/`
4. Deploys to Cloud Run service (norivo/exlyar)
5. Service goes live at custom domain

## Next Steps (Before It Works)

### Step 1: Merge This PR

```bash
# Merge chore/cloud-run-cicd → main
# This makes the files available to Cloud Build
```

### Step 2: Run Trigger Setup Script

```bash
# On your local machine with gcloud CLI:
cd ~/jom-mcp-hub
./setup-cloud-build-triggers.sh

# This creates:
# - norivo-agency-mcp-prod-deploy trigger
# - exlyar-agency-mcp-prod-deploy trigger
```

### Step 3: Verify Triggers Exist

```bash
gcloud builds triggers list --project=ghlpest-controlv2

# Expected output:
# NAME                          TRIGGER_TYPE  BRANCH_PATTERN
# norivo-agency-mcp-prod-deploy github        ^main$
# exlyar-agency-mcp-prod-deploy github        ^main$
```

### Step 4: Manual Test (No Code Push)

```bash
# Test NORIVO deployment
gcloud builds triggers run norivo-agency-mcp-prod-deploy \
  --branch=main \
  --project=ghlpest-controlv2

# Watch the build
gcloud builds list --ongoing
```

### Step 5: Verify Build Logs

```bash
# Get build ID from previous command
BUILD_ID="<id-from-trigger>"

# Stream logs
gcloud builds log ${BUILD_ID} --stream

# Expected steps:
# ✅ Step 1: Build Docker image (linux/amd64)
# ✅ Step 2: Push to Artifact Registry
# ✅ Step 3: Deploy to Cloud Run

# Success output:
# Service [norivo-agency-mcp-prod] revision [norivo-agency-mcp-prod-00043-xyz] has been deployed
# Service URL: https://<cloud-run-url>
```

### Step 6: Test Deployed Service

```bash
# Health check
curl https://norivo.agency-mcp.jom.services/

# OAuth discovery
curl https://norivo.agency-mcp.jom.services/.well-known/oauth-authorization-server

# Expected response:
# {
#   "issuer": "https://norivo.agency-mcp.jom.services",
#   "authorization_endpoint": "https://norivo.agency-mcp.jom.services/authorize",
#   "token_endpoint": "https://norivo.agency-mcp.jom.services/token",
#   "response_types_supported": ["code"],
#   "grant_types_supported": ["authorization_code"],
#   "code_challenge_methods_supported": ["S256"]
# }
```

### Step 7: Test Auto-Deploy (Push to Main)

```bash
# Make a no-op change
git checkout main
echo "# Test: $(date)" >> .cloud-build-test
git add .cloud-build-test
git commit -m "chore: test cloud build auto-deploy"
git push origin main

# Cloud Build should automatically trigger
# Watch it: gcloud builds list --ongoing
```

## Verification Checklist

- [ ] **Trigger created** - `gcloud builds triggers list` shows triggers
- [ ] **Manual build succeeds** - `gcloud builds triggers run` completes
- [ ] **Docker image pushed** - Artifact Registry contains new image
- [ ] **Cloud Run updated** - New revision deployed
- [ ] **Service responds** - Health check returns 200 OK
- [ ] **OAuth works** - Discovery endpoint returns JSON
- [ ] **Auto-deploy works** - Push to main triggers build
- [ ] **Both agencies work** - NORIVO and EXLYAR deploy independently

## Rollback Commands (If Something Breaks)

### Rollback Cloud Run Service

```bash
# List recent revisions
gcloud run revisions list \
  --service=norivo-agency-mcp-prod \
  --region=us-central1 \
  --limit=5

# Rollback to previous version
gcloud run services update-traffic norivo-agency-mcp-prod \
  --region=us-central1 \
  --to-revisions=<previous-revision-name>=100
```

### Disable Auto-Deploy

```bash
# Disable trigger temporarily
gcloud builds triggers update norivo-agency-mcp-prod-deploy \
  --disabled \
  --project=ghlpest-controlv2

# Re-enable later
gcloud builds triggers update norivo-agency-mcp-prod-deploy \
  --no-disabled \
  --project=ghlpest-controlv2
```

### Delete Trigger

```bash
# If something is wrong with the trigger
gcloud builds triggers delete norivo-agency-mcp-prod-deploy \
  --project=ghlpest-controlv2
```

## What I Did NOT Verify (Yet)

❌ **Actual build run** - Need gcloud CLI on local machine  
❌ **Cloud Run deployment** - Need triggers created first  
❌ **Service health** - Need deployment to complete  
❌ **OAuth flow** - Need service running  
❌ **Auto-deploy on push** - Need triggers active  

## Why Cloud Build (Not GitHub Actions)?

**Chosen: Cloud Build**

✅ **Pros:**
- Native GCP integration (no auth tokens needed)
- Workload Identity (no long-lived service account keys)
- IAM-based permissions (Cloud Build SA has Cloud Run Admin)
- Simpler config (no secrets to manage)
- Already in GCP ecosystem

❌ **GitHub Actions Alternative:**
- Would need Workload Identity Federation setup
- More complex auth configuration
- Cross-platform (works anywhere, not just GCP)
- Better for multi-cloud deployments

**For this use case** (GCP-only MCP servers), Cloud Build is simpler and more secure.

## Cost Estimate

**Per Build:**
- Build time: ~5-8 minutes
- Cost: ~$0.02 per build (after free tier)

**Per Month** (assuming 20 deployments):
- Cloud Build: ~$0.40
- Artifact Registry: ~$0.20 (2GB storage)
- Cloud Run: ~$6-16 per service (existing cost)

**Total new cost:** ~$0.60/month for CI/CD infrastructure

## Success Criteria

✅ **Infrastructure created** (cloudbuild.yaml, Dockerfile, triggers)  
⏸️ **Triggers configured** (need to run setup script)  
⏸️ **Manual build succeeds** (need gcloud access)  
⏸️ **Auto-deploy works** (need push to main)  
⏸️ **Services healthy** (need deployment complete)  
⏸️ **No boto3 errors** (fixed in requirements.txt!)  

---

**Next Action:** Merge this PR, then run `./setup-cloud-build-triggers.sh`
