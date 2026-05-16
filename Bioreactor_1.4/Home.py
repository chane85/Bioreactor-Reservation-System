import streamlit as st
import datetime
import time
import utils
import plotly.express as px

_t_start = time.time()

st.set_page_config(page_title="Bioreactor Manager", layout="wide")

if 'inventory' not in st.session_state: st.session_state.inventory = utils.generate_inventory()
if 'bookings' not in st.session_state: st.session_state.bookings = utils.load_data()

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
    c1, c2 = st.columns([4, 1])
    c1.subheader("배양기 운용 현황판")
    hl_date = c2.date_input("🔍 Highlight Date", value=None, key="hl_bio")

    ids_6f = [r for r in st.session_state.inventory['id'] if r.startswith("6층")]
    ids_5f = [r for r in st.session_state.inventory['id'] if r.startswith("5층")]
    ids_7f = [r for r in st.session_state.inventory['id'] if r.startswith("7층")]

    o6_1, o6_2 = utils.calculate_generic_occupancy(ids_6f, st.session_state.bookings, m1_start, m1_end, m2_start, m2_end)
    o5_1, o5_2 = utils.calculate_generic_occupancy(ids_5f, st.session_state.bookings, m1_start, m1_end, m2_start, m2_end)
    o7_1, o7_2 = utils.calculate_generic_occupancy(ids_7f, st.session_state.bookings, m1_start, m1_end, m2_start, m2_end)

    m1, m2, m3, m4, m5, m6 = st.columns(6)
    m1.metric(f"{m1_start.strftime('%B')} (6층)", f"{o6_1:.1f}%")
    m2.metric(f"{m1_start.strftime('%B')} (5층)", f"{o5_1:.1f}%")
    m3.metric(f"{m1_start.strftime('%B')} (7층)", f"{o7_1:.1f}%")
    m4.metric(f"{m2_start.strftime('%B')} (6층)", f"{o6_2:.1f}%")
    m5.metric(f"{m2_start.strftime('%B')} (5층)", f"{o5_2:.1f}%")
    m6.metric(f"{m2_start.strftime('%B')} (7층)", f"{o7_2:.1f}%")
    st.divider()

    reactors = sorted([r for r in st.session_state.inventory['id'] if not r.startswith("Ambr")], key=utils.custom_sort_key)
    if reactors:
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
           
            # BIOREACTOR LABEL (Using Annotation for convenience)
            annots.append(dict(
                xref="paper", yref="y", x=-0.05, y=y,
                text=f"<b>{'-'.join(rid.split('-')[1:])}</b>",
                showarrow=False, xanchor="center", yanchor="middle",
                font=dict(color="black", size=14),
                bgcolor=c, bordercolor="black", borderwidth=1,
                width=65, height=H_ROW-2
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
                x=-0.09, y=(min_y+max_y)/2, 
                text=f"<b>{fl}</b>", 
                showarrow=False, xanchor="center", yanchor="middle", 
                font=dict(color="black", size=16),
                # Using Annotation ensures COLOR is visible
                bgcolor=c, bordercolor="black", borderwidth=1, 
                width=60, height=pixel_height
            ))
            
        fig = utils.create_gantt_chart(reactors, y_map, st.session_state.bookings, extra_shapes=shapes, extra_annotations=annots, highlight_date=hl_date, height_per_row=H_ROW)
        st.plotly_chart(fig, use_container_width=True)

# --- TAB 2: AMBR 250 ---
elif tab_choice == "Ambr250":
    c1, c2 = st.columns([4, 1])
    c1.subheader("Ambr 250 Schedule")
    hl_250 = c2.date_input("🔍 Highlight Date", value=None, key="hl_250")
   
    config_order = [conf[2] for conf in utils.INVENTORY_CONFIGS if conf[0] == "Ambr250"]
    units = sorted([r for r in st.session_state.inventory['id'] if r.startswith("Ambr250")],
                   key=lambda x: config_order.index(x.split("-")[1]) if x.split("-")[1] in config_order else 999)
   
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

        fig = utils.create_gantt_chart(units, y_map, st.session_state.bookings, extra_shapes=shapes, extra_annotations=annots, highlight_date=hl_250, height_per_row=H_ROW, margin_top=160)
        st.plotly_chart(fig, use_container_width=True)

# --- TAB 3: AMBR 15 ---
else: # Ambr15
    c1, c2 = st.columns([4, 1])
    c1.subheader("Ambr 15 Schedule")
    hl_15 = c2.date_input("🔍 Highlight Date", value=None, key="hl_15")
   
    config_order = [conf[2] for conf in utils.INVENTORY_CONFIGS if conf[0] == "Ambr15"]
    units = sorted([r for r in st.session_state.inventory['id'] if r.startswith("Ambr15")],
                   key=lambda x: config_order.index(x.split("-")[1]) if x.split("-")[1] in config_order else 999)

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
            pixel_height = (row_count * H_ROW) - 10.6
            
            # [FIX] Use annots.append (NOT shapes) to ensure Background Color appears
            annots.append(dict(
                xref="paper", yref="y", x=-0.06, y=(min_y+max_y)/2, 
                text=f"<b>{eq_id.replace('EQ0000','')}</b>", 
                showarrow=False, xanchor="center", yanchor="middle", 
                font=dict(color="black", size=12),
                bgcolor="#FFDAC1", bordercolor="black", borderwidth=1, 
                width=80, height=pixel_height
            ))

        fig = utils.create_gantt_chart(units, y_map, st.session_state.bookings, extra_shapes=shapes, extra_annotations=annots, highlight_date=hl_15, height_per_row=H_ROW, margin_top=50)
        st.plotly_chart(fig, use_container_width=True)

st.caption(f"⏱ Render: {time.time() - _t_start:.2f}s ({tab_choice})")