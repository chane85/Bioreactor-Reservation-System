import streamlit as st
import pandas as pd
import utils
import auth
import datetime
import openpyxl
from io import BytesIO

st.set_page_config(page_title="Admin", layout="wide")

# Auth gate 1: must have admin role to even see this page
auth.render_sidebar_auth()
auth.require_role('admin')

st.header("🔒 Admin Dashboard")
st.caption(f"Logged in as **{auth.current_user()}** (admin role). "
           "Some destructive actions require an additional password (2nd factor).")

# --- AUTHENTICATION (2nd factor for destructive actions) ---
if 'admin_auth' not in st.session_state: 
    st.session_state.admin_auth = False

if not st.session_state.admin_auth:
    with st.form("login_form"):
        pwd = st.text_input("2nd-factor password (required for destructive actions)", type="password")
        submitted = st.form_submit_button("Unlock destructive actions")
        
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

    # =============================================================
    # TABS: Bookings | Backup | Bulk Import
    # =============================================================
    tab1, tab2, tab3 = st.tabs(["📋 Bookings", "💾 Backup", "📊 Bulk Import"])

    # -------------------------------------------------------------
    # TAB 1: BOOKINGS — Manage Bookings
    # -------------------------------------------------------------
    with tab1:
        # --- MANAGE BOOKINGS ---
        st.subheader("📋 Manage Bookings")
        
        if 'inventory' not in st.session_state: 
            st.session_state.inventory = utils.generate_inventory()

        df = st.session_state.get('bookings', utils.load_data())
        
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
               
            # Select All checkbox for mass deletion
            select_all = st.checkbox(
                f"☑️ Select All ({len(view)} rows shown) — check to mark all for deletion",
                value=False, key="select_all_delete"
            )

            view.insert(0, "Delete", select_all)
            cols = ['Delete', 'booking_id', 'reactor_id', 'scale', 'user', 'project', 'start', 'end', 'stage', 'method']
            extra_cols = [c for c in view.columns if c not in cols]
            final_view = view[cols + extra_cols]

            edited = st.data_editor(
                final_view,
                hide_index=True,
                use_container_width=True,
                column_config={
                    "Delete": st.column_config.CheckboxColumn("Delete", default=False),
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
            
        # =============================================================
        # FIX / CALIBRATION BLOCKS
        # =============================================================
        st.markdown("### 🔧 Fix / Calibration Blocks")
        with st.expander("Click to expand", expanded=False):
            st.caption(
                "Mark bioreactors as unavailable for a date range. "
                "Stored as 수리중 bookings — appear grey on Gantt and block double-booking. "
                "⚠️ Existing conflicting bookings will be deleted (auto-backup is created first)."
            )

            if 'inventory' not in st.session_state:
                st.session_state.inventory = utils.generate_inventory()

            # ── Create new block ────────────────────────────────────
            st.markdown("#### Create New Block")
            blk_c1, blk_c2 = st.columns(2)
            with blk_c1:
                blk_start = st.date_input("Start Date", value=datetime.date.today(), key="blk_start")
            with blk_c2:
                blk_end = st.date_input("End Date", value=datetime.date.today() + datetime.timedelta(days=7), key="blk_end")

            blk_reason = st.text_input(
                "Reason (e.g. Calibration, Repair, Preventive Maintenance)",
                key="blk_reason"
            )

            all_reactor_ids = sorted(st.session_state.inventory['id'].tolist(), key=utils.custom_sort_key)
            blk_reactors = st.multiselect(
                "Select Reactor(s) to Block",
                all_reactor_ids,
                key="blk_reactors",
                help="One block will be created per selected reactor."
            )

            if blk_start and blk_end and blk_end < blk_start:
                st.error("⚠️ End date must be on or after start date.")
            elif blk_reactors and blk_reason and blk_start and blk_end:
                # Pre-validate conflicts (for warning display only — no Skip option)
                current_bookings = st.session_state.get('bookings', utils.load_data())
                conflicts = []
                for rid in blk_reactors:
                    if not utils.check_availability(rid, blk_start, blk_end, current_bookings):
                        conflicts.append(rid)

                if conflicts:
                    st.warning(
                        f"⚠️ {len(conflicts)} reactor(s) have existing bookings in this date range that will be DELETED: "
                        f"{', '.join(conflicts)}"
                    )
                else:
                    st.success(f"✅ All {len(blk_reactors)} reactor(s) available — no existing bookings to delete.")

                if st.button("🔒 Create Block(s)", type="primary", key="blk_create_btn"):
                    bid_ts = str(int(datetime.datetime.now().timestamp()))
                    bookings_df = current_bookings.copy()

                    # Auto-backup before any destructive change
                    backup_filename = None
                    if conflicts:
                        try:
                            backup_filename = utils.create_backup()
                        except Exception as e:
                            st.error(f"❌ Backup failed — block creation aborted to protect data: {e}")
                            st.stop()

                    # Delete conflicting bookings within the date range
                    deleted_n = 0
                    if conflicts:
                        mask = (
                            bookings_df['reactor_id'].isin(conflicts) &
                            (pd.to_datetime(bookings_df['start']) <= pd.to_datetime(blk_end)) &
                            (pd.to_datetime(bookings_df['end']) >= pd.to_datetime(blk_start))
                        )
                        deleted_n = int(mask.sum())
                        bookings_df = bookings_df[~mask]

                    # Create one block per selected reactor (force = all selected)
                    new_blocks = []
                    for i, rid in enumerate(blk_reactors):
                        new_blocks.append({
                            "booking_id": f"BLOCK_{bid_ts}_{i}",
                            "reactor_id": rid,
                            "user": f"Admin ({auth.current_user()})",
                            "project": "수리중",
                            "stage": "Block",
                            "start": pd.to_datetime(blk_start),
                            "end": pd.to_datetime(blk_end),
                            "method": "N/A",
                        })

                    bookings_df = pd.concat([bookings_df, pd.DataFrame(new_blocks)], ignore_index=True)
                    st.session_state.bookings = bookings_df
                    utils.save_data(bookings_df)

                    # Audit log entry
                    try:
                        utils.log_audit(
                            action='block_created',
                            filename=backup_filename if backup_filename else 'N/A',
                            submitted_by=blk_reason,
                            actioned_by=auth.current_user(),
                        )
                    except Exception as e:
                        st.warning(f"⚠️ Block created but audit log write failed: {e}")

                    msg = f"✅ Created {len(new_blocks)} block(s) — reason: {blk_reason}"
                    if deleted_n:
                        msg += f" (deleted {deleted_n} conflicting booking(s); backup saved as {backup_filename})"
                    st.success(msg)
                    st.rerun()

            st.divider()

            # ── View / Clear existing blocks ────────────────────────
            st.markdown("#### Active Blocks")
            current_bookings_view = st.session_state.get('bookings', utils.load_data())
            if current_bookings_view.empty:
                st.info("No blocks active.")
            else:
                blocks_df = current_bookings_view[
                    current_bookings_view['booking_id'].astype(str).str.startswith('BLOCK_')
                ].copy()
                if blocks_df.empty:
                    st.info("No blocks active.")
                else:
                    blocks_df['start'] = pd.to_datetime(blocks_df['start']).dt.strftime('%Y-%m-%d')
                    blocks_df['end'] = pd.to_datetime(blocks_df['end']).dt.strftime('%Y-%m-%d')
                    blocks_show = blocks_df[['booking_id', 'reactor_id', 'start', 'end', 'user']].rename(columns={
                        'booking_id': 'Block ID',
                        'reactor_id': 'Reactor',
                        'start': 'Start',
                        'end': 'End',
                        'user': 'Created By',
                    })
                    st.dataframe(blocks_show, use_container_width=True, hide_index=True)

                    clear_choices = blocks_df['booking_id'].tolist()
                    to_clear = st.multiselect(
                        "Select Block(s) to Clear",
                        clear_choices,
                        format_func=lambda bid: f"{bid} ({blocks_df[blocks_df['booking_id']==bid]['reactor_id'].iloc[0]})",
                        key="blk_clear_select"
                    )
                    if to_clear and st.button("✅ Clear Selected Block(s)", type="secondary", key="blk_clear_btn"):
                        bookings_df = current_bookings_view[
                            ~current_bookings_view['booking_id'].isin(to_clear)
                        ]
                        st.session_state.bookings = bookings_df
                        utils.save_data(bookings_df)

                        # Audit log for block clearance
                        try:
                            utils.log_audit(
                                action='block_cleared',
                                filename=','.join(to_clear),
                                submitted_by='',
                                actioned_by=auth.current_user(),
                            )
                        except Exception as e:
                            st.warning(f"⚠️ Blocks cleared but audit log write failed: {e}")

                        st.success(f"✅ Cleared {len(to_clear)} block(s).")
                        st.rerun()

        st.divider()
        
    # -------------------------------------------------------------
    # TAB 2: BACKUP — Manual Export/Restore + Auto-Backups
    # -------------------------------------------------------------
    with tab2:
        # --- 1. BACKUP / RESTORE (Manual) ---
        st.subheader("📤 Manual Export / Restore (CSV)")
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

        # --- 2. RESTORE BACKUP (Auto-generated) ---
        st.subheader("🔄 Auto-Backups (last 10)")
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
                        actioned_by=auth.current_user()
                    )
                    st.session_state.bookings = utils.load_data()
                    st.success(f"✅ Restored {n} booking(s) from {selected_backup}")
                    st.rerun()
                except Exception as e:
                    st.error(f"❌ Failed to restore: {e}")
        
        st.divider()

        # --- AUDIT LOG ---
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

    # -------------------------------------------------------------
    # TAB 3: BULK IMPORT — Gantt CSV Import
    # -------------------------------------------------------------
    with tab3:
        # --- IMPORT FROM GANTT CSV ---
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