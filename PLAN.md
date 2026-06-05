# CI/CD Setup Plan for jom-mcp-hub

## Current State Analysis

### Repository: `jom-mcp-hub`
- **Purpose:** Static MCP catalog/discovery site (HTML + JSON)
- **GitHub:** `moemeyer/jom-mcp-hub`
- **Current Branch:** `claude/slack-session-U4JKc`
- **Current Deployment:** GitHub Pages → `mcp.jom.services`
- **Contents:**
  - Static files: `index.html`, `mcp-catalog.json`, `request-access.html`
  - OAuth Python module: `oauth/oauth_provider.py` (should NOT be here)
  - No build files: No `Dockerfile`, `cloudbuild.yaml`, `.github/workflows/`

### Referenced MCP Servers (NOT in this repo)
According to README.md, three MCP servers are deployed:
1. **BrioStack Operations** → AWS App Runner `vnf9mp2vik.us-east-2.awsapprunner.com`
2. **CardPointe Payments** → AWS App Runner `qwnm3rvm8m.us-east-2.awsapprunner.com`
3. **Agency / GHL Operations** → AWS App Runner `gdip7vymuh.us-west-2.awsapprunner.com`

These are **NOT deployed from this repo** — they're separate Python services.

### GCP Error Analysis
**Error:** `ModuleNotFoundError: No module named 'boto3'`
**Source:** `jom-slack-bot` (seen in first screenshot)
**Project:** `ghlpest-controlv2` (Jom Seamless Connection)

This error is **NOT from jom-mcp-hub**. It's from a different service (`jom-slack-bot`) that's missing Python dependencies.

### Architecture Confusion Detected

**Problem:** This repo has conflicting purposes:
1. Static catalog site (GitHub Pages) ✅ Currently working
2. OAuth Python module (`oauth/`) that belongs in MCP server repos ❌ Misplaced

**The `oauth/` directory should NOT be in this repo.** It should be in:
- `jom-agency-shared/` (NORIVO/EXLYAR servers we just created)
- Or separate MCP server repos

---

## Goals

### What Should Happen for `jom-mcp-hub`?
**Option A: Keep as static site only (RECOMMENDED)**
- Continue using GitHub Pages for `mcp.jom.services`
- Remove `oauth/` directory (move to actual MCP server repos)
- No Cloud Run deployment needed
- Auto-deploy via GitHub Pages on push to `main`

**Option B: Convert to dynamic service**
- Deploy to Cloud Run
- Serve catalog dynamically
- Not needed — static files work fine

### What Should Happen for MCP Servers?
The **actual Python MCP servers** need CI/CD:
- `jom-agency-shared` → Cloud Run (`norivo-agency-mcp-prod`, `exlyar-agency-mcp-prod`)
- BrioStack server repo → Cloud Run (migrate from AWS App Runner?)
- CardPointe server repo → Cloud Run (migrate from AWS App Runner?)
- Agency server repo → Cloud Run (migrate from AWS App Runner?)

---

## Key Questions

1. **Is `jom-mcp-hub` supposed to be deployed to Cloud Run?**
   - No evidence suggests this
   - It's a static site on GitHub Pages
   - The MCP servers are separate repos

2. **What is `jom-slack-bot` and where is it?**
   - That's the service with the `boto3` error
   - Not in this repo
   - Likely a separate Cloud Run service in `ghlpest-controlv2`

3. **Do you want CI/CD for:**
   - ☐ This catalog site (`jom-mcp-hub`)? → Already auto-deploys via GitHub Pages
   - ☐ The new multi-agency servers (`jom-agency-shared`)? → Needs Cloud Run CI/CD
   - ☐ The `jom-slack-bot` that's failing? → Different repo/service

---

## Recommendation: STOP and Clarify

Before setting up CI/CD, we need to:

### 1. **Fix the `boto3` error in `jom-slack-bot`**
That's a separate service with missing dependencies. Not related to `jom-mcp-hub`.

### 2. **Move `oauth/` directory to correct repos**
The OAuth module should be in MCP server repos, not this catalog:
```bash
# Should move oauth/ to:
/home/user/jom-agency-shared/oauth/  # ✅ Correct location
/home/user/jom-mcp-hub/oauth/        # ❌ Wrong location
```

### 3. **Set up CI/CD for the RIGHT repos**

**For `jom-mcp-hub` (this catalog site):**
- ✅ Already has CI/CD via GitHub Pages
- ✅ Pushes to `main` auto-deploy
- ❌ Does NOT need Cloud Run

**For `jom-agency-shared` (NORIVO/EXLYAR servers):**
- ❌ Not yet in GitHub
- ❌ No CI/CD configured
- ✅ SHOULD deploy to Cloud Run
- ✅ NEEDS Cloud Build or GitHub Actions

**For `jom-slack-bot` (the failing service):**
- ❌ Missing `boto3` dependency
- ❌ Unknown repo location
- ✅ NEEDS dependency fix in `requirements.txt`

---

## Open Questions

1. **Which service are you trying to fix?**
   - The catalog site (`jom-mcp-hub`)? → Already works
   - The Slack bot (`jom-slack-bot`)? → Missing dependencies
   - The new agency servers (`jom-agency-shared`)? → Needs GitHub + CI/CD

2. **Where is the `jom-slack-bot` repo?**
   - Not in `/home/user/jom-mcp-hub`
   - Need to locate and fix `requirements.txt`

3. **Do you want me to:**
   - ☐ Set up CI/CD for `jom-agency-shared` → Cloud Run?
   - ☐ Fix the `boto3` error in `jom-slack-bot`?
   - ☐ Move `oauth/` to the correct repos?
   - ☐ All of the above?

---

## My Recommendation

**Don't set up CI/CD for `jom-mcp-hub`.** It's already auto-deploying via GitHub Pages.

**Instead, do this:**

### Phase 1: Fix Architecture Issues
1. Move `oauth/` from `jom-mcp-hub` to `jom-agency-shared`
2. Locate `jom-slack-bot` repo and add `boto3` to `requirements.txt`
3. Push `jom-agency-shared` to GitHub

### Phase 2: Set Up CI/CD for MCP Servers
1. Create GitHub repo for `jom-agency-shared`
2. Set up Cloud Build trigger: `main` branch → deploy to:
   - `norivo-agency-mcp-prod` (us-central1)
   - `exlyar-agency-mcp-prod` (us-central1)
3. Use **Cloud Build** (not GitHub Actions) because:
   - No secrets to manage (uses GCP IAM)
   - Native integration with Cloud Run
   - Simpler for monorepo → multiple services

### Phase 3: Verify
1. Push test commit
2. Watch Cloud Build logs
3. Verify both services deploy

---

## STOP HERE

**Before I proceed, please confirm:**

Which service do you want CI/CD for?
1. The catalog site (already works)?
2. The new agency servers (need GitHub first)?
3. The Slack bot (need to find repo)?

Or do you want me to:
- Fix all the architecture issues first?
- Then set up proper CI/CD?

**What should I do next?**
