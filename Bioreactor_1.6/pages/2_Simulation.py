import streamlit as st
import pandas as pd
import datetime
import utils
import auth
import re

st.set_page_config(page_title="Tetris", layout="wide")

# Auth: editor or admin role required
auth.init_auth()
auth.require_role('viewer')

# =============================================================
# INITIALIZATION
# =============================================================
if 'inventory' not in st.session_state:
    st.session_state.inventory = utils.generate_inventory()
if 'bookings' not in st.session_state:
    st.session_state.bookings = utils.load_data()

# Sandbox: working copy of real bookings. All edits happen here.
if 'sandbox_bookings' not in st.session_state:
    st.session_state.sandbox_bookings = st.session_state.bookings.copy()

# Undo stack: list of {"label": str, "state": DataFrame}
if 'sandbox_undo_stack' not in st.session_state:
    st.session_state.sandbox_undo_stack = []

# Diff cache: recomputed only after confirmed mutations, not on every render
if 'sandbox_diff_cache' not in st.session_state:
    st.session_state.sandbox_diff_cache = None

# Gantt cache: recomputed only when user clicks Refresh
if 'sandbox_gantt_fig' not in st.session_state:
    st.session_state.sandbox_gantt_fig = None

MAX_UNDO = 10


def today():
    """Always returns the current date. Avoids stale value if session runs overnight."""
    return datetime.date.today()


# =============================================================
# HELPERS — Undo stack
# =============================================================
def push_undo(label: str):
    """
    Snapshot sandbox before a mutation.
    Stores {label, state} so the user can select which step to revert to.
    """
    st.session_state.sandbox_undo_stack.append({
        "label": label,
        "state": st.session_state.sandbox_bookings.copy(deep=True)
    })
    if len(st.session_state.sandbox_undo_stack) > MAX_UNDO:
        st.session_state.sandbox_undo_stack.pop(0)


def invalidate_diff():
    """Mark diff cache as stale after a mutation. Recomputed lazily below."""
    st.session_state.sandbox_diff_cache = None


def invalidate_gantt():
    """Clear cached Gantt so user knows it needs a refresh."""
    st.session_state.sandbox_gantt_fig = None


def get_diff():
    """
    Return cached diff rows. Recomputes only if cache is None (stale).
    This avoids re-iterating all bookings on every widget interaction.
    """
    if st.session_state.sandbox_diff_cache is None:
        st.session_state.sandbox_diff_cache = _compute_diff(
            st.session_state.bookings,
            st.session_state.sandbox_bookings
        )
    return st.session_state.sandbox_diff_cache


def _compute_diff(real_df, sandbox_df):
    real_ids = set(real_df['booking_id'].astype(str)) if not real_df.empty else set()
    sandbox_ids = set(sandbox_df['booking_id'].astype(str)) if not sandbox_df.empty else set()
    added_ids = sandbox_ids - real_ids
    removed_ids = real_ids - sandbox_ids
    rows = []
    if added_ids and not sandbox_df.empty:
        adf = sandbox_df[sandbox_df['booking_id'].astype(str).isin(added_ids)].copy()
        adf['start'] = pd.to_datetime(adf['start']).dt.strftime('%Y-%m-%d')
        adf['end'] = pd.to_datetime(adf['end']).dt.strftime('%Y-%m-%d')
        for _, r in adf.iterrows():
            rows.append({'Action': '➕ Added', 'reactor_id': r['reactor_id'],
                         'project': r['project'], 'start': r['start'], 'end': r['end'],
                         'stage': r.get('stage',''), 'method': r.get('method','')})
    if removed_ids and not real_df.empty:
        rdf = real_df[real_df['booking_id'].astype(str).isin(removed_ids)].copy()
        rdf['start'] = pd.to_datetime(rdf['start']).dt.strftime('%Y-%m-%d')
        rdf['end'] = pd.to_datetime(rdf['end']).dt.strftime('%Y-%m-%d')
        for _, r in rdf.iterrows():
            rows.append({'Action': '➖ Removed', 'reactor_id': r['reactor_id'],
                         'project': r['project'], 'start': r['start'], 'end': r['end'],
                         'stage': r.get('stage',''), 'method': r.get('method','')})
    return rows


# =============================================================
# HELPERS — Booking filters
# =============================================================
def fmt_rid(x):
    return x.replace("6층-", "").replace("5층-", "[5층] ").replace("7층-", "[7층] ")


def build_booking_labels(bookings_df, project_filter=None, date_filter=None, exact_start=False):
    """
    Build label→id map.
    - Restricts to start >= today() (eligible for editing).
    - exact_start=False → date_filter matches bookings active on that date (overlap).
    - exact_start=True → date_filter matches bookings starting exactly on that date.
    """
    df_b = bookings_df.copy()
    df_b['start'] = pd.to_datetime(df_b['start'])
    df_b['end'] = pd.to_datetime(df_b['end'])
    df_b = df_b[df_b['start'].dt.date >= today()].reset_index(drop=True)

    if project_filter and project_filter != "All":
        df_b = df_b[df_b['project'] == project_filter]
    if date_filter:
        fdt = pd.to_datetime(date_filter)
        if exact_start:
            df_b = df_b[df_b['start'].dt.date == fdt.date()]
        else:
            df_b = df_b[(df_b['start'] <= fdt) & (df_b['end'] >= fdt)]

    df_b['_label'] = df_b['reactor_id'] + " | " + df_b['project'].astype(str)
    seen, unique_labels = {}, []
    for lbl in df_b['_label']:
        if lbl in seen:
            seen[lbl] += 1
            unique_labels.append(f"{lbl} ({seen[lbl]})")
        else:
            seen[lbl] = 0
            unique_labels.append(lbl)
    df_b['_label'] = unique_labels
    return df_b['_label'].tolist(), dict(zip(df_b['_label'], df_b['booking_id']))


def get_active_df():
    """Sandbox bookings with start >= today(). Computed once per section."""
    df = st.session_state.sandbox_bookings.copy()
    df['start'] = pd.to_datetime(df['start'])
    df['end'] = pd.to_datetime(df['end'])
    return df[df['start'].dt.date >= today()]


def projects_starting_on(date_val):
    """Return sorted project list where start == date_val exactly."""
    df = st.session_state.sandbox_bookings.copy()
    df['start'] = pd.to_datetime(df['start'])
    matched = df[df['start'].dt.date == date_val]
    return sorted(matched['project'].astype(str).unique().tolist())


# =============================================================
# CSS (matches other pages)
# =============================================================
st.markdown("""
    <style>
    div[data-testid="stTextInput"] input,
    div[data-testid="stDateInput"] input,
    div[data-testid="stNumberInput"] input { text-align: center !important; border-radius: 4px; }
    div[data-testid="stSelectbox"] div[data-baseweb="select"] { border-radius: 4px; text-align: center !important; }
    div[data-testid="stSelectbox"] div[data-baseweb="select"] > div:first-child {
        display: flex !important; justify-content: center !important;
        align-items: center !important; margin: 0 auto !important; width: 100% !important; }
    div[data-testid="stSelectbox"] div[data-baseweb="select"] span,
    div[data-testid="stSelectbox"] div[data-baseweb="select"] div {
        text-align: center !important; justify-content: center !important; }
    </style>
""", unsafe_allow_html=True)

st.header("배양기 운용 현황판 시뮬레이션(a.k.a 테트리스)")
st.caption("⚠️ 모든 변경은 **Finalize & Apply**에 아이디, 비번 입력 후 적용됩니다.")


# =============================================================
# SIDEBAR — Finalize & Apply + Selectable Undo
# =============================================================
with st.sidebar:

    # ── Selectable Undo ──────────────────────────────────────
    st.header("시뮬레이션")
    
    stack = st.session_state.sandbox_undo_stack

    if not stack:
        st.caption("시뮬레이션 없음")
    else:
        # Show newest first so index 0 = most recent
        labels_newest_first = [
            f"No. {len(stack) - i}: {entry['label']}"
            for i, entry in enumerate(reversed(stack))
        ]
        selected_label = st.selectbox(
            "시뮬레이션 리스트:",
            labels_newest_first,
            key="undo_select"
        )
        st.caption("선택한 번호 이후의 모든 시뮬레이션 삭제됨.")
        if st.button("↩️ 삭제", use_container_width=True, key="undo_apply_btn"):
            # Map label back to stack index (stack is oldest-first internally)
            chosen_display_idx = labels_newest_first.index(selected_label)
            # chosen_display_idx 0 = most recent = stack[-1]
            stack_idx = len(stack) - 1 - chosen_display_idx
            st.session_state.sandbox_bookings = stack[stack_idx]['state'].copy(deep=True)
            # Discard everything after (and including) the chosen snapshot
            st.session_state.sandbox_undo_stack = stack[:stack_idx]
            invalidate_diff()
            invalidate_gantt()
            # Clear transient selection state
            for key in list(st.session_state.keys()):
                if any(key.startswith(p) for p in [
                    'move_available', 'move_ids_snap', 'move_original',
                    'move_stored', 'move_meta',
                    'swap_avail', 'swap_ids', 'swap_qty',
                    'swap_start', 'swap_end', 'swap_meta',
                    'qr_available', 'qr_end'
                ]):
                    st.session_state.pop(key, None)
            st.rerun()
    # st.markdown("#### 🔄 Reset")
    st.caption("시뮬레이션 전체 삭제")
    if st.button("🔄 Reset", use_container_width=True, key="reset_sandbox_btn"):
        st.session_state.sandbox_bookings = st.session_state.bookings.copy()
        st.session_state.sandbox_undo_stack = []
        st.session_state.sandbox_diff_cache = None
        st.session_state.sandbox_gantt_fig = None
        for key in list(st.session_state.keys()):
            if any(key.startswith(p) for p in ['move_', 'swap_', 'delete_', 'qr_']):
                st.session_state.pop(key, None)
        st.rerun()
    st.divider()
   # ── Finalize & Apply ─────────────────────────────────────
    st.header("💾 적용")
    st.caption("""아이디, 비밀번호 입력으로 현황판에 적용.  
    적용 전 **시뮬레이션 적용 현황판**에서 확인 가능.""")
    if 'sim_apply_auth' not in st.session_state:
        st.session_state.sim_apply_auth = False
    if 'sim_apply_user' not in st.session_state:
        st.session_state.sim_apply_user = ''

    if not st.session_state.sim_apply_auth:
        st.caption("🔒 아이디, 비밀번호 입력:")
        with st.form("sim_apply_auth_form"):
            apply_username = st.text_input("아이디")
            apply_pwd = st.text_input("비밀번호", type="password")
            if st.form_submit_button("🔓 입력"):
                user_data = auth.get_user(apply_username.strip())
                if (user_data
                        and auth.verify_password(apply_pwd, user_data['password'])
                        and 'admin' in user_data.get('roles', [])):
                    st.session_state.sim_apply_auth = True
                    st.session_state.sim_apply_user = apply_username.strip()
                    st.rerun()
                else:
                    st.error("❌ Invalid credentials or insufficient permissions.")
    else:
        st.success(f"🔓 Unlocked as **{st.session_state.sim_apply_user}**")
        if st.button("🔒 Lock Apply", key="sim_apply_lock_btn"):
            st.session_state.sim_apply_auth = False
            st.session_state.sim_apply_user = ''
            st.rerun()

        diff_rows = get_diff()
        n_changes = len(diff_rows)

        if n_changes == 0:
            st.info("No pending changes to apply.")
        else:
            st.warning(f"**{n_changes} pending change(s)** will be applied.")
            if st.button("🚀 Finalize & Apply", type="primary",
                         use_container_width=True, key="finalize_btn"):
                try:
                    utils.create_backup()
                    filename = utils.save_simulation(
                        sandbox_df=st.session_state.sandbox_bookings,
                        real_df=st.session_state.bookings,
                        submitted_by=st.session_state.sim_apply_user
                    )
                    n_added, n_removed = utils.apply_simulation_diff(
                        filename=filename,
                        actioned_by=st.session_state.sim_apply_user
                    )
                    utils.log_audit(
                        action='applied', filename=filename,
                        submitted_by=st.session_state.sim_apply_user,
                        actioned_by=st.session_state.sim_apply_user
                    )
                    st.session_state.bookings = utils.load_data()
                    st.session_state.sandbox_bookings = st.session_state.bookings.copy()
                    st.session_state.sandbox_undo_stack = []
                    st.session_state.sandbox_diff_cache = None
                    st.session_state.sandbox_gantt_fig = None
                    st.success(
                        f"✅ Applied: {n_added} added, {n_removed} removed. "
                        f"File: {filename}"
                    )
                    st.balloons()
                    st.rerun()
                except Exception as e:
                    st.error(f"❌ Finalize failed: {e}")
                    import traceback
                    st.code(traceback.format_exc())


# =============================================================
# TOOLBAR — change counter + Reset Sandbox
# (Undo is now in the sidebar — toolbar stays lightweight)
# =============================================================
diff_rows = get_diff() # uses cache; no recomputation unless stale
n_changes = len(diff_rows)

if n_changes == 0:
    st.info("🟢 Sandbox matches real schedule — no pending changes.")
else:
    st.warning(f"🟡 **{n_changes} change(s) pending** — use sidebar to Finalize or Undo.")

if n_changes > 0:
    with st.expander(f"📋 적용 대기 시뮬레이션 수: ({n_changes})", expanded=False):
        st.dataframe(pd.DataFrame(diff_rows), use_container_width=True, hide_index=True)

st.divider()


# =============================================================
# SECTION 1: QUICK RESERVE (sandbox)
# =============================================================
st.subheader("⚡ 배양기 예약")
st.caption("**단일 stage 예약!** (여러 stage 예약은 Reservation탭에서.)")

c1, c2, c3, c4 = st.columns(4)
with c1: sim_user = st.text_input("SME", key="sim_user")
with c2: sim_project = st.text_input("제품평", key="sim_project")
with c3: sim_start = st.date_input("시작 일정", value=today(), key="sim_start")
with c4: sim_days = st.number_input("배양 일수", min_value=1, max_value=30, value=11, key="sim_days")

c5, c6, c7, c8, _ = st.columns([1, 1, 1, 1, 1])
with c5:
    sim_stage = st.selectbox("Stage", ["N-4","N-3","N-2","N-1","N"], index=4, key="sim_stage")
with c6:
    sim_scale = st.selectbox("Scale", ["2L","5L","10L","50L","200L","Wave","Ambr250","Ambr15"], key="sim_scale")
with c7:
    is_n = sim_stage == 'N'
    is_n1 = sim_stage == 'N-1'
    m_opts = utils.get_method_options_for_scale(sim_scale)
    if is_n:
        sim_method = st.selectbox("공정", m_opts, index=0, key="sim_method")
    elif is_n1:
        sim_method = st.selectbox("공정", ["Fed-batch", "Perfusion"], index=0, key="sim_method")
    else:
        st.selectbox("공정", ["Fed-batch"], index=0, key="sim_method", disabled=True)
        sim_method = "Fed-batch"
with c8:
    sim_qty = st.number_input("배양기 수", min_value=1, max_value=20, value=1, key="sim_qty")

st.divider()

allow_same_day_sim = st.checkbox(
                            "털.들 배양기 포함",
                            value=False,
                            key="allow_same_day_sim"
                        )

if st.button("🔍 확인", type="primary", use_container_width=True, key="sim_check"):
    if not sim_user or not sim_project:
        st.error("⚠️ Please fill in User Name and Project Name")
    else:
        sim_end = sim_start + datetime.timedelta(days=sim_days)
        subset = st.session_state.inventory[st.session_state.inventory['scale'] == sim_scale]
        candidate_ids = subset['id'].tolist()
        if sim_stage == 'N-1' and sim_method == 'Perfusion':
            candidate_ids = [r for r in candidate_ids if re.search(r'-P\d+$', r)]
        available = sorted(
            [rid for rid in candidate_ids
             if utils.check_availability(rid, sim_start, sim_end, st.session_state.sandbox_bookings, allow_same_day=allow_same_day_sim)],
            key=utils.custom_sort_key
        )
        st.session_state.qr_available = available
        st.session_state.qr_end = sim_end
        st.rerun()

if 'qr_available' in st.session_state:
    available = st.session_state.qr_available
    sim_end_saved = st.session_state.qr_end
    if len(available) < sim_qty:
        st.error(f"❌ Insufficient: Found {len(available)}, need {sim_qty}")
        if available: st.info(f"Available: {', '.join(available)}")
    else:
        st.success(f"✅ {len(available)} available {sim_scale} reactor(s)")
        selected_reactors = st.multiselect(
            f"Select {sim_qty} Reactor(s)", available,
            default=available[:sim_qty], max_selections=sim_qty,
            format_func=fmt_rid, key="sim_reactor_select"
        )
        if len(selected_reactors) == sim_qty:
            # Vessel count input for Ambr15 only
            sim_vessels_used_map = {}
            if sim_scale == 'Ambr15':
                for reactor in selected_reactors:
                    is_partial = st.checkbox(
                        f"Use fewer than 12 vessels for {reactor.split('-')[-1]}?",
                        key=f"sim_partial_{reactor}"
                    )
                    if is_partial:
                        sim_vessels_used_map[reactor] = st.number_input(
                            f"Vessels used in {reactor.split('-')[-1]} (1-12)",
                            min_value=1, max_value=12, value=12,
                            key=f"sim_vcount_{reactor}"
                        )
                    else:
                        sim_vessels_used_map[reactor] = 12

            if st.button("✅ Confirm Reservation (Sandbox)", type="primary", key="sim_confirm"):
                push_undo(f"Quick Reserve: {sim_project} — {sim_qty}× {sim_scale}")
                bid = str(int(datetime.datetime.now().timestamp()))
                new_rows = []
                for idx, reactor in enumerate(selected_reactors):
                    row = {
                        "booking_id": f"SIM_{bid}_{idx}",
                        "reactor_id": reactor,
                        "user": sim_user,
                        "project": sim_project,
                        "stage": sim_stage,
                        "start": pd.to_datetime(sim_start),
                        "end": pd.to_datetime(sim_end_saved),
                        "method": sim_method
                    }
                    if sim_scale == 'Ambr15':
                        row["vessels_used"] = sim_vessels_used_map.get(reactor, 12)
                    new_rows.append(row)
                st.session_state.sandbox_bookings = pd.concat(
                    [st.session_state.sandbox_bookings, pd.DataFrame(new_rows)],
                    ignore_index=True
                )
                invalidate_diff()
                invalidate_gantt()
                for k in ['qr_available', 'qr_end']: st.session_state.pop(k, None)
                st.success(f"🎉 Added {len(selected_reactors)} booking(s) for {sim_project}!")
                st.rerun()
        else:
            st.warning(f"⚠️ Please select exactly {sim_qty} reactor(s)")
            


st.divider()


# =============================================================
# SECTION 2: ADJUST SCHEDULE (Move / Swap / Delete)
# =============================================================
st.subheader("🔧 배양기 일정 조정: 이동 / 교환 / 삭제")
adj_col1, _ = st.columns([1, 3])
with adj_col1:
    action_type = st.radio(
        "선택", ["배양기 일정 이동", "제품 간 배양기 교환", "예약 배양기 삭제"], key="action_type"
    )

# -------------------------------------------------------------
# MOVE BOOKING
# -------------------------------------------------------------
if action_type == "배양기 일정 이동":
    st.markdown("#### 배양기 이동")
    st.caption("시작 일정 및 제품 선택 후 이동 가능 배양기 확인.")

    if st.session_state.sandbox_bookings.empty:
        st.info("No bookings available.")
    else:
        # ── Next Cascade (only when cascade mode is on + pending state) ──
        # Shown AFTER a successful Move (Mode 1 or Mode 2). Mode 1 auto-
        # advances the date filter to the moved stage's original end date.
        # Mode 2 clears the date (user sets it manually) because shifted
        # bookings may have mixed end dates.
        _pending = st.session_state.get('move_cascade_pending')
        if st.session_state.get('move_cascade_mode') and _pending:
            nc_col1, nc_col2, nc_col3 = st.columns([1, 2, 1])
            with nc_col1:
                if _pending.get('auto_advance') and _pending.get('next_date'):
                    nc_label = f"➡️ Next Cascade ({_pending['next_date']})"
                else:
                    nc_label = "➡️ Next Cascade"
                next_clicked = st.button(
                    nc_label,
                    key="move_next_cascade",
                    type="primary",
                    help=(
                        "Advance to the next cascade stage. Mode 1 moves set "
                        "the date filter to the just-moved stage's original "
                        "end date; Mode 2 (Shift) leaves the date for you to "
                        "pick because shifted bookings may have mixed dates."
                    ),
                )
            with nc_col2:
                if _pending.get('auto_advance') and _pending.get('next_date'):
                    st.info(
                        f"🔗 Cascade pending: next stage starts on "
                        f"**{_pending['next_date']}** for project "
                        f"**{_pending.get('project') or '—'}**."
                    )
                else:
                    st.info(
                        f"🔗 Cascade pending: project **"
                        f"{_pending.get('project') or '—'}**. "
                        f"Pick the next stage's start date manually."
                    )
            with nc_col3:
                cancel_clicked = st.button(
                    "✖ Cancel Cascade",
                    key="move_cancel_cascade",
                    help="Clear the cascade-pending state without advancing.",
                )

            if next_clicked:
                # Clear multiselect so previous labels don't linger
                st.session_state.pop('move_ids', None)
                # Advance date filter if auto_advance is on
                if _pending.get('auto_advance') and _pending.get('next_date'):
                    st.session_state['move_date_filter'] = _pending['next_date']
                # Preserve project filter if the project is still in the
                # project-starting-on(new_date) list; otherwise reset to All.
                _want_proj = _pending.get('project')
                if _want_proj:
                    _target_date = _pending.get('next_date') or st.session_state.get('move_date_filter')
                    if _target_date and _want_proj in projects_starting_on(_target_date):
                        st.session_state['move_proj_filter'] = _want_proj
                    else:
                        st.session_state['move_proj_filter'] = "All"
                # Clear pending state
                st.session_state.pop('move_cascade_pending', None)
                st.rerun()

            if cancel_clicked:
                st.session_state.pop('move_cascade_pending', None)
                st.rerun()

        fc1, fc2 = st.columns(2)
        with fc1:
            move_date_filter = st.date_input(
                "시작 일정", value=today(), key="move_date_filter"
            )
        with fc2:
            _move_projs = projects_starting_on(move_date_filter)
            project_opts = ["All"] + _move_projs
            move_proj_filter = st.selectbox(
                "제품 (설정한 시작 일정 때 D00인 제품만 보여줌)",
                project_opts, key="move_proj_filter"
            )

        bookings_list, label_to_id = build_booking_labels(
            st.session_state.sandbox_bookings,
            project_filter=move_proj_filter,
            date_filter=move_date_filter,
            exact_start=True,
        )

        if not bookings_list:
            st.info("No bookings match the selected filters.")
        else:
            move_labels = st.multiselect("이동할 배양기 선택", bookings_list, key="move_ids")

            if move_labels:
                move_ids = [label_to_id[l] for l in move_labels]
                selected_rows = st.session_state.sandbox_bookings[
                    st.session_state.sandbox_bookings['booking_id'].isin(move_ids)
                ].copy()
                selected_rows['start'] = pd.to_datetime(selected_rows['start'])
                selected_rows['end'] = pd.to_datetime(selected_rows['end'])
                inv_map = st.session_state.inventory.set_index('id')['scale'].to_dict()
                selected_rows['scale'] = selected_rows['reactor_id'].map(inv_map)
                original_qty = len(selected_rows)

                preview_df = selected_rows[['reactor_id','scale','project','start','end']].copy()
                preview_df['start'] = preview_df['start'].dt.strftime('%Y-%m-%d')
                preview_df['end'] = preview_df['end'].dt.strftime('%Y-%m-%d')
                st.markdown(f"**{original_qty} booking(s) selected:**")
                st.dataframe(preview_df, use_container_width=True, hide_index=True)
                st.divider()

                # ── Mode selector ────────────────────────────────────────
                move_mode = st.radio(
                    "Reschedule Mode",
                    ["New Start Date (all bookings → same date)",
                     "Shift by Offset (each booking shifts by N days)"],
                    key="move_mode",
                    horizontal=False,
                )

                # ═════════════════════════════════════════════════════════
                # MODE 1: NEW START DATE (original behavior)
                # ═════════════════════════════════════════════════════════
                if move_mode.startswith("New Start Date"):
                    mc1, mc2 = st.columns(2)
                    with mc1:
                        new_start_date = st.date_input("New Start Date", value=today(), key="move_new_start")
                    with mc2:
                        allow_diff_scale = st.checkbox(
                            "Allow different scale (bioreactors only: 2L/5L/10L/Wave)",
                            key="move_diff_scale"
                        )

                    durations = (selected_rows['end'] - selected_rows['start']).dt.days.unique().tolist()
                    if len(durations) > 1:
                        st.error(f"⚠️ Mixed durations: {durations} days. Select bookings with the same duration, or use Shift by Offset mode.")
                    else:
                        duration = durations[0]
                        new_end_date = new_start_date + datetime.timedelta(days=duration)
                        original_scale = selected_rows['scale'].iloc[0]

                        if allow_diff_scale:
                            if original_scale in {"2L","5L","10L","Wave"}:
                                scales_to_check = sorted(
                                    {"2L","5L","10L","Wave"} &
                                    set(st.session_state.inventory['scale'].unique())
                                )
                            else:
                                st.info(f"Scale change only applies to bioreactors. Keeping {original_scale}.")
                                scales_to_check = [original_scale]
                        else:
                            scales_to_check = [original_scale]

                      
                        if st.button("🔍 Check Availability", type="primary", key="move_check_avail"):
                            temp = st.session_state.sandbox_bookings[
                                ~st.session_state.sandbox_bookings['booking_id'].isin(move_ids)
                            ]
                            avail = []
                            for sc in scales_to_check:
                                sub = st.session_state.inventory[st.session_state.inventory['scale'] == sc]
                                avail.extend(sorted(
                                    [r for r in sub['id']
                                     if utils.check_availability(r, new_start_date, new_end_date, temp)],
                                    key=utils.custom_sort_key
                                ))
                            st.session_state.move_available_reactors = avail
                            st.session_state.move_ids_snapshot = move_ids
                            st.session_state.move_original_qty = original_qty
                            st.session_state.move_stored_start = new_start_date
                            st.session_state.move_stored_end = new_end_date
                            st.session_state.move_meta = selected_rows[
                                ['booking_id','user','project','stage','method']
                            ].set_index('booking_id').to_dict('index')
                            st.rerun()

                        if ('move_available_reactors' in st.session_state and
                                st.session_state.get('move_ids_snapshot') == move_ids):
                            st.divider()
                            avail = st.session_state.move_available_reactors
                            orig_qty_saved = st.session_state.move_original_qty

                            if not avail:
                                st.error("❌ No available reactors found for the selected dates.")
                            else:
                                st.success(
                                    f"✅ {len(avail)} reactor(s) available for "
                                    f"{st.session_state.move_stored_start} ~ {st.session_state.move_stored_end}"
                                )
                                chosen = st.multiselect(
                                    f"Select New Reactor(s) — originally {orig_qty_saved}",
                                    avail, default=[], format_func=fmt_rid, key="move_new_reactors"
                                )
                                qty_confirmed = True
                                if 0 < len(chosen) < orig_qty_saved:
                                    st.warning(
                                        f"⚠️ Moving {len(chosen)} of {orig_qty_saved}. "
                                        f"{orig_qty_saved - len(chosen)} booking(s) will be released."
                                    )
                                    qty_confirmed = st.checkbox(
                                        f"I confirm {orig_qty_saved - len(chosen)} booking(s) will be dropped",
                                        key="move_qty_confirm"
                                    )

                                # ── Cascade mode checkbox (above Confirm) ──
                                # Persists across moves. When on, a "Next
                                # Cascade" button appears after Confirm to
                                # advance the date filter to the just-moved
                                # stage's original end date.
                                st.checkbox(
                                    "🔗 Cascade mode (enables 'Next Cascade' after this move)",
                                    key="move_cascade_mode",
                                    help=(
                                        "After confirming, a 'Next Cascade' "
                                        "button will appear to advance the "
                                        "date filter to the just-moved stage's "
                                        "original end date."
                                    ),
                                )

                                if st.button("✅ Confirm Move (Sandbox)", type="primary", key="move_confirm"):
                                    if not chosen:
                                        st.error("⚠️ Please select at least one reactor.")
                                    elif not qty_confirmed:
                                        st.error("⚠️ Please confirm the quantity reduction.")
                                    else:
                                        # Capture original end date + project BEFORE mutation
                                        # (for cascade mode's Next Cascade button).
                                        _orig_end_dates = sorted(set(selected_rows['end'].dt.date))
                                        _orig_projects = selected_rows['project'].astype(str).unique().tolist()

                                        push_undo(
                                            f"Move: {len(chosen)}× {original_scale} → "
                                            f"{st.session_state.move_stored_start}"
                                        )
                                        st.session_state.sandbox_bookings = st.session_state.sandbox_bookings[
                                            ~st.session_state.sandbox_bookings['booking_id'].isin(
                                                st.session_state.move_ids_snapshot)
                                        ]
                                        bid_ts = str(int(datetime.datetime.now().timestamp()))
                                        meta = st.session_state.move_meta
                                        obids = st.session_state.move_ids_snapshot
                                        new_rows = []
                                        for i, reactor in enumerate(chosen):
                                            src = meta.get(
                                                obids[i] if i < len(obids) else obids[0],
                                                {'user':'','project':'','stage':'N','method':'Fed-batch'}
                                            )
                                            new_rows.append({
                                                "booking_id": f"MOV_{bid_ts}_{i}",
                                                "reactor_id": reactor,
                                                "user": src['user'],
                                                "project": src['project'],
                                                "stage": src['stage'],
                                                "method": src['method'],
                                                "start": pd.to_datetime(st.session_state.move_stored_start),
                                                "end": pd.to_datetime(st.session_state.move_stored_end),
                                            })
                                        st.session_state.sandbox_bookings = pd.concat(
                                            [st.session_state.sandbox_bookings, pd.DataFrame(new_rows)],
                                            ignore_index=True
                                        )
                                        for k in ['move_available_reactors','move_ids_snapshot',
                                                  'move_original_qty','move_stored_start',
                                                  'move_stored_end','move_meta']:
                                            st.session_state.pop(k, None)
                                        invalidate_diff()
                                        invalidate_gantt()

                                        # Stash cascade context if cascade mode is on.
                                        # Mode 1 requires a single original end date AND
                                        # a single project for auto-advance to be meaningful.
                                        if st.session_state.get('move_cascade_mode'):
                                            if len(_orig_end_dates) == 1 and len(_orig_projects) == 1:
                                                st.session_state['move_cascade_pending'] = {
                                                    'next_date': _orig_end_dates[0],
                                                    'project': _orig_projects[0],
                                                    'auto_advance': True,
                                                }
                                            else:
                                                st.session_state['move_cascade_pending'] = {
                                                    'next_date': None,
                                                    'project': _orig_projects[0] if len(_orig_projects) == 1 else None,
                                                    'auto_advance': False,
                                                }

                                        st.success(f"✅ Moved {len(new_rows)} booking(s)!")
                                        st.rerun()

                # ═════════════════════════════════════════════════════════
                # MODE 2: SHIFT BY OFFSET (per-booking, keeps spacing)
                # ═════════════════════════════════════════════════════════
                else:
                    st.caption(
                        "Each selected booking shifts by the same N days. "
                        "If its original reactor is free at the new dates, it stays. "
                        "Otherwise, the app auto-assigns another reactor of the same scale — "
                        "which you can override per booking before confirming."
                    )

                    move_offset = st.number_input(
                        "Shift by N days (+forward / −backward)",
                        value=7, step=1, key="move_offset"
                    )

                    # Invalidate cached plan if inputs change
                    offset_sig = (tuple(sorted(move_ids)), int(move_offset))
                    if st.session_state.get('move_offset_sig') != offset_sig:
                        for k in ['move_offset_sig', 'move_offset_plan', 'move_offset_alt_options']:
                            st.session_state.pop(k, None)

                    if st.button("🔍 Check Availability", type="primary", key="move_offset_check"):
                        offset = int(move_offset)
                        temp = st.session_state.sandbox_bookings[
                            ~st.session_state.sandbox_bookings['booking_id'].isin(move_ids)
                        ]
                        plan = [] # per-booking dict with auto-assigned reactor + status
                        alt_options = {} # booking_id → list of alternative available reactors
                        batch_assigned = set() # reactors used in this batch, to avoid double-assignment

                        for _, r in selected_rows.iterrows():
                            bid = r['booking_id']
                            old_start = r['start'].date()
                            old_end = r['end'].date()
                            new_start = old_start + datetime.timedelta(days=offset)
                            new_end = old_end + datetime.timedelta(days=offset)
                            scale = r['scale']

                            if new_start < today():
                                plan.append({
                                    "booking_id": bid,
                                    "stage": r['stage'],
                                    "old_reactor": r['reactor_id'],
                                    "new_reactor": None,
                                    "new_start": str(new_start),
                                    "new_end": str(new_end),
                                    "status": f"❌ Past ({new_start})",
                                })
                                alt_options[bid] = []
                                continue

                            # Get all available reactors of same scale at new dates,
                            # excluding ones already assigned within this batch
                            sub = st.session_state.inventory[st.session_state.inventory['scale'] == scale]
                            available = sorted(
                                [rid for rid in sub['id']
                                 if rid not in batch_assigned
                                 and utils.check_availability(rid, new_start, new_end, temp)],
                                key=utils.custom_sort_key
                            )

                            # Prefer original reactor if available
                            if r['reactor_id'] in available:
                                assigned = r['reactor_id']
                                status = "✅ OK (same reactor)"
                            elif available:
                                assigned = available[0]
                                status = "🔀 OK (reactor changed)"
                            else:
                                assigned = None
                                status = "⚠️ No available reactor"

                            if assigned:
                                batch_assigned.add(assigned)

                            plan.append({
                                "booking_id": bid,
                                "stage": r['stage'],
                                "old_reactor": r['reactor_id'],
                                "new_reactor": assigned,
                                "new_start": str(new_start),
                                "new_end": str(new_end),
                                "status": status,
                            })
                            alt_options[bid] = available

                        st.session_state.move_offset_sig = offset_sig
                        st.session_state.move_offset_plan = plan
                        st.session_state.move_offset_alt_options = alt_options
                        st.session_state.move_offset_meta = selected_rows[
                            ['booking_id','user','project','stage','method']
                        ].set_index('booking_id').to_dict('index')
                        st.rerun()

                    # ── Preview + per-booking override ───────────────────
                    if st.session_state.get('move_offset_sig') == offset_sig:
                        plan = st.session_state.move_offset_plan
                        alt_options = st.session_state.move_offset_alt_options

                        # Counts for summary
                        n_ok_same = sum(1 for p in plan if p['status'].startswith("✅"))
                        n_changed = sum(1 for p in plan if p['status'].startswith("🔀"))
                        n_none = sum(1 for p in plan if p['status'].startswith("⚠️"))
                        n_past = sum(1 for p in plan if p['status'].startswith("❌"))

                        st.markdown(
                            f"**Preview:** {n_ok_same} kept · {n_changed} reactor changed · "
                            f"{n_none} no alternative · {n_past} past-error "
                            f"(of {len(plan)} bookings)"
                        )

                        # Show preview table first (read-only snapshot)
                        preview_table = pd.DataFrame([
                            {
                                "stage": p['stage'],
                                "old_reactor": fmt_rid(p['old_reactor']),
                                "new_reactor": fmt_rid(p['new_reactor']) if p['new_reactor'] else "—",
                                "new_start": p['new_start'],
                                "new_end": p['new_end'],
                                "status": p['status'],
                            } for p in plan
                        ])
                        st.dataframe(preview_table, use_container_width=True, hide_index=True)

                        # Per-booking override dropdowns (only for shiftable rows)
                        overridable = [p for p in plan if p['new_reactor'] is not None or alt_options.get(p['booking_id'])]
                        if overridable:
                            with st.expander("🔧 Override reactor per booking (optional)", expanded=False):
                                overrides = {}
                                for p in overridable:
                                    bid = p['booking_id']
                                    opts = alt_options.get(bid, [])
                                    if not opts:
                                        continue
                                    default_val = p['new_reactor'] if p['new_reactor'] in opts else opts[0]
                                    label = f"{p['stage']} · {fmt_rid(p['old_reactor'])} → (new dates {p['new_start']} ~ {p['new_end']})"
                                    chosen = st.selectbox(
                                        label,
                                        opts,
                                        index=opts.index(default_val),
                                        format_func=fmt_rid,
                                        key=f"move_override_{bid}",
                                    )
                                    overrides[bid] = chosen

                            # Apply overrides to the plan (and detect duplicates)
                            assigned_set = set()
                            dup = False
                            for p in plan:
                                if p['booking_id'] in overrides:
                                    p['new_reactor'] = overrides[p['booking_id']]
                                if p['new_reactor']:
                                    if p['new_reactor'] in assigned_set:
                                        dup = True
                                    assigned_set.add(p['new_reactor'])
                            if dup:
                                st.error("❌ Two or more bookings are assigned the same reactor. Please fix overrides.")

                        if n_past > 0:
                            st.error(f"❌ {n_past} booking(s) would land before today. Reduce the offset.")
                        if n_none > 0:
                            st.warning(f"⚠️ {n_none} booking(s) have no available reactor — they will be dropped on apply.")

                        apply_disabled = (n_past > 0) or all(p['new_reactor'] is None for p in plan)

                        # ── Cascade mode checkbox (above Confirm) ──
                        # Persists across moves. When on, a "Next Cascade"
                        # button appears after Confirm. Note: Mode 2 does not
                        # auto-advance the date filter (shifted bookings may
                        # have mixed end dates); user picks next date manually.
                        st.checkbox(
                            "🔗 Cascade mode (enables 'Next Cascade' after this shift)",
                            key="move_cascade_mode",
                            help=(
                                "After confirming, a 'Next Cascade' button "
                                "will appear. In Shift-by-Offset mode the "
                                "date filter does not auto-advance — you pick "
                                "the next stage's date manually."
                            ),
                        )

                        if st.button("✅ Confirm Shift (Sandbox)", type="primary",
                                     key="move_offset_confirm", disabled=apply_disabled):
                            offset = int(move_offset)
                            push_undo(f"Shift {len(plan)} booking(s) by {offset:+d}d")

                            # Remove originals from sandbox
                            ids_to_remove = [p['booking_id'] for p in plan]
                            st.session_state.sandbox_bookings = st.session_state.sandbox_bookings[
                                ~st.session_state.sandbox_bookings['booking_id'].isin(ids_to_remove)
                            ]

                            bid_ts = str(int(datetime.datetime.now().timestamp()))
                            meta = st.session_state.move_offset_meta
                            new_rows = []
                            shifted = 0
                            for i, p in enumerate(plan):
                                if p['new_reactor'] is None:
                                    continue # dropped
                                src = meta.get(
                                    p['booking_id'],
                                    {'user':'','project':'','stage':'N','method':'Fed-batch'}
                                )
                                new_rows.append({
                                    "booking_id": f"SFT_{bid_ts}_{i}",
                                    "reactor_id": p['new_reactor'],
                                    "user": src['user'],
                                    "project": src['project'],
                                    "stage": src['stage'],
                                    "method": src['method'],
                                    "start": pd.to_datetime(p['new_start']),
                                    "end": pd.to_datetime(p['new_end']),
                                })
                                shifted += 1

                            if new_rows:
                                st.session_state.sandbox_bookings = pd.concat(
                                    [st.session_state.sandbox_bookings, pd.DataFrame(new_rows)],
                                    ignore_index=True
                                )
                            for k in ['move_offset_sig','move_offset_plan',
                                      'move_offset_alt_options','move_offset_meta']:
                                st.session_state.pop(k, None)
                            invalidate_diff()
                            invalidate_gantt()

                            # Stash cascade context if cascade mode is on.
                            # Mode 2 (Shift by Offset) never auto-advances the
                            # date filter (per v8 spec Q3=C) because shifted
                            # bookings may have mixed original end dates.
                            # User will set the date filter manually.
                            if st.session_state.get('move_cascade_mode'):
                                _orig_projects = selected_rows['project'].astype(str).unique().tolist()
                                st.session_state['move_cascade_pending'] = {
                                    'next_date': None,
                                    'project': _orig_projects[0] if len(_orig_projects) == 1 else None,
                                    'auto_advance': False,
                                }

                            dropped = len(plan) - shifted
                            if dropped:
                                st.success(f"✅ Shifted {shifted} booking(s), dropped {dropped}.")
                            else:
                                st.success(f"✅ Shifted {shifted} booking(s) by {offset:+d} days.")
                            st.rerun()


# -------------------------------------------------------------
# SWAP BOOKINGS (exact_start=True)
# -------------------------------------------------------------
elif action_type == "제품 간 배양기 교환":
    st.markdown("#### 제품간 배양기 교환")
    st.caption(
        "선택한 시작 일정에 D00인 배양기만 보여줌."
    )

    if st.session_state.sandbox_bookings.empty:
        st.info("No bookings available.")
    else:
        inv_map = st.session_state.inventory.set_index('id')['scale'].to_dict()
        col_a, col_b = st.columns(2)

        with col_a:
            st.markdown("### 제품 A")
            swap_date_a = st.date_input("시작 일정", value=today(), key="swap_date_a")
            _projs_a = projects_starting_on(swap_date_a)
            proj_opts_a = ["All"] + _projs_a
            swap_proj_a = st.selectbox("제품", proj_opts_a, key="swap_proj_a")
            labels_a, label_to_id_a = build_booking_labels(
                st.session_state.sandbox_bookings,
                project_filter=swap_proj_a, date_filter=swap_date_a, exact_start=True,
            )
            swap_labels_a = st.multiselect("배양기 선택", labels_a, key="swap_select_a")

        with col_b:
            st.markdown("### 제품 B")
            swap_date_b = st.date_input("시작 일정", value=today(), key="swap_date_b")
            _projs_b = projects_starting_on(swap_date_b)
            proj_opts_b = ["All"] + _projs_b
            swap_proj_b = st.selectbox("제품", proj_opts_b, key="swap_proj_b")
            labels_b, label_to_id_b = build_booking_labels(
                st.session_state.sandbox_bookings,
                project_filter=swap_proj_b, date_filter=swap_date_b, exact_start=True,
            )
            sel_a_ids = [label_to_id_a[l] for l in swap_labels_a] if swap_labels_a else []
            labels_b_filtered = [l for l in labels_b if label_to_id_b.get(l) not in sel_a_ids]
            swap_labels_b = st.multiselect("배양기 선택", labels_b_filtered, key="swap_select_b")

        if swap_labels_a and swap_labels_b:
            ids_a = [label_to_id_a[l] for l in swap_labels_a]
            ids_b = [label_to_id_b[l] for l in swap_labels_b]
            rows_a = st.session_state.sandbox_bookings[
                st.session_state.sandbox_bookings['booking_id'].isin(ids_a)].copy()
            rows_b = st.session_state.sandbox_bookings[
                st.session_state.sandbox_bookings['booking_id'].isin(ids_b)].copy()

            for df_ in [rows_a, rows_b]:
                df_['start'] = pd.to_datetime(df_['start'])
                df_['end'] = pd.to_datetime(df_['end'])
            rows_a['scale'] = rows_a['reactor_id'].map(inv_map)
            rows_b['scale'] = rows_b['reactor_id'].map(inv_map)

            st.divider()
            pc1, pc2 = st.columns(2)
            for col, rows, lbl in [(pc1, rows_a, "제품 A"), (pc2, rows_b, "제품 B")]:
                with col:
                    st.markdown(f"**{lbl} 배양기:**")
                    pv = rows[['reactor_id','scale','project','start','end']].copy()
                    pv['start'] = pv['start'].dt.strftime('%Y-%m-%d')
                    pv['end'] = pv['end'].dt.strftime('%Y-%m-%d')
                    st.dataframe(pv, use_container_width=True, hide_index=True)

            dur_a = rows_a['end'].sub(rows_a['start']).dt.days.unique().tolist()
            dur_b = rows_b['end'].sub(rows_b['start']).dt.days.unique().tolist()
            has_error = False
            if len(dur_a) > 1:
                st.error(f"⚠️ Block A mixed durations: {dur_a} days."); has_error = True
            if len(dur_b) > 1:
                st.error(f"⚠️ Block B mixed durations: {dur_b} days."); has_error = True

            if not has_error:
                dur_a, dur_b = dur_a[0], dur_b[0]
                scale_a, scale_b = rows_a['scale'].iloc[0], rows_b['scale'].iloc[0]

                st.markdown("#### 변경 후 시작 일정")
                st.caption("Default: each block takes the other block's start date.")
                nsc1, nsc2 = st.columns(2)
                with nsc1:
                    start_a_new = st.date_input(
                        "제품 A의 변경 일정",
                        value=rows_b['start'].min().date(), key="swap_new_start_a"
                    )
                with nsc2:
                    start_b_new = st.date_input(
                        "제품 B의 변경 일정",
                        value=rows_a['start'].min().date(), key="swap_new_start_b"
                    )
                end_a_new = start_a_new + datetime.timedelta(days=dur_a)
                end_b_new = start_b_new + datetime.timedelta(days=dur_b)

                st.info(
                    f"""제품 A 수정 일정: **{len(ids_a)}개 배양기**, {dur_a}d → {start_a_new} ~ {end_a_new}  
                    제품 B 수정 일정:  **{len(ids_b)}개 배양기**, {dur_b}d → {start_b_new} ~ {end_b_new}"""
                )

                if st.button("🔍 확인", type="primary", key="swap_check_avail"):
                    temp = st.session_state.sandbox_bookings[
                        ~st.session_state.sandbox_bookings['booking_id'].isin(ids_a + ids_b)
                    ]
                    sub_a = st.session_state.inventory[st.session_state.inventory['scale'] == scale_a]
                    sub_b = st.session_state.inventory[st.session_state.inventory['scale'] == scale_b]
                    avail_a = sorted(
                        [r for r in sub_a['id'] if utils.check_availability(r, start_a_new, end_a_new, temp)],
                        key=utils.custom_sort_key
                    )
                    avail_b = sorted(
                        [r for r in sub_b['id'] if utils.check_availability(r, start_b_new, end_b_new, temp)],
                        key=utils.custom_sort_key
                    )
                    st.session_state.swap_avail_a = avail_a
                    st.session_state.swap_avail_b = avail_b
                    st.session_state.swap_ids_a = ids_a
                    st.session_state.swap_ids_b = ids_b
                    st.session_state.swap_qty_a = len(ids_a)
                    st.session_state.swap_qty_b = len(ids_b)
                    st.session_state.swap_start_a_new = start_a_new
                    st.session_state.swap_end_a_new = end_a_new
                    st.session_state.swap_start_b_new = start_b_new
                    st.session_state.swap_end_b_new = end_b_new
                    st.session_state.swap_meta_a = rows_a[
                        ['booking_id','user','project','stage','method']
                    ].set_index('booking_id').to_dict('index')
                    st.session_state.swap_meta_b = rows_b[
                        ['booking_id','user','project','stage','method']
                    ].set_index('booking_id').to_dict('index')
                    st.rerun()

                snap_match = (
                    st.session_state.get('swap_ids_a') == ids_a and
                    st.session_state.get('swap_ids_b') == ids_b
                )
                if 'swap_avail_a' in st.session_state and snap_match:
                    st.divider()
                    avail_a = st.session_state.swap_avail_a
                    avail_b = st.session_state.swap_avail_b
                    qty_a = st.session_state.swap_qty_a
                    qty_b = st.session_state.swap_qty_b

                    rc1, rc2 = st.columns(2)
                    with rc1:
                        if not avail_a:
                            st.error(f"❌ No reactors for Block A on {st.session_state.swap_start_a_new}")
                            chosen_a = []
                        else:
                            st.success(f"✅ 제품 A 사용 가능 배양기 {len(avail_a)}개")
                            chosen_a = st.multiselect(
                                f"제품 A {st.session_state.swap_start_a_new}에 사용 가능 배양기",
                                avail_a, default=[], format_func=fmt_rid, key="swap_pick_a"
                            )
                    with rc2:
                        if not avail_b:
                            st.error(f"❌ No reactors for Block B on {st.session_state.swap_start_b_new}")
                            chosen_b = []
                        else:
                            st.success(f"✅ 제품 B 사용 가능 배양기 {len(avail_b)}개")
                            chosen_b = st.multiselect(
                                f"제품 B {st.session_state.swap_start_b_new}에 사용 가능 배양기",
                                avail_b, default=[], format_func=fmt_rid, key="swap_pick_b"
                            )

                    qty_confirmed_a = qty_confirmed_b = True
                    if 0 < len(chosen_a) < qty_a:
                        st.warning(f"⚠️ Block A: {len(chosen_a)} of {qty_a}. {qty_a-len(chosen_a)} will be released.")
                        qty_confirmed_a = st.checkbox(
                            f"I confirm {qty_a-len(chosen_a)} Block A booking(s) dropped", key="swap_confirm_qty_a"
                        )
                    if 0 < len(chosen_b) < qty_b:
                        st.warning(f"⚠️ Block B: {len(chosen_b)} of {qty_b}. {qty_b-len(chosen_b)} will be released.")
                        qty_confirmed_b = st.checkbox(
                            f"I confirm {qty_b-len(chosen_b)} Block B booking(s) dropped", key="swap_confirm_qty_b"
                        )

                    if st.button("✅ 교환 확정", type="primary", key="swap_confirm"):
                        if not chosen_a and not chosen_b:
                            st.error("⚠️ Please select reactors for at least one block.")
                        elif not qty_confirmed_a or not qty_confirmed_b:
                            st.error("⚠️ Please confirm quantity reductions.")
                        else:
                            push_undo(
                                f"Swap: Block A→{st.session_state.swap_start_a_new} / "
                                f"Block B→{st.session_state.swap_start_b_new}"
                            )
                            st.session_state.sandbox_bookings = st.session_state.sandbox_bookings[
                                ~st.session_state.sandbox_bookings['booking_id'].isin(
                                    st.session_state.swap_ids_a + st.session_state.swap_ids_b)
                            ]
                            bid_ts = str(int(datetime.datetime.now().timestamp()))
                            new_rows = []
                            for block_chosen, meta, bids, s, e, tag in [
                                (chosen_a, st.session_state.swap_meta_a, st.session_state.swap_ids_a,
                                 st.session_state.swap_start_a_new, st.session_state.swap_end_a_new, 'A'),
                                (chosen_b, st.session_state.swap_meta_b, st.session_state.swap_ids_b,
                                 st.session_state.swap_start_b_new, st.session_state.swap_end_b_new, 'B'),
                            ]:
                                for i, reactor in enumerate(block_chosen):
                                    src = meta.get(
                                        bids[i] if i < len(bids) else bids[0],
                                        {'user':'','project':'','stage':'N','method':'Fed-batch'}
                                    )
                                    new_rows.append({
                                        "booking_id": f"SWP_{bid_ts}_{tag}{i}",
                                        "reactor_id": reactor,
                                        "user": src['user'],
                                        "project": src['project'],
                                        "stage": src['stage'],
                                        "method": src['method'],
                                        "start": pd.to_datetime(s),
                                        "end": pd.to_datetime(e),
                                    })
                            st.session_state.sandbox_bookings = pd.concat(
                                [st.session_state.sandbox_bookings, pd.DataFrame(new_rows)],
                                ignore_index=True
                            )
                            for k in ['swap_avail_a','swap_avail_b','swap_ids_a','swap_ids_b',
                                      'swap_qty_a','swap_qty_b','swap_start_a_new','swap_end_a_new',
                                      'swap_start_b_new','swap_end_b_new','swap_meta_a','swap_meta_b']:
                                st.session_state.pop(k, None)
                            invalidate_diff()
                            invalidate_gantt()
                            st.success(f"✅ Swap complete — {len(new_rows)} booking(s) created!")
                            st.rerun()


# -------------------------------------------------------------
# DELETE BOOKING
# -------------------------------------------------------------
elif action_type == "예약 배양기 삭제":
    st.markdown("#### 예약 배양기 삭제")
    st.caption("금일 이후의 예약만 삭제 가능.")

    if st.session_state.sandbox_bookings.empty:
        st.info("No bookings available.")
    else:
        del_date = st.date_input("시작 일정", value=today(), key="del_date_filter")
        _del_projs = projects_starting_on(del_date)
        d_proj_opts = ["All"] + _del_projs
        del_proj = st.selectbox(
            "제품",
            d_proj_opts, key="del_proj_filter"
        )

        bookings_list, label_to_id = build_booking_labels(
            st.session_state.sandbox_bookings,
            project_filter=del_proj, date_filter=del_date, exact_start=True,
        )
        if not bookings_list:
            st.info("No bookings match the selected filters.")
        else:
            delete_labels = st.multiselect("삭제할 배양기 선택", bookings_list, key="delete_ids")
            if delete_labels:
                delete_ids = [label_to_id[l] for l in delete_labels]
                to_del_df = st.session_state.sandbox_bookings[
                    st.session_state.sandbox_bookings['booking_id'].isin(delete_ids)
                ][['reactor_id','project','start','end']].copy()
                to_del_df['start'] = pd.to_datetime(to_del_df['start']).dt.strftime('%Y-%m-%d')
                to_del_df['end'] = pd.to_datetime(to_del_df['end']).dt.strftime('%Y-%m-%d')
                st.warning(f"**⚠️ {len(delete_ids)} booking(s) will be removed:**")
                st.dataframe(to_del_df, use_container_width=True, hide_index=True)

                if st.button("⚠️ Confirm Delete (Sandbox)", type="secondary", key="apply_delete"):
                    push_undo(f"Delete: {len(delete_ids)} booking(s) — {del_proj}")
                    st.session_state.sandbox_bookings = st.session_state.sandbox_bookings[
                        ~st.session_state.sandbox_bookings['booking_id'].isin(delete_ids)
                    ]
                    invalidate_diff()
                    invalidate_gantt()
                    st.success(f"✅ Deleted {len(delete_ids)} booking(s)")
                    st.rerun()

st.divider()



# =============================================================
# SECTION 4: SANDBOX GANTT VIEW (manual refresh — no auto-render)
# =============================================================
st.subheader("📊 시뮬레이션 적용 현황판")
st.caption(
    "Click **Refresh Gantt** to render the current sandbox state. "
    "The chart is not updated automatically to keep the page responsive."
)

gt1, gt2, gt3, gt4 = st.columns([2, 2, 1, 1])
with gt1:
    gantt_scope = st.selectbox(
        "Scope", ["Bioreactor (배양기)", "Ambr250", "Ambr15"], key="gantt_scope"
    )
with gt2:
    proj_filter_gantt = st.selectbox(
        "Filter Project",
        ["All"] + sorted(st.session_state.sandbox_bookings['project'].astype(str).unique().tolist()),
        key="gantt_proj_filter"
    )
with gt3:
    hl_sandbox = st.date_input("🔍 Highlight Date", value=None, key="hl_sandbox")
with gt4:
    st.write("") # vertical alignment spacer
    st.write("")
    refresh_gantt = st.button("🔄 시뮬레이션 적용", use_container_width=True, key="gantt_refresh_btn")

if refresh_gantt:
    # Build reactor list per scope (matches Home.py)
    if gantt_scope == "Bioreactor (배양기)":
        reactors = sorted(
            [r for r in st.session_state.inventory['id'] if not r.startswith("Ambr")],
            key=utils.custom_sort_key
        )
        height_per_row = 40
        margin_top = 120
    elif gantt_scope == "Ambr250":
        cfg_order = [c[2] for c in utils.INVENTORY_CONFIGS if c[0] == "Ambr250"]
        reactors = sorted(
            [r for r in st.session_state.inventory['id'] if r.startswith("Ambr250")],
            key=lambda x: cfg_order.index(x.split("-")[1]) if x.split("-")[1] in cfg_order else 999
        )
        height_per_row = 25
        margin_top = 160
    else: # Ambr15
        cfg_order = [c[2] for c in utils.INVENTORY_CONFIGS if c[0] == "Ambr15"]
        reactors = sorted(
            [r for r in st.session_state.inventory['id'] if r.startswith("Ambr15")],
            key=lambda x: cfg_order.index(x.split("-")[1]) if x.split("-")[1] in cfg_order else 999
        )
        height_per_row = 20
        margin_top = 50

    if not reactors:
        st.info(f"No inventory for scope: {gantt_scope}")
        st.session_state.sandbox_gantt_fig = None
    else:
        y_map = {rid: (len(reactors) - 1 - i) for i, rid in enumerate(reactors)}
        scale_map = dict(zip(st.session_state.inventory['id'], st.session_state.inventory['scale']))
        sandbox_view = st.session_state.sandbox_bookings.copy()
        if proj_filter_gantt != "All":
            sandbox_view = sandbox_view[sandbox_view['project'].astype(str) == proj_filter_gantt]

        # Build reactor labels (mirrors Home.py per scope)
        annots = []
        if gantt_scope == "Bioreactor (배양기)":
            for rid in reactors:
                y, scale = y_map[rid], scale_map.get(rid, "")
                c = {"2L":"#BDD7EE","5L":"#90EE90","10L":"#32CD32",
                     "50L":"#FFA500","200L":"#CC0000","Wave":"#D3D3D3"}.get(scale, "#FFFFFF")
                annots.append(dict(
                    xref="paper", yref="y", x=-0.05, y=y,
                    text=f"<b>{'-'.join(rid.split('-')[1:])}</b>",
                    showarrow=False, xanchor="center", yanchor="middle",
                    font=dict(color="black", size=14),
                    bgcolor=c, bordercolor="black", borderwidth=1,
                    width=65, height=height_per_row - 2
                ))
        elif gantt_scope == "Ambr250":
            for rid in reactors:
                annots.append(dict(
                    xref="paper", yref="y", x=-0.0239, y=y_map[rid],
                    text=f"<b>{rid.split('-')[2]}</b>",
                    showarrow=False, xanchor="center", yanchor="middle",
                    font=dict(color="black", size=13),
                    bgcolor="#82CAFF", bordercolor="black", borderwidth=1,
                    width=35, height=height_per_row - 2
                ))
        else:
            for rid in reactors:
                annots.append(dict(
                    xref="paper", yref="y", x=-0.02, y=y_map[rid],
                    text=f"<b>{rid.split('-')[2]}</b>",
                    showarrow=False, xanchor="center", yanchor="middle",
                    font=dict(color="black", size=13),
                    bgcolor="#FFB7B2", bordercolor="black", borderwidth=1,
                    width=35, height=height_per_row - 2
                ))

        st.session_state.sandbox_gantt_fig = utils.create_gantt_chart(
            reactors, y_map, sandbox_view,
            extra_shapes=[], extra_annotations=annots,
            highlight_date=hl_sandbox,
            height_per_row=height_per_row,
            margin_top=margin_top,
        )

# Display cached figure (renders only when available)
if st.session_state.sandbox_gantt_fig is not None:
    st.plotly_chart(st.session_state.sandbox_gantt_fig, use_container_width=True)
else:
    st.info("📊 Click **Refresh Gantt** above to render the sandbox schedule.")