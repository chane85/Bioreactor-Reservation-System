import streamlit as st
import pandas as pd
import datetime
import uuid
import utils

st.set_page_config(page_title="Simulation", layout="wide")

# Ensure Data is Loaded
if 'inventory' not in st.session_state:
    st.session_state.inventory = utils.generate_inventory()
if 'bookings' not in st.session_state:
    st.session_state.bookings = utils.load_data()

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

st.header("🧪 Simulation & Quick Reserve")

# --- SECTION 1: QUICK RESERVE ---
st.subheader("⚡ Quick Reserve")
st.caption("For single-stage reactor booking")

c1, c2, c3, c4 = st.columns(4)

with c1:
    sim_user = st.text_input("👤 User Name", key="sim_user")
with c2:
    sim_project = st.text_input("📁 Project Name", key="sim_project")
with c3:
    sim_start = st.date_input("📅 Start Date", value=datetime.date.today(), key="sim_start")
with c4:
    sim_days = st.number_input("⏱️ Duration (Days)", min_value=1, max_value=30, value=11, key="sim_days")

c5, c6, c7, c8, _ = st.columns([1, 1, 1, 1, 1])

with c5:
    sim_stage = st.selectbox(
        "📊 Select Stage",
        ["N-4", "N-3", "N-2", "N-1", "N"],
        index=4,
        key="sim_stage"
    )

with c6:
    sim_scale = st.selectbox(
        "⚗️ Select Scale",
        ["2L", "5L", "10L", "50L", "200L", "Wave", "Ambr250", "Ambr15"],
        key="sim_scale"
    )

with c7:
    is_n_stage = sim_stage == 'N'
    sim_method_opts = utils.get_method_options_for_scale(sim_scale)
   
    if is_n_stage:
        sim_method = st.selectbox(
            "🔬 Select Method",
            sim_method_opts,
            index=0,
            key="sim_method"
        )
    else:
        sim_method = st.selectbox(
            "🔬 Select Method",
            ["Fed-batch"],
            index=0,
            key="sim_method",
            disabled=True
        )
        sim_method = "Fed-batch"

with c8:
    sim_qty = st.number_input("🔢 Quantity", min_value=1, max_value=20, value=1, key="sim_qty")

st.divider()

if st.button("🔍 Check Availability", type="primary", use_container_width=True, key="sim_check"):
    if not sim_user or not sim_project:
        st.error("⚠️ Please fill in User Name and Project Name")
    else:
        sim_end = sim_start + datetime.timedelta(days=sim_days)
        subset = st.session_state.inventory[st.session_state.inventory['scale'] == sim_scale]
        available = [id for id in subset['id'] if utils.check_availability(id, sim_start, sim_end, st.session_state.bookings)]
        available = sorted(available, key=utils.custom_sort_key)
       
        if len(available) < sim_qty:
            st.error(f"❌ Insufficient availability: Found {len(available)} reactors, need {sim_qty}")
            if available: st.info(f"Available reactors: {', '.join(available)}")
        else:
            st.success(f"✅ Found {len(available)} available {sim_scale} reactors")
            def fmt(x): return x.replace("6층-", "").replace("5층-", "[5층] ").replace("7층-", "[7층] ")
           
            selected_reactors = st.multiselect(f"Select {sim_qty} Reactor(s)", available, default=available[:sim_qty], max_selections=sim_qty, format_func=fmt, key="sim_reactor_select")
           
            if len(selected_reactors) == sim_qty:
                if st.button("✅ Confirm Reservation", type="primary", key="sim_confirm"):
                    bid = str(int(datetime.datetime.now().timestamp()))
                    new_bookings = []
                    for idx, reactor in enumerate(selected_reactors):
                        new_bookings.append({
                            "booking_id": f"SIM_{bid}_{idx}",
                            "reactor_id": reactor,
                            "user": sim_user,
                            "project": sim_project,
                            "stage": sim_stage,
                            "start": pd.to_datetime(sim_start),
                            "end": pd.to_datetime(sim_end),
                            "method": sim_method
                        })
                    new_df = pd.DataFrame(new_bookings)
                    st.session_state.bookings = pd.concat([st.session_state.bookings, new_df], ignore_index=True)
                    utils.save_data(st.session_state.bookings)
                    st.success(f"🎉 Successfully reserved {len(selected_reactors)} reactor(s) for {sim_project}!")
                    st.balloons()
                    st.session_state.sim_user = ""
                    st.session_state.sim_project = ""
                    st.rerun()
            else:
                st.warning(f"⚠️ Please select exactly {sim_qty} reactor(s)")

st.divider()

# --- SECTION 2: ADJUST SCHEDULE ---
st.subheader("🔧 Adjust Schedule: Move / Swap / Delete")

adj_col1, adj_col2 = st.columns([1, 3])

with adj_col1:
    action_type = st.radio("Action Type", ["Move Booking", "Swap Bookings", "Delete Booking"], key="action_type")

if action_type == "Move Booking":
    st.markdown("#### Move a Booking to New Dates")
    bookings_list = st.session_state.bookings['booking_id'].tolist() if not st.session_state.bookings.empty else []
   
    if not bookings_list:
        st.info("No bookings available to move")
    else:
        move_id = st.selectbox("Select Booking to Move", bookings_list, key="move_id")
       
        if move_id:
            current = st.session_state.bookings[st.session_state.bookings['booking_id'] == move_id].iloc[0]
           
            col1, col2, col3 = st.columns(3)
            with col1:
                st.info(f"**Current:** - Reactor: {current['reactor_id']} - Project: {current['project']} - Start: {current['start'].date()} - End: {current['end'].date()}")
           
            with col2:
                new_start = st.date_input("New Start Date", value=current['start'].date(), key="move_new_start")
                new_end = st.date_input("New End Date", value=current['end'].date(), key="move_new_end")
           
            with col3:
                if st.button("Apply Move", type="primary", key="apply_move"):
                    if new_start >= new_end:
                        st.error("End date must be after start date")
                    else:
                        temp_bookings = st.session_state.bookings[st.session_state.bookings['booking_id'] != move_id]
                        if utils.check_availability(current['reactor_id'], new_start, new_end, temp_bookings):
                            st.session_state.bookings.loc[st.session_state.bookings['booking_id'] == move_id, 'start'] = pd.to_datetime(new_start)
                            st.session_state.bookings.loc[st.session_state.bookings['booking_id'] == move_id, 'end'] = pd.to_datetime(new_end)
                            utils.save_data(st.session_state.bookings)
                            st.success(f"✅ Moved booking to {new_start} ~ {new_end}")
                            st.rerun()
                        else:
                            st.error("❌ Reactor not available for new dates")

elif action_type == "Swap Bookings":
    st.markdown("#### Swap Two Bookings")
    bookings_list = st.session_state.bookings['booking_id'].tolist() if not st.session_state.bookings.empty else []
   
    if len(bookings_list) < 2:
        st.info("Need at least 2 bookings to swap")
    else:
        col1, col2, col3 = st.columns(3)
       
        with col1:
            swap_id1 = st.selectbox("Select First Booking", bookings_list, key="swap_id1")
        with col2:
            swap_id2 = st.selectbox("Select Second Booking", [b for b in bookings_list if b != swap_id1], key="swap_id2")
       
        if swap_id1 and swap_id2:
            booking1 = st.session_state.bookings[st.session_state.bookings['booking_id'] == swap_id1].iloc[0]
            booking2 = st.session_state.bookings[st.session_state.bookings['booking_id'] == swap_id2].iloc[0]
           
            with col3:
                st.info(f"**Swap:** {booking1['reactor_id']} ↔️ {booking2['reactor_id']}")
               
                if st.button("Execute Swap", type="primary", key="apply_swap"):
                    st.session_state.bookings.loc[st.session_state.bookings['booking_id'] == swap_id1, 'reactor_id'] = booking2['reactor_id']
                    st.session_state.bookings.loc[st.session_state.bookings['booking_id'] == swap_id2, 'reactor_id'] = booking1['reactor_id']
                    utils.save_data(st.session_state.bookings)
                    st.success("✅ Swapped successfully")
                    st.rerun()

elif action_type == "Delete Booking":
    st.markdown("#### Delete a Booking")
    bookings_list = st.session_state.bookings['booking_id'].tolist() if not st.session_state.bookings.empty else []
   
    if not bookings_list:
        st.info("No bookings available to delete")
    else:
        delete_id = st.selectbox("Select Booking to Delete", bookings_list, key="delete_id")
       
        if delete_id:
            to_delete = st.session_state.bookings[st.session_state.bookings['booking_id'] == delete_id].iloc[0]
           
            col1, col2 = st.columns([2, 1])
            with col1:
                st.warning(f"**Will Delete:** - Booking ID: {delete_id} - Reactor: {to_delete['reactor_id']} - Project: {to_delete['project']} - Period: {to_delete['start'].date()} ~ {to_delete['end'].date()}")
           
            with col2:
                if st.button("⚠️ Confirm Delete", type="secondary", key="apply_delete"):
                    st.session_state.bookings = st.session_state.bookings[st.session_state.bookings['booking_id'] != delete_id]
                    utils.save_data(st.session_state.bookings)
                    st.success("✅ Deleted successfully")
                    st.rerun()