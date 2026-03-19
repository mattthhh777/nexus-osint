# NexusOSINT app.py Fix Plan - Progress Tracker

## Status: ✅ Plan Approved | 🚀 Implementation Started

### Breakdown of Approved Plan (Logical Steps):

#### 1. **Fix Imports & Syntax** ✅ **DONE**
   - Added `Optional`, `run_search` imports  
   - Added `pd/json/re` globals  
   - Added `_inject_css()` function  
   - Removed unused session_state keys

#### 2. **Fix _execute_search()** [PENDING]
   - Use `validate_query(raw_query)` → `.cleaned`/`.query_type`
   - Config: `SearchConfig.auto(q_type)` or manual
   - Quota: `guardian.can_run(config)` / `estimate_cost(config)`
   - Cache call already correct

#### 3. **Fix _fallback_search()** [PENDING]
   - Inline import `run_search`

#### 4. **Fix _render_results()** [PENDING]
   - Safe None-checks for `oath`, `sherl`, `extra`
   - Fix JSON export with `results.__dict__`
   - Pagination state

#### 5. **Fix _render_extras()** [PENDING]
   - Match oathnet_client extras structure

#### 6. **Cleanup** [PENDING]
   - Remove unused session_state keys
   - Minor param fixes

#### 7. **Test** [PENDING]
   - `streamlit run app.py`
   - Verify search/quota/exports

**Next Step:** Fix _fallback_search() + test search logic (Step 2-3)  

**Completed:** 1/7 | Est. Time left: 15 min
