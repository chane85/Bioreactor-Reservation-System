import streamlit as st
import pandas as pd
import datetime
import utils
import auth

st.set_page_config(page_title="비용 산출", layout="wide")

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
            267915,
            1239045, 1392776, 1620680,
            1211714, 1268641, 1436718, 2166611, 2238964,
            26891157, 33645055, 27318015, 76861560, 79701514
        ]
    }
    st.session_state.cost_matrix = pd.DataFrame(cost_data)

st.header("💰 비용 산출")

unknown_count = (st.session_state.bookings['method'] == 'Unknown').sum() if 'method' in st.session_state.bookings.columns else 0
if unknown_count > 0:
    st.warning(f"⚠️ {unknown_count} bookings have 'Unknown' method. Cost calculations will exclude these bookings. Please assign methods in Admin page.")

st.divider()

tab1, tab2 = st.tabs(["📊 제품별 비용 계산", "📅 월별 비용 계산"])

with tab1:
    st.subheader("제품별 비용 계산")
    st.caption("본배양 및 스케일(Ambr15, Ambr250, 2L, 200L) 기반 비용 계산")
    
    
    n_stage_bookings = st.session_state.bookings[st.session_state.bookings['stage'] == 'N']
    
    if n_stage_bookings.empty:
        st.info("No N-stage bookings found.")
    else:
        projects = sorted(n_stage_bookings['project'].unique())
        
        c1, c2 = st.columns([1, 3])
        with c1:
            selected_projects = st.multiselect("제품 선택", projects)
            st.caption("여러 제품 선택 가능")
        if selected_projects:
            grand_total = 0
            for selected_project in selected_projects:
                cost_data = utils.calculate_project_cost(
                    selected_project,
                    st.session_state.bookings,
                    st.session_state.cost_matrix
                )
                st.markdown(f"### 📁 {selected_project}")
                if cost_data['total'] == 0:
                    st.info(f"No cost data available for {selected_project}.")
                else:
                    breakdown_df = pd.DataFrame(cost_data['breakdown'])
                    breakdown_df['unit_cost'] = breakdown_df['unit_cost'].apply(lambda x: f"{x:,.0f} KRW")
                    breakdown_df['subtotal'] = breakdown_df['subtotal'].apply(lambda x: f"{x:,.0f} KRW")
                    breakdown_df = breakdown_df.rename(columns={
                        'scale': 'Scale',
                        'method': 'Method',
                        'bioreactors': 'Bioreactors',
                        'stations': 'Stations',
                        'vessels': 'Vessels',
                        'unit_cost': 'Unit Cost (per vessel)',
                        'subtotal': 'Subtotal'
                    })
                    display_cols = ['Scale', 'Method', 'Bioreactors', 'Stations', 'Vessels', 'Unit Cost (per vessel)', 'Subtotal']
                    st.dataframe(breakdown_df[display_cols], use_container_width=True, hide_index=True)
                    col1, col2, col3 = st.columns([2, 1, 1])
                    with col2:
                        st.metric(f"Total ({selected_project})", f"{cost_data['total']:,.0f} KRW")
                    grand_total += cost_data['total']
                st.markdown("---")

            if len(selected_projects) > 1:
                col1, col2, col3 = st.columns([2, 1, 1])
                with col2:
                    st.metric("**Combined Total**", f"{grand_total:,.0f} KRW")
                

with tab2:
    st.subheader("월별 비용 계산")
    st.caption("💡 지정 기간 내 비용")
    
    c1, c2, c3 = st.columns([1, 1, 2])
    
    today = datetime.date.today()
    default_start = today.replace(day=1)
    default_end = (default_start + datetime.timedelta(days=32)).replace(day=1) - datetime.timedelta(days=1)
    
    with c1:
        start_date = st.date_input("시작 일자", value=default_start)
    with c2:
        end_date = st.date_input("종료 일자", value=default_end)
    
    if start_date > end_date:
        st.error("⚌ 시작 일자는 종료 일자보다 앞의 일자를 선택해야합니다.")
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
            st.markdown("### 제품별 비용 산출")
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
                st.metric("**총비용**", f"{grand_total:,.0f} KRW")
            
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
                        'Bioreactors': item['bioreactors'],
                        'Stations': item['stations'],
                        'Vessels': item['vessels'],
                        'Unit Cost (KRW per vessel)': item['unit_cost'],
                        'Subtotal (KRW)': item['subtotal']
                    })
            
            if export_data:
                export_df = pd.DataFrame(export_data)
                csv = export_df.to_csv(index=False).encode('utf-8')
                st.download_button(
                    label="⬇️ 다운로드 (.csv)",
                    data=csv,
                    file_name=f"cost_report_{start_date}_{end_date}.csv",
                    mime="text/csv"
                )

st.divider()

with st.expander("스케일/공정별 개발 비용"):
    st.markdown("### Current Unit Costs")
    cost_display = st.session_state.cost_matrix.copy()
    cost_display['cost'] = cost_display['cost'].apply(lambda x: f"{x:,.0f} KRW")
    cost_display = cost_display.rename(columns={'scale': 'Scale', 'method': 'Method', 'cost': 'Unit Cost'})
    st.dataframe(cost_display, use_container_width=True, hide_index=True)
 

