import streamlit as st
import pandas as pd
import datetime
import plotly.graph_objects as go
import os
import re
import shutil

# --- CONFIGURATION ---
DATA_FILE = "Bioreactor_reservation.csv"
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
    ("Ambr15", "48way", "EQ00000257", 1, 4, False, "Ambr15"),
    ("Ambr15", "48way", "EQ00000256", 1, 4, False, "Ambr15"),
    ("Ambr15", "48way", "EQ00000258", 1, 4, False, "Ambr15"),
    ("Ambr15", "48way", "EQ00006443", 1, 4, False, "Ambr15"),
    ("Ambr15", "48way", "EQ00006444", 1, 4, False, "Ambr15")
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
            if scale == "Ambr15":
                # 1 station = 12 mini-bioreactors (operational unit per Samsung Bioepis convention)
                num_str = f"S{i}"
                r_id = f"{room}-{prefix}-{num_str}"
                display_name = f"[{room}] {scale} Station {i} (12 vessels)"
            else:
                if scale == "5L" and is_p: num_str = f"P{i:02d}"
                elif is_p: num_str = f"P{i}"
                else: num_str = f"{i:02d}"
                r_id = f"{room}-{prefix}-{num_str}"
                display_name = f"[{room}] {scale} {b_type} ({num_str})"
            inventory_list.append({"id": r_id, "name": display_name, "scale": scale, "type": b_type, "location": f"Room {room}", "status": "Active"})
    return pd.DataFrame(inventory_list)

# --- COST FUNCTIONS ---
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

def get_vessel_count(reactor_id, vessels_used=None):
    """
    Returns the number of physical vessels represented by one booking row.
    If vessels_used is provided (user-specified), use that value.
    Ambr15 stations default to 12 mini-bioreactors if not specified.
    All other reactor types represent 1 vessel per booking row.
    """
    parts = reactor_id.split('-')
    if len(parts) >= 3 and parts[0] == 'Ambr15' and parts[-1].startswith('S'):
        if vessels_used is not None and not pd.isna(vessels_used):
            return int(vessels_used)
        return 12
    return 1

def calculate_project_cost(project_name, bookings_df, cost_matrix):
    """
    Calculate total cost for a project (N-stage only, selected scales only).
    Ambr15 stations are counted as 12 vessels each for cost purposes.
    Returns: dict with breakdown and total. Breakdown rows include both
    'stations' (booking row count) and 'vessels' (effective vessel count).
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
   
    # Compute per-row vessel count (1 for most, 12 for Ambr15 stations)
    n_bookings['vessel_count'] = n_bookings['reactor_id'].apply(get_vessel_count)
   
    breakdown = []
    total_cost = 0
   
    # Group by scale and method
    for (scale, method), group in n_bookings.groupby(['scale', 'method']):
        n_rows = len(group)
        vessels_sum = int(group['vessel_count'].sum())
        unit_cost = get_cost_for_scale_method(scale, method, cost_matrix)
        subtotal = vessels_sum * unit_cost # cost is per-vessel
        total_cost += subtotal

        # Route the row count to the appropriate column:
        #   2L / 200L (and other traditional)  → bioreactors
        #   Ambr250                            → vessels (1 per booking row)
        #   Ambr15                             → stations (rows) + vessels (× 12)
        if scale == 'Ambr15':
            bioreactors_count = '-'
            stations_count = n_rows
            vessels_count = vessels_sum
        elif scale == 'Ambr250':
            bioreactors_count = '-'
            stations_count = '-'
            vessels_count = vessels_sum
        else:
            bioreactors_count = n_rows
            stations_count = '-'
            vessels_count = '-'

        breakdown.append({
            'scale': scale,
            'method': method,
            'bioreactors': bioreactors_count,
            'stations': stations_count,
            'vessels': vessels_count,
            'qty': vessels_sum, # legacy key — kept for any caller still using 'qty'
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

    bookings_df = bookings_df.copy()
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
def check_availability(reactor_id, start_date, end_date, bookings, allow_same_day=True):
    if bookings.empty: return True
    check_start = pd.to_datetime(start_date)
    check_end = pd.to_datetime(end_date)
   
    subset = bookings[bookings['reactor_id'] == reactor_id].copy()
    if subset.empty: return True
   
    subset['start'] = pd.to_datetime(subset['start'], errors='coerce')
    subset['end'] = pd.to_datetime(subset['end'], errors='coerce')
   
    overlap = subset[(subset['start'] < check_end) & (subset['end'] > check_start)]
    if not overlap.empty: return False

    if not allow_same_day:
        buffer_end = check_start + pd.Timedelta(days=1)
        too_close = subset[subset['end'] >= check_start]
        if not too_close.empty: return False

    return True

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
# Korean public holidays 2025–2027 (verify lunar dates against KASI before each year)
KR_HOLIDAYS = {
    # 2025
    datetime.date(2025, 1, 1),
    datetime.date(2025, 1, 28), datetime.date(2025, 1, 29), datetime.date(2025, 1, 30),
    datetime.date(2025, 3, 1),
    datetime.date(2025, 5, 5),
    datetime.date(2025, 6, 6),
    datetime.date(2025, 8, 15),
    datetime.date(2025, 10, 3),
    datetime.date(2025, 10, 6), datetime.date(2025, 10, 7), datetime.date(2025, 10, 8),
    datetime.date(2025, 10, 9),
    datetime.date(2025, 12, 25),
    # 2026
    datetime.date(2026, 1, 1),
    datetime.date(2026, 2, 16), datetime.date(2026, 2, 17), datetime.date(2026, 2, 18),
    datetime.date(2026, 3, 1), datetime.date(2026, 3, 2),
    datetime.date(2026, 5, 5),
    datetime.date(2026, 5, 24), datetime.date(2026, 5, 25),
    datetime.date(2026, 6, 6),
    datetime.date(2026, 8, 15), datetime.date(2026, 8, 17),
    datetime.date(2026, 9, 24), datetime.date(2026, 9, 25), datetime.date(2026, 9, 26),
    datetime.date(2026, 10, 3), datetime.date(2026, 10, 5),
    datetime.date(2026, 10, 9),
    datetime.date(2026, 12, 25),
    # 2027
    datetime.date(2027, 1, 1),
    datetime.date(2027, 2, 6), datetime.date(2027, 2, 7), datetime.date(2027, 2, 8), datetime.date(2027, 2, 9),
    datetime.date(2027, 3, 1),
    datetime.date(2027, 5, 5), datetime.date(2027, 5, 13),
    datetime.date(2027, 6, 6), datetime.date(2027, 6, 7),
    datetime.date(2027, 8, 15), datetime.date(2027, 8, 16),
    datetime.date(2027, 9, 14), datetime.date(2027, 9, 15), datetime.date(2027, 9, 16),
    datetime.date(2027, 10, 3), datetime.date(2027, 10, 4),
    datetime.date(2027, 10, 9), datetime.date(2027, 10, 11),
    datetime.date(2027, 12, 25),
}

def create_gantt_chart(reactors, reactor_y_map, bookings_df, extra_shapes=None, extra_annotations=None, highlight_date=None, height_per_row=40, margin_top=120, y_domain_top=0.99):
    if not reactors: return go.Figure()
    n_reactors = len(reactors)
   
    total_height = (n_reactors * height_per_row) + margin_top + 10
   
    today_d = datetime.date.today()
    v_start = datetime.datetime.combine(today_d - datetime.timedelta(days=10), datetime.time.min)
    v_end = datetime.datetime.combine(today_d + datetime.timedelta(days=70), datetime.time.min)
   
    shapes = list(extra_shapes) if extra_shapes else []
    annotations = extra_annotations if extra_annotations else []
   
    # Grid
  

    for i, rid in enumerate(reactors):
        y = reactor_y_map[rid]
        if i % 2 == 0 or i == len(reactors) - 1:
            shapes.insert(0, dict(type="rect", xref="paper", yref="y", x0=0, x1=1, y0=y-0.5, y1=y+0.5, fillcolor="rgba(210,210,210,0.5)", layer="below", line_width=0))
  
    curr_d = v_start
    while curr_d <= v_end:
        is_month = (curr_d.day == 1)
        d_only = curr_d.date() if hasattr(curr_d, 'date') else curr_d
        is_weekend = d_only.weekday() >= 5 # 5=Sat, 6=Sun
        is_holiday = d_only in KR_HOLIDAYS

        # Light-red background band for weekends/holidays
        if is_weekend or is_holiday:
            next_d = curr_d + datetime.timedelta(days=1)
            shapes.append(dict(type="rect", x0=curr_d, x1=next_d, y0=-0.5, y1=n_reactors-0.5, yref="y",
                               fillcolor="rgba(255, 200, 200, 0.35)", line_width=0, layer="below"))

        shapes.append(dict(type="line", x0=curr_d, x1=curr_d, y0=-0.5, y1=n_reactors-0.5, yref="y", line=dict(color="black" if is_month else "#E0E0E0", width=3 if is_month else 1), layer="below"))
        curr_d += datetime.timedelta(days=1)
       
    # Bookingsy
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
                match = re.search(r"SB[ ._-]*(\d+)", clean_p, re.IGNORECASE)
                b_name = f"SB{int(match.group(1))}" if match else clean_p
               
                bg = PROJECT_BG_MAP.get(b_name, "#808080")
                fc = PROJECT_FONT_MAP.get(b_name, "black")
               
                shapes.append(dict(type="rect", x0=row['plot_start'], x1=row['plot_end'], y0=y-0.35, y1=y+0.35, fillcolor=bg, line=dict(width=1 if bg.upper()=='#FFFFFF' else 0, color="black"), layer="below"))
                shapes.append(dict(type="line", x0=row['plot_end'], x1=row['plot_end'], y0=y-0.35, y1=y+0.35, line=dict(color="black", width=3), layer="below"))
               
                mid = row['plot_start'] + (row['plot_end'] - row['plot_start'])/2
                days = (row['end'] - row['start']).days
                sx.append(mid); sy.append(y); stxt.append(f"{row['project']} ({days}d)"); sc.append(fc)
                sho.append(f"<b>{row['project']}</b><br>User: {row['user']}<br>{row['start'].date()} ~ {row['end'].date()}<br>({days} Days)")
               
    # Build set of (reactor_id, date) that are occupied by a booking
    occupied = set()
    if not bookings_df.empty:
        for _, brow in bookings_df.iterrows():
            if brow['reactor_id'] not in reactor_y_map: continue
            _bs = pd.to_datetime(brow['start']).date()
            _be = pd.to_datetime(brow['end']).date()
            _d = _bs
            while _d <= _be:
                occupied.add((brow['reactor_id'], _d))
                _d += datetime.timedelta(days=1)

    grid_x, grid_y, grid_hover = [], [], []
    _g_curr = v_start
    while _g_curr <= v_end:
        _g_date = _g_curr.date() if hasattr(_g_curr, 'date') else _g_curr
        _g_date_str = _g_curr.strftime("%Y-%m-%d (%a)")
        for _rid in reactors:
            if (_rid, _g_date) not in occupied:
                grid_x.append(_g_curr)
                grid_y.append(reactor_y_map[_rid])
                grid_hover.append(f"<b>{_rid}</b><br>{_g_date_str}")
        _g_curr += datetime.timedelta(days=1)

    fig = go.Figure()
    fig.add_trace(go.Scatter(x=[v_start, v_end], y=[-1, -1], xaxis="x2", mode="markers", marker=dict(opacity=0), showlegend=False, hoverinfo="skip"))
    fig.add_trace(go.Scatter(x=grid_x, y=grid_y, mode="markers", marker=dict(opacity=0, size=8), hovertext=grid_hover, hoverinfo="text", showlegend=False))
    if sx: fig.add_trace(go.Scatter(x=sx, y=sy, text=stxt, mode="text", textposition="middle center", textfont=dict(color=sc, size=13, family="Arial Black"), hovertext=sho, hoverinfo="text"))
    for ann in annotations: fig.add_annotation(ann)
    fig.add_vline(x=datetime.datetime.now().timestamp()*1000, line_width=2, line_color="#FF4B4B")
    if highlight_date:
        ts = datetime.datetime.combine(highlight_date, datetime.time.min).timestamp()*1000
        fig.add_vline(x=ts, line_width=2, line_color="blue")
        fig.add_vline(x=ts+86400000, line_width=2, line_color="blue")
   
    fig.update_layout(height=total_height, margin=dict(t=margin_top, l=215, r=10, b=10), showlegend=False, dragmode=False,
        xaxis=dict(side="top", type="date", tickformat="%d", dtick="D1", range=[v_start, v_end], showgrid=False, fixedrange=True, ticklabelmode="period"),
        xaxis2=dict(overlaying="x", side="top", anchor="free", position=1.0, type="date", tickformat="%B %Y", dtick="M1", range=[v_start, v_end], showgrid=False, tickfont=dict(size=22), fixedrange=True, ticklabelmode="period"),
        yaxis=dict(showticklabels=False, range=[-0.55, n_reactors-0.45], showgrid=False, domain=[0, y_domain_top], fixedrange=True, zeroline=False),
        shapes=shapes)
    return fig

# --- SIMULATION FOLDER PATHS ---
SIM_PENDING_DIR = os.path.join("simulations", "pending")
SIM_APPLIED_DIR = os.path.join("simulations", "applied")
SIM_BACKUP_DIR = os.path.join("simulations", "backups")
AUDIT_LOG_FILE = os.path.join("simulations", "audit_log.csv")
MAX_BACKUPS = 10

def _ensure_sim_dirs():
    for d in [SIM_PENDING_DIR, SIM_APPLIED_DIR, SIM_BACKUP_DIR]:
        os.makedirs(d, exist_ok=True)

def save_simulation(sandbox_df, real_df, submitted_by):
    """
    Compute diff between real and sandbox, save only changed rows to pending folder.
    Returns the filename saved.
    """
    _ensure_sim_dirs()
    real_ids = set(real_df['booking_id'].astype(str).tolist()) if not real_df.empty else set()
    sandbox_ids = set(sandbox_df['booking_id'].astype(str).tolist()) if not sandbox_df.empty else set()

    added_ids = sandbox_ids - real_ids
    removed_ids = real_ids - sandbox_ids

    added_df = sandbox_df[sandbox_df['booking_id'].astype(str).isin(added_ids)].copy() if added_ids else pd.DataFrame()
    removed_df = real_df[real_df['booking_id'].astype(str).isin(removed_ids)].copy() if removed_ids else pd.DataFrame()

    added_df['_diff_action'] = 'added'
    removed_df['_diff_action'] = 'removed'

    diff_df = pd.concat([added_df, removed_df], ignore_index=True)

    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_user = submitted_by.strip().replace(" ", "_")
    filename = f"SIM_{safe_user}_{ts}.csv"
    filepath = os.path.join(SIM_PENDING_DIR, filename)
    diff_df.to_csv(filepath, index=False)
    return filename

def load_pending_simulations():
    """
    Load metadata for all pending simulation CSVs.
    Returns list of dicts: filename, submitted_by, submitted_at, n_added, n_removed.
    """
    _ensure_sim_dirs()
    results = []
    for fname in sorted(os.listdir(SIM_PENDING_DIR)):
        if not fname.endswith('.csv'):
            continue
        fpath = os.path.join(SIM_PENDING_DIR, fname)
        try:
            df = pd.read_csv(fpath, dtype=str)
            n_added = int((df['_diff_action'] == 'added').sum()) if '_diff_action' in df.columns else 0
            n_removed = int((df['_diff_action'] == 'removed').sum()) if '_diff_action' in df.columns else 0
            parts = fname.replace('.csv', '').split('_')
            submitted_by = parts[1] if len(parts) > 1 else 'Unknown'
            ts_str = f"{parts[-2]}_{parts[-1]}" if len(parts) >= 3 else ''
            try:
                submitted_at = datetime.datetime.strptime(ts_str, "%Y%m%d_%H%M%S").strftime("%Y-%m-%d %H:%M:%S")
            except Exception:
                submitted_at = ''
            results.append({
                'filename': fname,
                'submitted_by': submitted_by,
                'submitted_at': submitted_at,
                'n_added': n_added,
                'n_removed': n_removed,
            })
        except Exception:
            continue
    return results

def apply_simulation_diff(filename, actioned_by):
    """
    Apply added/removed rows from a pending simulation CSV to real bookings.
    Auto-backs up before applying. Moves file to applied folder.
    Returns (n_added, n_removed).
    """
    _ensure_sim_dirs()
    filepath = os.path.join(SIM_PENDING_DIR, filename)
    diff_df = pd.read_csv(filepath, dtype=str)

    # Auto-backup before applying
    create_backup()

    real_df = load_data()

    added_df = diff_df[diff_df['_diff_action'] == 'added'].drop(columns=['_diff_action'])
    removed_df = diff_df[diff_df['_diff_action'] == 'removed'].drop(columns=['_diff_action'])

    n_added = len(added_df)
    n_removed = len(removed_df)

    # Remove rows marked for removal
    if not removed_df.empty:
        remove_ids = set(removed_df['booking_id'].astype(str).tolist())
        real_df = real_df[~real_df['booking_id'].astype(str).isin(remove_ids)]

    # Add new rows
    if not added_df.empty:
        added_df['start'] = pd.to_datetime(added_df['start'], errors='coerce')
        added_df['end'] = pd.to_datetime(added_df['end'], errors='coerce')
        added_df = added_df.dropna(subset=['start', 'end'])
        if 'method' not in added_df.columns:
            added_df['method'] = 'Fed-batch'
        real_df = pd.concat([real_df, added_df], ignore_index=True)

    save_data(real_df)

    # Move to applied folder
    applied_path = os.path.join(SIM_APPLIED_DIR, filename)
    shutil.move(filepath, applied_path)

    return n_added, n_removed

def create_backup():
    """
    Save a timestamped snapshot of current real bookings to backup folder.
    Keeps only the last MAX_BACKUPS backups.
    """
    _ensure_sim_dirs()
    real_df = load_data()
    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"BACKUP_{ts}.csv"
    filepath = os.path.join(SIM_BACKUP_DIR, filename)
    real_df.to_csv(filepath, index=False)

    # Enforce MAX_BACKUPS limit — delete oldest if exceeded
    all_backups = sorted([
        f for f in os.listdir(SIM_BACKUP_DIR) if f.startswith('BACKUP_') and f.endswith('.csv')
    ])
    while len(all_backups) > MAX_BACKUPS:
        oldest = os.path.join(SIM_BACKUP_DIR, all_backups.pop(0))
        os.remove(oldest)
    return filename

def load_backups():
    """
    Load metadata for all backup files.
    Returns list of dicts: filename, created_at, n_bookings — newest first.
    """
    _ensure_sim_dirs()
    results = []
    for fname in sorted(os.listdir(SIM_BACKUP_DIR), reverse=True):
        if not fname.endswith('.csv'):
            continue
        fpath = os.path.join(SIM_BACKUP_DIR, fname)
        try:
            df = pd.read_csv(fpath, dtype=str)
            ts_str = fname.replace('BACKUP_', '').replace('.csv', '')
            try:
                created_at = datetime.datetime.strptime(ts_str, "%Y%m%d_%H%M%S").strftime("%Y-%m-%d %H:%M:%S")
            except Exception:
                created_at = ''
            results.append({
                'filename': fname,
                'created_at': created_at,
                'n_bookings': len(df),
            })
        except Exception:
            continue
    return results

def restore_backup(filename):
    """
    Replace current real bookings with a backup file.
    Returns number of bookings restored.
    """
    _ensure_sim_dirs()
    fpath = os.path.join(SIM_BACKUP_DIR, filename)
    df = pd.read_csv(fpath, dtype=str)
    df['start'] = pd.to_datetime(df['start'], errors='coerce')
    df['end'] = pd.to_datetime(df['end'], errors='coerce')
    df = df.dropna(subset=['start', 'end'])
    if 'method' not in df.columns:
        df['method'] = 'Fed-batch'
    save_data(df)
    return len(df)

def log_audit(action, filename, submitted_by, actioned_by):
    """
    Append one row to the audit log CSV.
    Columns: timestamp, action, filename, submitted_by, actioned_by.
    """
    _ensure_sim_dirs()
    row = {
        'timestamp': datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        'action': action,
        'filename': filename,
        'submitted_by': submitted_by,
        'actioned_by': actioned_by,
    }
    write_header = not os.path.exists(AUDIT_LOG_FILE)
    with open(AUDIT_LOG_FILE, 'a', newline='', encoding='utf-8') as f:
        import csv
        writer = csv.DictWriter(f, fieldnames=row.keys())
        if write_header:
            writer.writeheader()
        writer.writerow(row)

def load_audit_log():
    """
    Load the full audit log.
    Returns DataFrame or empty DataFrame if no log exists.
    """
    if not os.path.exists(AUDIT_LOG_FILE):
        return pd.DataFrame(columns=['timestamp', 'action', 'filename', 'submitted_by', 'actioned_by'])
    try:
        return pd.read_csv(AUDIT_LOG_FILE, dtype=str)
    except Exception:
        return pd.DataFrame(columns=['timestamp', 'action', 'filename', 'submitted_by', 'actioned_by'])