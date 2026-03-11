# SentinelLens - End-to-End Testing Setup Guide (Phase 5)

## Overview
This guide walks you through setting up and testing SentinelLens with **real Azure credentials** and **real data** from your Microsoft Sentinel workspace.

**Duration**: ~15 minutes setup, then walk through the complete workflow

---

## Prerequisites

Before starting, you'll need:
- ✅ Azure subscription with Microsoft Sentinel workspace
- ✅ Azure AD application registration (service principal)
- ✅ Python 3.10+ installed
- ✅ Node.js 18+ and npm 9+ installed
- ✅ Git (for pulling latest code)

---

## Step 1: Get Azure Credentials

### 1.1 Get Your Subscription Details
```bash
# Open Azure Portal and note:
# - Subscription ID: https://portal.azure.com/#view/Microsoft_Azure_Billing/SubscriptionsBlade
# - Tenant ID: https://portal.azure.com/#view/Microsoft_AAD_IAM/TenantProperties
```

### 1.2 Create or Use Existing App Registration

**Option A: Create New App Registration**
1. Go to: Azure Portal → Azure AD → App registrations
2. Click **New registration**
3. Enter Name: `SentinelLens-Dev`
4. Leave other settings as default
5. Click **Register**

**Option B: Use Existing App Registration**
1. Go to: Azure Portal → Azure AD → App registrations
2. Find your app (e.g., `SentinelLens-Dev`)

### 1.3 Get Client ID and Secret

1. **Client ID** (Application ID):
   - In your app registration, go to **Overview**
   - Copy the **Application (client) ID** value

2. **Client Secret**:
   - In your app registration, go to **Certificates & secrets**
   - Click **New client secret**
   - Give it a name (e.g., `dev-secret`)
   - Set expiration (e.g., 12 months)
   - Click **Add**
   - ⚠️ **Copy the secret VALUE immediately** - you won't see it again!

### 1.4 Grant Permissions to Your Workspace

1. Go to your Log Analytics workspace → **Access control (IAM)**
2. Click **Add role assignment**
3. Select role: **Log Analytics Contributor**
4. Assign to: Your app registration (search for `SentinelLens-Dev`)
5. Click **Review + assign**

---

## Step 2: Setup Backend

### 2.1 Install Dependencies

```bash
cd backend

# Install Python dependencies
pip install -r requirements.txt

# Verify installation
python -c "import fastapi; import azure.identity; print('✅ Dependencies installed')"
```

### 2.2 Create Backend Configuration

```bash
# In the backend directory, create .env.local:
cat > .env.local << 'EOF'
ENVIRONMENT=dev
DEBUG=false
APP_NAME=SentinelLens
AZURE_SUBSCRIPTION_ID=<your-subscription-id>
AZURE_TENANT_ID=<your-tenant-id>
AZURE_KEY_VAULT_URL=https://vault-name.vault.azure.net/
FRONTEND_URL=http://localhost:3000
AZURE_CLIENT_ID=<your-app-registration-client-id>
AZURE_CLIENT_SECRET=<your-app-registration-client-secret>
EOF
```

**Replace these values:**
- `<your-subscription-id>` - From Step 1.1
- `<your-tenant-id>` - From Step 1.1
- `<your-app-registration-client-id>` - From Step 1.3
- `<your-app-registration-client-secret>` - From Step 1.3

⚠️ **Security**: Keep this file safe! It contains your credentials. It's in `.gitignore` and never committed.

### 2.3 Start Backend

```bash
# Terminal 1 - Backend
cd backend
python -m uvicorn src.main:app --host 127.0.0.1 --port 8002

# Expected output:
# INFO:     Uvicorn running on http://127.0.0.1:8002
# INFO:     [STARTUP] SentinelLens backend starting
```

**Test Backend**:
```bash
# In another terminal:
curl http://127.0.0.1:8002/health
# Should return: {"status":"healthy",...}
```

---

## Step 3: Setup Frontend

### 3.1 Install Dependencies

```bash
cd frontend

# Install npm dependencies
npm install

# Verify
npm --version  # Should be 9+
node --version # Should be 18+
```

### 3.2 Create Frontend Configuration

```bash
# In the frontend directory, create .env.local:
cat > .env.local << 'EOF'
NEXT_PUBLIC_TENANT_ID=<your-tenant-id>
NEXT_PUBLIC_CLIENT_ID=<your-app-registration-client-id>
NEXT_PUBLIC_API_BASE_URL=http://localhost:8002/api/v1
EOF
```

**Replace these values:**
- `<your-tenant-id>` - From Step 1.1
- `<your-app-registration-client-id>` - From Step 1.3

### 3.3 Start Frontend

```bash
# Terminal 2 - Frontend
cd frontend
npm run dev

# Expected output:
# ▲ Next.js 14.0.0
#  - Local:        http://localhost:3000
```

---

## Step 4: End-to-End Workflow Testing

### Screen 1: Setup Page (/setup)

**URL**: `http://localhost:3000/setup`

**What to do**:
1. Open the URL
2. You should see a form with two fields:
   - Client ID
   - Client Secret
3. Enter your Azure credentials from Step 1.3
4. Click **Configure Credentials**
5. You should see: ✅ "Credentials configured successfully!"
6. You'll be redirected to dashboard after 2 seconds

**Expected Flow**:
- POST to `http://localhost:8002/api/v1/setup/credentials`
- Backend writes credentials to `.env.local`
- Backend responds with success
- Frontend auto-redirects to dashboard

**Verify**:
```bash
# Check that backend .env.local was created
cat backend/.env.local
# Should contain your AZURE_CLIENT_ID and AZURE_CLIENT_SECRET
```

---

### Screen 2: Dashboard (/dashboard)

**URL**: `http://localhost:3000/dashboard` (auto-redirect from setup)

**What you should see**:
- "SentinelLens" header
- Summary cards (Audits Completed, etc.)
- List of audit jobs (initially empty since this is first run)
- **New Audit** button

**Expected behavior**:
- Page loads successfully
- You can see the dashboard layout
- Ready to start first audit

**Verify**:
```bash
# Check backend logs for successful requests:
# Should see: "GET /api/v1/workspaces" - 200 OK
```

---

### Screen 3: New Audit (/audit/new)

**URL**: Click **New Audit** button on dashboard

**What you should see**:
- **Workspace**: Dropdown showing your Log Analytics workspaces from Azure
- **Days Lookback**: Input field (default 30)
- **Start Audit** button

**What to do**:
1. Click the **Workspace** dropdown
2. Select one of your real workspaces (should load from Azure)
3. Keep Days Lookback as 30
4. Click **Start Audit**
5. You'll be redirected to the Progress page

**Expected Flow**:
- GET `http://localhost:8002/api/v1/workspaces` returns your real workspaces
- Dropdown populates with workspace names
- POST `http://localhost:8002/api/v1/audits` creates job
- Job ID returned in response
- Redirected to `/audit/[jobId]/progress`

**Verify**:
```bash
# Check backend logs:
# Should see: "GET /api/v1/workspaces" - 200 OK
# Should see: "POST /api/v1/audits" - 200 OK with new job ID
```

---

### Screen 4: Progress Page (/audit/[jobId]/progress)

**URL**: `http://localhost:3000/audit/[jobId]/progress`

**What you should see**:
- Job ID at top
- Status indicator (running/completed)
- Real-time progress with steps:
  - Connecting to workspace
  - Fetching tables
  - Analyzing usage patterns
  - Calculating costs
  - Generating recommendations
- Progress bar
- Elapsed time
- **Cancel** button (if still running)

**Expected Flow**:
- GET `http://localhost:8002/api/v1/audits/{job_id}` returns status
- GET `http://localhost:8002/api/v1/audits/{job_id}/stream` opens SSE connection
- Backend sends progress updates in real-time
- Page updates as messages arrive

**What's happening in the backend**:
1. Agent connects to Log Analytics workspace
2. Fetches all tables in workspace
3. Analyzes usage patterns (queries, data volume)
4. Calculates costs per table
5. Identifies candidates:
   - Archive: Not used in 30+ days
   - Low usage: Less than X queries/month
   - Active: Normal usage

**Verify**:
```bash
# Watch backend logs:
# Should see progress messages like:
# [PROGRESS] Step 1/5: Connecting to workspace
# [PROGRESS] Step 2/5: Fetching tables
# ... etc
```

**⏱️ Duration**: ~30-60 seconds depending on workspace size

---

### Screen 5: Report Page (/audit/[jobId]/report)

**URL**: Auto-redirected after progress completes

**What you should see**:
- Executive Summary:
  - Total tables analyzed
  - Archive candidates count
  - Low usage tables count
  - Active tables count
  - Estimated monthly cost savings
  - Estimated annual savings

- Tabbed view:
  1. **Archive Candidates**: Tables not used in 30+ days
     - Table name
     - Last query date
     - Data retained (GB)
     - Estimated monthly cost
     - Recommended tier (delete or Archive)

  2. **Low Usage**: Tables with very low activity
     - Table name
     - Query count (last 30 days)
     - Data volume
     - Estimated cost
     - Recommendation

  3. **Active Tables**: Tables with normal usage
     - Table name
     - Query frequency
     - Data volume
     - Current cost

  4. **Warnings**: Any issues found
     - Permission errors
     - Timeout issues
     - Missing data

- Charts:
  - Cost breakdown pie chart
  - Usage heatmap
  - Storage trends

**Expected Data**:
- All values calculated from YOUR real workspace
- Real table names from your Sentinel
- Real cost calculations based on Azure pricing
- Real usage patterns from your queries

**Verify**:
```bash
# Check that:
# 1. Tables match your workspace
# 2. Costs are not $0 or $NaN
# 3. Usage data shows real patterns
# 4. Multiple tabs have content
```

**Potential Issues**:
- If showing "$NaN": Backend didn't restart after credential change
- If no tables: Workspace might be empty or you don't have permission
- If cost is $0: Table is very small (normal for small workspaces)

---

### Screen 6: Approval Flow (/audit/[jobId]/approve)

**URL**: Click **Approve & Migrate** button on report

**What you should see**:
- Summary of recommended changes
- Checkboxes for each table:
  - Archive candidates: Option to archive or delete
  - Low usage: Option to move to lower tier
  - Active: Keep as-is
- Live savings calculation:
  - "Saving $X/month" for each selected table
  - "Total savings: $Y/month"
- **Confirm Migration** button

**What to do** (optional, don't actually migrate unless ready):
1. Review the recommendations
2. Check boxes for tables you want to migrate
3. See savings calculation update in real-time
4. Click **Confirm Migration** (or **Cancel** to go back)

**Expected Flow**:
- POST `http://localhost:8002/api/v1/audits/{job_id}/approve` with selected tables
- Backend processes the migration request
- Response shows success
- Redirected to dashboard
- New audit appears in history

**Verify**:
```bash
# Check backend logs:
# Should see: "POST /api/v1/audits/{job_id}/approve" - 200 OK
# Should see: "Approvals logged to audit trail"
```

---

## Step 5: Verify Complete Workflow

### Checklist

- [ ] Setup page accepts credentials
- [ ] Credentials saved to backend .env.local
- [ ] Dashboard loads with no errors
- [ ] Workspace dropdown populated from Azure
- [ ] New Audit starts and creates job
- [ ] Progress page shows real-time updates
- [ ] Report page loads with real data
- [ ] All tabs (Archive/Low Usage/Active/Warnings) have content
- [ ] Cost calculations are correct
- [ ] Approval flow allows selecting tables
- [ ] Savings calculations are accurate

---

## Troubleshooting

### Backend Won't Start
```bash
# Error: Address already in use (port 8002)
lsof -i :8002  # macOS/Linux
netstat -ano | grep 8002  # Windows
# Kill the process and restart

# Or use a different port:
python -m uvicorn src.main:app --host 127.0.0.1 --port 9000
# Then update frontend .env.local:
# NEXT_PUBLIC_API_BASE_URL=http://localhost:9000/api/v1
```

### Frontend Won't Start
```bash
# Error: Port 3000 already in use
npm run dev -- -p 3001  # Use port 3001 instead

# Clear Next.js cache
rm -rf .next
npm run dev
```

### Setup Endpoint Returns 404
```bash
# Make sure backend is running on port 8002
curl http://127.0.0.1:8002/health
# If this fails, backend isn't running

# Try restarting:
# Kill old process
kill %1  # or Ctrl+C
# Start fresh
python -m uvicorn src.main:app --host 127.0.0.1 --port 8002
```

### Workspaces Not Showing
```bash
# Check that you granted permissions in Step 1.4
# Verify app registration has Log Analytics Contributor role
# Check Azure Portal → Log Analytics workspace → Access control (IAM)

# Test permissions via API:
curl -H "Authorization: Bearer YOUR_TOKEN" \
  http://127.0.0.1:8002/api/v1/workspaces
```

### Report Showing Wrong Data
```bash
# Backend needs restart after credential changes
# Kill the process (Ctrl+C) and restart:
python -m uvicorn src.main:app --host 127.0.0.1 --port 8002
```

### SSE Connection Lost
```bash
# Make sure frontend .env.local has correct API URL:
cat frontend/.env.local
# Should show: NEXT_PUBLIC_API_BASE_URL=http://localhost:8002/api/v1

# If using different port, update and restart frontend:
npm run dev
```

---

## What's Being Tested

### Backend Integration
- ✅ Azure AD authentication (service principal)
- ✅ Log Analytics workspace queries
- ✅ Cost calculations with real Azure pricing
- ✅ Table analysis and recommendations
- ✅ SSE progress streaming
- ✅ Agent orchestrator (ReAct loop)
- ✅ Security (PII masking, audit logging)

### Frontend Integration
- ✅ Azure AD login (MSAL.js)
- ✅ Real-time progress updates
- ✅ Data visualization (charts, tables)
- ✅ Form handling
- ✅ Error handling
- ✅ Responsive design

### End-to-End
- ✅ Complete workflow from setup to approval
- ✅ Real data from your Azure subscription
- ✅ Real cost calculations
- ✅ Real recommendations
- ✅ Authentication and authorization

---

## Next Steps

After completing this test:

1. **Document Results**: Note any issues or unexpected behavior
2. **Performance Check**: Measure time taken for each step
3. **Error Testing**: Try invalid inputs, network failures
4. **Security Audit**: Verify no credentials in logs
5. **Load Testing**: Test with multiple audits
6. **Production Readiness**: Check deployment checklist

---

## Support

If you encounter issues:
1. Check the Troubleshooting section above
2. Review backend logs for error messages
3. Check frontend browser console for errors
4. Verify Azure Portal permissions
5. Ensure all credentials are correct

---

Good luck! 🚀
