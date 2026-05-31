import streamlit as st
import pandas as pd
import datetime
import re
import sys
import os
import utils
import auth

# Ensure gantt_component is importable from pages/ subdirectory
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from gantt_component import gantt_chart

st.set_page_config(page_title="Tetris", layout="wide")

auth.init_auth()
auth.require_role('viewer')

# =============================================================
# INITIALIZATION
# =============================================================
if 'inventory' not in st.session_state:
    st.session_state.inventory = utils.generate_inventory()
if 'bookings' not in st.session_state:
    st.session_state.bookings = utils.load_data()

if 'sandbox_bookings' not in st.session_state:
    st.session_state.sandbox_bookings = st.session_state.bookings.copy()

if 'sandbox_undo_stack' not in st.session_state:
    st.session_state.sandbox_undo_stack = []

if 'sandbox_diff_cache' not in st.session_state:
    st.session_state.sandbox_diff_cache = None

MAX_UNDO = 10


def today():
    return datetime.date.today()


# =============================================================
# HELPERS — Undo stack
# =============================================================
def push_undo(label: str):
    st.session_state.sandbox_undo_stack.append({
        "label": label,
        "state": st.session_state.sandbox_bookings.copy(deep=True),
    })
    if len(st.session_state.sandbox_undo_stack) > MAX_UNDO:
        st.session_state.sandbox_undo_stack.pop(0)


def invalidate_diff():
    st.session_state.sandbox_diff_cache = None


def get_diff():
    if st.session_state.sandbox_diff_cache is None:
        st.session_state.sandbox_diff_cache = _compute_diff(
            st.session_state.bookings,
            st.session_state.sandbox_bookings,
        )
    return st.session_state.sandbox_diff_cache


def _compute_diff(real_df, sandbox_df):
    real_ids    = set(real_df['booking_id'].astype(str))    if not real_df.empty    else set()
    sandbox_ids = set(sandbox_df['booking_id'].astype(str)) if not sandbox_df.empty else set()
    added_ids   = sandbox_ids - real_ids
    removed_ids = real_ids - sandbox_ids
    rows = []
    if added_ids and not sandbox_df.empty:
        adf = sandbox_df[sandbox_df['booking_id'].astype(str).isin(added_ids)].copy()
        adf['start'] = pd.to_datetime(adf['start']).dt.strftime('%Y-%m-%d')
        adf['end']   = pd.to_datetime(adf['end']).dt.strftime('%Y-%m-%d')
        for _, r in adf.iterrows():
            rows.append({'Action': '➕ Added', 'reactor_id': r['reactor_id'],
                         'project': r['project'], 'start': r['start'], 'end': r['end'],
                         'stage': r.get('stage', ''), 'method': r.get('method', '')})
    if removed_ids and not real_df.empty:
        rdf = real_df[real_df['booking_id'].astype(str).isin(removed_ids)].copy()
        rdf['start'] = pd.to_datetime(rdf['start']).dt.strftime('%Y-%m-%d')
        rdf['end']   = pd.to_datetime(rdf['end']).dt.strftime('%Y-%m-%d')
        for _, r in rdf.iterrows():
            rows.append({'Action': '➖ Removed', 'reactor_id': r['reactor_id'],
                         'project': r['project'], 'start': r['start'], 'end': r['end'],
                         'stage': r.get('stage', ''), 'method': r.get('method', '')})
    return rows


def fmt_rid(x):
    return x.replace("6층-", "").replace("5층-", "[5층] ").replace("7층-", "[7층] ")


def projects_starting_on(date_val):
    df = st.session_state.sandbox_bookings.copy()
    df['start'] = pd.to_datetime(df['start'])
    return sorted(df[df['start'].dt.date == date_val]['project'].astype(str).unique().tolist())


def _norm_project(raw):
    clean = str(raw).strip()
    m = re.search(r"SB[ ._-]*(\d+)", clean, re.IGNORECASE)
    return f"SB{int(m.group(1))}" if m else clean


def _build_gantt_data(sandbox_view, reactors):
    """Serialize sandbox bookings + reactor list for the gantt_chart component."""
    bookings_out = []
    if not sandbox_view.empty:
        df = sandbox_view[sandbox_view['reactor_id'].isin(reactors)].copy()
        df['start'] = pd.to_datetime(df['start'], errors='coerce')
        df['end']   = pd.to_datetime(df['end'],   errors='coerce')
        df = df.dropna(subset=['start', 'end'])
        for _, row in df.iterrows():
            key = _norm_project(row['project'])
            bookings_out.append({
                "booking_id":  str(row['booking_id']),
                "reactor_id":  str(row['reactor_id']),
                "start":       row['start'].strftime('%Y-%m-%d'),
                "end":         row['end'].strftime('%Y-%m-%d'),
                "project":     str(row['project']),
                "stage":       str(row.get('stage', '')),
                "user":        str(row.get('user', '')),
                "color":       utils.PROJECT_BG_MAP.get(key, '#808080'),
                "font_color":  utils.PROJECT_FONT_MAP.get(key, '#ffffff'),
            })
    reactors_out = [{"id": rid, "label": fmt_rid(rid)} for rid in reactors]
    return bookings_out, reactors_out


# =============================================================
# CSS
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

st.header("배양기 운용 현황판 시뮬레이션 (테트리스)")
st.caption("배양기 바를 **좌우 드래그** → 날짜 변경 | **다른 행으로 드래그** → 배양기 변경 | 적용은 사이드바 **Finalize & Apply**")


# =============================================================
# SIDEBAR — Undo + Finalize & Apply
# =============================================================
with st.sidebar:
    st.header("시뮬레이션")

    stack = st.session_state.sandbox_undo_stack
    if not stack:
        st.caption("시뮬레이션 없음")
    else:
        labels_newest_first = [
            f"No. {len(stack) - i}: {entry['label']}"
            for i, entry in enumerate(reversed(stack))
        ]
        selected_label = st.selectbox("시뮬레이션 리스트:", labels_newest_first, key="undo_select")
        st.caption("선택한 번호 이후의 모든 시뮬레이션 삭제됨.")
        if st.button("↩️ 삭제", use_container_width=True, key="undo_apply_btn"):
            chosen_display_idx = labels_newest_first.index(selected_label)
            stack_idx = len(stack) - 1 - chosen_display_idx
            st.session_state.sandbox_bookings = stack[stack_idx]['state'].copy(deep=True)
            st.session_state.sandbox_undo_stack = stack[:stack_idx]
            invalidate_diff()
            st.rerun()

    st.caption("시뮬레이션 전체 삭제")
    if st.button("🔄 Reset", use_container_width=True, key="reset_sandbox_btn"):
        st.session_state.sandbox_bookings = st.session_state.bookings.copy()
        st.session_state.sandbox_undo_stack = []
        st.session_state.sandbox_diff_cache = None
        st.rerun()

    st.divider()

    st.header("💾 적용")
    st.caption("입력 시 audit log에 아이디, 시간 자동 저장")

    if 'sim_apply_auth' not in st.session_state:
        st.session_state.sim_apply_auth = False
    if 'sim_apply_user' not in st.session_state:
        st.session_state.sim_apply_user = ''

    if not st.session_state.sim_apply_auth:
        st.caption("🔒 아이디, 비밀번호 입력:")
        with st.form("sim_apply_auth_form"):
            apply_username = st.text_input("아이디")
            apply_pwd      = st.text_input("비밀번호", type="password")
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
                        submitted_by=st.session_state.sim_apply_user,
                    )
                    n_added, n_removed = utils.apply_simulation_diff(
                        filename=filename,
                        actioned_by=st.session_state.sim_apply_user,
                    )
                    utils.log_audit(
                        action='applied', filename=filename,
                        submitted_by=st.session_state.sim_apply_user,
                        actioned_by=st.session_state.sim_apply_user,
                    )
                    st.session_state.bookings        = utils.load_data()
                    st.session_state.sandbox_bookings = st.session_state.bookings.copy()
                    st.session_state.sandbox_undo_stack  = []
                    st.session_state.sandbox_diff_cache  = None
                    st.success(f"✅ Applied: {n_added} added, {n_removed} removed. File: {filename}")
                    st.balloons()
                    st.rerun()
                except Exception as e:
                    st.error(f"❌ Finalize failed: {e}")
                    import traceback
                    st.code(traceback.format_exc())


# =============================================================
# TOOLBAR — pending change counter
# =============================================================
diff_rows = get_diff()
n_changes = len(diff_rows)

if n_changes == 0:
    st.info("🟢 적용 예정 시뮬레이션 없음.")
else:
    st.warning(f"🟡 **{n_changes} change(s) pending** — use sidebar to Finalize or Undo.")
    with st.expander(f"📋 적용 대기 시뮬레이션 ({n_changes})", expanded=False):
        st.dataframe(pd.DataFrame(diff_rows), use_container_width=True, hide_index=True)

st.divider()


# =============================================================
# SECTION 1: QUICK RESERVE (sandbox)
# =============================================================
st.subheader("⚡ 배양기 예약")
st.caption("**단일 stage 예약!** (여러 stage 예약은 Reservation탭에서.)")

c1, c2, c3, c4 = st.columns(4)
with c1: sim_user    = st.text_input("SME",       key="sim_user")
with c2: sim_project = st.text_input("제품명",     key="sim_project")
with c3: sim_start   = st.date_input("시작 일정",  value=today(), key="sim_start")
with c4: sim_days    = st.number_input("배양 일수", min_value=1, max_value=30, value=11, key="sim_days")

c5, c6, c7, c8, _ = st.columns([1, 1, 1, 1, 1])
with c5:
    sim_stage = st.selectbox("Stage", ["N-4", "N-3", "N-2", "N-1", "N"], index=4, key="sim_stage")
with c6:
    sim_scale = st.selectbox("Scale", ["2L", "5L", "10L", "50L", "200L", "Wave", "Ambr250", "Ambr15"], key="sim_scale")
with c7:
    is_n  = sim_stage == 'N'
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
allow_same_day_sim = st.checkbox("털들 배양기 포함", value=False, key="allow_same_day_sim")

if st.button("🔍 확인", type="primary", use_container_width=True, key="sim_check"):
    if not sim_user or not sim_project:
        st.error("⚠️ Please fill in User Name and Project Name")
    else:
        sim_end       = sim_start + datetime.timedelta(days=sim_days)
        subset        = st.session_state.inventory[st.session_state.inventory['scale'] == sim_scale]
        candidate_ids = subset['id'].tolist()
        if sim_stage == 'N-1' and sim_method == 'Perfusion':
            candidate_ids = [r for r in candidate_ids if re.search(r'-P\d+$', r)]
        available = sorted(
            [rid for rid in candidate_ids
             if utils.check_availability(rid, sim_start, sim_end,
                                         st.session_state.sandbox_bookings,
                                         allow_same_day=allow_same_day_sim)],
            key=utils.custom_sort_key,
        )
        st.session_state.qr_available = available
        st.session_state.qr_end       = sim_end
        st.rerun()

if 'qr_available' in st.session_state:
    available     = st.session_state.qr_available
    sim_end_saved = st.session_state.qr_end
    if len(available) < sim_qty:
        st.error(f"❌ Insufficient: Found {len(available)}, need {sim_qty}")
        if available:
            st.info(f"Available: {', '.join(available)}")
    else:
        st.success(f"✅ {len(available)} available {sim_scale} reactor(s)")
        selected_reactors = st.multiselect(
            f"Select {sim_qty} Reactor(s)", available,
            default=available[:sim_qty], max_selections=sim_qty,
            format_func=fmt_rid, key="sim_reactor_select",
        )
        if len(selected_reactors) == sim_qty:
            sim_vessels_used_map = {}
            if sim_scale == 'Ambr15':
                for reactor in selected_reactors:
                    is_partial = st.checkbox(
                        f"Use fewer than 12 vessels for {reactor.split('-')[-1]}?",
                        key=f"sim_partial_{reactor}",
                    )
                    sim_vessels_used_map[reactor] = st.number_input(
                        f"Vessels used ({reactor.split('-')[-1]})",
                        min_value=1, max_value=12, value=12,
                        key=f"sim_vcount_{reactor}",
                    ) if is_partial else 12

            if st.button("✅ Confirm Reservation (Sandbox)", type="primary", key="sim_confirm"):
                push_undo(f"Quick Reserve: {sim_project} — {sim_qty}× {sim_scale}")
                bid      = str(int(datetime.datetime.now().timestamp()))
                new_rows = []
                for idx, reactor in enumerate(selected_reactors):
                    row = {
                        "booking_id": f"SIM_{bid}_{idx}",
                        "reactor_id": reactor,
                        "user":       sim_user,
                        "project":    sim_project,
                        "stage":      sim_stage,
                        "start":      pd.to_datetime(sim_start),
                        "end":        pd.to_datetime(sim_end_saved),
                        "method":     sim_method,
                    }
                    if sim_scale == 'Ambr15':
                        row["vessels_used"] = sim_vessels_used_map.get(reactor, 12)
                    new_rows.append(row)
                st.session_state.sandbox_bookings = pd.concat(
                    [st.session_state.sandbox_bookings, pd.DataFrame(new_rows)],
                    ignore_index=True,
                )
                invalidate_diff()
                for k in ['qr_available', 'qr_end']:
                    st.session_state.pop(k, None)
                st.success(f"🎉 Added {len(selected_reactors)} booking(s) for {sim_project}!")
                st.rerun()
        else:
            st.warning(f"⚠️ Please select exactly {sim_qty} reactor(s)")

st.divider()


# =============================================================
# SECTION 2: DELETE (simplified — drag replaces move/swap)
# =============================================================
st.subheader("🗑️ 예약 삭제")
st.caption("금일 이후의 예약만 삭제 가능.")

if not st.session_state.sandbox_bookings.empty:
    del_c1, del_c2 = st.columns(2)
    with del_c1:
        del_date = st.date_input("시작 일정", value=today(), key="del_date_filter")
    with del_c2:
        del_proj = st.selectbox("제품", ["All"] + projects_starting_on(del_date), key="del_proj_filter")

    _df_del = st.session_state.sandbox_bookings.copy()
    _df_del['start'] = pd.to_datetime(_df_del['start'])
    _df_del = _df_del[_df_del['start'].dt.date == del_date]
    if del_proj != "All":
        _df_del = _df_del[_df_del['project'] == del_proj]

    if _df_del.empty:
        st.info("해당 날짜에 예약 없음.")
    else:
        _df_del['_label'] = _df_del['reactor_id'] + " | " + _df_del['project'].astype(str)
        lbl_map    = dict(zip(_df_del['_label'], _df_del['booking_id']))
        del_labels = st.multiselect("삭제할 배양기 선택", list(lbl_map.keys()), key="delete_ids")

        if del_labels:
            del_ids = [lbl_map[l] for l in del_labels]
            show_df = _df_del[_df_del['booking_id'].isin(del_ids)][['reactor_id', 'project', 'start', 'end']].copy()
            show_df['start'] = pd.to_datetime(show_df['start']).dt.strftime('%Y-%m-%d')
            show_df['end']   = pd.to_datetime(show_df['end']).dt.strftime('%Y-%m-%d')
            st.warning(f"**⚠️ {len(del_ids)} booking(s) will be removed:**")
            st.dataframe(show_df, use_container_width=True, hide_index=True)

            if st.button("⚠️ Confirm Delete (Sandbox)", type="secondary", key="apply_delete"):
                push_undo(f"Delete: {len(del_ids)} booking(s) — {del_proj}")
                st.session_state.sandbox_bookings = st.session_state.sandbox_bookings[
                    ~st.session_state.sandbox_bookings['booking_id'].isin(del_ids)
                ]
                invalidate_diff()
                st.success(f"✅ Deleted {len(del_ids)} booking(s)")
                st.rerun()

st.divider()


# =============================================================
# SECTION 3: DRAG & MOVE GANTT (vis.js Timeline component)
# =============================================================
st.subheader("📊 시뮬레이션 현황판")
st.caption("💡 **좌우 드래그** → 날짜 이동  |  **다른 행으로 드래그** → 배양기 변경  |  충돌 시 자동 복귀")

gt1, gt2, gt3 = st.columns([2, 2, 2])
with gt1:
    gantt_scope = st.selectbox("Scope", ["배양기", "Ambr250", "Ambr15"], key="gantt_scope")
with gt2:
    all_projs   = sorted(st.session_state.sandbox_bookings['project'].astype(str).unique().tolist())
    proj_filter = st.selectbox("제품", ["All"] + all_projs, key="gantt_proj_filter")
with gt3:
    hl_date = st.date_input("🔍 일자 설정", value=None, key="hl_sandbox")

# Build reactor list per scope (mirrors Home.py ordering)
if gantt_scope == "배양기":
    floor_choice = st.radio("Floor:", ["6층", "5층", "7층"], horizontal=True, key="gantt_floor")
    all_bio  = sorted(
        [r for r in st.session_state.inventory['id'] if not r.startswith("Ambr")],
        key=utils.custom_sort_key,
    )
    reactors = [r for r in all_bio if r.startswith(floor_choice)]
    H_ROW    = 40
elif gantt_scope == "Ambr250":
    cfg_order = [c[2] for c in utils.INVENTORY_CONFIGS if c[0] == "Ambr250"]
    reactors  = sorted(
        [r for r in st.session_state.inventory['id'] if r.startswith("Ambr250")],
        key=lambda x: cfg_order.index(x.split("-")[1]) if x.split("-")[1] in cfg_order else 999,
    )
    H_ROW = 25
else:  # Ambr15
    cfg_order = [c[2] for c in utils.INVENTORY_CONFIGS if c[0] == "Ambr15"]
    reactors  = sorted(
        [r for r in st.session_state.inventory['id'] if r.startswith("Ambr15")],
        key=lambda x: cfg_order.index(x.split("-")[1]) if x.split("-")[1] in cfg_order else 999,
    )
    H_ROW = 20

# Filter + window bookings for the component
sandbox_view = st.session_state.sandbox_bookings.copy()
if proj_filter != "All":
    sandbox_view = sandbox_view[sandbox_view['project'].astype(str) == proj_filter]
if not sandbox_view.empty:
    _win_s = pd.Timestamp(datetime.date.today() - datetime.timedelta(days=7))
    _win_e = pd.Timestamp(datetime.date.today() + datetime.timedelta(days=60))
    _s = pd.to_datetime(sandbox_view['start'], errors='coerce')
    _e = pd.to_datetime(sandbox_view['end'],   errors='coerce')
    sandbox_view = sandbox_view[(_s <= _win_e) & (_e >= _win_s)]

bookings_data, reactors_data = _build_gantt_data(sandbox_view, reactors)

# Render drag-enabled Gantt; key changes with floor to force re-init on scope switch
_gantt_key = f"gantt_{gantt_scope}_{st.session_state.get('gantt_floor', '')}"
drag = gantt_chart(
    bookings=bookings_data,
    reactors=reactors_data,
    highlight_date=str(hl_date) if hl_date else None,
    height_per_row=H_ROW,
    key=_gantt_key,
)

# --- Drag result handler ---
# ts-based dedup prevents the same drag from firing twice on rerun
if drag is not None:
    drag_ts = drag.get('ts', 0)
    if drag_ts != st.session_state.get('_last_drag_ts', -1):
        st.session_state['_last_drag_ts'] = drag_ts

        bid       = drag['booking_id']
        new_rid   = drag['new_reactor_id']
        new_start = drag['new_start']
        new_end   = drag['new_end']

        # Validate: exclude the dragged booking from the conflict check
        temp = st.session_state.sandbox_bookings[
            st.session_state.sandbox_bookings['booking_id'].astype(str) != bid
        ]
        if utils.check_availability(new_rid, new_start, new_end, temp):
            push_undo(f"Drag: …{bid[-8:]} → {new_rid} ({new_start})")
            mask = st.session_state.sandbox_bookings['booking_id'].astype(str) == bid
            st.session_state.sandbox_bookings.loc[mask, 'reactor_id'] = new_rid
            st.session_state.sandbox_bookings.loc[mask, 'start'] = pd.to_datetime(new_start)
            st.session_state.sandbox_bookings.loc[mask, 'end']   = pd.to_datetime(new_end)
            invalidate_diff()
            st.rerun()
        else:
            st.error(f"❌ {new_rid} is not available for {new_start} ~ {new_end}. Move reverted.")
