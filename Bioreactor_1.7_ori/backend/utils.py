# Ported from Bioreactor_1.7_ori/utils.py — streamlit removed, all business logic preserved.
# All paths are absolute, rooted at DATA_DIR (defaults to the original Streamlit app folder).

import pandas as pd
import datetime
import os
import re
import csv

# --- PATH CONFIGURATION ---
_BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.environ.get(
    "DATA_DIR",
    os.path.normpath(os.path.join(_BACKEND_DIR, "..", "..", "Bioreactor_5"))
)
DATA_FILE = os.path.join(DATA_DIR, "Bioreactor_reservation.csv")

SIM_PENDING_DIR = os.path.join(DATA_DIR, "simulations", "pending")
SIM_APPLIED_DIR = os.path.join(DATA_DIR, "simulations", "applied")
SIM_BACKUP_DIR  = os.path.join(DATA_DIR, "simulations", "backups")
AUDIT_LOG_FILE  = os.path.join(DATA_DIR, "simulations", "audit_log.csv")
MAX_BACKUPS = 10

# --- COLORS (kept for API consumers that render client-side) ---
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
    'SB46': '#B8860B', 'SB47': '#FFFFFF', '수리중': '#808080', 'FSR': '#FFD700',
    'E304': '#008000', 'ILR': '#FFD700', 'E307': '#FFFFFF', 'NCR': '#FFD700',
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
    'SB46': '#008000', 'SB47': '#008000', '수리중': '#FF0000', 'FSR': '#FF0000',
    'E304': '#FFFFFF', 'ILR': '#FF0000', 'E307': '#FF0000', 'NCR': '#FF0000',
}

REACTOR_EQ_MAP = {
    "6층-5L-01": "EQ_411", "6층-5L-02": "EQ_412", "6층-5L-03": "EQ_413", "6층-5L-04": "EQ_414",
    "6층-5L-05": "EQ_415", "6층-5L-06": "EQ_416", "6층-5L-07": "EQ_417", "6층-5L-08": "EQ_418",
    "6층-5L-P01": "EQ_409", "6층-5L-P02": "EQ_410", "6층-5L-P03": "EQ_408", "6층-2L-01": "EQ_328",
    "6층-2L-02": "EQ_329", "6층-2L-03": "EQ_330", "6층-2L-04": "EQ_331", "6층-2L-05": "EQ_332",
    "6층-2L-06": "EQ_333", "6층-2L-07": "EQ_334", "6층-2L-08": "EQ_337", "6층-2L-09": "EQ_338",
    "6층-2L-10": "EQ_339", "6층-2L-11": "EQ_310", "6층-2L-12": "EQ_311", "6층-2L-13": "EQ_312",
    "6층-2L-14": "EQ_313", "6층-2L-15": "EQ_314", "6층-2L-16": "EQ_315", "6층-2L-17": "EQ_320",
    "6층-2L-18": "EQ_321", "6층-2L-19": "EQ_316", "6층-2L-20": "EQ_317", "6층-2L-21": "EQ_318",
    "6층-2L-22": "EQ_319", "6층-2L-23": "EQ_6495", "6층-2L-24": "EQ_6496", "6층-2L-25": "EQ_6497",
    "6층-2L-26": "EQ_6498", "6층-2L-27": "EQ_6499", "6층-2L-28": "EQ_6500", "6층-2L-29": "EQ_6501",
    "6층-2L-30": "EQ_6502", "6층-2L-31": "EQ_6503", "6층-2L-32": "EQ_6504", "6층-2L-33": "EQ_6505",
    "6층-2L-34": "EQ_6506", "6층-2L-35": "EQ_6507", "6층-2L-36": "EQ_6508", "6층-2L-37": "EQ_6509",
    "6층-2L-38": "EQ_6510", "6층-2L-39": "EQ_6511", "6층-2L-40": "EQ_6512", "6층-2L-41": "EQ_6513",
    "6층-2L-42": "EQ_6514", "6층-2L-43": "EQ_6515", "6층-2L-44": "EQ_6516", "6층-2L-45": "EQ_6517",
    "6층-2L-46": "EQ_6518", "6층-2L-47": "EQ_340", "6층-2L-48": "EQ_341", "6층-2L-49": "EQ_342",
    "6층-2L-50": "EQ_343", "6층-2L-51": "EQ_344", "6층-2L-52": "EQ_345", "6층-2L-53": "EQ_346",
    "6층-2L-54": "EQ_347", "6층-2L-55": "EQ_348", "6층-2L-56": "EQ_349", "6층-2L-57": "EQ_350",
    "6층-2L-58": "EQ_351", "6층-2L-59": "EQ_352", "6층-2L-60": "EQ_353", "6층-2L-61": "EQ_354",
    "6층-2L-62": "EQ_355", "6층-2L-63": "EQ_356", "6층-2L-64": "EQ_357", "6층-2L-65": "EQ_358",
    "6층-2L-66": "EQ_359", "6층-2L-67": "EQ_360", "6층-2L-68": "EQ_361", "6층-2L-69": "EQ_362",
    "6층-2L-70": "EQ_363", "6층-2L-71": "EQ_364", "6층-2L-72": "EQ_365", "6층-2L-73": "EQ_366",
    "6층-2L-74": "EQ_367", "6층-2L-75": "EQ_394", "6층-2L-76": "EQ_395", "6층-2L-77": "EQ_396",
    "6층-2L-78": "EQ_397", "6층-2L-79": "EQ_398", "6층-2L-80": "EQ_399", "6층-2L-81": "EQ_400",
    "6층-2L-82": "EQ_401", "6층-2L-83": "EQ_402", "6층-2L-84": "EQ_403", "6층-2L-85": "EQ_404",
    "6층-2L-86": "EQ_405", "6층-2L-87": "EQ_322", "6층-2L-88": "EQ_323", "6층-2L-89": "EQ_324",
    "6층-2L-90": "EQ_325", "6층-2L-91": "EQ_326", "6층-2L-92": "EQ_327", "6층-2L-P1": "EQ_368",
    "6층-2L-P2": "EQ_369", "6층-2L-P3": "EQ_370", "6층-2L-P4": "EQ_371", "6층-2L-P5": "EQ_372",
    "6층-2L-P6": "EQ_373", "6층-2L-P7": "EQ_374", "6층-2L-P8": "EQ_375", "6층-2L-P9": "EQ_376",
    "6층-2L-P10": "EQ_377", "6층-2L-P11": "EQ_378", "6층-2L-P12": "EQ_379", "6층-2L-P13": "EQ_380",
    "6층-2L-P14": "EQ_381", "6층-2L-P15": "EQ_382", "6층-2L-P16": "EQ_383", "6층-2L-P17": "EQ_384",
    "6층-2L-P18": "EQ_385", "6층-2L-P19": "EQ_386", "6층-2L-P20": "EQ_387", "6층-2L-P21": "EQ_388",
    "6층-2L-P22": "EQ_389", "6층-2L-P23": "EQ_390", "6층-2L-P24": "EQ_391", "6층-Wave-03": "EQ_6408",
    "6층-Wave-04": "EQ_6409", "6층-Wave-05": "EQ_6410", "5층-Wave-01": "EQ_432", "5층-Wave-02": "EQ_433",
    "5층-5L-01": "EQ_419", "5층-5L-02": "EQ_420", "5층-5L-03": "EQ_421", "5층-5L-04": "EQ_422",
    "5층-10L-01": "EQ_423", "5층-10L-02": "EQ_424", "5층-50L-01": "EQ_425", "5층-50L-02": "EQ_426",
    "5층-50L-03": "EQ_427", "5층-50L-04": "EQ_428", "5층-200L-01": "EQ_429", "5층-200L-02": "EQ_430",
    "5층-200L-03": "EQ_431", "5층-200L-04": "EQ_5942", "5층-200L-05": "EQ_6078", "7층-2L-01": "EQ_4369",
    "7층-2L-02": "EQ_4370", "7층-2L-03": "EQ_4371", "7층-2L-04": "EQ_4372", "7층-2L-05": "EQ_4373",
    "7층-2L-06": "EQ_4374", "7층-2L-07": "EQ_4375", "7층-2L-08": "EQ_4376", "7층-2L-09": "EQ_4377",
    "7층-2L-10": "EQ_4378", "7층-2L-11": "EQ_4379", "7층-2L-12": "EQ_4380", "7층-Wave-06": "EQ_5940",
    "7층-Wave-07": "EQ_5941", "7층-10L-01": "EQ_5936", "7층-10L-02": "EQ_5937", "7층-50L-05": "EQ_434",
    "7층-50L-06": "EQ_5938", "7층-200L-06": "EQ_5939",
}

INVENTORY_CONFIGS = [
    ("5L", "Fed-batch", "5L", 1, 8, False, "6층"),
    ("5L", "Perfusion", "5L", 1, 3, True, "6층"),
    ("2L", "Double", "2L", 1, 10, False, "6층"),
    ("2L", "Double", "2L", 17, 22, False, "6층"),
    ("2L", "Double", "2L", 87, 92, False, "6층"),
    ("2L", "Single_Seed", "2L", 11, 16, False, "6층"),
    ("2L", "Single_New", "2L", 23, 46, False, "6층"),
    ("2L", "Single_300cc", "2L", 47, 74, False, "6층"),
    ("2L", "Single_150cc", "2L", 75, 86, False, "6층"),
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
    ("Ambr15", "48way", "EQ00006444", 1, 4, False, "Ambr15"),
]

# --- DATA HELPERS ---
def load_data() -> pd.DataFrame:
    if os.path.exists(DATA_FILE):
        encodings = ['utf-8-sig', 'utf-8', 'cp949', 'euc-kr', 'latin1', 'iso-8859-1']
        df = None
        for enc in encodings:
            try:
                df = pd.read_csv(DATA_FILE, dtype=str, encoding=enc)
                break
            except (UnicodeDecodeError, LookupError):
                continue
        if df is None:
            raise RuntimeError(f"Could not read {DATA_FILE} with any known encoding")
        df['start'] = pd.to_datetime(df['start'], errors='coerce')
        df['end']   = pd.to_datetime(df['end'],   errors='coerce')
        if 'method' not in df.columns:
            df['method'] = 'Unknown'
        df['method'] = df['method'].fillna('Unknown')
        if 'stage' in df.columns:
            df['stage'] = df['stage'].astype(str).str.strip()
            df.loc[df['stage'].str.lower() == 'ambr run', 'stage'] = 'N'
        return df.dropna(subset=['start', 'end'])
    return pd.DataFrame(columns=["booking_id", "reactor_id", "user", "start", "end", "project", "stage", "method"])


def save_data(df: pd.DataFrame):
    df.to_csv(DATA_FILE, index=False, encoding='utf-8-sig')


def generate_inventory() -> pd.DataFrame:
    inventory_list = []
    for scale, b_type, prefix, start, end, is_p, room in INVENTORY_CONFIGS:
        for i in range(start, end + 1):
            if scale == "Ambr15":
                num_str = f"S{i}"
                r_id = f"{room}-{prefix}-{num_str}"
                display_name = f"[{room}] {scale} Station {i} (12 vessels)"
            else:
                if scale == "5L" and is_p:
                    num_str = f"P{i:02d}"
                elif is_p:
                    num_str = f"P{i}"
                else:
                    num_str = f"{i:02d}"
                r_id = f"{room}-{prefix}-{num_str}"
                display_name = f"[{room}] {scale} {b_type} ({num_str})"
            inventory_list.append({
                "id": r_id,
                "name": display_name,
                "scale": scale,
                "type": b_type,
                "location": f"Room {room}",
                "status": "Active",
                "eq_num": REACTOR_EQ_MAP.get(r_id, ""),
            })
    return pd.DataFrame(inventory_list)


# --- AVAILABILITY CHECK ---
def check_availability(reactor_id: str, start_date, end_date, bookings: pd.DataFrame, allow_same_day=True) -> bool:
    if bookings.empty:
        return True
    check_start = pd.to_datetime(start_date)
    check_end   = pd.to_datetime(end_date)

    subset = bookings[bookings['reactor_id'] == reactor_id].copy()
    if 'booking_id' in subset.columns:
        subset = subset[~subset['booking_id'].astype(str).str.startswith('VBLOCK_')]
    if subset.empty:
        return True

    subset['start'] = pd.to_datetime(subset['start'], errors='coerce')
    subset['end']   = pd.to_datetime(subset['end'],   errors='coerce')

    overlap = subset[(subset['start'] < check_end) & (subset['end'] > check_start)]
    if not overlap.empty:
        return False

    if not allow_same_day:
        too_close = subset[subset['end'] >= check_start]
        if not too_close.empty:
            return False

    return True


def custom_sort_key(reactor_id: str):
    parts = reactor_id.split('-')
    if len(parts) < 3:
        return (99, 99, 99, 99)
    room, scale, num = parts[0].strip(), parts[1].strip(), parts[-1].strip()
    room_prio  = {"6층": 1, "5층": 2, "7층": 3}.get(room, 99)
    scale_prio = {"5L": 1, "2L": 2, "10L": 3, "50L": 4, "200L": 5, "Wave": 6}.get(scale, 99)
    is_pilot = 1 if 'P' in num else 0
    try:
        num_val = int(num.replace('P', ''))
    except ValueError:
        num_val = 0
    return (room_prio, scale_prio, is_pilot, num_val)


# --- SIMULATION FILE HELPERS ---
def _ensure_sim_dirs():
    for d in [SIM_PENDING_DIR, SIM_APPLIED_DIR, SIM_BACKUP_DIR]:
        os.makedirs(d, exist_ok=True)


def save_simulation(sandbox_df: pd.DataFrame, real_df: pd.DataFrame, submitted_by: str) -> str:
    """Compute diff between real and sandbox, save only changed rows to pending folder."""
    _ensure_sim_dirs()
    real_ids    = set(real_df['booking_id'].astype(str).tolist())    if not real_df.empty    else set()
    sandbox_ids = set(sandbox_df['booking_id'].astype(str).tolist()) if not sandbox_df.empty else set()

    added_ids   = sandbox_ids - real_ids
    removed_ids = real_ids - sandbox_ids

    added_df   = sandbox_df[sandbox_df['booking_id'].astype(str).isin(added_ids)].copy()   if added_ids   else pd.DataFrame()
    removed_df = real_df   [real_df   ['booking_id'].astype(str).isin(removed_ids)].copy() if removed_ids else pd.DataFrame()

    added_df['_diff_action']   = 'added'
    removed_df['_diff_action'] = 'removed'

    diff_df = pd.concat([added_df, removed_df], ignore_index=True)

    ts        = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_user = submitted_by.strip().replace(" ", "_")
    filename  = f"SIM_{safe_user}_{ts}.csv"
    filepath  = os.path.join(SIM_PENDING_DIR, filename)
    diff_df.to_csv(filepath, index=False, encoding='utf-8-sig')
    return filename


def apply_simulation_diff(filename: str, actioned_by: str):
    """Apply a pending simulation diff to live bookings. Returns (n_added, n_removed)."""
    _ensure_sim_dirs()
    filepath = os.path.join(SIM_PENDING_DIR, filename)
    diff_df  = pd.read_csv(filepath, dtype=str, encoding='utf-8-sig')

    create_backup()

    real_df    = load_data()
    added_df   = diff_df[diff_df['_diff_action'] == 'added'  ].drop(columns=['_diff_action'])
    removed_df = diff_df[diff_df['_diff_action'] == 'removed'].drop(columns=['_diff_action'])

    n_added   = len(added_df)
    n_removed = len(removed_df)

    if not removed_df.empty:
        remove_ids = set(removed_df['booking_id'].astype(str).tolist())
        real_df    = real_df[~real_df['booking_id'].astype(str).isin(remove_ids)]

    if not added_df.empty:
        added_df['start'] = pd.to_datetime(added_df['start'], errors='coerce')
        added_df['end']   = pd.to_datetime(added_df['end'],   errors='coerce')
        added_df          = added_df.dropna(subset=['start', 'end'])
        if 'method' not in added_df.columns:
            added_df['method'] = 'Fed-batch'
        real_df = pd.concat([real_df, added_df], ignore_index=True)

    save_data(real_df)

    applied_path = os.path.join(SIM_APPLIED_DIR, filename)
    os.rename(filepath, applied_path)
    return n_added, n_removed


def create_backup():
    """Save a timestamped snapshot of current live bookings. Keeps MAX_BACKUPS most recent."""
    _ensure_sim_dirs()
    real_df  = load_data()
    ts       = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"BACKUP_{ts}.csv"
    filepath = os.path.join(SIM_BACKUP_DIR, filename)
    real_df.to_csv(filepath, index=False, encoding='utf-8-sig')

    all_backups = sorted([
        f for f in os.listdir(SIM_BACKUP_DIR)
        if f.startswith('BACKUP_') and f.endswith('.csv')
    ])
    while len(all_backups) > MAX_BACKUPS:
        oldest = os.path.join(SIM_BACKUP_DIR, all_backups.pop(0))
        os.remove(oldest)


def log_audit(action: str, filename: str, submitted_by: str, actioned_by: str):
    """Append one row to the audit log CSV."""
    _ensure_sim_dirs()
    row = {
        'timestamp':    datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        'action':       action,
        'filename':     filename,
        'submitted_by': submitted_by,
        'actioned_by':  actioned_by,
    }
    write_header = not os.path.exists(AUDIT_LOG_FILE)
    with open(AUDIT_LOG_FILE, 'a', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=row.keys())
        if write_header:
            writer.writeheader()
        writer.writerow(row)
