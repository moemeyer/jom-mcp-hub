# Technical Debt - CI/CD Setup

**Generated:** June 5, 2026  
**Session:** Cloud Run CI/CD for jom-mcp-hub  
**Status:** Merged to main, pending activation  

---

## ⚠️ What Was NOT Verified

### **1. Cloud Build Triggers Not Created**

**Issue:** Triggers don't exist yet  
**Why:** No `gcloud` CLI in this remote environment  
**Impact:** Auto-deploy won't work until triggers created  
**Fix:** Run `./setup-cloud-build-triggers.sh` from local machine  
**Estimated Time:** 5 minutes  

```bash
cd ~/jom-mcp-hub
./setup-cloud-build-triggers.sh
```

---

### **2. No Actual Build Executed**

**Issue:** Cannot verify cloudbuild.yaml works  
**Why:** No `gcloud` CLI to trigger builds  
**Impact:** Unknown if build will succeed  
**Fix:** Run manual trigger test after setup  
**Estimated Time:** 10 minutes  

```bash
gcloud builds triggers run norivo-agency-mcp-prod-deploy --branch=main
gcloud builds log <BUILD_ID> --stream
```

**Risk:** Medium - cloudbuild.yaml syntax verified but not tested

---

### **3. Cloud Run Services Not Deployed**

**Issue:** No new Cloud Run revisions created  
**Why:** Triggers don't exist yet  
**Impact:** Services still running old code (or not running)  
**Fix:** Wait for first build to complete  
**Estimated Time:** 15 minutes after build starts  

```bash
# Check deployment
gcloud run services describe norivo-agency-mcp-prod --region=us-central1
curl https://norivo.agency-mcp.jom.services/
```

---

### **4. Auto-Deploy Not Tested**

**Issue:** Push to main won't trigger deploy yet  
**Why:** Triggers not configured  
**Impact:** Manual deploys required until fixed  
**Fix:** Test after triggers created  
**Estimated Time:** 2 minutes  

```bash
echo "test" >> .cloud-build-test
git add . && git commit -m "test: auto-deploy"
git push origin main
gcloud builds list --ongoing  # Should show new build
```

---

### **5. Service Health Not Verified**

**Issue:** Don't know if services respond correctly  
**Why:** Services not deployed yet  
**Impact:** May have runtime errors  
**Fix:** Test endpoints after deployment  
**Estimated Time:** 5 minutes  

```bash
# Health checks
curl https://norivo.agency-mcp.jom.services/
curl https://norivo.agency-mcp.jom.services/.well-known/oauth-authorization-server

# Expected: 200 OK with OAuth metadata JSON
```

---

## 🐛 Potential Issues

### **Missing GCP Secrets**

**Problem:** Cloud Run services expect secrets in Secret Manager  
**Required Secrets:**
- `pestpro-integrations-norivo-agency`
- `pestpro-integrations-exlyar-agency`

**Verify:**
```bash
gcloud secrets describe pestpro-integrations-norivo-agency --project=ghlpest-controlv2
gcloud secrets describe pestpro-integrations-exlyar-agency --project=ghlpest-controlv2
```

**If missing:** Run `/home/user/jom-agency-shared/setup-secrets.sh` first

---

### **Cloud Run Services Don't Exist**

**Problem:** Build will fail if target services don't exist  
**Required Services:**
- `norivo-agency-mcp-prod` (us-central1)
- `exlyar-agency-mcp-prod` (us-central1)

**Verify:**
```bash
gcloud run services list --region=us-central1 --project=ghlpest-controlv2
```

**If missing:** Deploy manually once:
```bash
gcloud run services create norivo-agency-mcp-prod \
  --image=us-central1-docker.pkg.dev/ghlpest-controlv2/openclaw-mcp-repo/agency-mcp:latest \
  --region=us-central1 \
  --set-env-vars=AGENCY_ID=norivo,SECRET_PATH=pestpro/integrations/norivo-agency
```

---

### **Cloud Build IAM Permissions**

**Problem:** Cloud Build SA may lack permissions  
**Required Roles:**
- `roles/run.admin` (to update Cloud Run)
- `roles/iam.serviceAccountUser` (to use service account)
- `roles/artifactregistry.writer` (to push images)

**Verify:**
```bash
# Get Cloud Build SA
SA="<PROJECT_NUMBER>@cloudbuild.gserviceaccount.com"

# Check roles
gcloud projects get-iam-policy ghlpest-controlv2 --flatten="bindings[].members" --filter="bindings.members:$SA"
```

---

### **Docker Build Platform**

**Problem:** Cloud Build might not use amd64  
**Risk:** ARM images won't run on Cloud Run  
**Mitigation:** cloudbuild.yaml has `--platform=linux/amd64` ✅  
**Verify:** Check build logs for platform warning  

---

### **DNS Not Configured**

**Problem:** Custom domains may not point to Cloud Run  
**Required CNAME:**
- `norivo.agency-mcp.jom.services` → `ghs.googlehosted.com`
- `exlyar.agency-mcp.jom.services` → `ghs.googlehosted.com`

**Verify:**
```bash
dig norivo.agency-mcp.jom.services +short
# Expected: CNAME to ghs.googlehosted.com
```

**Fix:** Add DNS records in DNSimple

---

## 📝 Assumptions Made

1. ✅ GCP project `ghlpest-controlv2` exists and is accessible
2. ✅ GitHub repo `moemeyer/jom-mcp-hub` is connected to Cloud Build
3. ⚠️ Cloud Run services already exist (not verified)
4. ⚠️ GCP secrets exist (not verified)
5. ⚠️ Cloud Build SA has correct permissions (not verified)
6. ⚠️ DNS is configured (not verified)
7. ✅ Artifact Registry repo `openclaw-mcp-repo` exists
8. ✅ Python code is correct (server_template.py copied from working version)

---

## 🔧 Quick Fix Checklist

Run this checklist before activating CI/CD:

```bash
# 1. Verify secrets exist
gcloud secrets list --project=ghlpest-controlv2 | grep norivo
gcloud secrets list --project=ghlpest-controlv2 | grep exlyar

# 2. Verify Cloud Run services exist
gcloud run services list --region=us-central1 | grep mcp-prod

# 3. Verify Cloud Build permissions
gcloud projects get-iam-policy ghlpest-controlv2 --flatten="bindings[].members" | grep cloudbuild

# 4. Verify DNS
dig norivo.agency-mcp.jom.services +short

# 5. Create triggers
cd ~/jom-mcp-hub
./setup-cloud-build-triggers.sh

# 6. Test manual build
gcloud builds triggers run norivo-agency-mcp-prod-deploy --branch=main

# 7. Watch build
gcloud builds log <BUILD_ID> --stream

# 8. Test service
curl https://norivo.agency-mcp.jom.services/
```

---

## 📊 Completion Status

| Task | Status | Blocker |
|------|--------|---------|
| Infrastructure code | ✅ Complete | None |
| Merge to main | ✅ Complete | None |
| Documentation | ✅ Complete | None |
| Trigger creation | ⏸️ Pending | Need local gcloud CLI |
| Build execution | ⏸️ Pending | Triggers needed |
| Service deployment | ⏸️ Pending | Build needed |
| Health verification | ⏸️ Pending | Deployment needed |

**Overall: 50% complete** (code done, activation pending)

---

## 🎯 Next Actions

1. **Immediate:** Run `./setup-cloud-build-triggers.sh`
2. **Verify:** Check if secrets and services exist
3. **Test:** Run manual trigger
4. **Monitor:** Watch build logs
5. **Validate:** Test service endpoints
6. **Activate:** Push to main should auto-deploy

**Estimated time to 100% complete:** 30 minutes

---

## 📞 Support

**If build fails:**
- Check logs: `gcloud builds log <BUILD_ID>`
- Verify IAM: Cloud Build SA needs Cloud Run Admin
- Verify secrets: Services need GCP secrets to exist

**If service fails:**
- Check logs: `gcloud run services logs read <SERVICE> --region=us-central1`
- Verify secrets: `SECRET_PATH` must match actual secret name
- Verify Python deps: `requirements.txt` includes boto3 ✅

**If auto-deploy doesn't work:**
- Verify trigger: `gcloud builds triggers list`
- Check trigger status: Must be enabled
- Verify branch: Trigger watches `main` branch
