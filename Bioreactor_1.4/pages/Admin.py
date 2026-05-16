import streamlit as st
import pandas as pd
import utils
import datetime
import openpyxl
from io import BytesIO

st.set_page_config(page_title="Admin", layout="wide")

st.header("🔒 Admin Dashboard")

# --- AUTHENTICATION ---
if 'admin_auth' not in st.session_state: 
    st.session_state.admin_auth = False

if not st.session_state.admin_auth:
    with st.form("login_form"):
        pwd = st.text_input("Password", type="password")
        submitted = st.form_submit_button("Login")
        
        if submitted:
            if pwd == "bio135":
                st.session_state.admin_auth = True
                st.rerun()
            else:
                st.error("❌ Incorrect password")
else:
    # ✅ RIGHT HERE - Add these 3 lines
    if 'bookings' not in st.session_state:
        st.session_state.bookings = utils.load_data()
    
    if st.button("Log Out"):
        st.session_state.admin_auth = False
        st.rerun()
   
    st.divider()
   
    # --- 1. BACKUP / RESTORE ---
    st.subheader("💾 Backup & Restore")
    c1, c2 = st.columns(2)
    df = st.session_state.get('bookings', utils.load_data())
   
    c1.download_button(
        "⬇️ Download Backup", 
        df.to_csv(index=False).encode('utf-8'), 
        "backup.csv", 
        "text/csv"
    )
   
    up = c2.file_uploader("Restore CSV", type=["csv"])
    if up and c2.button("⚠️ Restore Data"):
        try:
            ndf = pd.read_csv(up)
            ndf['start'] = pd.to_datetime(ndf['start'], format='mixed', errors='coerce')
            ndf['end'] = pd.to_datetime(ndf['end'], format='mixed', errors='coerce')
            ndf = ndf.dropna(subset=['start', 'end'])
            
            if 'method' not in ndf.columns:
                ndf['method'] = 'Unknown'
            ndf['method'] = ndf['method'].fillna('Unknown')
            
            st.session_state.bookings = ndf
            utils.save_data(ndf)
            st.success("✅ 복구 완료! (Restored successfully)")
            st.rerun()
        except Exception as e: 
            st.error(f"Error restoring data: {e}")
       
    st.divider()
    
    # --- 2. APPLY SIMULATION CSV ---
    st.subheader("📊 Apply Simulation Schedule")
    st.caption("Upload a simulation CSV to add bookings to the system")
    
    sim_upload = st.file_uploader("Upload Simulation CSV", type=["csv"], key="sim_upload")
    
    if sim_upload:
        try:
            sim_df = pd.read_csv(sim_upload)
            
            # Show preview
            st.write("**Preview of Simulation Data:**")
            st.dataframe(sim_df.head(10), use_container_width=True)
            
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Total Rows", len(sim_df))
            with col2:
                unique_reactors = sim_df['reactor_id'].nunique() if 'reactor_id' in sim_df.columns else 0
                st.metric("Unique Reactors", unique_reactors)
            with col3:
                unique_projects = sim_df['project'].nunique() if 'project' in sim_df.columns else 0
                st.metric("Projects", unique_projects)
            
            # Validate required columns
            required_cols = ['booking_id', 'reactor_id', 'user', 'project', 'stage', 'start', 'end']
            missing_cols = [col for col in required_cols if col not in sim_df.columns]
            
            if missing_cols:
                st.error(f"❌ Missing required columns: {', '.join(missing_cols)}")
            else:
                # Parse dates
                sim_df['start'] = pd.to_datetime(sim_df['start'], errors='coerce')
                sim_df['end'] = pd.to_datetime(sim_df['end'], errors='coerce')
                
                # Add method column if missing
                if 'method' not in sim_df.columns:
                    sim_df['method'] = 'Fed-batch'
                sim_df['method'] = sim_df['method'].fillna('Fed-batch')
                
                # Remove invalid rows
                sim_df = sim_df.dropna(subset=['start', 'end'])
                
                if st.button("✅ Apply Simulation to Real Schedule", type="primary"):
                    # Append to existing bookings
                    st.session_state.bookings = pd.concat(
                        [st.session_state.bookings, sim_df], 
                        ignore_index=True
                    )
                    utils.save_data(st.session_state.bookings)
                    st.success(f"🎉 Successfully added {len(sim_df)} bookings from simulation!")
                    st.balloons()
                    st.rerun()
        
        except Exception as e:
            st.error(f"Error processing simulation file: {e}")
    
    st.divider()
   
    # --- 3. IMPORT FROM GANTT CSV ---
    st.subheader("📊 Import from Gantt Schedule CSV")
    st.caption("Upload preprocessed CSV from Excel Gantt chart (use excel_to_csv_preprocessor.py)")

    gantt_csv_upload = st.file_uploader("Upload Gantt CSV", type=["csv"], key="gantt_csv_upload")

    if gantt_csv_upload:
        try:
            # Read CSV
            gantt_df = pd.read_csv(gantt_csv_upload)
           
            st.success(f"✅ Loaded {len(gantt_df)} bookings from CSV")
           
            # Show preview
            st.write("**Preview of Gantt Data:**")
            st.dataframe(gantt_df.head(10), use_container_width=True)
           
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Total Bookings", len(gantt_df))
            with col2:
                unique_reactors = gantt_df['reactor_id'].nunique() if 'reactor_id' in gantt_df.columns else 0
                st.metric("Unique Reactors", unique_reactors)
            with col3:
                unique_projects = gantt_df['project'].nunique() if 'project' in gantt_df.columns else 0
                st.metric("Projects", unique_projects)
           
            # Validate required columns
            required_cols = ['reactor_id', 'project', 'user', 'stage', 'method', 'start', 'end']
            missing_cols = [col for col in required_cols if col not in gantt_df.columns]
           
            if missing_cols:
                st.error(f"❌ Missing required columns: {', '.join(missing_cols)}")
            else:
                # Parse dates
                gantt_df['start'] = pd.to_datetime(gantt_df['start'], errors='coerce')
                gantt_df['end'] = pd.to_datetime(gantt_df['end'], errors='coerce')
               
                # Remove invalid rows
                gantt_df = gantt_df.dropna(subset=['start', 'end'])
               
                # Generate booking IDs BEFORE data_editor
                gantt_df['booking_id'] = [f"GANTT_{int(datetime.datetime.now().timestamp())}_{i}" for i in range(len(gantt_df))]
               
                st.markdown("### 📋 Preview & Edit Before Import")
                st.caption("Review and modify Stage/Method if needed")
               
                edited_gantt_df = st.data_editor(
                    gantt_df,
                    hide_index=True,
                    use_container_width=True,
                    column_config={
                        "booking_id": st.column_config.TextColumn("Booking ID", disabled=True),
                        "reactor_id": st.column_config.TextColumn("Reactor ID", disabled=True),
                        "project": st.column_config.TextColumn("Project", disabled=True),
                        "user": st.column_config.TextColumn("User"),
                        "stage": st.column_config.SelectboxColumn(
                            "Stage",
                            options=["N-4", "N-3", "N-2", "N-1", "N"],
                            required=True
                        ),
                        "method": st.column_config.SelectboxColumn(
                            "Method",
                            options=["Fed-batch", "EFB", "iEFB", "N1", "EN1"],
                            required=True
                        ),
                        "start": st.column_config.DateColumn("Start Date"),
                        "end": st.column_config.DateColumn("End Date")
                    },
                    num_rows="fixed"
                )
               
                # Validation
                st.markdown("### 🔍 Validation")
               
                validation_errors = []
               
                if 'inventory' not in st.session_state:
                    st.session_state.inventory = utils.generate_inventory()
               
                invalid_reactors = edited_gantt_df[~edited_gantt_df['reactor_id'].isin(st.session_state.inventory['id'])]
                if not invalid_reactors.empty:
                    validation_errors.append(f"❌ Invalid reactor IDs: {invalid_reactors['reactor_id'].unique().tolist()}")
               
                overlap_count = 0
                for idx, row in edited_gantt_df.iterrows():
                    if not utils.check_availability(row['reactor_id'], row['start'].date(), row['end'].date(), st.session_state.bookings):
                        overlap_count += 1
               
                if overlap_count > 0:
                    validation_errors.append(f"⚠️ {overlap_count} bookings have conflicts with existing schedule")
               
                if validation_errors:
                    for error in validation_errors:
                        st.warning(error)
                else:
                    st.success("✅ All validations passed")
               
                col1, col2 = st.columns(2)
               
                with col1:
                    import_mode = st.radio(
                        "Import Mode",
                        ["Add to Existing", "Replace All Bookings"],
                        help="Add: Keep existing bookings, append new ones | Replace: Delete all, use only CSV data",
                        key="gantt_import_mode"
                    )
               
                with col2:
                    handle_conflicts = st.radio(
                        "If Conflicts Found",
                        ["Skip Conflicting", "Force Overwrite"],
                        help="Skip: Don't import bookings with conflicts | Force: Delete conflicting bookings and import",
                        key="gantt_handle_conflicts"
                    )
               
                if st.button("✅ Apply Gantt CSV Import", type="primary", use_container_width=True):
                    if import_mode == "Replace All Bookings":
                        st.session_state.bookings = pd.DataFrame(columns=["booking_id", "reactor_id", "user", "start", "end", "project", "stage", "method"])
                        st.session_state.bookings = pd.concat([st.session_state.bookings, edited_gantt_df], ignore_index=True)
                        utils.save_data(st.session_state.bookings)
                        st.success(f"🎉 Replaced all bookings with {len(edited_gantt_df)} bookings from Gantt CSV!")
                        st.balloons()
                        st.rerun()
                   
                    else:
                        if handle_conflicts == "Skip Conflicting":
                            valid_bookings = []
                            skipped = 0
                            for idx, row in edited_gantt_df.iterrows():
                                if utils.check_availability(row['reactor_id'], row['start'].date(), row['end'].date(), st.session_state.bookings):
                                    valid_bookings.append(row)
                                else:
                                    skipped += 1
                           
                            if valid_bookings:
                                new_bookings_df = pd.DataFrame(valid_bookings)
                                st.session_state.bookings = pd.concat([st.session_state.bookings, new_bookings_df], ignore_index=True)
                                utils.save_data(st.session_state.bookings)
                                st.success(f"✅ Added {len(valid_bookings)} bookings (skipped {skipped} conflicts)")
                                st.rerun()
                            else:
                                st.error("❌ All bookings have conflicts. Nothing imported.")
                       
                        else:
                            remaining_bookings = st.session_state.bookings.copy()
                            deleted_count = 0
                           
                            for idx, row in edited_gantt_df.iterrows():
                                mask = (
                                    (remaining_bookings['reactor_id'] == row['reactor_id']) &
                                    (remaining_bookings['start'] < row['end']) &
                                    (remaining_bookings['end'] > row['start'])
                                )
                                deleted_count += mask.sum()
                                remaining_bookings = remaining_bookings[~mask]
                           
                            st.session_state.bookings = pd.concat([remaining_bookings, edited_gantt_df], ignore_index=True)
                            utils.save_data(st.session_state.bookings)
                            st.success(f"✅ Imported {len(edited_gantt_df)} bookings (deleted {deleted_count} conflicts)")
                            st.balloons()
                            st.rerun()
       
        except Exception as e:
            st.error(f"❌ Error processing Gantt CSV file: {e}")
            import traceback
            st.code(traceback.format_exc())
    
    st.divider()
   
    # --- 4. MANAGE BOOKINGS ---
    st.subheader("📋 Manage Bookings")
    
    if 'inventory' not in st.session_state: 
        st.session_state.inventory = utils.generate_inventory()
    
    if not df.empty:
        view = df.copy()
        view['start'] = pd.to_datetime(view['start'])
        view['end'] = pd.to_datetime(view['end'])
        
        inv_map = st.session_state.inventory.set_index('id')['scale'].to_dict()
        view['scale'] = view['reactor_id'].map(inv_map)
        
        if 'method' not in view.columns:
            view['method'] = 'Unknown'
        view['method'] = view['method'].fillna('Unknown')

        fc1, fc2, fc3, fc4 = st.columns(4)
        
        f_proj = fc1.selectbox("Filter Project", ["All"] + sorted(view['project'].astype(str).unique()))
        scale_opts = ["All"] + sorted(list(set([s for s in inv_map.values() if pd.notna(s)])))
        f_scale = fc2.selectbox("Filter Scale", scale_opts)
        method_opts = ["All"] + sorted(view['method'].unique().tolist())
        f_method = fc3.selectbox("Filter Method", method_opts)
        use_date = fc4.checkbox("Filter by Start Date")
        f_date = fc4.date_input("Select Date", value=None, disabled=not use_date)
       
        if f_proj != "All": 
            view = view[view['project'] == f_proj]
        if f_scale != "All":
            view = view[view['scale'] == f_scale]
        if f_method != "All":
            view = view[view['method'] == f_method]
        if use_date and f_date:
            view = view[view['start'].dt.date == f_date]
           
        view.insert(0, "Delete", False)
        cols = ['Delete', 'booking_id', 'reactor_id', 'scale', 'user', 'project', 'start', 'end', 'stage', 'method']
        extra_cols = [c for c in view.columns if c not in cols]
        final_view = view[cols + extra_cols]

        edited = st.data_editor(
            final_view, 
            hide_index=True, 
            use_container_width=True,
            column_config={
                "method": st.column_config.SelectboxColumn(
                    "Method",
                    options=['Unknown', 'Fed-batch', 'EFB', 'iEFB', 'N1', 'EN1'],
                    required=True
                ),
                "start": st.column_config.DatetimeColumn("Start", format="YYYY-MM-DD"),
                "end": st.column_config.DatetimeColumn("End", format="YYYY-MM-DD")
            }
        )
       
        col1, col2 = st.columns(2)
        
        with col1:
            if st.button("🗑️ Delete Selected", type="secondary"):
                ids_to_del = edited[edited['Delete']]['booking_id'].tolist()
                if ids_to_del:
                    st.session_state.bookings = df[~df['booking_id'].isin(ids_to_del)]
                    utils.save_data(st.session_state.bookings)
                    st.success(f"Deleted {len(ids_to_del)} bookings!")
                    st.rerun()
                else:
                    st.warning("No rows selected for deletion.")
        
        with col2:
            if st.button("💾 Save Changes", type="primary"):
                edited_clean = edited.drop(columns=['Delete'])
                for idx, row in edited_clean.iterrows():
                    booking_id = row['booking_id']
                    for col in edited_clean.columns:
                        if col in df.columns:
                            df.loc[df['booking_id'] == booking_id, col] = row[col]
                
                st.session_state.bookings = df
                utils.save_data(df)
                st.success("✅ Changes saved successfully!")
                st.rerun()
        
        unknown_count = (final_view['method'] == 'Unknown').sum()
        if unknown_count > 0:
            st.warning(f"⚠️ {unknown_count} bookings have 'Unknown' method. Please assign methods for accurate cost calculation.")
    else:
        st.info("No bookings found.")

    st.divider()

    # --- 5. RESTORE BACKUP ---
    st.subheader("🔄 Restore Backup")
    st.caption("Restore real bookings to a previous snapshot. Last 10 backups are kept.")

    backups = utils.load_backups()
    if not backups:
        st.info("No backups available.")
    else:
        backup_df = pd.DataFrame(backups)
        backup_df = backup_df.rename(columns={
            'filename': 'Backup File',
            'created_at': 'Created At',
            'n_bookings': 'Bookings'
        })
        st.dataframe(backup_df, use_container_width=True, hide_index=True)

        selected_backup = st.selectbox(
            "Select Backup to Restore",
            [b['filename'] for b in backups],
            key="restore_backup_select"
        )
        if st.button("⚠️ Restore Selected Backup", type="secondary", key="restore_backup_btn"):
            try:
                n = utils.restore_backup(selected_backup)
                utils.log_audit(
                    action='restored',
                    filename=selected_backup,
                    submitted_by='',
                    actioned_by='Admin'
                )
                st.session_state.bookings = utils.load_data()
                st.success(f"✅ Restored {n} booking(s) from {selected_backup}")
                st.rerun()
            except Exception as e:
                st.error(f"❌ Failed to restore: {e}")

# =============================================================
# AUDIT LOG — visible to all users (outside password block)
# =============================================================
st.divider()
st.subheader("📋 Audit Log")
st.caption("Read-only record of all simulation submissions, applications, and restores.")

audit_df = utils.load_audit_log()
if audit_df.empty:
    st.info("No audit log entries yet.")
else:
    st.dataframe(
        audit_df.sort_values('timestamp', ascending=False),
        use_container_width=True,
        hide_index=True
    )
    if st.session_state.get('admin_auth'):
        st.markdown("#### 🗑️ Delete Audit Entry (Admin only)")
        del_idx = st.selectbox(
            "Select entry to delete (by index)",
            audit_df.index.tolist(),
            format_func=lambda i: f"{audit_df.loc[i, 'timestamp']} — {audit_df.loc[i, 'action']} — {audit_df.loc[i, 'filename']}",
            key="audit_del_idx"
        )
        if st.button("⚠️ Delete Audit Entry", type="secondary", key="audit_del_btn"):
            audit_df = audit_df.drop(index=del_idx).reset_index(drop=True)
            audit_df.to_csv(utils.AUDIT_LOG_FILE, index=False)
            st.success("✅ Audit entry deleted.")
            st.rerun()