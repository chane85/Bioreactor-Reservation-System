import streamlit as st
import datetime
import time
import utils
import auth
import plotly.express as px
import pandas as pd

_t_start = time.time()

st.set_page_config(page_title="Bioreactor Manager", layout="wide")

# Auth: render login/logout in sidebar (Home is public — no role gate)
auth.init_auth()

if 'inventory' not in st.session_state: st.session_state.inventory = utils.generate_inventory()
if 'bookings' not in st.session_state: st.session_state.bookings = utils.load_data()


def get_project_options(bookings_df):
    """Unique sorted project names for filter dropdown."""
    if bookings_df.empty or 'project' not in bookings_df.columns:
        return []
    return sorted(bookings_df['project'].dropna().unique().tolist())

# --- DAILY STARTS ALARM ---
def get_starts_on_date(bookings_df, target_date):
    """Return DataFrame of bookings whose start date equals target_date (start-only)."""
    if bookings_df.empty:
        return pd.DataFrame()
    df = bookings_df.copy()
    df['start'] = pd.to_datetime(df['start'], errors='coerce')
    return df[df['start'].dt.date == target_date]

_today = datetime.date.today()
_tomorrow = _today + datetime.timedelta(days=1)
_d_tomorrow = _today + datetime.timedelta(days=2)

st.markdown("### 🔔 데일리 실험 일정 (D00)")
a1, a2, a3, a4 = st.columns([1, 1, 1, 2])
_starts_today = get_starts_on_date(st.session_state.bookings, _today)
_starts_tomorrow = get_starts_on_date(st.session_state.bookings, _tomorrow)
a1.metric("📅 오늘", f"{len(_starts_today)} 개", help=f"Bookings starting on {_today}")
a2.metric("📅 내일", f"{len(_starts_tomorrow)} 개", help=f"Bookings starting on {_tomorrow}")
custom_date = a3.date_input("확인 일자 설정", value=_d_tomorrow, key="alarm_custom_date", label_visibility="visible")
_starts_custom = get_starts_on_date(st.session_state.bookings, custom_date)
a4.metric(f"📅 {custom_date}", f"{len(_starts_custom)} 개")

with st.expander("📋 View Details", expanded=False):
    _tab_today, _tab_tomorrow, _tab_custom = st.tabs(["Today", "Tomorrow", f"Custom ({custom_date})"])
    _detail_cols = ['reactor_id', 'project', 'stage', 'method', 'user', 'end']
    for _tab, _df, _label in [
        (_tab_today, _starts_today, _today),
        (_tab_tomorrow, _starts_tomorrow, _tomorrow),
        (_tab_custom, _starts_custom, custom_date),
    ]:
        with _tab:
            if _df.empty:
                st.info(f"No bookings starting on {_label}.")
            else:
                _show = _df[_detail_cols].copy()
                _show['end'] = pd.to_datetime(_show['end']).dt.strftime('%Y-%m-%d')
                _show = _show.rename(columns={
                    'reactor_id': 'Reactor',
                    'project': 'Project',
                    'stage': 'Stage',
                    'method': 'Method',
                    'user': 'SME',
                    'end': 'End Date'
                })
                st.dataframe(_show, use_container_width=True, hide_index=True)

st.divider()
# --- CSS STYLING ---
st.markdown("""
    <style>
    div[data-testid="stTextInput"] input,
    div[data-testid="stDateInput"] input,
    div[data-testid="stNumberInput"] input {
        text-align: center !important;
        border-radius: 4px;
    }
    div[data-testid="stSelectbox"] div[data-baseweb="select"] {
       border-radius: 4px;
        text-align: center !important;
    }
    div[data-testid="stSelectbox"] div[data-baseweb="select"] > div:first-child {
        display: flex !important;
        justify-content: center !important;
        align-items: center !important;   
        margin: 0 auto !important;        
        width: 100% !important;           
    }
    div[data-testid="stSelectbox"] div[data-baseweb="select"] span,
    div[data-testid="stSelectbox"] div[data-baseweb="select"] div {
        text-align: center !important;
        justify-content: center !important;
    }
    div[data-testid="stDateInput"] div[data-baseweb="input"] {
        background-color: #F0F2F6 !important;
        border: 1px solid transparent !important;
    }
    div[data-testid="stDateInput"] div[data-baseweb="base-input"] {
        background-color: transparent !important;
    }
    [data-testid="stMetric"] {
        text-align: center;
        margin: auto;
    }
    [data-testid="stMetricLabel"] {
        justify-content: center;
    }
    [data-testid="stMetricValue"] {
        justify-content: center;
    }
    </style>
""", unsafe_allow_html=True)


tab_choice = st.radio(
    "View:",
    ["배양기", "Ambr250", "Ambr15"],
    horizontal=True,
    key="home_scope",
    label_visibility="collapsed",
)

m1_start, m1_end, m2_start, m2_end = utils.get_month_ranges()

# --- TAB 1: BIOREACTOR ---
if tab_choice == "배양기":
    # Sub-radio: pick one floor at a time
    floor_choice = st.radio(
        "Floor:",
        ["6층", "5층", "7층"],
        horizontal=True,
        key="bio_floor",
        label_visibility="collapsed",
    )

    c1, c2, c3 = st.columns([3, 2, 1])
    c1.subheader(f"배양기 운용 현황판 — {floor_choice}")
    proj_opts_bio = get_project_options(st.session_state.bookings)
    sel_proj_bio = c2.multiselect("🔍 제품 필터 (최대 2개)", proj_opts_bio, max_selections=2, key="proj_bio")
    hl_date = c3.date_input("🔍 일자 설정", value=None, key="hl_bio")

    # Filter reactors to the selected floor only
    floor_ids = [r for r in st.session_state.inventory['id'] if r.startswith(floor_choice)]

    show_chart = True

    occ_1, occ_2 = utils.calculate_generic_occupancy(
        floor_ids, st.session_state.bookings, m1_start, m1_end, m2_start, m2_end
    )

    m1, m2, _ = st.columns([1, 1, 4])
    m1.metric(f"{m1_start.strftime('%B')} ({floor_choice})", f"{occ_1:.1f}%")
    m2.metric(f"{m2_start.strftime('%B')} ({floor_choice})", f"{occ_2:.1f}%")
    st.divider()

    reactors = sorted(floor_ids, key=utils.custom_sort_key)
    bookings_view = st.session_state.bookings.copy()
    if sel_proj_bio:
        bookings_view = bookings_view[bookings_view['project'].isin(sel_proj_bio)]

    # --- DATE WINDOW FILTER (span-aware: keep bookings overlapping the window) ---
    _win_start = pd.Timestamp(_today - datetime.timedelta(days=7))
    _win_end = pd.Timestamp(_today + datetime.timedelta(days=60))
    if not bookings_view.empty:
        _s = pd.to_datetime(bookings_view['start'], errors='coerce')
        _e = pd.to_datetime(bookings_view['end'], errors='coerce')
        bookings_view = bookings_view[(_s <= _win_end) & (_e >= _win_start)]

    if show_chart and reactors:
        y_map = {rid: (len(reactors) - 1 - i) for i, rid in enumerate(reactors)}
        scale_map = dict(zip(st.session_state.inventory['id'], st.session_state.inventory['scale']))
        shapes, annots = [], []
        floor_ranges = {}
      
        # ROW HEIGHT
        H_ROW = 40

        for i, rid in enumerate(reactors):
            y, scale, fl = y_map[rid], scale_map.get(rid, ""), rid.split('-')[0]
            floor_ranges.setdefault(fl, [y, y])
            floor_ranges[fl] = [min(floor_ranges[fl][0], y), max(floor_ranges[fl][1], y)]
          
            # Colors
            if scale == "2L": c = "#BDD7EE" # Light Blue
            elif scale == "5L": c = "#90EE90" # Light Green
            elif scale == "10L": c = "#32CD32" # Lime Green
            elif scale == "50L": c = "#FFA500" # Orange
            elif scale == "200L":c = "#CC0000" # Red
            elif scale == "Wave":c = "#D3D3D3" # Grey
            else: c = "#FFFFFF" # White (Fallback)
          
           # EQ NUMBER LABEL (middle column)
            eq_num = utils.REACTOR_EQ_MAP.get(rid, "—")
            annots.append(dict(
                xref="paper", yref="y", x=-0.069, y=y,
                text=f"<b>{eq_num}</b>",
                showarrow=False, xanchor="center", yanchor="middle",
                font=dict(color="black", size=14),
                bgcolor="#F5F5F5", bordercolor="black", borderwidth=1,
                width=75, height=H_ROW-2
            ))

            # BIOREACTOR LABEL (right column)
            annots.append(dict(
                xref="paper", yref="y", x=-0.025, y=y,
                text=f"<b>{'-'.join(rid.split('-')[1:])}</b>",
                showarrow=False, xanchor="center", yanchor="middle",
                font=dict(color="black", size=14),
                bgcolor=c, bordercolor="black", borderwidth=1,
                width=60, height=H_ROW-2
            ))

        # --- FLOOR COLUMN LOOP (Using SHAPES for Perfect Alignment) ---
        for fl, (min_y, max_y) in floor_ranges.items():
            c = {"5층":"#90EE90", "6층":"#B0E0E6", "7층":"#FFA500"}.get(fl, "#EEE")
          
            # 1. DRAW BOX (Shape)
            # Starts exactly at bottom row - 0.5 and ends at top row + 0.5
             # Row Calculation
            row_count = max_y - min_y + 1
           
            # Height Calculation (Now exact because utils.py is fixed)
            # Subtract 2 pixels just for the border thickness
            pixel_height = (row_count * H_ROW) - 8
            if fl == "6층":
                pixel_height = pixel_height - 45
            annots.append(dict(
                xref="paper", yref="y",
                x=-0.118, y=(min_y+max_y)/2,
                text=f"<b>{fl}</b>",
                showarrow=False, xanchor="center", yanchor="middle",
                font=dict(color="black", size=16),
                # Using Annotation ensures COLOR is visible
                bgcolor=c, bordercolor="black", borderwidth=1,
                width=60, height=pixel_height
            ))
           
        fig = utils.create_gantt_chart(reactors, y_map, bookings_view, extra_shapes=shapes, extra_annotations=annots, highlight_date=hl_date, height_per_row=H_ROW)
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info(f"{floor_choice}에 등록된 배양기가 없습니다.")

# --- TAB 2: AMBR 250 ---
elif tab_choice == "Ambr250":
    c1, c2, c3 = st.columns([3, 2, 1])
    c1.subheader("Ambr 250 Schedule")
    proj_opts_250 = get_project_options(st.session_state.bookings)
    sel_proj_250 = c2.multiselect("🔍 제품 필터 (최대 2개)", proj_opts_250, max_selections=2, key="proj_250")
    hl_250 = c3.date_input("🔍 일자 설정", value=None, key="hl_250")
  
    config_order = [conf[2] for conf in utils.INVENTORY_CONFIGS if conf[0] == "Ambr250"]
    units = sorted([r for r in st.session_state.inventory['id'] if r.startswith("Ambr250")],
                   key=lambda x: config_order.index(x.split("-")[1]) if x.split("-")[1] in config_order else 999)
    bookings_view = st.session_state.bookings.copy()
    if sel_proj_250:
        bookings_view = bookings_view[bookings_view['project'].isin(sel_proj_250)]
  
    occ_1, occ_2 = utils.calculate_generic_occupancy(units, st.session_state.bookings, m1_start, m1_end, m2_start, m2_end)
    m1, m2, _ = st.columns([1,1,4])
    m1.metric(f"{m1_start.strftime('%B')}", f"{occ_1:.1f}%"); m2.metric(f"{m2_start.strftime('%B')}", f"{occ_2:.1f}%")
    st.divider()

    if units:
        y_map = {rid: (len(units) - 1 - i) for i, rid in enumerate(units)}
        shapes, annots, eq_ranges = [], [], {}
      
        H_ROW = 25

        for rid in units:
            y, eq_id, v_num = y_map[rid], rid.split("-")[1], rid.split("-")[2]
            eq_ranges.setdefault(eq_id, [y, y])
            eq_ranges[eq_id] = [min(eq_ranges[eq_id][0], y), max(eq_ranges[eq_id][1], y)]
          
            annots.append(dict(
                xref="paper", yref="y", x=-0.0239, y=y,
                text=f"<b>{v_num}</b>",
                showarrow=False, xanchor="center", yanchor="middle",
                font=dict(color="black", size=13),
                bgcolor="#82CAFF", bordercolor="black", borderwidth=1,
                width=35, height=H_ROW-2
            ))
          
        for eq_id, (min_y, max_y) in eq_ranges.items():
            # Using Shape for Ambr too for consistency
             row_count = max_y - min_y + 1
           
            # [FIX] Subtract 4 pixels to make it shorter
             pixel_height = (row_count * H_ROW) - 5.6
            
            # [FIX] Use annots.append (NOT shapes) to ensure Background Color appears
             annots.append(dict(
                xref="paper", yref="y", x=-0.065, y=(min_y+max_y)/2,
                text=f"<b>{eq_id.replace('EQ0000','')}</b>",
                showarrow=False, xanchor="center", yanchor="middle",
                font=dict(color="black", size=14),
                bgcolor="#B2EBF2", bordercolor="black", borderwidth=1,
                width=80, height=pixel_height
            ))

        fig = utils.create_gantt_chart(units, y_map, bookings_view, extra_shapes=shapes, extra_annotations=annots, highlight_date=hl_250, height_per_row=H_ROW, margin_top=160)
        st.plotly_chart(fig, use_container_width=True)

# --- TAB 3: AMBR 15 ---
else: # Ambr15
    c1, c2, c3 = st.columns([3, 2, 1])
    c1.subheader("Ambr 15 Schedule")
    proj_opts_15 = get_project_options(st.session_state.bookings)
    sel_proj_15 = c2.multiselect("🔍 제품 필터 (최대 2개)", proj_opts_15, max_selections=2, key="proj_15")
    hl_15 = c3.date_input("🔍 일자 설정", value=None, key="hl_15")
  
    config_order = [conf[2] for conf in utils.INVENTORY_CONFIGS if conf[0] == "Ambr15"]
    units = sorted([r for r in st.session_state.inventory['id'] if r.startswith("Ambr15")],
                   key=lambda x: config_order.index(x.split("-")[1]) if x.split("-")[1] in config_order else 999)
    bookings_view = st.session_state.bookings.copy()
    if sel_proj_15:
        bookings_view = bookings_view[bookings_view['project'].isin(sel_proj_15)]

    occ_1, occ_2 = utils.calculate_generic_occupancy(units, st.session_state.bookings, m1_start, m1_end, m2_start, m2_end)
    m1, m2, _ = st.columns([1,1,4])
    m1.metric(f"{m1_start.strftime('%B')}", f"{occ_1:.1f}%"); m2.metric(f"{m2_start.strftime('%B')}", f"{occ_2:.1f}%")
    st.divider()
  
    if units:
        y_map = {rid: (len(units) - 1 - i) for i, rid in enumerate(units)}
        shapes, annots, eq_ranges = [], [], {}
      
        H_ROW = 20

        for rid in units:
            y, eq_id, v_num = y_map[rid], rid.split("-")[1], rid.split("-")[2]
            eq_ranges.setdefault(eq_id, [y, y])
            eq_ranges[eq_id] = [min(eq_ranges[eq_id][0], y), max(eq_ranges[eq_id][1], y)]
          
            annots.append(dict(
                xref="paper", yref="y", x=-0.02, y=y,
                text=f"<b>{v_num}</b>",
                showarrow=False, xanchor="center", yanchor="middle",
                font=dict(color="black", size=13),
                bgcolor="#FFB7B2", bordercolor="black", borderwidth=1,
                width=35, height=H_ROW-2
            ))
          
        for eq_id, (min_y, max_y) in eq_ranges.items():
            # Using Shape for Ambr too for consistency
            row_count = max_y - min_y + 1
           
            # [FIX] Subtract 4 pixels to make it shorter
            pixel_height = (row_count * H_ROW) - 6.6
           
            # [FIX] Use annots.append (NOT shapes) to ensure Background Color appears
            annots.append(dict(
                xref="paper", yref="y", x=-0.06, y=(min_y+max_y)/2,
                text=f"<b>{eq_id.replace('EQ0000','')}</b>",
                showarrow=False, xanchor="center", yanchor="middle",
                font=dict(color="black", size=12),
                bgcolor="#FFDAC1", bordercolor="black", borderwidth=1,
                width=80, height=pixel_height
            ))

        fig = utils.create_gantt_chart(units, y_map, bookings_view, extra_shapes=shapes, extra_annotations=annots, highlight_date=hl_15, height_per_row=H_ROW, margin_top=120, y_domain_top=0.92)
        st.plotly_chart(fig, use_container_width=True)
        
        # --- VESSEL BLOCK NOTIFICATION TABLE ---
        _all_bookings = st.session_state.bookings
        if not _all_bookings.empty and 'booking_id' in _all_bookings.columns:
            _vblocks = _all_bookings[
                _all_bookings['booking_id'].astype(str).str.startswith('VBLOCK_')
            ].copy()
            
            if not _vblocks.empty:
                # Filter to visible window (today - 10d to today + 70d, matching Gantt range)
                _win_s = pd.Timestamp(_today - datetime.timedelta(days=7))
                _win_e = pd.Timestamp(_today + datetime.timedelta(days=63))
                _vblocks['start'] = pd.to_datetime(_vblocks['start'], errors='coerce')
                _vblocks['end'] = pd.to_datetime(_vblocks['end'], errors='coerce')
                _vblocks = _vblocks[(_vblocks['start'] <= _win_e) & (_vblocks['end'] >= _win_s)]
                
                if not _vblocks.empty:
                    # Parse station + vessel from reactor_id (e.g., Ambr15-EQ257-S1-V03)
                    _vblocks['Station'] = _vblocks['reactor_id'].apply(
                        lambda r: '-'.join(r.split('-')[:-1])
                    )
                    _vblocks['Vessel'] = _vblocks['reactor_id'].apply(
                        lambda r: r.split('-')[-1]
                    )
                    _vblocks['Start'] = _vblocks['start'].dt.strftime('%Y-%m-%d')
                    _vblocks['End'] = _vblocks['end'].dt.strftime('%Y-%m-%d')
                    _vblocks_show = _vblocks[['Station', 'Vessel', 'Start', 'End', 'user']].rename(
                        columns={'user': '등록자'}
                    ).sort_values(['Station', 'Start', 'Vessel'])
                    
                    st.markdown(f"#### ⚠️ 고장/Calibration 중 Vessel 수: {len(_vblocks_show)}")
                    st.caption("해당 vessel의 station 예약 가능. 비용 계산에서는 제외.")
                    st.dataframe(_vblocks_show, use_container_width=True, hide_index=True)

st.caption(f"⏱ Render: {time.time() - _t_start:.2f}s ({tab_choice})")
