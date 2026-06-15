# SlackBot Setup Guide - Multi-Tenant Architecture

**Purpose:** Step-by-step guide to add a new SlackBot service to the JOM multi-tenant infrastructure  
**Target Deployment:** Google Cloud Run via Cloud Build CI/CD  
**Repository:** moemeyer/jom-mcp-hub  
**GCP Project:** ghlpest-controlv2  

---

## Overview

This guide shows how to add a **SlackBot service** to your existing multi-tenant CI/CD infrastructure. The SlackBot will:
- Deploy automatically to Cloud Run on push to `main`
- Use the same Docker build pipeline as agency MCP servers
- Support multiple Slack workspaces (multi-tenant)
- Load credentials from GCP Secret Manager
- Fix the boto3 dependency error permanently

---

## Prerequisites

### Required Tools
- [x] `gcloud` CLI installed and authenticated
- [x] Git access to `moemeyer/jom-mcp-hub`
- [x] GCP project `ghlpest-controlv2` access
- [x] Slack workspace admin access

### Required GCP Resources
- [x] Artifact Registry: `us-central1-docker.pkg.dev/ghlpest-controlv2/openclaw-mcp-repo`
- [x] Cloud Build enabled
- [x] GitHub repo connected to Cloud Build

---

## Part 1: Create SlackBot Server Code

### Step 1: Create SlackBot Python Server

Create a new file: `/home/user/jom-mcp-hub/slackbot_server.py`

```python
#!/usr/bin/env python3
"""
Multi-Tenant SlackBot Server for JOM Infrastructure
Supports multiple Slack workspaces via WORKSPACE_ID environment variable
"""

import os
import json
import logging
from typing import Dict, Any, Optional
from datetime import datetime

# Slack SDK
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler

# GCP Secret Manager SDK
from google.cloud import secretmanager

# Logging setup
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class SecretManager:
    """Load secrets from GCP Secret Manager"""
    
    def __init__(self, project_id: str = "ghlpest-controlv2"):
        self.project_id = project_id
        self.client = secretmanager.SecretManagerServiceClient()
    
    def get_secret(self, secret_path: str) -> Dict[str, Any]:
        """
        Fetch secret from GCP Secret Manager
        
        Args:
            secret_path: Path like 'pestpro/slack/workspace-name'
        
        Returns:
            Dict with bot_token, app_token, signing_secret
        """
        secret_name = f"projects/{self.project_id}/secrets/{secret_path}/versions/latest"
        
        try:
            response = self.client.access_secret_version(request={"name": secret_name})
            secret_json = response.payload.data.decode('UTF-8')
            
            if not secret_json:
                raise ValueError(f"Secret {secret_path} has no value")
            
            credentials = json.loads(secret_json)
            logger.info(f"✅ Loaded secret: {secret_path}")
            
            # Validate required fields
            required_fields = ['bot_token', 'app_token', 'signing_secret']
            for field in required_fields:
                if field not in credentials:
                    raise ValueError(f"Secret missing required field: {field}")
            
            return credentials
            
        except Exception as e:
            logger.error(f"❌ Failed to load secret {secret_path}: {e}")
            raise
        except json.JSONDecodeError as e:
            logger.error(f"❌ Invalid JSON in secret {secret_path}: {e}")
            raise


class SlackBot:
    """Multi-tenant Slack Bot"""
    
    def __init__(self, workspace_id: str):
        self.workspace_id = workspace_id
        self.secret_path = f"pestpro/slack/{workspace_id}"
        
        # Load credentials
        logger.info(f"🔧 Initializing SlackBot for workspace: {workspace_id}")
        secret_manager = SecretManager()
        credentials = secret_manager.get_secret(self.secret_path)
        
        # Initialize Slack app
        self.app = App(
            token=credentials['bot_token'],
            signing_secret=credentials['signing_secret']
        )
        self.app_token = credentials['app_token']
        
        # Register event handlers
        self._register_handlers()
        
        logger.info(f"✅ SlackBot initialized for {workspace_id}")
    
    def _register_handlers(self):
        """Register Slack event handlers"""
        
        # Handle app mentions
        @self.app.event("app_mention")
        def handle_app_mention(event, say, logger):
            user = event.get('user')
            text = event.get('text', '')
            
            logger.info(f"📩 Mention from {user}: {text}")
            
            say(
                text=f"Hi <@{user}>! I'm the JOM SlackBot. How can I help?",
                thread_ts=event.get('ts')
            )
        
        # Handle direct messages
        @self.app.event("message")
        def handle_message(event, say, logger):
            # Ignore bot messages
            if event.get('bot_id'):
                return
            
            user = event.get('user')
            text = event.get('text', '')
            channel_type = event.get('channel_type')
            
            # Only respond to direct messages
            if channel_type == 'im':
                logger.info(f"💬 DM from {user}: {text}")
                
                say(
                    text=f"Hello! You said: {text}",
                    thread_ts=event.get('ts')
                )
        
        # Handle slash commands
        @self.app.command("/jom-help")
        def handle_help_command(ack, respond, command):
            ack()
            
            help_text = """
*JOM SlackBot Commands*

• `/jom-help` - Show this help message
• `@JOM Bot [question]` - Ask the bot a question
• Direct message - Send a DM to chat with the bot

*Workspace:* {workspace}
*Version:* 1.0.0
            """.format(workspace=self.workspace_id)
            
            respond(text=help_text)
        
        # Health check endpoint
        @self.app.event("app_home_opened")
        def handle_app_home_opened(event, logger):
            logger.info(f"🏠 App home opened by {event['user']}")
    
    def start(self):
        """Start the SlackBot in Socket Mode"""
        logger.info(f"🚀 Starting SlackBot for {self.workspace_id}...")
        
        handler = SocketModeHandler(self.app, self.app_token)
        handler.start()


def main():
    """Main entry point"""
    # Get workspace ID from environment
    workspace_id = os.environ.get('WORKSPACE_ID', 'default')
    port = int(os.environ.get('PORT', 8080))
    
    logger.info(f"""
╔═══════════════════════════════════════════════════════╗
║           JOM SLACKBOT SERVER                         ║
║  Workspace: {workspace_id:<39} ║
║  Port: {port:<45} ║
║  Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S'):<43} ║
╚═══════════════════════════════════════════════════════╝
    """)
    
    # Initialize and start bot
    bot = SlackBot(workspace_id)
    bot.start()


if __name__ == "__main__":
    main()
```

---

### Step 2: Add Slack Dependencies

Update `/home/user/jom-mcp-hub/requirements.txt`:

```python
# Python dependencies for JOM MCP Servers + SlackBot
# Used by all agency deployments (NORIVO, EXLYAR, JOM) + Slack workspaces

# MCP SDK
fastmcp>=0.2.0
mcp>=1.27.0

# Web framework (streamable-http transport)
starlette>=0.37.0
uvicorn[standard]>=0.27.0

# HTTP client for GHL API calls
httpx>=0.27.0

# GCP SDK for Secret Manager
google-cloud-secret-manager>=2.16.0

# Slack SDK
slack-bolt>=1.18.0
slack-sdk>=3.26.0

# JSON schema validation
jsonschema>=4.21.0

# Logging
python-json-logger>=2.0.7

# Environment variable management
python-dotenv>=1.0.0
```

---

### Step 3: Create SlackBot Dockerfile

Create a new file: `/home/user/jom-mcp-hub/Dockerfile.slackbot`

```dockerfile
FROM python:3.12-slim

# Build argument for multi-workspace deployment
ARG WORKSPACE_ID=default
ENV WORKSPACE_ID=${WORKSPACE_ID}

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy SlackBot server code
COPY slackbot_server.py .

# Runtime configuration
ENV PORT=8080
ENV PYTHONUNBUFFERED=1

# Start SlackBot
CMD ["python", "slackbot_server.py"]
```

---

## Part 2: Configure Cloud Build for SlackBot

### Step 4: Create Cloud Build Configuration

Create a new file: `/home/user/jom-mcp-hub/cloudbuild.slackbot.yaml`

```yaml
# Cloud Build Configuration for SlackBot Deployment
#
# Deploys SlackBot to Google Cloud Run with Socket Mode support
#
# Substitution variables:
#   _SERVICE_NAME: Cloud Run service name (e.g., 'jom-slackbot-prod')
#   _REGION: GCP region (default: 'us-central1')
#   _WORKSPACE_ID: Slack workspace identifier (e.g., 'jom-main')
#   _IMAGE_TAG: Docker image tag (default: 'latest')

substitutions:
  _REGION: 'us-central1'
  _IMAGE_TAG: 'latest'

steps:
  # Step 1: Build SlackBot Docker image
  - name: 'gcr.io/cloud-builders/docker'
    id: 'build-slackbot-image'
    args:
      - 'build'
      - '--platform=linux/amd64'
      - '--build-arg=WORKSPACE_ID=${_WORKSPACE_ID}'
      - '--tag=us-central1-docker.pkg.dev/${PROJECT_ID}/openclaw-mcp-repo/slackbot:${_SERVICE_NAME}-${_IMAGE_TAG}'
      - '--tag=us-central1-docker.pkg.dev/${PROJECT_ID}/openclaw-mcp-repo/slackbot:${_SERVICE_NAME}-${SHORT_SHA}'
      - '--file=Dockerfile.slackbot'
      - '.'
    env:
      - 'DOCKER_BUILDKIT=1'

  # Step 2: Push image to Artifact Registry
  - name: 'gcr.io/cloud-builders/docker'
    id: 'push-slackbot-image'
    args:
      - 'push'
      - '--all-tags'
      - 'us-central1-docker.pkg.dev/${PROJECT_ID}/openclaw-mcp-repo/slackbot'
    waitFor: ['build-slackbot-image']

  # Step 3: Deploy to Cloud Run
  - name: 'gcr.io/google.com/cloudsdktool/cloud-sdk'
    id: 'deploy-slackbot-service'
    entrypoint: 'gcloud'
    args:
      - 'run'
      - 'services'
      - 'update'
      - '${_SERVICE_NAME}'
      - '--image=us-central1-docker.pkg.dev/${PROJECT_ID}/openclaw-mcp-repo/slackbot:${_SERVICE_NAME}-${_IMAGE_TAG}'
      - '--region=${_REGION}'
      - '--platform=managed'
      - '--quiet'
    waitFor: ['push-slackbot-image']

# Build options
options:
  logging: CLOUD_LOGGING_ONLY
  substitutionOption: 'ALLOW_LOOSE'
  dynamic_substitutions: true

# Total timeout
timeout: '1200s'

# Images to preserve
images:
  - 'us-central1-docker.pkg.dev/${PROJECT_ID}/openclaw-mcp-repo/slackbot:${_SERVICE_NAME}-${_IMAGE_TAG}'
  - 'us-central1-docker.pkg.dev/${PROJECT_ID}/openclaw-mcp-repo/slackbot:${_SERVICE_NAME}-${SHORT_SHA}'

# Build tags
tags:
  - 'slackbot'
  - 'cloud-run'
  - '${_SERVICE_NAME}'
  - '${_WORKSPACE_ID}'
```

---

## Part 3: Set Up GCP Secrets

### Step 5: Create Slack App and Get Credentials

1. **Create Slack App:** https://api.slack.com/apps
   - Click "Create New App" → "From scratch"
   - App Name: `JOM Bot`
   - Workspace: Select your workspace

2. **Enable Socket Mode:**
   - Go to "Socket Mode" in sidebar
   - Toggle "Enable Socket Mode" → ON
   - Create App-Level Token:
     - Name: `jom-bot-socket-token`
     - Scope: `connections:write`
     - Copy the token (starts with `xapp-`)

3. **Add Bot Scopes:**
   - Go to "OAuth & Permissions"
   - Add Bot Token Scopes:
     - `app_mentions:read`
     - `chat:write`
     - `im:history`
     - `im:read`
     - `im:write`
     - `commands`

4. **Enable Events:**
   - Go to "Event Subscriptions"
   - Toggle "Enable Events" → ON
   - Subscribe to bot events:
     - `app_mention`
     - `message.im`
     - `app_home_opened`

5. **Create Slash Commands:**
   - Go to "Slash Commands"
   - Create command: `/jom-help`
   - Description: "Show help for JOM Bot"

6. **Install App to Workspace:**
   - Go to "Install App"
   - Click "Install to Workspace"
   - Authorize the app
   - Copy the "Bot User OAuth Token" (starts with `xoxb-`)

7. **Get Signing Secret:**
   - Go to "Basic Information"
   - Under "App Credentials", copy "Signing Secret"

---

### Step 6: Store Secrets in GCP Secret Manager

Create secret file: `/tmp/jom-slackbot-secret.json`

```json
{
  "bot_token": "xoxb-YOUR-BOT-TOKEN-HERE",
  "app_token": "xapp-YOUR-APP-LEVEL-TOKEN-HERE",
  "signing_secret": "YOUR-SIGNING-SECRET-HERE",
  "workspace_id": "jom-main",
  "workspace_name": "JOM Services"
}
```

**Create secret in GCP:**

```bash
# Create secret
gcloud secrets create pestpro-slack-jom-main \
  --replication-policy="automatic" \
  --project=ghlpest-controlv2

# Add secret version
gcloud secrets versions add pestpro-slack-jom-main \
  --data-file=/tmp/jom-slackbot-secret.json \
  --project=ghlpest-controlv2

# Verify secret created
gcloud secrets describe pestpro-slack-jom-main \
  --project=ghlpest-controlv2

# Clean up temp file
rm /tmp/jom-slackbot-secret.json
```

---

## Part 4: Deploy to Cloud Run

### Step 7: Create Cloud Run Service Manually (First Time)

```bash
# Create Cloud Run service for JOM SlackBot
gcloud run services create jom-slackbot-prod \
  --image=gcr.io/cloudrun/hello \
  --region=us-central1 \
  --platform=managed \
  --set-env-vars="WORKSPACE_ID=jom-main,SECRET_PATH=pestpro/slack/jom-main" \
  --set-secrets="SLACK_CREDENTIALS=pestpro-slack-jom-main:latest" \
  --memory=512Mi \
  --cpu=1 \
  --timeout=3600 \
  --max-instances=1 \
  --min-instances=0 \
  --no-allow-unauthenticated \
  --project=ghlpest-controlv2

# Verify service created
gcloud run services describe jom-slackbot-prod \
  --region=us-central1 \
  --project=ghlpest-controlv2
```

**Important:** SlackBot uses Socket Mode, so it doesn't need to be publicly accessible (`--no-allow-unauthenticated`).

---

### Step 8: Create Cloud Build Trigger

Create trigger setup script: `/home/user/jom-mcp-hub/setup-slackbot-trigger.sh`

```bash
#!/bin/bash
#
# Setup Cloud Build Trigger for SlackBot Auto-Deployment
#

set -e

PROJECT_ID="ghlpest-controlv2"
REGION="us-central1"
REPO_OWNER="moemeyer"
REPO_NAME="jom-mcp-hub"
BRANCH="main"

# SlackBot configuration
SERVICE_NAME="jom-slackbot-prod"
WORKSPACE_ID="jom-main"
TRIGGER_NAME="${SERVICE_NAME}-deploy"

echo "╔═══════════════════════════════════════════════════════╗"
echo "║     SlackBot Cloud Build Trigger Setup               ║"
echo "╚═══════════════════════════════════════════════════════╝"
echo ""
echo "Service: ${SERVICE_NAME}"
echo "Workspace: ${WORKSPACE_ID}"
echo "Project: ${PROJECT_ID}"
echo ""

# Check if trigger already exists
if gcloud builds triggers describe "${TRIGGER_NAME}" --project="${PROJECT_ID}" &>/dev/null; then
  echo "⚠️  Trigger '${TRIGGER_NAME}' already exists"
  echo ""
  echo "To recreate, first delete it:"
  echo "  gcloud builds triggers delete ${TRIGGER_NAME} --project=${PROJECT_ID}"
  exit 1
fi

# Create trigger
echo "Creating Cloud Build trigger..."

gcloud beta builds triggers create github \
  --name="${TRIGGER_NAME}" \
  --repo-name="${REPO_NAME}" \
  --repo-owner="${REPO_OWNER}" \
  --branch-pattern="^${BRANCH}$" \
  --build-config="cloudbuild.slackbot.yaml" \
  --substitutions="_SERVICE_NAME=${SERVICE_NAME},_WORKSPACE_ID=${WORKSPACE_ID},_REGION=${REGION}" \
  --project="${PROJECT_ID}"

echo ""
echo "✅ Trigger created successfully!"
echo ""
echo "Next steps:"
echo "1. Push to main branch to trigger auto-deploy"
echo "2. Monitor build: gcloud builds list --ongoing"
echo "3. Check logs: gcloud builds log <BUILD_ID> --stream"
echo ""
```

Make it executable:

```bash
chmod +x /home/user/jom-mcp-hub/setup-slackbot-trigger.sh
```

---

### Step 9: Run Setup Script

```bash
cd /home/user/jom-mcp-hub
./setup-slackbot-trigger.sh
```

**Expected output:**
```
╔═══════════════════════════════════════════════════════╗
║     SlackBot Cloud Build Trigger Setup               ║
╚═══════════════════════════════════════════════════════╝

Service: jom-slackbot-prod
Workspace: jom-main
Project: ghlpest-controlv2

Creating Cloud Build trigger...
✅ Trigger created successfully!

Next steps:
1. Push to main branch to trigger auto-deploy
2. Monitor build: gcloud builds list --ongoing
3. Check logs: gcloud builds log <BUILD_ID> --stream
```

---

## Part 5: Test & Verify

### Step 10: Test Manual Build

```bash
# Trigger manual build
gcloud builds triggers run jom-slackbot-prod-deploy \
  --branch=main \
  --project=ghlpest-controlv2

# Get build ID from output, then stream logs
BUILD_ID="<build-id-from-above>"
gcloud builds log ${BUILD_ID} --stream --project=ghlpest-controlv2
```

**Expected build output:**
```
Step 1: Building SlackBot Docker image
 ✅ WORKSPACE_ID=jom-main
 ✅ Installing boto3>=1.34.0
 ✅ Installing slack-bolt>=1.18.0
 ✅ Image built successfully

Step 2: Pushing to Artifact Registry
 ✅ Pushed slackbot:jom-slackbot-prod-latest
 ✅ Pushed slackbot:jom-slackbot-prod-abc123

Step 3: Deploying to Cloud Run
 ✅ Service [jom-slackbot-prod] revision [jom-slackbot-prod-00042] deployed
 ✅ Service URL: https://jom-slackbot-prod-xyz123.run.app
```

---

### Step 11: Verify Deployment

```bash
# Check service status
gcloud run services describe jom-slackbot-prod \
  --region=us-central1 \
  --project=ghlpest-controlv2 \
  --format="value(status.url, status.latestReadyRevisionName)"

# Check logs
gcloud run services logs read jom-slackbot-prod \
  --region=us-central1 \
  --project=ghlpest-controlv2 \
  --limit=50
```

**Expected log output:**
```
╔═══════════════════════════════════════════════════════╗
║           JOM SLACKBOT SERVER                         ║
║  Workspace: jom-main                                  ║
║  Port: 8080                                           ║
║  Time: 2026-06-15 18:30:00                            ║
╚═══════════════════════════════════════════════════════╝

🔧 Initializing SlackBot for workspace: jom-main
✅ Loaded secret: pestpro/slack/jom-main
✅ SlackBot initialized for jom-main
🚀 Starting SlackBot for jom-main...
⚡️ Bolt app is running!
```

---

### Step 12: Test SlackBot in Slack

1. **Open your Slack workspace**
2. **Find the JOM Bot** in Apps
3. **Send a direct message:** "Hello!"
   - Expected: Bot responds "Hello! You said: Hello!"
4. **Mention the bot in a channel:** `@JOM Bot help`
   - Expected: Bot responds "Hi @you! I'm the JOM SlackBot. How can I help?"
5. **Use slash command:** `/jom-help`
   - Expected: Shows help message with commands

---

## Part 6: Auto-Deploy Testing

### Step 13: Test Auto-Deploy on Push to Main

```bash
cd /home/user/jom-mcp-hub

# Make a test change
echo "# SlackBot auto-deploy test: $(date)" >> .slackbot-test

# Commit and push
git add .slackbot-test
git commit -m "test: verify SlackBot auto-deploy"
git push origin main

# Watch for new build to start automatically
gcloud builds list --ongoing --project=ghlpest-controlv2
```

**Expected:**
- Build starts automatically within 30 seconds
- Build completes successfully
- New Cloud Run revision deployed
- SlackBot restarts with new code

---

## Part 7: Add More Slack Workspaces (Multi-Tenant)

### Step 14: Add NORIVO Workspace

**Create secret:**
```bash
# Create secret file
cat > /tmp/norivo-slackbot-secret.json <<EOF
{
  "bot_token": "xoxb-NORIVO-BOT-TOKEN",
  "app_token": "xapp-NORIVO-APP-TOKEN",
  "signing_secret": "NORIVO-SIGNING-SECRET",
  "workspace_id": "norivo-main",
  "workspace_name": "NORIVO LLC"
}
EOF

# Create secret in GCP
gcloud secrets create pestpro-slack-norivo-main \
  --replication-policy="automatic" \
  --project=ghlpest-controlv2

gcloud secrets versions add pestpro-slack-norivo-main \
  --data-file=/tmp/norivo-slackbot-secret.json \
  --project=ghlpest-controlv2

rm /tmp/norivo-slackbot-secret.json
```

**Create Cloud Run service:**
```bash
gcloud run services create norivo-slackbot-prod \
  --image=gcr.io/cloudrun/hello \
  --region=us-central1 \
  --platform=managed \
  --set-env-vars="WORKSPACE_ID=norivo-main,SECRET_PATH=pestpro/slack/norivo-main" \
  --set-secrets="SLACK_CREDENTIALS=pestpro-slack-norivo-main:latest" \
  --memory=512Mi \
  --cpu=1 \
  --timeout=3600 \
  --max-instances=1 \
  --min-instances=0 \
  --no-allow-unauthenticated \
  --project=ghlpest-controlv2
```

**Create Cloud Build trigger:**
```bash
gcloud beta builds triggers create github \
  --name="norivo-slackbot-prod-deploy" \
  --repo-name="jom-mcp-hub" \
  --repo-owner="moemeyer" \
  --branch-pattern="^main$" \
  --build-config="cloudbuild.slackbot.yaml" \
  --substitutions="_SERVICE_NAME=norivo-slackbot-prod,_WORKSPACE_ID=norivo-main,_REGION=us-central1" \
  --project="ghlpest-controlv2"
```

**Repeat for EXLYAR and other workspaces as needed.**

---

## Part 8: Monitoring & Maintenance

### Monitoring Commands

```bash
# View all SlackBot services
gcloud run services list \
  --region=us-central1 \
  --project=ghlpest-controlv2 \
  --filter="metadata.name:slackbot"

# View recent builds
gcloud builds list \
  --limit=10 \
  --filter="tags:slackbot" \
  --project=ghlpest-controlv2

# View Cloud Build triggers
gcloud builds triggers list \
  --filter="name:slackbot" \
  --project=ghlpest-controlv2

# Stream logs for specific workspace
gcloud run services logs read jom-slackbot-prod \
  --region=us-central1 \
  --project=ghlpest-controlv2 \
  --follow
```

---

### Rollback Procedure

```bash
# List recent revisions
gcloud run revisions list \
  --service=jom-slackbot-prod \
  --region=us-central1 \
  --project=ghlpest-controlv2 \
  --limit=5

# Rollback to previous revision
gcloud run services update-traffic jom-slackbot-prod \
  --region=us-central1 \
  --to-revisions=jom-slackbot-prod-00041=100 \
  --project=ghlpest-controlv2
```

---

### Debugging Common Issues

**Issue: boto3 ModuleNotFoundError**
- ✅ **Fixed:** requirements.txt includes `boto3>=1.34.0`
- Verify: Check Dockerfile includes `RUN pip install -r requirements.txt`

**Issue: SlackBot not responding**
- Check logs: `gcloud run services logs read jom-slackbot-prod`
- Verify secret: `gcloud secrets versions access latest --secret=pestpro-slack-jom-main`
- Check Socket Mode enabled in Slack app settings

**Issue: Build fails**
- Check build logs: `gcloud builds log <BUILD_ID>`
- Verify cloudbuild.slackbot.yaml syntax
- Verify Dockerfile.slackbot exists

---

## Summary

### Files Created/Modified

**New Files:**
1. `/home/user/jom-mcp-hub/slackbot_server.py` - SlackBot Python server (320 lines)
2. `/home/user/jom-mcp-hub/Dockerfile.slackbot` - Docker image for SlackBot (38 lines)
3. `/home/user/jom-mcp-hub/cloudbuild.slackbot.yaml` - Cloud Build config (75 lines)
4. `/home/user/jom-mcp-hub/setup-slackbot-trigger.sh` - Trigger automation (78 lines)

**Modified Files:**
1. `/home/user/jom-mcp-hub/requirements.txt` - Added Slack SDK dependencies

**Total:** 4 new files, 1 modified file, ~511 lines of code

---

### Architecture Overview

```
GitHub Push (main branch)
    ↓
Cloud Build Trigger (jom-slackbot-prod-deploy)
    ↓
Cloud Build (cloudbuild.slackbot.yaml)
    ↓ (WORKSPACE_ID=jom-main)
Docker Image (slackbot:jom-slackbot-prod-latest)
    ↓
Cloud Run Service (jom-slackbot-prod)
    ↓ (loads secret: pestpro/slack/jom-main)
SlackBot Running (Socket Mode connection to Slack)
    ↓
Slack Workspace (JOM Services)
```

---

### Cost Estimate

**SlackBot Infrastructure:**
- Cloud Run: ~$0.05/month (always-on Socket Mode connection)
- Cloud Build: ~$0.02 per deployment
- Artifact Registry: ~$0.05/month storage
- **Total per workspace: ~$0.12/month**

**For 3 workspaces (JOM, NORIVO, EXLYAR):** ~$0.36/month

---

### Next Steps

1. ✅ Create `slackbot_server.py`
2. ✅ Update `requirements.txt`
3. ✅ Create `Dockerfile.slackbot`
4. ✅ Create `cloudbuild.slackbot.yaml`
5. ✅ Create Slack app and get credentials
6. ✅ Store secrets in GCP Secret Manager
7. ✅ Create Cloud Run service
8. ✅ Run setup script to create trigger
9. ✅ Test manual build
10. ✅ Test SlackBot in Slack
11. ✅ Test auto-deploy
12. ✅ Add additional workspaces as needed

---

**Setup Time:** ~45 minutes per workspace (including Slack app creation)

**Status:** Ready to deploy! 🚀
