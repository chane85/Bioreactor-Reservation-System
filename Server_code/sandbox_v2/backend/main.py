"""
FastAPI backend for the Bioreactor Sandbox (drag-and-drop simulation).

Single-user design: one lock gates all sandbox entry.
Sandbox state lives entirely in process memory — no DB, no file persistence.
Apply is the only operation that writes to disk.

Run:
    uvicorn main:app --reload --port 8561
"""

from __future__ import annotations

import base64
import datetime
import os
import threading
import time
import uuid
from typing import Optional

import pandas as pd
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, model_validator

import utils
import auth_utils

_BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
_DIST_DIR = os.path.normpath(os.path.join(_BACKEND_DIR, "..", "frontend", "dist"))

# ---------------------------------------------------------------------------
# App + CORS
# ---------------------------------------------------------------------------
app = FastAPI(title="Bioreactor Sandbox API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*", "Authorization"],
)
# ---------------------------------------------------------------------------
# In-memory singleton state
# ---------------------------------------------------------------------------
LOCK_TIMEOUT_MINUTES = 30  # auto-release after N minutes of inactivity

class _State:
    lock: Optional[dict] = None           # {user, acquired_at, last_activity}
    sandbox_df: Optional[pd.DataFrame] = None
    snapshot_df: Optional[pd.DataFrame] = None  # live data at lock acquisition time

_s = _State()
_state_lock = threading.Lock()  # guards all mutations of _s

# Rate-limit tracking for /api/sandbox/apply: ip -> [unix timestamps of failures]
_apply_failures: dict[str, list] = {}
_apply_failures_lock = threading.Lock()
_APPLY_MAX_ATTEMPTS  = 5
_APPLY_LOCKOUT_SECS  = 300  # 5 minutes


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------
def _new_booking_id() -> str:
    return f"DRAG_{uuid.uuid4().hex[:12]}"


def _check_and_release_expired_lock():
    with _state_lock:
        if _s.lock is None:
            return
        elapsed = (datetime.datetime.now() - _s.lock["last_activity"]).total_seconds()
        if elapsed > LOCK_TIMEOUT_MINUTES * 60:
            _s.lock = _s.sandbox_df = _s.snapshot_df = None


def _release_lock():
    with _state_lock:
        _s.lock = _s.sandbox_df = _s.snapshot_df = None


def _touch_lock():
    with _state_lock:
        if _s.lock:
            _s.lock["last_activity"] = datetime.datetime.now()


def _check_apply_rate_limit(ip: str):
    now = time.time()
    with _apply_failures_lock:
        recent = [t for t in _apply_failures.get(ip, []) if now - t < _APPLY_LOCKOUT_SECS]
        _apply_failures[ip] = recent
        if len(recent) >= _APPLY_MAX_ATTEMPTS:
            wait = int(_APPLY_LOCKOUT_SECS - (now - recent[0]))
            raise HTTPException(status_code=429, detail=f"Too many failed attempts. Try again in {wait}s.")


def _record_apply_failure(ip: str):
    with _apply_failures_lock:
        _apply_failures.setdefault(ip, []).append(time.time())


def _clear_apply_failures(ip: str):
    with _apply_failures_lock:
        _apply_failures.pop(ip, None)


def _df_to_records(df: pd.DataFrame) -> list:
    if df is None or df.empty:
        return []
    out = df.copy()
    for col in ("start", "end"):
        if col in out.columns:
            out[col] = pd.to_datetime(out[col], errors="coerce").dt.strftime("%Y-%m-%d")
    out = out.where(pd.notna(out), None)
    return out.to_dict("records")


def _new_booking_id() -> str:
    return f"DRAG_{uuid.uuid4().hex[:12]}"


def _lock_info() -> Optional[dict]:
    if _s.lock is None:
        return None
    return {
        "user":         _s.lock["user"],
        "acquired_at":  _s.lock["acquired_at"].isoformat(),
        "last_activity": _s.lock["last_activity"].isoformat(),
        "expires_in_seconds": max(
            0,
            int(LOCK_TIMEOUT_MINUTES * 60 - (datetime.datetime.now() - _s.lock["last_activity"]).total_seconds())
        ),
    }


# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------
class LockRequest(BaseModel):
    user: str

class MoveRequest(BaseModel):
    user: str
    booking_id: str
    new_reactor_id: str
    new_start: str   # YYYY-MM-DD
    new_end: str     # YYYY-MM-DD

class DeleteRequest(BaseModel):
    user: str
    booking_id: str

class ApplyRequest(BaseModel):
    user: str  # sandbox lock holder

class UnlockRequest(BaseModel):
    user: str

class FindAvailableRequest(BaseModel):
    scale: str
    start_date: str   # YYYY-MM-DD
    days: int
    stage: str = "N"
    method: str = "Fed-batch"

    @model_validator(mode='after')
    def check_days(self):
        if self.days <= 0:
            raise ValueError('days must be a positive integer')
        return self

class AddBookingRequest(BaseModel):
    user: str
    reactor_ids: list
    project: str
    stage: str
    method: str
    start_date: str
    end_date: str

    @model_validator(mode='after')
    def check_dates(self):
        if self.start_date >= self.end_date:
            raise ValueError('end_date must be after start_date')
        return self


_API_VERSION = 10  # bump this any time new endpoints are added

# ---------------------------------------------------------------------------
# GET /api/version  — used by _sandbox_server.py to detect stale backends
# ---------------------------------------------------------------------------
@app.get("/api/version")
def get_version():
    return {"version": _API_VERSION}


@app.get("/api/inventory/eq-map")
def get_eq_map():
    return utils.REACTOR_EQ_MAP


# ---------------------------------------------------------------------------
# GET /api/schedule
# ---------------------------------------------------------------------------
@app.get("/api/schedule")
def get_schedule():
    """Return live bookings, full reactor inventory, and current lock status."""
    _check_and_release_expired_lock()
    live = utils.load_data()
    inv  = utils.generate_inventory()
    return {
        "bookings":  _df_to_records(live),
        "reactors":  inv.to_dict("records"),
        "colors":    {"bg": utils.PROJECT_BG_MAP, "font": utils.PROJECT_FONT_MAP},
        "lock":      _lock_info(),
    }


# ---------------------------------------------------------------------------
# POST /api/sandbox/lock  — claim the single-user lock
# ---------------------------------------------------------------------------
@app.post("/api/sandbox/lock")
def claim_lock(req: LockRequest):
    _check_and_release_expired_lock()

    if _s.lock is not None:
        raise HTTPException(
            status_code=423,
            detail={
                "message": f"Sandbox is in use by {_s.lock['user']}",
                "lock": _lock_info(),
            },
        )

    now = datetime.datetime.now()
    _s.lock = {"user": req.user, "acquired_at": now, "last_activity": now}

    live          = utils.load_data()
    _s.sandbox_df = live.copy()
    _s.snapshot_df = live.copy()

    return {
        "status":   "acquired",
        "lock":     _lock_info(),
        "bookings": _df_to_records(_s.sandbox_df),
    }


# ---------------------------------------------------------------------------
# DELETE /api/sandbox/lock  — explicit exit (releases without applying)
# ---------------------------------------------------------------------------
@app.delete("/api/sandbox/lock")
def release_lock(user: str):
    _check_and_release_expired_lock()

    if _s.lock is None:
        return {"status": "released"}

    if _s.lock["user"] != user:
        raise HTTPException(status_code=403, detail="Lock is held by a different user")

    _release_lock()
    return {"status": "released"}


# ---------------------------------------------------------------------------
# GET /api/sandbox/bookings  — current sandbox state
# ---------------------------------------------------------------------------
@app.get("/api/sandbox/bookings")
def get_sandbox_bookings():
    _check_and_release_expired_lock()

    if _s.lock is None or _s.sandbox_df is None:
        raise HTTPException(status_code=423, detail="No active sandbox lock")

    return {
        "bookings": _df_to_records(_s.sandbox_df),
        "lock":     _lock_info(),
    }


# ---------------------------------------------------------------------------
# POST /api/sandbox/move
# ---------------------------------------------------------------------------
@app.post("/api/sandbox/move")
def move_booking(req: MoveRequest):
    _check_and_release_expired_lock()

    if _s.lock is None:
        raise HTTPException(status_code=423, detail="No active sandbox lock")
    if _s.lock["user"] != req.user:
        raise HTTPException(status_code=403, detail="Lock held by a different user")

    # Find the booking
    mask = _s.sandbox_df["booking_id"].astype(str) == req.booking_id
    if not mask.any():
        raise HTTPException(status_code=404, detail=f"Booking {req.booking_id} not found in sandbox")

    row = _s.sandbox_df[mask].iloc[0].to_dict()

    # Remove original
    _s.sandbox_df = _s.sandbox_df[~mask].copy()

    # Add moved version with a new ID (so diff tracks it as removed+added)
    new_row = {
        **row,
        "booking_id": _new_booking_id(),
        "reactor_id": req.new_reactor_id,
        "start":      pd.to_datetime(req.new_start),
        "end":        pd.to_datetime(req.new_end),
    }
    _s.sandbox_df = pd.concat(
        [_s.sandbox_df, pd.DataFrame([new_row])],
        ignore_index=True,
    )

    _touch_lock()
    return {
        "status":         "moved",
        "new_booking_id": new_row["booking_id"],
        "bookings":       _df_to_records(_s.sandbox_df),
    }


# ---------------------------------------------------------------------------
# POST /api/sandbox/delete
# ---------------------------------------------------------------------------
@app.post("/api/sandbox/delete")
def delete_booking(req: DeleteRequest):
    _check_and_release_expired_lock()

    if _s.lock is None:
        raise HTTPException(status_code=423, detail="No active sandbox lock")
    if _s.lock["user"] != req.user:
        raise HTTPException(status_code=403, detail="Lock held by a different user")

    mask = _s.sandbox_df["booking_id"].astype(str) == req.booking_id
    if not mask.any():
        raise HTTPException(status_code=404, detail=f"Booking {req.booking_id} not found in sandbox")

    _s.sandbox_df = _s.sandbox_df[~mask].copy()

    _touch_lock()
    return {
        "status":   "deleted",
        "bookings": _df_to_records(_s.sandbox_df),
    }


# ---------------------------------------------------------------------------
# POST /admin/shutdown  — called by _sandbox_server.py on next Streamlit start
# ---------------------------------------------------------------------------
@app.post("/admin/shutdown")
def admin_shutdown():
    import threading
    threading.Thread(target=lambda: os._exit(0), daemon=True).start()
    return {"status": "shutting down"}


# ---------------------------------------------------------------------------
# POST /api/sandbox/unlock  — beacon-safe release (used by beforeunload)
# ---------------------------------------------------------------------------
@app.post("/api/sandbox/unlock")
def unlock_sandbox(req: UnlockRequest):
    _check_and_release_expired_lock()
    if _s.lock and _s.lock["user"] == req.user:
        _release_lock()
    return {"status": "released"}


# ---------------------------------------------------------------------------
# GET /api/sandbox/diff
# ---------------------------------------------------------------------------
@app.get("/api/sandbox/diff")
def get_diff():
    _check_and_release_expired_lock()

    if _s.lock is None:
        raise HTTPException(status_code=423, detail="No active sandbox lock")

    snapshot_ids = set(_s.snapshot_df["booking_id"].astype(str)) if _s.snapshot_df is not None and not _s.snapshot_df.empty else set()
    sandbox_ids  = set(_s.sandbox_df["booking_id"].astype(str))  if _s.sandbox_df  is not None and not _s.sandbox_df.empty  else set()

    added_ids   = sandbox_ids  - snapshot_ids
    removed_ids = snapshot_ids - sandbox_ids

    def _rows(df, ids):
        if not ids or df is None or df.empty:
            return []
        sub = df[df["booking_id"].astype(str).isin(ids)].copy()
        sub["start"] = pd.to_datetime(sub["start"], errors="coerce").dt.strftime("%Y-%m-%d")
        sub["end"]   = pd.to_datetime(sub["end"],   errors="coerce").dt.strftime("%Y-%m-%d")
        return sub.where(pd.notna(sub), None).to_dict("records")

    return {
        "added":   _rows(_s.sandbox_df,  added_ids),
        "removed": _rows(_s.snapshot_df, removed_ids),
    }


# ---------------------------------------------------------------------------
# POST /api/sandbox/apply
# ---------------------------------------------------------------------------
@app.post("/api/sandbox/apply")
def apply_sandbox(req: ApplyRequest, request: Request):
    ip = request.client.host if request.client else "unknown"
    _check_apply_rate_limit(ip)
    _check_and_release_expired_lock()

    if _s.lock is None:
        raise HTTPException(status_code=423, detail="No active sandbox lock")
    if _s.lock["user"] != req.user:
        raise HTTPException(status_code=403, detail="Lock held by a different user")

    # Parse Basic auth credentials from Authorization header
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Basic "):
        _record_apply_failure(ip)
        raise HTTPException(status_code=401, detail="Authorization header required (Basic)")
    try:
        decoded = base64.b64decode(auth_header[6:]).decode("utf-8")
        admin_user, admin_password = decoded.split(":", 1)
    except Exception:
        _record_apply_failure(ip)
        raise HTTPException(status_code=401, detail="Malformed Authorization header")

    user_data = auth_utils.get_user(admin_user)
    if not user_data or not auth_utils.verify_password(admin_password, user_data.get("password", "")):
        _record_apply_failure(ip)
        raise HTTPException(status_code=401, detail="Invalid credentials")
    _clear_apply_failures(ip)
    allowed_roles = {"admin", "editor"}
    if not allowed_roles.intersection(user_data.get("roles", [])):
        raise HTTPException(status_code=403, detail="Editor or Admin role required to apply")

    # Load fresh live data
    fresh_live = utils.load_data()

    # Compute what the user intended to change (diff vs original snapshot, not fresh live)
    snapshot_ids  = set(_s.snapshot_df["booking_id"].astype(str)) if _s.snapshot_df is not None and not _s.snapshot_df.empty else set()
    sandbox_ids   = set(_s.sandbox_df["booking_id"].astype(str))  if _s.sandbox_df  is not None and not _s.sandbox_df.empty  else set()
    fresh_live_ids = set(fresh_live["booking_id"].astype(str))    if not fresh_live.empty else set()

    user_added_ids   = sandbox_ids  - snapshot_ids   # user created/moved these
    user_removed_ids = snapshot_ids - sandbox_ids    # user deleted/moved-away these

    # Conflict check: test each user-added booking against fresh live (minus what user removed)
    temp_live = fresh_live[~fresh_live["booking_id"].astype(str).isin(user_removed_ids)]
    conflicts = []

    if user_added_ids and _s.sandbox_df is not None and not _s.sandbox_df.empty:
        added_rows = _s.sandbox_df[_s.sandbox_df["booking_id"].astype(str).isin(user_added_ids)]
        for _, row in added_rows.iterrows():
            # Exclude this specific booking from the check temp (defensive — shouldn't be in live)
            check_temp = temp_live[temp_live["booking_id"].astype(str) != str(row["booking_id"])]
            available = utils.check_availability(
                str(row["reactor_id"]), row["start"], row["end"], check_temp
            )
            if not available:
                conflicts.append({
                    "booking_id": str(row["booking_id"]),
                    "reactor_id": str(row["reactor_id"]),
                    "start":      str(row["start"])[:10],
                    "end":        str(row["end"])[:10],
                    "message":    (
                        f"{row['reactor_id']} is no longer available "
                        f"{str(row['start'])[:10]} ~ {str(row['end'])[:10]}"
                    ),
                })

    if conflicts:
        raise HTTPException(
            status_code=409,
            detail={"message": "Conflicts detected — not applied", "conflicts": conflicts},
        )

    # No conflicts — write to disk
    # Pass snapshot as real_df so diff = exactly what the user changed
    utils.create_backup()
    filename = utils.save_simulation(
        sandbox_df=_s.sandbox_df,
        real_df=_s.snapshot_df,
        submitted_by=admin_user,
    )
    n_added, n_removed = utils.apply_simulation_diff(filename=filename, actioned_by=req.user)
    utils.log_audit(
        action="applied",
        filename=filename,
        submitted_by=admin_user,
        actioned_by=req.user,
    )

    _release_lock()

    return {
        "status":    "applied",
        "n_added":   n_added,
        "n_removed": n_removed,
        "filename":  filename,
    }


# ---------------------------------------------------------------------------
# POST /api/sandbox/find-available  — find free reactors for a date window
# ---------------------------------------------------------------------------
@app.post("/api/sandbox/find-available")
def find_available(req: FindAvailableRequest):
    _check_and_release_expired_lock()

    try:
        start_dt = datetime.date.fromisoformat(req.start_date)
        end_dt   = start_dt + datetime.timedelta(days=req.days)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid start_date format (use YYYY-MM-DD)")

    end_date = end_dt.isoformat()

    # Use sandbox state if active, otherwise live data
    if _s.lock and _s.sandbox_df is not None:
        ref_df = _s.sandbox_df
    else:
        ref_df = utils.load_data()

    inv      = utils.generate_inventory()
    reactors = inv[inv["scale"] == req.scale]["id"].tolist()

    available = [r for r in reactors
                 if utils.check_availability(r, req.start_date, end_date, ref_df)]

    return {
        "available": available,
        "start":     req.start_date,
        "end":       end_date,
        "days":      req.days,
    }


# ---------------------------------------------------------------------------
# POST /api/sandbox/add  — add new booking(s) to sandbox
# ---------------------------------------------------------------------------
@app.post("/api/sandbox/add")
def add_booking(req: AddBookingRequest):
    _check_and_release_expired_lock()

    if _s.lock is None:
        raise HTTPException(status_code=423, detail="No active sandbox lock")
    if _s.lock["user"] != req.user:
        raise HTTPException(status_code=403, detail="Lock held by a different user")

    conflicts = []
    new_rows  = []
    for r_id in req.reactor_ids:
        if not utils.check_availability(r_id, req.start_date, req.end_date, _s.sandbox_df):
            conflicts.append(r_id)
        else:
            new_rows.append({
                "booking_id": _new_booking_id(),
                "reactor_id": r_id,
                "user":       req.user,
                "start":      pd.to_datetime(req.start_date),
                "end":        pd.to_datetime(req.end_date),
                "project":    req.project,
                "stage":      req.stage,
                "method":     req.method,
            })

    if conflicts:
        raise HTTPException(
            status_code=409,
            detail={"message": f"{', '.join(conflicts)} 에 충돌이 있습니다", "conflicts": conflicts},
        )

    _s.sandbox_df = pd.concat([_s.sandbox_df, pd.DataFrame(new_rows)], ignore_index=True)
    _touch_lock()

    return {
        "status":   "added",
        "n_added":  len(new_rows),
        "bookings": _df_to_records(_s.sandbox_df),
    }


# ---------------------------------------------------------------------------
# Static files — serve built React app (must be registered AFTER all API routes)
# ---------------------------------------------------------------------------
if os.path.isdir(_DIST_DIR):
    _assets = os.path.join(_DIST_DIR, "assets")
    if os.path.isdir(_assets):
        app.mount("/assets", StaticFiles(directory=_assets), name="assets")

    _NO_CACHE = {"Cache-Control": "no-store, no-cache, must-revalidate"}

    @app.get("/")
    def serve_root():
        return FileResponse(os.path.join(_DIST_DIR, "index.html"), headers=_NO_CACHE)

    @app.get("/{full_path:path}")
    def serve_react(full_path: str):
        return FileResponse(os.path.join(_DIST_DIR, "index.html"), headers=_NO_CACHE)
