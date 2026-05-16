# ── SETTINGS — edit these paths ───────────────────────────────────────────────
INPUT_FILE  = 'Bioreactor_현황판.xlsx'   # path to your Excel file
OUTPUT_FILE = 'gantt_import.csv'         # output CSV file name
SHEET_INDEX = 0                          # 0 = first sheet (배양기 일정)

# ── Install dependency if needed ───────────────────────────────────────────────
import subprocess, sys
subprocess.check_call([sys.executable, '-m', 'pip', 'install', 'openpyxl', '-q'])
print('✅ openpyxl ready')

# ── Imports ────────────────────────────────────────────────────────────────────
import openpyxl
from datetime import date
import csv
from collections import defaultdict

# ── Constants ──────────────────────────────────────────────────────────────────
VALID_FLOORS = {'6층', '5층', '7층'}
SKIP_VALUES  = {'-', 'w', ''}
CONT_PREFIX  = 'D'

MONTH_MAP = {
    'Jan':1,'Feb':2,'Mar':3,'Apr':4,'May':5,'Jun':6,
    'Jul':7,'Aug':8,'Sep':9,'Oct':10,'Nov':11,'Dec':12,
    'January':1,'February':2,'March':3,'April':4,'June':6,
    'July':7,'August':8,'September':9,'October':10,
    'November':11,'December':12
}

# Valid reactor IDs — must match utils.py INVENTORY_CONFIGS
VALID_IDS = set()
_INV = [
    ('5L',   1,  8, False, '6층'), ('5L',  1,  3, True,  '6층'),
    ('2L',   1, 10, False, '6층'), ('2L', 17, 22, False, '6층'),
    ('2L',  87, 92, False, '6층'), ('2L', 11, 16, False, '6층'),
    ('2L',  23, 46, False, '6층'), ('2L', 47, 74, False, '6층'),
    ('2L',  75, 86, False, '6층'), ('2L',  1, 24, True,  '6층'),
    ('Wave', 3,  5, False, '6층'),
    ('Wave', 1,  2, False, '5층'), ('5L',   1,  4, False, '5층'),
    ('10L',  1,  2, False, '5층'), ('50L',  1,  4, False, '5층'),
    ('200L', 1,  5, False, '5층'),
    ('2L',   1, 12, False, '7층'), ('Wave', 6,  7, False, '7층'),
    ('10L',  1,  2, False, '7층'), ('50L',  5,  6, False, '7층'),
    ('200L', 6,  6, False, '7층'),
]
for _sc, _s, _e, _isp, _room in _INV:
    for _i in range(_s, _e + 1):
        if _sc == '5L' and _isp: _n = f'P{_i:02d}'
        elif _isp: _n = f'P{_i}'
        else: _n = f'{_i:02d}'
        VALID_IDS.add(f'{_room}-{_sc}-{_n}')

print(f'✅ {len(VALID_IDS)} valid reactor IDs loaded')

# ── Helper functions ───────────────────────────────────────────────────────────
def normalise(floor, vessel):
    """Normalise vessel ID to match app format."""
    v = vessel.strip().replace(' ', '')
    if v.startswith('W-'):
        v = 'Wave-' + v[2:]
    parts = v.rsplit('-', 1)
    if len(parts) == 2:
        prefix, num = parts
        if num.startswith('P') and num[1:].isdigit():
            n = int(num[1:])
            num = f'P{n:02d}' if '5L' in prefix else f'P{n}'
        elif num.isdigit():
            num = f'{int(num):02d}'
        v = f'{prefix}-{num}'
    return f'{floor}-{v}'


def extract_user(cell):
    """
    Extract department + SME from cell comment (second line onwards).
    Comment format: '나준호(Joonho Na):\n배양 김다혜'
    Returns: '배양 김다혜' (not the creator name)
    """
    if not cell.comment:
        return 'Unknown'
    text = cell.comment.text.strip()
    if not text:
        return 'Unknown'
    lines = [l.strip() for l in text.split('\n') if l.strip()]
    if len(lines) >= 2:
        return ' '.join(lines[1:])  # dept + SME from second line onwards
    return 'Unknown'


def build_date_map(ws):
    """Build {col_index: date} from Row 1 (months) and Row 2 (days)."""
    month_starts = {}
    for cell in ws[1]:
        if cell.value and cell.column >= 3:
            parts = str(cell.value).strip().split()
            if len(parts) == 2:
                try:
                    yr = int(parts[0])
                    mo = MONTH_MAP.get(parts[1])
                    if mo:
                        month_starts[cell.column] = (yr, mo)
                except ValueError:
                    pass

    col_to_date = {}
    current_yr, current_mo = None, None
    for cell in ws[2]:
        col = cell.column
        if col < 3:
            continue
        if col in month_starts:
            current_yr, current_mo = month_starts[col]
        val = cell.value
        if val is None:
            continue
        if isinstance(val, (int, float)):
            day = int(val)
        elif hasattr(val, 'day'):
            day = val.day
        else:
            continue
        if current_yr and current_mo and 1 <= day <= 31:
            try:
                col_to_date[col] = date(current_yr, current_mo, day)
            except ValueError:
                pass
    return col_to_date

print('✅ Helper functions ready')

# ── Load Excel and extract bookings ────────────────────────────────────────────
print(f'Loading {INPUT_FILE}...')
wb = openpyxl.load_workbook(INPUT_FILE, read_only=False)
ws = wb.worksheets[SHEET_INDEX]
print(f'Sheet: {ws.title} | Rows: {ws.max_row} | Cols: {ws.max_column}')

col_to_date = build_date_map(ws)
dates = sorted(col_to_date.values())
print(f'Date range: {dates[0]} → {dates[-1]} ({len(col_to_date)} columns)')

all_bookings = []
warnings = []
skipped_floors = defaultdict(int)
reactor_count = 0
sorted_cols = sorted(col_to_date.items())

for row in ws.iter_rows(min_row=3, max_row=ws.max_row, values_only=False):
    floor_cell  = row[0]
    vessel_cell = row[1]

    floor  = str(floor_cell.value).strip()  if floor_cell.value  else None
    vessel = str(vessel_cell.value).strip() if vessel_cell.value else None

    if not floor or not vessel:
        continue
    if floor not in VALID_FLOORS:
        skipped_floors[floor] += 1
        continue

    reactor_id = normalise(floor, vessel)
    if reactor_id not in VALID_IDS:
        warnings.append(f'Unknown reactor_id skipped: {reactor_id}')
        continue
    reactor_count += 1

    current_project = None
    current_user    = None
    booking_start   = None
    prev_date       = None

    for col, d in sorted_cols:
        cell = row[col - 1]
        raw  = cell.value
        val  = str(raw).strip() if raw is not None else ''

        is_skip = val in SKIP_VALUES
        is_cont = val.startswith(CONT_PREFIX) and len(val) > 1
        is_proj = val and not is_cont and not is_skip

        if is_proj:
            if current_project and booking_start:
                all_bookings.append({
                    'reactor_id': reactor_id, 'project': current_project,
                    'user': current_user, 'start': str(booking_start), 'end': str(prev_date)
                })
            current_project = val
            current_user    = extract_user(cell)
            booking_start   = d

        elif is_skip and current_project:
            all_bookings.append({
                'reactor_id': reactor_id, 'project': current_project,
                'user': current_user, 'start': str(booking_start), 'end': str(prev_date)
            })
            current_project = None
            current_user    = None
            booking_start   = None

        prev_date = d

    if current_project and booking_start:
        all_bookings.append({
            'reactor_id': reactor_id, 'project': current_project,
            'user': current_user, 'start': str(booking_start), 'end': str(prev_date)
        })

# Validate dates
valid_bookings = []
for b in all_bookings:
    try:
        s = date.fromisoformat(b['start'])
        e = date.fromisoformat(b['end'])
        if e < s:
            warnings.append(f'{b["reactor_id"]} | {b["project"]} | end < start — skipped')
        else:
            valid_bookings.append(b)
    except Exception:
        warnings.append(f'{b["reactor_id"]} | {b["project"]} | invalid date — skipped')

print(f'\n✅ Reactors processed : {reactor_count}')
print(f'✅ Bookings extracted  : {len(valid_bookings)}')
if skipped_floors:
    for f, c in skipped_floors.items():
        print(f'⚠️  Skipped floor: {repr(f)} ({c} rows)')
if warnings:
    print(f'\n⚠️  Warnings ({len(warnings)}):')
    for w in warnings:
        print(f'   {w}')

# ── Preview first 10 bookings ──────────────────────────────────────────────────
import pandas as pd
df_preview = pd.DataFrame(valid_bookings[:10])
print('\n=== Preview (first 10 bookings) ===')
print(df_preview.to_string(index=False))

# ── Write gantt_import.csv ─────────────────────────────────────────────────────
fields = ['booking_id', 'reactor_id', 'project', 'user', 'stage', 'method', 'start', 'end']

with open(OUTPUT_FILE, 'w', newline='', encoding='utf-8-sig') as f:
    writer = csv.DictWriter(f, fieldnames=fields)
    writer.writeheader()
    for i, b in enumerate(valid_bookings, 1):
        writer.writerow({
            'booking_id': f'GANTT_{i:04d}',
            'reactor_id': b['reactor_id'],
            'project':    b['project'],
            'user':       b['user'],
            'stage':      'N',
            'method':     'Fed-batch',
            'start':      b['start'],
            'end':        b['end'],
        })

print(f'\n✅ Saved: {OUTPUT_FILE}')
print(f'   Total bookings : {len(valid_bookings)}')
print(f'   → Upload to Bioreactor App → Admin → Section 3')
