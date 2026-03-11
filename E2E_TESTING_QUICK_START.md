# SentinelLens - Quick Start Checklist (5 minutes)

## Get Your Credentials (Azure Portal)

### 📋 Information You Need:

```
Subscription ID: ____________________________
Tenant ID: ____________________________
App Registration Client ID: ____________________________
App Registration Client Secret: ____________________________
```

**Where to get them:**
- Subscription ID & Tenant ID: Azure Portal → Subscriptions (or Azure AD → Properties)
- Client ID & Secret: Azure Portal → Azure AD → App registrations → Your app → Overview/Certificates & Secrets
- Grant permissions: Log Analytics workspace → Access control (IAM) → Add role assignment (Log Analytics Contributor)

---

## Setup (10 minutes)

### Terminal 1 - Backend Setup

```bash
# 1. Navigate to backend
cd backend

# 2. Install dependencies
pip install -r requirements.txt

# 3. Create .env.local with your credentials
cat > .env.local << 'EOF'
ENVIRONMENT=dev
DEBUG=false
APP_NAME=SentinelLens
AZURE_SUBSCRIPTION_ID=<PASTE-YOUR-SUBSCRIPTION-ID>
AZURE_TENANT_ID=<PASTE-YOUR-TENANT-ID>
AZURE_KEY_VAULT_URL=https://vault-name.vault.azure.net/
FRONTEND_URL=http://localhost:3000
AZURE_CLIENT_ID=<PASTE-YOUR-CLIENT-ID>
AZURE_CLIENT_SECRET=<PASTE-YOUR-CLIENT-SECRET>
EOF

# 4. Start backend
python -m uvicorn src.main:app --host 127.0.0.1 --port 8002
```

✅ **Backend should say**: `Uvicorn running on http://127.0.0.1:8002`

---

### Terminal 2 - Frontend Setup

```bash
# 1. Navigate to frontend
cd frontend

# 2. Install dependencies
npm install

# 3. Create .env.local
cat > .env.local << 'EOF'
NEXT_PUBLIC_TENANT_ID=<PASTE-YOUR-TENANT-ID>
NEXT_PUBLIC_CLIENT_ID=<PASTE-YOUR-CLIENT-ID>
NEXT_PUBLIC_API_BASE_URL=http://localhost:8002/api/v1
EOF

# 4. Start frontend
npm run dev
```

✅ **Frontend should say**: `Local: http://localhost:3000`

---

## Test (5 minutes)

### Open http://localhost:3000 and go through workflow:

1. **Setup** (`/setup`)
   - Enter your Client ID and Secret
   - Click "Configure Credentials"
   - ✅ See success message

2. **Dashboard** (`/dashboard`)
   - Auto-redirected from setup
   - ✅ See empty audit list

3. **New Audit** (`/audit/new`)
   - Click "New Audit" button
   - Select workspace from dropdown
   - Click "Start Audit"
   - ✅ Redirected to progress

4. **Progress** (`/audit/[jobId]/progress`)
   - Watch real-time updates
   - ✅ See progress bar moving

5. **Report** (`/audit/[jobId]/report`)
   - Auto-redirected when complete
   - ✅ See real data with costs

6. **Approval** (`/audit/[jobId]/approve`)
   - Click "Approve & Migrate"
   - ✅ See recommendations and savings

---

## Common Issues & Fixes

| Issue | Fix |
|-------|-----|
| **Port 8002 in use** | `lsof -i :8002` then kill process, or use different port |
| **Port 3000 in use** | `npm run dev -- -p 3001` or kill process |
| **Setup endpoint 404** | Make sure backend is running (`curl http://127.0.0.1:8002/health`) |
| **No workspaces showing** | Check IAM permissions in Log Analytics workspace |
| **Report shows $NaN** | Restart backend after credential changes (Ctrl+C, then restart) |
| **SSE connection lost** | Verify `NEXT_PUBLIC_API_BASE_URL` is correct in frontend/.env.local |

---

## Success Criteria

You'll know it's working when you can:

- [ ] Navigate to `/setup` and configure credentials
- [ ] See your workspaces from Azure in the `/audit/new` dropdown
- [ ] Start an audit and see real-time progress updates
- [ ] View the report with real data from your workspace
- [ ] See accurate cost calculations
- [ ] Navigate to approval flow without errors

---

## Next Steps

After testing:
1. Review the detailed guide: `E2E_TESTING_SETUP.md`
2. Check backend logs for any errors or warnings
3. Verify no credentials appear in logs
4. Test error scenarios (invalid input, network failures)
5. Measure performance of each step

---

**Ready? Start with Terminal 1 above! 🚀**
