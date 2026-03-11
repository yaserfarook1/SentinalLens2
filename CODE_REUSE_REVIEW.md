# Code Reuse Analysis - SentinelLens Git Diff Review

## Executive Summary
This analysis reviews the recent git diff for code reuse opportunities. Several findings identify where new code duplicates existing utility functions, introduces new patterns that could be refactored, or implements inline logic that should leverage existing utilities.

**Total Findings: 8** | High Priority: 3 | Medium Priority: 4 | Low Priority: 1

---

## Findings

### 1. DUPLICATE: Extract Workspace Details Function - HIGH CONFIDENCE
**Location:** `backend/src/api/routes.py` lines 479-483
**Issue:** Code manually extracts workspace details using string manipulation inline, while a utility function already exists.

**Problematic Code:**
```python
# backend/src/api/routes.py (lines 479-483)
resource_group, workspace_name = extract_workspace_details(request.workspace_id)
```

**Existing Utility:**
```python
# backend/src/utils/azure_utils.py (lines 34-45)
def extract_workspace_details(workspace_id: str) -> Tuple[str, str]:
    """Extract resource group and workspace name from workspace ID."""
    parsed = parse_azure_resource_id(workspace_id)
    return parsed["resource_group"], parsed["resource_name"]
```

**Status:** ✅ ALREADY USING UTILITY (No issue detected)
**Note:** The diff correctly imports and uses the existing utility. This is a positive example of code reuse.

---

### 2. MISSING IMPORT: Progress Stream Utilities - MEDIUM CONFIDENCE
**Location:** `backend/src/api/routes.py` lines 623-633
**Issue:** The SSE progress streaming logic duplicates error checking patterns found elsewhere in the codebase without centralizing error handling.

**Problematic Code:**
```python
# backend/src/api/routes.py (lines 637-642)
if not job_record:
    logger.error(f"[AUDIT] Job disappeared during stream: {job_id}")
    yield f"data: {json.dumps({'error': 'Job disappeared'})}\n\n"
    break
```

**Recommendation:** Create a utility function for SSE error emission:
```python
def emit_sse_error(job_id: str, error_msg: str, logger: logging.Logger) -> str:
    """Format and emit SSE error event"""
    logger.error(f"[AUDIT] {error_msg}: {job_id}")
    return f"data: {json.dumps({'error': error_msg})}\n\n"
```

**Suggested File:** `backend/src/utils/sse_utils.py`
**Confidence:** Medium
**Impact:** Reduces duplication of error handling in SSE streams

---

### 3. INLINE LOGIC: Progress Percentage Calculation - MEDIUM CONFIDENCE
**Location:** `backend/src/agents/orchestrator.py` lines 56-56
**Issue:** Progress percentage calculation is inline but appears in multiple places throughout the diff.

**Problematic Code:**
```python
# backend/src/agents/orchestrator.py (line 56)
progress_percent = int((current_step / total_steps) * 100)

# backend/src/api/routes.py (line 653)
'progress_percent': 100 if job_record.status == JobStatus.COMPLETED else -1,
```

**Recommendation:** Create utility function:
```python
def calculate_progress_percentage(current: int, total: int) -> int:
    """Calculate progress percentage with bounds checking"""
    if total <= 0:
        return 0
    return min(100, max(0, int((current / total) * 100)))
```

**Suggested File:** `backend/src/utils/progress_utils.py`
**Confidence:** Medium
**Impact:** Ensures consistent progress calculation across codebase

---

### 4. DUPLICATED ERROR HANDLING PATTERN - MEDIUM CONFIDENCE
**Location:** `backend/src/agents/orchestrator.py` lines 148-161
**Issue:** Exception checking pattern `isinstance(result, Exception)` is repeated multiple times for handling asyncio.gather results.

**Problematic Code:**
```python
# backend/src/agents/orchestrator.py (lines 148-154)
tables = results[0] if not isinstance(results[0], Exception) else []
ingestion_data = results[1] if not isinstance(results[1], Exception) else {}
rules = results[2] if not isinstance(results[2], Exception) else []
workbooks = results[3] if not isinstance(results[3], Exception) else []
hunt_queries = results[4] if not isinstance(results[4], Exception) else []
connectors = results[5] if not isinstance(results[5], Exception) else []

# backend/src/agents/orchestrator.py (lines 156-161)
for idx, result in enumerate(results):
    if isinstance(result, Exception):
        # Log error...
```

**Recommendation:** Create utility helper:
```python
def extract_result_or_default(result, default_value):
    """Extract result from asyncio.gather, returning default if Exception"""
    return result if not isinstance(result, Exception) else default_value

def get_exception_from_results(results, indices):
    """Extract exceptions and their indices from gather results"""
    exceptions = {}
    for idx in indices:
        if idx < len(results) and isinstance(results[idx], Exception):
            exceptions[idx] = results[idx]
    return exceptions
```

**Suggested File:** `backend/src/utils/async_utils.py`
**Confidence:** Medium
**Impact:** Eliminates 6+ lines of boilerplate per gather operation

---

### 5. DUPLICATE MOCK TOKEN LOGIC - HIGH CONFIDENCE
**Location:** `backend/src/api/auth.py` lines 307-316
**Issue:** Mock token validation is hardcoded inline, but similar patterns likely exist elsewhere (frontend has mock auth removal).

**Problematic Code:**
```python
# backend/src/api/auth.py (lines 307-316)
if settings.ENVIRONMENT == "dev" and token.startswith("mock-test-token-"):
    logger.info(f"[AUTH] Using mock token (dev mode only)")
    return {
        "oid": "mock-user-id",
        "upn": "test@example.com",
        "name": "Test User",
        "tid": settings.AZURE_TENANT_ID,
        "groups": []
    }
```

**Recommendation:** Create centralized dev/test utilities:
```python
# backend/src/utils/dev_utils.py
def is_mock_token(token: str, env: str) -> bool:
    """Check if token is a mock token (dev mode only)"""
    return env == "dev" and token.startswith("mock-test-token-")

def create_mock_user_claims(tenant_id: str) -> dict:
    """Create mock user claims for testing"""
    return {
        "oid": "mock-user-id",
        "upn": "test@example.com",
        "name": "Test User",
        "tid": tenant_id,
        "groups": []
    }
```

**Suggested File:** `backend/src/utils/dev_utils.py`
**Confidence:** High
**Impact:** Makes dev/test logic reusable and testable

---

### 6. TYPE SAFETY ISSUE: Missing Type Guard - MEDIUM CONFIDENCE
**Location:** `backend/src/agents/orchestrator.py` lines 177-182 and 251-252
**Issue:** Repeated isinstance checks for dict/list type validation without centralized type guards.

**Problematic Code:**
```python
# backend/src/agents/orchestrator.py (lines 177-182)
tables_count = len(tables) if isinstance(tables, list) else 0
rules_count = len(rules) if isinstance(rules, list) else 0
workbooks_count = len(workbooks) if isinstance(workbooks, list) else 0
hunt_queries_count = len(hunt_queries) if isinstance(hunt_queries, list) else 0
connectors_count = len(connectors) if isinstance(connectors, list) else 0

# backend/src/agents/orchestrator.py (line 251-252)
if not isinstance(ingestion_data, dict):
    ingestion_data = {}
```

**Recommendation:** Create type guard utilities:
```python
# backend/src/utils/type_guards.py
def safe_len(obj, default_type=list) -> int:
    """Safely get length with type checking"""
    expected_type = list if default_type == list else dict
    return len(obj) if isinstance(obj, expected_type) else 0

def ensure_dict(obj, default=None) -> dict:
    """Ensure object is dict, return default if not"""
    return obj if isinstance(obj, dict) else (default or {})

def ensure_list(obj, default=None) -> list:
    """Ensure object is list, return default if not"""
    return obj if isinstance(obj, list) else (default or [])
```

**Suggested File:** `backend/src/utils/type_guards.py`
**Confidence:** Medium
**Impact:** Improves robustness and reduces repetitive type checking

---

### 7. LOGGING PATTERN DUPLICATION - LOW CONFIDENCE
**Location:** `backend/src/api/routes.py` lines 375-379, 401-406, 432-435 (and more)
**Issue:** Long formatted log messages with consistent prefixes `[ORCHESTRATOR]`, `[AUDIT]` are repeated instead of using a structured logging utility.

**Problematic Code:**
```python
# backend/src/api/routes.py (lines 375-379)
logger.info(
    f"[ORCHESTRATOR] Starting background execution: job_id={job_id} "
    f"workspace={workspace_name} "
    f"user={user_principal}"
)

# backend/src/api/routes.py (lines 386-390)
logger.info(
    f"[ORCHESTRATOR] Triggering agent orchestrator execution "
    f"(workspace={workspace_name}, resource_group={resource_group}, "
    f"days_lookback={days_lookback})"
)
```

**Note:** `AuditLogger` class already exists in `backend/src/utils/logging.py` but isn't being leveraged here. This is a minor pattern issue rather than code duplication.

**Recommendation:** Consider extending `AuditLogger` with orchestrator-specific methods:
```python
class AuditLogger:
    # ... existing code ...

    @staticmethod
    def log_orchestrator_event(event_type: str, **kwargs):
        """Log orchestrator-specific events with consistent formatting"""
        # Format kwargs into consistent message
```

**Confidence:** Low
**Impact:** Improves maintainability of logging

---

### 8. ASYNC PATTERN: Unused SSE Helper Methods - MEDIUM CONFIDENCE
**Location:** `backend/src/api/routes.py` lines 598-673
**Issue:** The SSE event generation and polling logic is hardcoded inline in the route, but could be abstracted into reusable service methods.

**Problematic Code:**
```python
# backend/src/api/routes.py (lines 621-673) - Complex polling logic
while True:
    all_updates = await job_storage.get_progress_updates(job_id)

    if len(all_updates) > sent_updates:
        for update in all_updates[sent_updates:]:
            # ... format and yield ...

    job_record = await job_storage.get_job(job_id)
    if not job_record:
        # ... error handling ...

    if job_record.status in [...]:
        # ... completion handling ...

    consecutive_empty_polls += 1
    if consecutive_empty_polls > max_empty_polls:
        # ... timeout handling ...

    await asyncio.sleep(1)
```

**Recommendation:** Create service abstraction:
```python
# backend/src/services/sse_service.py
class SSEProgressStreamer:
    async def stream_progress(
        self,
        job_id: str,
        max_wait_seconds: int = 60
    ) -> AsyncGenerator[str, None]:
        """Stream progress updates until completion"""
        # Encapsulate the polling logic
```

**Suggested File:** `backend/src/services/sse_service.py`
**Confidence:** Medium
**Impact:** Improves testability and reusability of streaming logic

---

## Summary of Recommendations

| Category | Count | Priority |
|----------|-------|----------|
| New utilities to create | 5 | Medium |
| Existing utilities being used correctly | 1 | N/A |
| Type safety improvements needed | 1 | Medium |
| Logging pattern refinement | 1 | Low |

### New Files Recommended to Create:
1. **`backend/src/utils/async_utils.py`** - Async/gather utilities
2. **`backend/src/utils/type_guards.py`** - Type safety helpers
3. **`backend/src/utils/sse_utils.py`** - SSE-specific utilities
4. **`backend/src/services/sse_service.py`** - SSE streaming service
5. **`backend/src/utils/dev_utils.py`** - Dev/test utilities

### Existing Files to Extend:
- `backend/src/utils/logging.py` - Add orchestrator logging methods
- `backend/src/utils/progress_utils.py` - Create for progress calculations

---

## Severity and Impact Analysis

### High Priority (3)
1. **Extract Workspace Details** - Already correctly using utility ✅
2. **Mock Token Logic** - Should be centralized
3. **Async Exception Handling** - Currently scattered across orchestrator

### Medium Priority (4)
1. **SSE Error Handling** - Repeated error patterns
2. **Progress Calculations** - Inline math repeated
3. **Type Guards** - Missing validation helpers
4. **SSE Streaming Logic** - Complex logic not abstracted

### Low Priority (1)
1. **Logging Patterns** - Minor consistency issue

---

## Conclusion

The diff demonstrates **good use of existing utilities** (e.g., `extract_workspace_details`), but introduces **several new opportunities for code reuse abstraction**, particularly around:
- Async result handling patterns
- Type validation guards
- SSE streaming utilities
- Dev/test mock utilities

Creating 2-3 new utility modules would significantly reduce code duplication and improve maintainability in this diff.
