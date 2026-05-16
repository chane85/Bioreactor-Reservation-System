import streamlit as st
import pandas as pd
import datetime
import utils

st.set_page_config(page_title="Cost Analysis", layout="wide")

if 'inventory' not in st.session_state: st.session_state.inventory = utils.generate_inventory()
if 'bookings' not in st.session_state: st.session_state.bookings = utils.load_data()

# Hardcoded cost matrix
if 'cost_matrix' not in st.session_state:
    cost_data = {
        'scale': [
            'Ambr15', 
            'Ambr250', 'Ambr250', 'Ambr250',
            '2L', '2L', '2L', '2L', '2L',
            '200L', '200L', '200L', '200L', '200L'
        ],
        'method': [
            'Fed-batch',
            'EFB', 'iEFB', 'EN1',
            'Fed-batch', 'EFB', 'iEFB', 'N1', 'EN1',
            'Fed-batch', 'EFB', 'iEFB', 'N1', 'EN1'
        ],
        'cost': [
            303929,
            1211714, 3029285, 3029285,
            1211714, 3029285, 3029285, 3029285, 3029285,
            60585714, 151464286, 151464286, 151464286, 151464286
        ]
    }
    st.session_state.cost_matrix = pd.DataFrame(cost_data)

st.header("💰 Cost Analysis")

unknown_count = (st.session_state.bookings['method'] == 'Unknown').sum() if 'method' in st.session_state.bookings.columns else 0
if unknown_count > 0:
    st.warning(f"⚠️ {unknown_count} bookings have 'Unknown' method. Cost calculations will exclude these bookings. Please assign methods in Admin page.")

st.divider()

tab1, tab2 = st.tabs(["📊 Project-Level Analysis", "📅 Monthly Analysis"])

with tab1:
    st.subheader("Project-Level Cost Summary")
    st.caption("💡 Only N-stage reactors with scales: Ambr15, Ambr250, 2L, 200L are counted")
    
    n_stage_bookings = st.session_state.bookings[st.session_state.bookings['stage'] == 'N']
    
    if n_stage_bookings.empty:
        st.info("No N-stage bookings found.")
    else:
        projects = sorted(n_stage_bookings['project'].unique())
        
        c1, c2 = st.columns([1, 3])
        with c1:
            selected_project = st.selectbox("Select Project", projects)
        
        if selected_project:
            cost_data = utils.calculate_project_cost(
                selected_project, 
                st.session_state.bookings, 
                st.session_state.cost_matrix
            )
            
            if cost_data['total'] == 0:
                st.info(f"No cost data available for {selected_project}. This may be because:")
                st.markdown("- No N-stage bookings exist")
                st.markdown("- All N-stage reactors are excluded scales (5L, 10L, 50L)")
                st.markdown("- Methods are set to 'Unknown'")
            else:
                st.markdown("### Cost Breakdown")
                breakdown_df = pd.DataFrame(cost_data['breakdown'])
                breakdown_df['unit_cost'] = breakdown_df['unit_cost'].apply(lambda x: f"{x:,.0f} KRW")
                breakdown_df['subtotal'] = breakdown_df['subtotal'].apply(lambda x: f"{x:,.0f} KRW")
                breakdown_df = breakdown_df.rename(columns={
                    'scale': 'Scale',
                    'method': 'Method',
                    'qty': 'Quantity',
                    'unit_cost': 'Unit Cost',
                    'subtotal': 'Subtotal'
                })
                
                st.dataframe(breakdown_df, use_container_width=True, hide_index=True)
                
                st.markdown("---")
                col1, col2, col3 = st.columns([2, 1, 1])
                with col2:
                    st.metric("**Total Cost**", f"{cost_data['total']:,.0f} KRW")
                
                with st.expander("📋 View Detailed Bookings"):
                    project_bookings = st.session_state.bookings[
                        (st.session_state.bookings['project'] == selected_project) &
                        (st.session_state.bookings['stage'] == 'N')
                    ].copy()
                    
                    if not project_bookings.empty:
                        project_bookings['scale'] = project_bookings['reactor_id'].apply(utils.extract_scale_from_reactor_id)
                        display_cols = ['reactor_id', 'scale', 'method', 'user', 'start', 'end']
                        st.dataframe(project_bookings[display_cols], use_container_width=True, hide_index=True)

with tab2:
    st.subheader("Monthly Cost Analysis")
    st.caption("💡 Analyze costs across all projects within a date range")
    
    c1, c2, c3 = st.columns([1, 1, 2])
    
    today = datetime.date.today()
    default_start = today.replace(day=1)
    default_end = (default_start + datetime.timedelta(days=32)).replace(day=1) - datetime.timedelta(days=1)
    
    with c1:
        start_date = st.date_input("Start Date", value=default_start)
    with c2:
        end_date = st.date_input("End Date", value=default_end)
    
    if start_date > end_date:
        st.error("⚌ Start date must be before end date")
    else:
        monthly_data = utils.calculate_monthly_costs(
            start_date, 
            end_date, 
            st.session_state.bookings, 
            st.session_state.cost_matrix
        )
        
        if not monthly_data:
            st.info(f"No N-stage bookings found between {start_date} and {end_date}")
        else:
            st.markdown("### Projects Summary")
            monthly_df = pd.DataFrame(monthly_data)
            monthly_df['total_cost'] = monthly_df['total_cost'].apply(lambda x: f"{x:,.0f} KRW")
            monthly_df = monthly_df.rename(columns={
                'project': 'Project',
                'n_stage_reactors': 'N-Stage Reactors',
                'total_cost': 'Total Cost'
            })
            
            st.dataframe(monthly_df, use_container_width=True, hide_index=True)
            
            grand_total = sum([d['total_cost'] for d in monthly_data])
            st.markdown("---")
            col1, col2, col3 = st.columns([2, 1, 1])
            with col2:
                st.metric("**Period Total**", f"{grand_total:,.0f} KRW")
            
            st.markdown("### 📥 Export Data")
            
            export_data = []
            for project_info in monthly_data:
                cost_details = utils.calculate_project_cost(
                    project_info['project'],
                    st.session_state.bookings,
                    st.session_state.cost_matrix
                )
                for item in cost_details['breakdown']:
                    export_data.append({
                        'Project': project_info['project'],
                        'Scale': item['scale'],
                        'Method': item['method'],
                        'Quantity': item['qty'],
                        'Unit Cost (KRW)': item['unit_cost'],
                        'Subtotal (KRW)': item['subtotal']
                    })
            
            if export_data:
                export_df = pd.DataFrame(export_data)
                csv = export_df.to_csv(index=False).encode('utf-8')
                st.download_button(
                    label="⬇️ Download Cost Report (CSV)",
                    data=csv,
                    file_name=f"cost_report_{start_date}_{end_date}.csv",
                    mime="text/csv"
                )

st.divider()

with st.expander("📖 View Cost Matrix Reference"):
    st.markdown("### Current Unit Costs")
    cost_display = st.session_state.cost_matrix.copy()
    cost_display['cost'] = cost_display['cost'].apply(lambda x: f"{x:,.0f} KRW")
    cost_display = cost_display.rename(columns={'scale': 'Scale', 'method': 'Method', 'cost': 'Unit Cost'})
    st.dataframe(cost_display, use_container_width=True, hide_index=True)
 

