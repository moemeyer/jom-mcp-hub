# jomAI App MCP Slash Commands Failing - Root Cause Analysis

## Issue Summary
The jomAI app is showing repeated errors:
```
Error: MCP_API_KEY not configured
```

## Root Cause

The error "MCP_API_KEY not configured" indicates that one or more of the three MCP servers (BrioStack, CardPointe, or Agency/GHL) are failing to load their API keys from AWS Secrets Manager.

### Primary Issues Identified:

1. **Critical Syntax Error in OAuth Provider** (oauth/oauth_provider.py:410-495)
   - The `_handle_authorize_post` function is malformed with duplicated code blocks
   - Lines 417 and 426 have orphaned code: `p = {k: form.get(k, "") for k in (` and `)}`
   - Lines 430-433 duplicate the api_key validation logic
   - This would cause a Python SyntaxError on server startup

2. **Missing handle_authorize Method**
   - The routes() method references `self.handle_authorize` (line 565)
   - But only `_handle_authorize_post` exists (which is also malformed)
   - Should be a unified `handle_authorize` method handling both GET and POST

3. **Secrets Manager Configuration**
   - The servers expect API keys at these Secret Manager paths:
     - BrioStack: `pestpro/integrations/briostack`  
     - CardPointe: `pestpro/integrations/cardpointe`
     - Agency/GHL: `pestpro/integrations/ghl`
   - The OAuth provider expects: `pestpro/integrations/mcp-api-key`

## Impact

If the oauth_provider.py file with syntax errors is deployed to the Cloud Run instances, the servers would:
1. Fail to start due to Python import/syntax errors
2. Return generic error messages
3. Unable to authenticate any MCP tool calls

## Recommended Fixes

### Fix 1: Correct the OAuth Provider Code

Replace the malformed `_handle_authorize_post` with proper `handle_authorize` method that handles both GET and POST requests.

### Fix 2: Verify Secrets Manager Configuration

Check that all three secrets exist and contain the correct keys:
```bash
# BrioStack
aws secretsmanager get-secret-value --secret-id pestpro/integrations/briostack --region us-east-2

# CardPointe  
aws secretsmanager get-secret-value --secret-id pestpro/integrations/cardpointe --region us-east-1

# Agency/GHL
aws secretsmanager get-secret-value --secret-id pestpro/integrations/ghl --region us-east-2
```

### Fix 3: Check Cloud Run Deployment Status

Verify the three Cloud Run services are running:
```bash
# Check service status
gcloud run services list --region us-east-2
gcloud run services list --region us-west-2
```

### Fix 4: Review IAM Permissions

Ensure the Cloud Run service accounts have `secretsmanager:GetSecretValue` permissions for the `pestpro/*` secrets.

## Next Steps

1. Fix the syntax errors in oauth/oauth_provider.py
2. Redeploy all three MCP servers (BrioStack, CardPointe, Agency/GHL)  
3. Verify secrets are accessible
4. Test MCP tool calls from the jomAI app
5. Monitor Cloud Run logs for any remaining errors

## Testing

After fixes are deployed, test with:
```bash
# Test each MCP endpoint
curl -H "Accept: text/event-stream" https://<briostack-endpoint>/mcp
curl -H "Accept: text/event-stream" https://<cardpointe-endpoint>/mcp  
curl -H "Accept: text/event-stream" https://<agency-endpoint>/mcp
```

Expected response: MCP protocol handshake or "Not Acceptable" (which indicates server is healthy).
