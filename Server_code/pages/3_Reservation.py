import streamlit as st
import pandas as pd
import datetime
import uuid
import utils
import auth

st.set_page_config(page_title="배양기 예약", layout="wide")

auth.render_sidebar_auth()
auth.require_role('editor')

# Ensure Data is Loaded
if 'inventory' not in st.session_state: st.session_state.inventory = utils.generate_inventory()
st.session_state.bookings = utils.load_data()

# --- [FIX] RESET INPUTS LOGIC (MUST BE AT THE TOP) ---
if 'reset_inputs' in st.session_state and st.session_state.reset_inputs:
    if 'proj_name_input' in st.session_state: st.session_state.proj_name_input = ""
    if 'user_name_input' in st.session_state: st.session_state.user_name_input = ""
    if 'ambr_proj_input' in st.session_state: st.session_state.ambr_proj_input = ""
    if 'ambr_sme_input' in st.session_state: st.session_state.ambr_sme_input = ""
    st.session_state.reset_inputs = False

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
    </style>
""", unsafe_allow_html=True)

tab_bio, tab_ambr = st.tabs(["Reservation Wizard", "Ambr Reservation"])

# --- BIOREACTOR WIZARD ---
with tab_bio:
    st.header("배양기 예약")

    # Scheduling mode selector (Forward = N-4 anchor, Reverse = N anchor)
    mode = st.radio(
        "배양기 예약",
        ["Forward (N-4부터)", "Reverse (본배양부터)"],
        horizontal=True,
        key="bio_schedule_mode"
    )
    is_reverse = mode.startswith("Reverse")

    # Clear stale campaign_plan if user toggled mode after Check Availability
    if st.session_state.get('_last_bio_mode') != mode:
        st.session_state.pop('campaign_plan', None)
        st.session_state._last_bio_mode = mode

    c1, c2, c3, _ = st.columns([1, 1, 1, 3])
    with c1:
        if 'proj_name_input' not in st.session_state: st.session_state.proj_name_input = ""
        project_name = st.text_input("제품명", value=st.session_state.proj_name_input, key="proj_name_input")
    with c2:
        if 'user_name_input' not in st.session_state: st.session_state.user_name_input = ""
        user_name = st.text_input("SME", value=st.session_state.user_name_input, key="user_name_input")
    with c3:
        date_label = "N 시작 일정" if is_reverse else "N-4 시작 일정"
        anchor_date = st.date_input(date_label, datetime.date.today())

    st.divider()
    st.markdown("### 🛠️ 배양기 예약")

    h1, h2, h3, h4, h5, _ = st.columns([1, 1, 1, 1, 2, 2])
    h1.markdown("#### Stage")
    h2.markdown("#### Scale")
    h3.markdown("#### 공정")
    h4.markdown("#### 배양 일수")
    h5.markdown("#### 배양기 수")

    if 'wizard_stages' not in st.session_state:
        st.session_state.wizard_stages = [
            {"id": str(uuid.uuid4()), "Stage": "N-4", "days": 4,  "scale": "2L", "qty": 2, "method": "Fed-batch"},
            {"id": str(uuid.uuid4()), "Stage": "N-3", "days": 4,  "scale": "2L", "qty": 2, "method": "Fed-batch"},
            {"id": str(uuid.uuid4()), "Stage": "N-2", "days": 4,  "scale": "2L", "qty": 3, "method": "Fed-batch"},
            {"id": str(uuid.uuid4()), "Stage": "N-1", "days": 5,  "scale": "5L", "qty": 2, "method": "Fed-batch"},
            {"id": str(uuid.uuid4()), "Stage": "N",   "days": 11, "scale": "2L", "qty": 12, "method": "Fed-batch"}
        ]
 
    idx_to_remove = -1
    stage_render_order = list(enumerate(st.session_state.wizard_stages))
    if is_reverse:
        stage_render_order = list(reversed(stage_render_order))

    for i, stage in stage_render_order:
        if 'id' not in stage: stage['id'] = str(uuid.uuid4())
        if 'method' not in stage: stage['method'] = 'Fed-batch'
     
        r1, r2, r3, r4, r5, r6, _ = st.columns([1, 1, 1, 1, 1, 1, 2])
        uk = stage['id']
    
        with r1:
            opts = ["N-4", "N-3", "N-2", "N-1", "N"]
            try: idx = opts.index(stage.get('Stage', 'N'))
            except: idx = 0
            st.session_state.wizard_stages[i]['Stage'] = st.selectbox("Stage", opts, index=idx, key=f"s_{uk}", label_visibility="collapsed")
     
        with r2:
            s_opts = ["2L","5L","10L", "Wave", "50L", "200L"]
            try: s_idx = s_opts.index(stage['scale'])
            except: s_idx = 0
            selected_scale = st.selectbox("Scale", s_opts, index=s_idx, key=f"sc_{uk}", label_visibility="collapsed")
            st.session_state.wizard_stages[i]['scale'] = selected_scale
     
        with r3:
            stage_name = st.session_state.wizard_stages[i]['Stage']
            is_n_stage = stage_name == 'N'
            is_n1_stage = stage_name == 'N-1'
            method_opts = utils.get_method_options_for_scale(selected_scale)
         
            try: m_idx = method_opts.index(stage['method'])
            except: m_idx = 0
         
            if is_n_stage:
                st.session_state.wizard_stages[i]['method'] = st.selectbox(
                    "Method",
                    method_opts,
                    index=m_idx,
                    key=f"m_{uk}",
                    label_visibility="collapsed"
                )
            elif is_n1_stage:
                # N-1: allow Fed-batch or Perfusion
                n1_opts = ["Fed-batch", "Perfusion"]
                try: n1_idx = n1_opts.index(stage['method'])
                except: n1_idx = 0
                st.session_state.wizard_stages[i]['method'] = st.selectbox(
                    "Method",
                    n1_opts,
                    index=n1_idx,
                    key=f"m_{uk}",
                    label_visibility="collapsed"
                )
            else:
                st.selectbox(
                    "Method",
                    ["Fed-batch"],
                    index=0,
                    key=f"m_{uk}",
                    label_visibility="collapsed",
                    disabled=True
                )
                st.session_state.wizard_stages[i]['method'] = 'Fed-batch'
     
        with r4:
            st.session_state.wizard_stages[i]['days'] = st.number_input("Days", 1, value=int(stage['days']), key=f"d_{uk}", label_visibility="collapsed")
     
        with r5:
            st.session_state.wizard_stages[i]['qty'] = st.number_input("Qty", 1, value=int(stage['qty']), key=f"q_{uk}", label_visibility="collapsed")
     
        with r6:
            if st.button("🗑️", key=f"del_{uk}"): idx_to_remove = i

    if idx_to_remove != -1:
        st.session_state.wizard_stages.pop(idx_to_remove)
        st.rerun()

    if st.button("➕ Stage 추가"):
        st.session_state.wizard_stages.append({
            "id": str(uuid.uuid4()),
            "Stage": "New Stage",
            "days": 4,
            "scale": "2L",
            "qty": 3,
            "method": "Fed-batch"
        })
        st.rerun()
    st.markdown("---")
    
    allow_same_day = st.checkbox(
        "털들 배양기 포함",
        value=False,
        key="allow_same_day_bio"
    )
    
    if st.button("🔍 확인", type="primary", use_container_width=True):
        plan = []
        today = datetime.date.today()

        if is_reverse:
            # Backward cascade: anchor is N's start; walk N → N-4
            stages_iter = list(reversed(st.session_state.wizard_stages))
            reverse_plan = []
            for j, stage in enumerate(stages_iter):
                if j == 0:
                    s = anchor_date
                    e = anchor_date + datetime.timedelta(days=stage['days'])
                else:
                    e = reverse_plan[-1]['start']  # this stage ends where the next-later stage began
                    s = e - datetime.timedelta(days=stage['days'])

                sub = st.session_state.inventory[st.session_state.inventory['scale'] == stage['scale']]
                if stage['Stage'] == 'N-1' and stage.get('method') == 'Perfusion':
                    sub = sub[sub['type'] == 'Perfusion']
                cands = sorted(
                    [id for id in sub['id'] if utils.check_availability(id, s, e, st.session_state.bookings, allow_same_day=allow_same_day)],
                    key=utils.custom_sort_key
                )
                reverse_plan.append({
                    "stage": stage['Stage'],
                    "start": s,
                    "end": e,
                    "candidates": cands,
                    "scale": stage['scale'],
                    "qty": stage['qty'],
                    "method": stage['method']
                })

            # Two-phase today-guard: validate AFTER full cascade completes
            earliest = min(p['start'] for p in reverse_plan)
            if earliest < today:
                gap = (today - earliest).days
                st.error(f"⚠️ Reverse cascade lands on {earliest}, before today ({today}). Move N's start later by at least {gap} days.")
                st.stop()

            # Store chronologically (N-4 → N) so booking-write loop and sels[i] stay invariant
            plan = list(reversed(reverse_plan))

        else:
            # Forward cascade — original behavior
            curr = anchor_date
            for stage in st.session_state.wizard_stages:
                end = curr + datetime.timedelta(days=stage['days'])
                sub = st.session_state.inventory[st.session_state.inventory['scale'] == stage['scale']]
                if stage['Stage'] == 'N-1' and stage.get('method') == 'Perfusion':
                    sub = sub[sub['type'] == 'Perfusion']
                cands = sorted([id for id in sub['id'] if utils.check_availability(id, curr, end, st.session_state.bookings, allow_same_day=allow_same_day)], key=utils.custom_sort_key)
                plan.append({
                    "stage": stage['Stage'],
                    "start": curr,
                    "end": end,
                    "candidates": cands,
                    "scale": stage['scale'],
                    "qty": stage['qty'],
                    "method": stage['method']
                })
                curr = end

        st.session_state.campaign_plan = plan
        st.session_state.campaign_is_reverse = is_reverse
        st.rerun()

    if 'campaign_plan' in st.session_state:
        st.divider()
        with st.form("confirm"):
            all_valid, sels = True, {}
            def fmt(x): return x.replace("6층-", "").replace("5층-", "[5층] ").replace("7층-", "[7층] ")

            render_order = list(enumerate(st.session_state.campaign_plan))
            if st.session_state.get('campaign_is_reverse', False):
                render_order = list(reversed(render_order))

            for i, step in render_order:
                c1, c2 = st.columns([1, 3])
                c1.write(f"**{step['stage']}** ({step['method']})")
                c1.caption(f"{step['start']} ~ {step['end']} ({(step['end']-step['start']).days + 1} Days)")
                if len(step['candidates']) < step['qty']:
                    c2.error(f"Need {step['qty']}, Found {len(step['candidates'])}")
                    all_valid = False
                else:
                    sels[i] = c2.multiselect(f"Select {step['qty']}", step['candidates'], max_selections=step['qty'], key=f"sel_{i}", format_func=fmt)
                    if len(sels[i]) != step['qty']: all_valid = False
        
            if st.form_submit_button("Book Campaign", type="primary"):
                if not st.session_state.proj_name_input or not st.session_state.user_name_input:
                    st.error("⚠️ Fill Project/User Name")
                elif not all_valid:
                    st.error("⚠️ Select all reactors")
                else:
                    bid = str(int(datetime.datetime.now().timestamp()))
                    rows = []
                    for i, step in enumerate(st.session_state.campaign_plan):
                        for u_idx, unit in enumerate(sels[i]):
                            rows.append({
                                "booking_id": f"{bid}_{i}_{u_idx}",
                                "reactor_id": unit,
                                "user": st.session_state.user_name_input,
                                "project": st.session_state.proj_name_input,
                                "stage": step['stage'],
                                "start": step['start'],
                                "end": step['end'],
                                "method": step['method']
                            })
                    st.session_state.bookings = pd.concat([st.session_state.bookings, pd.DataFrame(rows)], ignore_index=True)
                    utils.save_data(st.session_state.bookings)
                    st.cache_data.clear()
                    st.success("Booked!")
                    del st.session_state['campaign_plan']
                
                    st.session_state.reset_inputs = True
                    st.rerun()

# --- AMBR WIZARD ---
with tab_ambr:
    st.header("Ambr 예약")
    c_a1, c_a2, c_a3 , _ = st.columns([1, 1, 1, 3])
    with c_a1:
        if 'ambr_proj_input' not in st.session_state: st.session_state.ambr_proj_input = ""
        ambr_proj = st.text_input("제품명", value=st.session_state.ambr_proj_input, key="ambr_proj_input")
    with c_a2:
        if 'ambr_sme_input' not in st.session_state: st.session_state.ambr_sme_input = ""
        ambr_sme = st.text_input("SME", value=st.session_state.ambr_sme_input, key="ambr_sme_input")
    with c_a3:
        ambr_start_date = st.date_input("시작 일정 (Start Date)", value=datetime.date.today(), key="ambr_start_pick")

    if 'ambr_wizard_stages' not in st.session_state:
        st.session_state.ambr_wizard_stages = [
            {"id": str(uuid.uuid4()), "scale": "Ambr250", "days": 7, "qty": 1, "method": "EFB"}
        ]

    st.markdown("#### Configuration")
    ambr_opts = [c[0] for c in utils.INVENTORY_CONFIGS if c[0].startswith("Ambr")]
    ambr_opts = sorted(list(set(ambr_opts)), reverse=True)

    h1, h2, h3, h4, h5 = st.columns([1, 1, 1, 1, 2])
    h1.caption("System")
    h2.caption("Method")
    h3.caption("Days")
    h4.caption("Vessels(Ambr250)  \nStations(Ambr15)")

    idx_ambr_remove = -1
    for i, stage in enumerate(st.session_state.ambr_wizard_stages):
        if 'method' not in stage:
            stage['method'] = 'EFB' if stage['scale'] == 'Ambr250' else 'Fed-batch'
     
        c1, c2, c3, c4, c5 = st.columns([1, 1, 1, 1, 2])
        uk = stage['id']
     
        with c1:
            try: cur_idx = ambr_opts.index(stage['scale'])
            except: cur_idx = 0
            selected_ambr_scale = st.selectbox("System", ambr_opts, index=cur_idx, key=f"asc_{uk}", label_visibility="collapsed")
            st.session_state.ambr_wizard_stages[i]['scale'] = selected_ambr_scale
     
        with c2:
            ambr_method_opts = utils.get_method_options_for_scale(selected_ambr_scale)
            try: am_idx = ambr_method_opts.index(stage['method'])
            except: am_idx = 0
            st.session_state.ambr_wizard_stages[i]['method'] = st.selectbox(
                "Method",
                ambr_method_opts,
                index=am_idx,
                key=f"am_{uk}",
                label_visibility="collapsed"
            )
     
        with c3:
            st.session_state.ambr_wizard_stages[i]['days'] = st.number_input("Days", 1, value=int(stage['days']), key=f"ad_{uk}", label_visibility="collapsed")
     
        with c4:
            st.session_state.ambr_wizard_stages[i]['qty'] = st.number_input("Vessels", 1, value=int(stage['qty']), key=f"aq_{uk}", label_visibility="collapsed")
     
        with c5:
            if st.button("🗑️", key=f"adel_{uk}"): idx_ambr_remove = i

    if idx_ambr_remove != -1:
        st.session_state.ambr_wizard_stages.pop(idx_ambr_remove)
        st.rerun()

    if st.button("➕ 시스템 추가", key="ambr_add_row_btn"):
        st.session_state.ambr_wizard_stages.append({
            "id": str(uuid.uuid4()),
            "scale": "Ambr250",
            "days": 15,
            "qty": 12,
            "method": "EFB"
        })
        st.rerun()
    st.write("")

    if st.button("🔍 확인", type="primary", use_container_width=True, key="ambr_check_btn_final"):
        ambr_plan, curr_date = [], ambr_start_date
        for stage in st.session_state.ambr_wizard_stages:
            end_date = curr_date + datetime.timedelta(days=stage['days'])
            candidates = []
            if not st.session_state.inventory.empty:
                subset = st.session_state.inventory[st.session_state.inventory['id'].str.startswith(stage['scale'])]
                for rid in subset['id']:
                    if utils.check_availability(rid, curr_date, end_date, st.session_state.bookings):
                        candidates.append(rid)
            ambr_plan.append({
                "stage": "N",
                "start": curr_date,
                "end": end_date,
                "candidates": sorted(candidates),
                "scale": stage['scale'],
                "qty": stage['qty'],
                "method": stage['method']
            })
            curr_date = end_date
        st.session_state.ambr_plan = ambr_plan
        st.rerun()

    if 'ambr_plan' in st.session_state:
        st.divider()
        st.subheader("🔍 Confirm Ambr Booking")
        all_valid, final_booking_data = True, []
        config_order_map = [c[2] for c in utils.INVENTORY_CONFIGS if len(c)>2]

        for i, step in enumerate(st.session_state.ambr_plan):
            st.markdown(f"#### Step {i+1}: {step['stage']} ({step['scale']}) - {step['method']}")
            st.caption(f"📅 {step['start']} ~ {step['end']} • Need {step['qty']} vessels")

            if not step['candidates']:
                st.error("⚌ No availability found.")
                all_valid = False
            else:
                eq_map = {}
                for cid in step['candidates']:
                    eq_id = cid.split("-")[1]
                    eq_map.setdefault(eq_id, []).append(cid)
            
                def get_order_index(e_id):
                    return config_order_map.index(e_id) if e_id in config_order_map else 999
            
                unique_eqs = sorted(list(eq_map.keys()), key=get_order_index)

                c_eq, c_ves = st.columns([1, 2])
                with c_eq: selected_eq = st.selectbox("Select Equipment", unique_eqs, key=f"eq_pick_{i}")
                available_vessels = sorted(eq_map[selected_eq])
                with c_ves:
                    chosen_vessels = st.multiselect(f"Select Vessels (Found {len(available_vessels)})", available_vessels, default=available_vessels[:step['qty']], format_func=lambda x: x.split("-")[-1], key=f"ves_pick_{i}")

                if len(chosen_vessels) != step['qty']:
                    st.warning(f"⚠️ Selected {len(chosen_vessels)} / Required {step['qty']}")
                    all_valid = False

                # Vessel count per station — only relevant for Ambr15 (12 vessels per station)
                # Ambr250 booking row = 1 vessel, so no partial-count checkbox needed
                vessels_used_per_station = {}
                if step['scale'] == 'Ambr15':
                    for v in chosen_vessels:
                        partial_key = f"partial_{i}_{v}"
                        full_key = f"full_{i}_{v}"
                        _vc1, _vc2, _vc3 = st.columns([2, 1, 7])
                        with _vc1:
                            is_partial = st.checkbox(
                                f"{v.split('-')[-1]} 내 사용 Vessel 수 (<12개 시)",
                                key=partial_key
                            )
                        with _vc2:
                            if is_partial:
                                n_used = st.number_input(
                                    f"Vessels ({v.split('-')[-1]})",
                                    min_value=1, max_value=12, value=12,
                                    key=full_key
                                )
                                vessels_used_per_station[v] = n_used
                            else:
                                vessels_used_per_station[v] = 12
                else:
                    # Ambr250 / other: each chosen vessel = 1 vessel, no override needed
                    for v in chosen_vessels:
                        vessels_used_per_station[v] = 1

                final_booking_data.append({
                    "step_idx": i,
                    "stage": step['stage'],
                    "start": step['start'],
                    "end": step['end'],
                    "vessels": chosen_vessels,
                    "vessels_used_map": vessels_used_per_station,
                    "method": step['method']
                })
            st.markdown("---")

        if st.button("✅ Book Ambr Run", type="primary"):
            if not ambr_proj or not ambr_sme: st.error("⚌ Fill Product & SME Name")
            elif not all_valid: st.error("⚌ Fix selection errors")
            else:
                bid = str(int(datetime.datetime.now().timestamp()))
                new_rows = []
                for item in final_booking_data:
                    for unit in item['vessels']:
                        new_rows.append({
                            "booking_id": f"AMBR_{bid}_{item['step_idx']}",
                            "reactor_id": unit,
                            "user": ambr_sme,
                            "project": ambr_proj,
                            "stage": item['stage'],
                            "start": pd.to_datetime(item['start']),
                            "end": pd.to_datetime(item['end']),
                            "method": item['method'],
                            "vessels_used": item['vessels_used_map'].get(unit, 12)
                        })
                st.session_state.bookings = pd.concat([st.session_state.bookings, pd.DataFrame(new_rows)], ignore_index=True)
                utils.save_data(st.session_state.bookings)
                st.cache_data.clear()
                st.success("🎉 Ambr Booked!")
                del st.session_state['ambr_plan']
            
                st.session_state.reset_inputs = True
                st.rerun()
