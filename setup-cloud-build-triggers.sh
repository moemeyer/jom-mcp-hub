#!/bin/bash
# Setup Cloud Build triggers for multi-agency MCP deployments
#
# Creates separate triggers for each agency that auto-deploy on push to main branch.
# Each trigger can be enabled/disabled independently.

set -e

PROJECT_ID="${GCP_PROJECT_ID:-ghlpest-controlv2}"
REGION="${GCP_REGION:-us-central1}"
REPO_OWNER="${GITHUB_OWNER:-moemeyer}"
REPO_NAME="${GITHUB_REPO:-jom-mcp-hub}"

echo "🔨 Setting up Cloud Build triggers for MCP server deployments"
echo "   Project: ${PROJECT_ID}"
echo "   Region: ${REGION}"
echo "   GitHub: ${REPO_OWNER}/${REPO_NAME}"
echo ""

# Function to create a trigger
create_trigger() {
  local SERVICE_NAME=$1
  local AGENCY_ID=$2
  local BRANCH=${3:-main}

  echo "📋 Creating trigger for: ${SERVICE_NAME} (agency: ${AGENCY_ID})"

  gcloud beta builds triggers create github \
    --name="${SERVICE_NAME}-deploy" \
    --description="Auto-deploy ${SERVICE_NAME} to Cloud Run on push to ${BRANCH}" \
    --repo-owner="${REPO_OWNER}" \
    --repo-name="${REPO_NAME}" \
    --branch-pattern="^${BRANCH}$" \
    --build-config="cloudbuild.yaml" \
    --project="${PROJECT_ID}" \
    --substitutions="_SERVICE_NAME=${SERVICE_NAME},_AGENCY_ID=${AGENCY_ID},_REGION=${REGION}" \
    --include-logs-with-status \
    2>/dev/null || echo "   ⚠️  Trigger ${SERVICE_NAME}-deploy already exists (skipping)"

  echo "   ✅ Trigger created: ${SERVICE_NAME}-deploy"
  echo ""
}

# Create triggers for each agency
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Creating deployment triggers..."
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# NORIVO LLC
create_trigger "norivo-agency-mcp-prod" "norivo" "main"

# EXLYAR LLC
create_trigger "exlyar-agency-mcp-prod" "exlyar" "main"

# JOM Services (if migrating from AWS App Runner)
# create_trigger "jom-agency-mcp-prod" "jom" "main"

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "✅ All triggers created successfully!"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# List all triggers
echo "📋 Active Cloud Build triggers:"
gcloud builds triggers list --project="${PROJECT_ID}" --filter="name~mcp-prod"

echo ""
echo "🎯 Next steps:"
echo "   1. Verify triggers are enabled: gcloud builds triggers list"
echo "   2. Push to 'main' branch to trigger deployment"
echo "   3. Monitor builds: gcloud builds list --ongoing"
echo "   4. View logs: gcloud builds log <BUILD_ID>"
echo ""
echo "🔧 Manual trigger test:"
echo "   gcloud builds triggers run norivo-agency-mcp-prod-deploy --branch=main"
echo "   gcloud builds triggers run exlyar-agency-mcp-prod-deploy --branch=main"
echo ""
