import streamlit as st
import pandas as pd
import datetime
import plotly.graph_objects as go
import os
import re

# --- CONFIGURATION ---
DATA_FILE = "Bioreactor_reservation.csv"
COST_FILE = "배치_단가.csv"
ADMIN_PASSWORD = "bio135"

# --- COLORS ---
PROJECT_BG_MAP = {
    'SB2': '#800080', 'SB3': '#008000', 'SB4': '#800020', 'SB5': '#FFA500',
    'SB8': '#0000FF', 'SB9': '#FF0000', 'SB11': '#000000', 'SB12': '#B8860B',
    'SB13': '#808080', 'SB14': '#FFFFFF', 'SB15': '#800080', 'SB16': '#008000',
    'SB17': '#FFA500', 'SB19': '#FF0000', 'SB20': '#B8860B', 'SB21': '#808080',
    'SB22': '#FFA500', 'SB23': '#FFD700', 'SB24': '#B8860B', 'SB25': '#FFFFFF',
    'SB26': '#800080', 'SB27': '#008000', 'SB28': '#0909FF', 'SB29': '#FFA500',
    'SB30': '#FFD700', 'SB31': '#0000FF', 'SB32': '#FF0000', 'SB33': '#000000',
    'SB34': '#B8860B', 'SB35': '#808080', 'SB36': '#FFFFFF', 'SB37': '#800080',
    'SB38': '#008000', 'SB39': '#F28500', 'SB40': '#FFD700', 'SB41': '#FF0000',
    'SB42': '#B8860B', 'SB43': '#808080', 'SB44': '#FFA500', 'SB45': '#FFD700',
    'SB46': '#B8860B', 'SB47': '#FFFFFF', '수리중': '#808080', 'FSR':'#FFD700',
    'E304':'#008000', 'ILR':'#FFD700', 'E307':'#FFFFFF', 'NCR':'#FFD700'
}

PROJECT_FONT_MAP = {
    'SB2': '#FFFFFF', 'SB3': '#FFFFFF', 'SB4': '#FFFFFF', 'SB5': '#FFFFFF',
    'SB8': '#FFFFFF', 'SB9': '#FFFFFF', 'SB11': '#FFFFFF', 'SB12': '#000000',
    'SB13': '#000000', 'SB14': '#000000', 'SB15': '#008000', 'SB16': '#000000',
    'SB17': '#000000', 'SB19': '#000000', 'SB20': '#FFFFFF', 'SB21': '#FFFFFF',
    'SB22': '#008000', 'SB23': '#008000', 'SB24': '#008000', 'SB25': '#008000',
    'SB26': '#FFFFFF', 'SB27': '#FFFFFF', 'SB28': '#FFFFFF', 'SB29': '#FFFFFF',
    'SB30': '#000000', 'SB31': '#FFFFFF', 'SB32': '#FFFFFF', 'SB33': '#FFFFFF',
    'SB34': '#000000', 'SB35': '#000000', 'SB36': '#000000', 'SB37': '#008000',
    'SB38': '#000000', 'SB39': '#000000', 'SB40': '#FFFFFF', 'SB41': '#000000',
    'SB42': '#FFFFFF', 'SB43': '#FFFFFF', 'SB44': '#008000', 'SB45': '#008000',
    'SB46': '#008000', 'SB47': '#008000', '수리중': '#FF0000', 'FSR':'#FF0000',
    'E304':'#FFFFFF', 'ILR':'#FF0000', 'E307':'#FF0000', 'NCR':'#FF0000'
}

INVENTORY_CONFIGS = [
    ("5L", "Fed-batch", "5L", 1, 8, False, "6층"),
    ("5L", "Perfusion", "5L", 1, 3, True, "6층"),
    ("2L", "Double", "2L", 1, 10, False, "6층"),
    ("2L", "Double", "2L", 17, 22, False, "6층"),
    ("2L", "Double", "2L", 87, 92, False, "6층"),
    ("2L", "Single_Seed", "2L", 11, 16, False, "6층"),
    ("2L", "Single_New", "2L", 23, 46, False, "6층"),
    ("2L", "Single_300cc","2L", 47, 74, False, "6층"),
    ("2L", "Single_150cc","2L", 75, 86, False, "6층"),
    ("2L", "Perfusion", "2L", 1, 24, True, "6층"),
    ("Wave", "Wave", "Wave", 3, 5, False, "6층"),
    ("Wave", "Wave", "Wave", 1, 2, False, "5층"),
    ("5L", "Fed-batch", "5L", 1, 4, False, "5층"),
    ("10L", "Fed-batch", "10L", 1, 2, False, "5층"),
    ("50L", "Fed-batch", "50L", 1, 2, False, "5층"),
    ("50L", "Fed-batch", "50L", 3, 4, False, "5층"),
    ("200L", "Fed-batch", "200L", 1, 5, False, "5층"),
    ("Wave", "Wave", "Wave", 6, 7, False, "7층"),
    ("2L", "Fed-batch", "2L", 1, 12, False, "7층"),
    ("10L", "Fed-batch", "10L", 1, 2, False, "7층"),
    ("50L", "Fed-batch", "50L", 5, 6, False, "7층"),
    ("200L", "Fed-batch", "200L", 6, 6, False, "7층"),
    ("Ambr250", "24way", "EQ00005350", 1, 24, False, "Ambr250"),
    ("Ambr250", "12way", "EQ00000259", 1, 12, False, "Ambr250"),
    ("Ambr250", "12way", "EQ00006418", 1, 12, False, "Ambr250"),
    ("Ambr250", "12way", "EQ00005349", 1, 12, False, "Ambr250"),
    ("Ambr250", "12way", "EQ00005348", 1, 12, False, "Ambr250"),
    ("Ambr250", "12way", "EQ00006417", 1, 12, False, "Ambr250"),
    ("Ambr250", "12way", "EQ00006416", 1, 12, False, "Ambr250"),
    ("Ambr250", "12way", "EQ00006419", 1, 12, False, "Ambr250"),
    ("Ambr250", "12way", "EQ00005678", 1, 12, False, "Ambr250"),
    ("Ambr15", "48way", "EQ00000257", 1, 48, False, "Ambr15"),
    ("Ambr15", "48way", "EQ00000256", 1, 48, False, "Ambr15"),
    ("Ambr15", "48way", "EQ00000258", 1, 48, False, "Ambr15"),
    ("Ambr15", "48way", "EQ00006443", 1, 48, False, "Ambr15"),
    ("Ambr15", "48way", "EQ00006444", 1, 48, False, "Ambr15")
]

# --- DATA HELPERS ---
def load_data():
    if os.path.exists(DATA_FILE):
        try:
            # Try multiple encodings for the reservation CSV file
            encodings = ['utf-8', 'utf-8-sig', 'cp949', 'euc-kr', 'latin1', 'iso-8859-1']
            df = None
           
            for encoding in encodings:
                try:
                    df = pd.read_csv(DATA_FILE, dtype=str, encoding=encoding)
                    break
                except (UnicodeDecodeError, LookupError):
                    continue
           
            if df is None:
                st.error(f"Could not read {DATA_FILE} with any known encoding")
                return pd.DataFrame(columns=["booking_id", "reactor_id", "user", "start", "end", "project", "stage", "method"])
           
            df['start'] = pd.to_datetime(df['start'], errors='coerce')
            df['end'] = pd.to_datetime(df['end'], errors='coerce')
           
            # Add 'method' column if it doesn't exist (for legacy data)
            if 'method' not in df.columns:
                df['method'] = 'Unknown'
           
            # Fill NaN values in method column with 'Unknown'
            df['method'] = df['method'].fillna('Unknown')
           
            return df.dropna(subset=['start', 'end'])
        except Exception as e:
            st.error(f"⚌ DATA LOAD ERROR: {e}")
    return pd.DataFrame(columns=["booking_id", "reactor_id", "user", "start", "end", "project", "stage", "method"])

def save_data(df):
    df.to_csv(DATA_FILE, index=False)

def generate_inventory():
    inventory_list = []
    for scale, b_type, prefix, start, end, is_p, room in INVENTORY_CONFIGS:
        for i in range(start, end + 1):
            if scale == "5L" and is_p: num_str = f"P{i:02d}"
            elif is_p: num_str = f"P{i}"
            else: num_str = f"{i:02d}"
            r_id = f"{room}-{prefix}-{num_str}"
            inventory_list.append({"id": r_id, "name": f"[{room}] {scale} {b_type} ({num_str})", "scale": scale, "type": b_type, "location": f"Room {room}", "status": "Active"})
    return pd.DataFrame(inventory_list)

# --- COST FUNCTIONS ---
def load_cost_matrix():
    """Load cost data from CSV file"""
    if not os.path.exists(COST_FILE):
        st.warning(f"⚠️ Cost file '{COST_FILE}' not found. Cost calculations will be unavailable.")
        return pd.DataFrame(columns=['scale', 'method', 'cost'])
   
    try:
        # Try multiple encodings
        encodings = ['utf-8', 'utf-8-sig', 'cp949', 'euc-kr', 'latin1', 'iso-8859-1']
        df = None
       
        for encoding in encodings:
            try:
                df = pd.read_csv(COST_FILE, encoding=encoding)
                break
            except (UnicodeDecodeError, LookupError):
                continue
       
        if df is None:
            st.error(f"Could not read {COST_FILE} with any known encoding")
            return pd.DataFrame(columns=['scale', 'method', 'cost'])
       
        # Ensure column names are correct
        if 'Scale' in df.columns:
            df = df.rename(columns={'Scale': 'scale'})
        if 'Method' in df.columns:
            df = df.rename(columns={'Method': 'method'})
        if 'Cost' in df.columns:
            df = df.rename(columns={'Cost': 'cost'})
       
        # Clean data - REMOVE ALL SPACES
        df['scale'] = df['scale'].astype(str).str.strip().str.replace(' ', '')
        df['method'] = df['method'].astype(str).str.strip().str.replace(' ', '')
        df['cost'] = pd.to_numeric(df['cost'], errors='coerce')
       
        return df.dropna(subset=['scale', 'method', 'cost'])
    except Exception as e:
        st.error(f"Error loading cost file: {e}")
        return pd.DataFrame(columns=['scale', 'method', 'cost'])

def get_cost_for_scale_method(scale, method, cost_matrix):
    """Get unit cost for a specific scale-method combination"""
    if cost_matrix.empty:
        return 0
   
    result = cost_matrix[(cost_matrix['scale'] == scale) & (cost_matrix['method'] == method)]
    if not result.empty:
        return result.iloc[0]['cost']
    return 0

def extract_scale_from_reactor_id(reactor_id):
    """
    Extract scale from reactor_id
    Examples:
    - '6층-2L-01' → '2L'
    - 'Ambr250-EQ00005350-V01' → 'Ambr250'
    - '5층-200L-01' → '200L'
    """
    parts = reactor_id.split('-')
    if len(parts) >= 2:
        # For standard reactors: '6층-2L-01'
        if parts[1] in ['2L', '5L', '10L', '50L', '200L', 'Wave']:
            return parts[1]
        # For Ambr systems: 'Ambr250-...'
        if 'Ambr' in parts[0]:
            return parts[0]
    return None

def get_method_options_for_scale(scale):
    """Return available methods for a given scale"""
    method_map = {
        'Ambr15': ['Fed-batch'],
        'Ambr250': ['EFB', 'iEFB', 'EN1'],
        '2L': ['Fed-batch', 'EFB', 'iEFB', 'N1', 'EN1'],
        '5L': ['Fed-batch', 'EFB', 'iEFB', 'N1', 'EN1'],
        '10L': ['Fed-batch', 'EFB', 'iEFB', 'N1', 'EN1'],
        '50L': ['Fed-batch', 'EFB', 'iEFB', 'N1', 'EN1'],
        '200L': ['Fed-batch', 'EFB', 'iEFB', 'N1', 'EN1'],
        'Wave': ['Fed-batch']
    }
    return method_map.get(scale, ['Fed-batch'])

def calculate_project_cost(project_name, bookings_df, cost_matrix):
    """
    Calculate total cost for a project (N-stage only, selected scales only)
    Returns: dict with breakdown and total
    """
    if bookings_df.empty or cost_matrix.empty:
        return {'breakdown': [], 'total': 0}
   
    # Filter: only N-stage
    n_bookings = bookings_df[bookings_df['stage'] == 'N'].copy()
   
    # Filter: only specific project
    n_bookings = n_bookings[n_bookings['project'] == project_name]
   
    if n_bookings.empty:
        return {'breakdown': [], 'total': 0}
   
    # Extract scale from reactor_id
    n_bookings['scale'] = n_bookings['reactor_id'].apply(extract_scale_from_reactor_id)
   
    # Filter: only Ambr15, Ambr250, 2L, 200L
    valid_scales = ['Ambr15', 'Ambr250', '2L', '200L']
    n_bookings = n_bookings[n_bookings['scale'].isin(valid_scales)]
   
    breakdown = []
    total_cost = 0
   
    # Group by scale and method
    for (scale, method), group in n_bookings.groupby(['scale', 'method']):
        qty = len(group)
        unit_cost = get_cost_for_scale_method(scale, method, cost_matrix)
        subtotal = qty * unit_cost
        total_cost += subtotal
       
        breakdown.append({
            'scale': scale,
            'method': method,
            'qty': qty,
            'unit_cost': unit_cost,
            'subtotal': subtotal
        })
   
    return {'breakdown': breakdown, 'total': total_cost}

def calculate_monthly_costs(start_date, end_date, bookings_df, cost_matrix):
    """
    Calculate costs for all projects within a date range
    Returns: list of dicts with project-level costs
    """
    if bookings_df.empty or cost_matrix.empty:
        return []
   
    # Filter bookings by date range
    bookings_df['start'] = pd.to_datetime(bookings_df['start'])
    bookings_df['end'] = pd.to_datetime(bookings_df['end'])
   
    start_dt = pd.to_datetime(start_date)
    end_dt = pd.to_datetime(end_date)
   
    # Bookings that overlap with the date range
    filtered = bookings_df[
        (bookings_df['start'] <= end_dt) &
        (bookings_df['end'] >= start_dt)
    ]
   
    results = []
    for project in filtered['project'].unique():
        cost_data = calculate_project_cost(project, filtered, cost_matrix)
        if cost_data['total'] > 0:
            results.append({
                'project': project,
                'n_stage_reactors': sum([b['qty'] for b in cost_data['breakdown']]),
                'total_cost': cost_data['total']
            })
   
    return results

# --- AVAILABILITY CHECK ---
def check_availability(reactor_id, start_date, end_date, bookings):
    if bookings.empty: return True
    check_start = pd.to_datetime(start_date)
    check_end = pd.to_datetime(end_date)
   
    subset = bookings[bookings['reactor_id'] == reactor_id].copy()
    if subset.empty: return True
   
    subset['start'] = pd.to_datetime(subset['start'], errors='coerce')
    subset['end'] = pd.to_datetime(subset['end'], errors='coerce')
   
    overlap = subset[(subset['start'] < check_end) & (subset['end'] > check_start)]
    return overlap.empty

def custom_sort_key(reactor_id):
    parts = reactor_id.split('-')
    if len(parts) < 3: return (99, 99, 99, 99)
    room, scale, num = parts[0].strip(), parts[1].strip(), parts[-1].strip()
    room_prio = {"6층":1, "5층":2, "7층":3}.get(room, 99)
    scale_prio = {"5L":1, "2L":2, "10L":3, "50L":4, "200L":5, "Wave":6}.get(scale, 99)
    is_pilot = 1 if 'P' in num else 0
    try: num_val = int(num.replace('P', ''))
    except: num_val = 0
    return (room_prio, scale_prio, is_pilot, num_val)

# --- METRIC HELPERS ---
def get_month_ranges():
    today = datetime.date.today()
    m1_start = today.replace(day=1)
    m2_start = (m1_start + datetime.timedelta(days=32)).replace(day=1)
    m3_start = (m2_start + datetime.timedelta(days=32)).replace(day=1)
    m1_end, m2_end = m2_start - datetime.timedelta(days=1), m3_start - datetime.timedelta(days=1)
    return m1_start, m1_end, m2_start, m2_end

def calculate_generic_occupancy(reactor_ids, bookings_df, m1_start, m1_end, m2_start, m2_end):
    total_units = len(reactor_ids)
    if total_units == 0: return 0.0, 0.0
    cap_m1 = max(total_units * ((m1_end - m1_start).days + 1), 1)
    cap_m2 = max(total_units * ((m2_end - m2_start).days + 1), 1)
    occ_m1, occ_m2 = 0, 0
    if not bookings_df.empty:
        df = bookings_df[bookings_df['reactor_id'].isin(reactor_ids)].copy()
        if not df.empty:
            df['start'] = pd.to_datetime(df['start']).dt.date
            df['end'] = pd.to_datetime(df['end']).dt.date
            for _, row in df.iterrows():
                 o1_s, o1_e = max(row['start'], m1_start), min(row['end'], m1_end)
                 if o1_s <= o1_e: occ_m1 += (o1_e - o1_s).days + 1
                 o2_s, o2_e = max(row['start'], m2_start), min(row['end'], m2_end)
                 if o2_s <= o2_e: occ_m2 += (o2_e - o2_s).days + 1
    return (occ_m1 / cap_m1) * 100, (occ_m2 / cap_m2) * 100

# --- UNIFIED PLOTTING ENGINE ---
def create_gantt_chart(reactors, reactor_y_map, bookings_df, extra_shapes=None, extra_annotations=None, highlight_date=None, height_per_row=40, margin_top=120):
    if not reactors: return go.Figure()
    n_reactors = len(reactors)
   
    total_height = (n_reactors * height_per_row) + margin_top + 10
   
    today_d = datetime.date.today()
    v_start = datetime.datetime.combine(today_d - datetime.timedelta(days=10), datetime.time.min)
    v_end = datetime.datetime.combine(today_d + datetime.timedelta(days=70), datetime.time.min)
   
    shapes = extra_shapes if extra_shapes else []
    annotations = extra_annotations if extra_annotations else []
   
    # Grid
    for i, rid in enumerate(reactors):
        y = reactor_y_map[rid]
        if i % 2 == 0:
            shapes.append(dict(type="rect", xref="paper", yref="y", x0=0, x1=1, y0=y-0.5, y1=y+0.5, fillcolor="rgba(210,210,210,0.5)", layer="below", line_width=0))
    curr_d = v_start
    while curr_d <= v_end:
        is_month = (curr_d.day == 1)
        shapes.append(dict(type="line", x0=curr_d, x1=curr_d, y0=-0.5, y1=n_reactors-0.5, yref="y", line=dict(color="black" if is_month else "#E0E0E0", width=3 if is_month else 1), layer="below"))
        curr_d += datetime.timedelta(days=1)
       
    # Bookings
    sx, sy, stxt, sho, sc = [], [], [], [], []
    if not bookings_df.empty:
        df_viz = bookings_df[bookings_df['reactor_id'].isin(reactors)].copy()
        if not df_viz.empty:
            df_viz['start'] = pd.to_datetime(df_viz['start'], errors='coerce')
            df_viz['end'] = pd.to_datetime(df_viz['end'], errors='coerce')
            df_viz = df_viz.dropna(subset=['start', 'end'])
           
            # SPLIT LOGIC
            df_viz = df_viz.sort_values(by=['reactor_id', 'start']).reset_index(drop=True)
            df_viz['plot_start'] = df_viz['start']
            df_viz['plot_end'] = df_viz['end'] + pd.Timedelta(hours=23, minutes=59, seconds=59)
            s_norm = df_viz['start'].dt.normalize()
            e_norm = df_viz['end'].dt.normalize()

            for i in range(len(df_viz) - 1):
                if df_viz.iloc[i]['reactor_id'] == df_viz.iloc[i+1]['reactor_id']:
                    if e_norm.iloc[i] == s_norm.iloc[i+1]:
                        meet_day = e_norm.iloc[i]
                        df_viz.at[i, 'plot_end'] = meet_day + pd.Timedelta(hours=12)
                        df_viz.at[i+1, 'plot_start'] = meet_day + pd.Timedelta(hours=12)

            for _, row in df_viz.iterrows():
                rid = row['reactor_id']
                if rid not in reactor_y_map: continue
                y = reactor_y_map[rid]
                clean_p = str(row['project']).strip()
                match = re.search(r"SB[ ._-]*(d+)", clean_p, re.IGNORECASE)
                b_name = f"SB{int(match.group(1))}" if match else clean_p
               
                bg = PROJECT_BG_MAP.get(b_name, "#808080")
                fc = PROJECT_FONT_MAP.get(b_name, "black")
               
                shapes.append(dict(type="rect", x0=row['plot_start'], x1=row['plot_end'], y0=y-0.35, y1=y+0.35, fillcolor=bg, line=dict(width=1 if bg.upper()=='#FFFFFF' else 0, color="black"), layer="below"))
                shapes.append(dict(type="line", x0=row['plot_end'], x1=row['plot_end'], y0=y-0.35, y1=y+0.35, line=dict(color="black", width=3), layer="below"))
               
                mid = row['plot_start'] + (row['plot_end'] - row['plot_start'])/2
                days = (row['end'] - row['start']).days
                sx.append(mid); sy.append(y); stxt.append(f"{row['project']} ({days}d)"); sc.append(fc)
                sho.append(f"<b>{row['project']}</b><br>User: {row['user']}<br>{row['start'].date()} ~ {row['end'].date()}<br>({days} Days)")
               
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=[v_start, v_end], y=[-1, -1], xaxis="x2", mode="markers", marker=dict(opacity=0), showlegend=False, hoverinfo="skip"))
    if sx: fig.add_trace(go.Scatter(x=sx, y=sy, text=stxt, mode="text", textposition="middle center", textfont=dict(color=sc, size=13, family="Arial Black"), hovertext=sho, hoverinfo="text"))
   
    for ann in annotations: fig.add_annotation(ann)
    fig.add_vline(x=datetime.datetime.now().timestamp()*1000, line_width=2, line_color="#FF4B4B")
    if highlight_date:
        ts = datetime.datetime.combine(highlight_date, datetime.time.min).timestamp()*1000
        fig.add_vline(x=ts, line_width=2, line_color="blue")
        fig.add_vline(x=ts+86400000, line_width=2, line_color="blue")
   
    fig.update_layout(height=total_height, margin=dict(t=margin_top, l=215, r=10, b=10), showlegend=False, dragmode=False,
        xaxis=dict(side="top", type="date", tickformat="%d", dtick="D1", range=[v_start, v_end], showgrid=False, fixedrange=True, ticklabelmode="period"),
        xaxis2=dict(overlaying="x", side="top", position=1, type="date", tickformat="%B %Y", dtick="M1", range=[v_start, v_end], showgrid=False, tickfont=dict(size=22), fixedrange=True, ticklabelmode="period"),
        yaxis=dict(showticklabels=False, range=[-0.5, n_reactors-0.5], showgrid=False, domain=[0, 0.99], fixedrange=True),
        shapes=shapes)
    return fig