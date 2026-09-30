import streamlit as st
import pandas as pd
import pyreadstat
from datetime import datetime, timedelta
import os
import tempfile

st.set_page_config(
    page_title="Project Star: Control Room",
    page_icon="⭐",
    layout="wide"
)

# --- CONTROL ROOM HEADER ---
st.markdown("### `[02 // CONTROL ROOM]` &nbsp;&nbsp;&nbsp; `SYS.READY // PIPELINE 2.2`")
st.markdown("Execute and monitor each section of the Project Star 911 market research data pipeline.")
st.markdown("---")

# --- SYSTEM METRICS BAR ---
col_m1, col_m2, col_m3, col_m4 = st.columns(4)
col_m1.metric("Pipeline Status", "IDLE / READY", "Stable")
col_m2.metric("Active Wave", "Wave 22", "2026")
col_m3.metric("Modules Loaded", "3 / 3", "Growth, R10Mil, PUBSC")
col_m4.metric("Environment", "Cloud Control Room", "Secure")

st.markdown("---")

# --- GLOBAL DATE CONFIGURATION PANEL ---
st.subheader("📅 Global Execution Parameters")
date_mode = st.radio("Select Date Filtering Mode for Runs:", ["Dynamic Past 7 Days (Auto Friday)", "Custom Date Range"], horizontal=True)

today = datetime.now()

if date_mode == "Dynamic Past 7 Days (Auto Friday)":
    current_weekday = today.weekday()
    if current_weekday == 4:
        days_to_subtract = 7
    else:
        days_to_subtract = (current_weekday - 4) % 7
        if days_to_subtract == 0:
            days_to_subtract = 7
    last_friday = today - timedelta(days=days_to_subtract)
    last_friday = last_friday.replace(hour=0, minute=0, second=0, microsecond=0)
    st.info(f"🎯 Target active execution window: **{last_friday.strftime('%Y-%m-%d')}** to **{today.strftime('%Y-%m-%d')}**")
else:
    col_d1, col_d2 = st.columns(2)
    with col_d1:
        start_date_input = st.date_input("Start Date", value=today - timedelta(days=7))
    with col_d2:
        end_date_input = st.date_input("End Date", value=today)
    
    last_friday = datetime.combine(start_date_input, datetime.min.time())
    today = datetime.combine(end_date_input, datetime.max.time())

st.markdown("---")

# --- CORE PROCESSING FUNCTION ---
def run_pipeline(uploaded_file, section_choice):
    with tempfile.NamedTemporaryFile(delete=False, suffix=".sav") as tmp_file:
        tmp_file.write(uploaded_file.getvalue())
        tmp_path = tmp_file.name

    try:
        df, meta = pyreadstat.read_sav(tmp_path)
        
        if 'V9999' in df.columns:
            df_filtered = df[df['V9999'] == 1].copy()
        else:
            df_filtered = df.copy()

        if 'STIME' in df_filtered.columns:
            df_filtered['STIME_CLEAN'] = df_filtered['STIME'].astype(str).str.strip().str[:8]
            def parse_stime_date(x):
                try:
                    return datetime.strptime(x, "%Y%m%d")
                except:
                    return None
            df_filtered['STIME_DATE'] = df_filtered['STIME_CLEAN'].apply(parse_stime_date)
            
            df_filtered = df_filtered[
                (df_filtered['STIME_DATE'] >= last_friday) & 
                (df_filtered['STIME_DATE'] <= today)
            ].copy()

        if df_filtered.empty:
            st.warning(f"⚠️ No records found matching the criteria for {section_choice}.")
            return None

        if 'INTNR' not in df_filtered.columns:
            df_filtered['INTNR'] = range(1, len(df_filtered) + 1)
            
        valid_intnr = df_filtered['INTNR'] > 0

        df_filtered.loc[valid_intnr, 'PARENT_TYPE'] = "Juristic"
        df_filtered.loc[valid_intnr, 'WAVE'] = "22"
        if 'V80116' in df_filtered.columns:
            df_filtered.loc[valid_intnr, 'CLIENT_UCN'] = df_filtered['V80116']
        df_filtered.loc[valid_intnr, 'CLIENT_TYPE'] = "Full Client"
        df_filtered.loc[valid_intnr, 'COMPANY_CODE'] = "15"
        df_filtered.loc[valid_intnr, 'CASE_SUBJECT'] = "Coverage"
        df_filtered.loc[valid_intnr, 'REQUEST_CATEGORY'] = "Care"
        df_filtered.loc[valid_intnr, 'TOPIC'] = "Complaints"

        tq13_open_clean = df_filtered['TQ13_OPEN'].fillna('').astype(str) if 'TQ13_OPEN' in df_filtered.columns else ""
        df_filtered.loc[valid_intnr, 'CASE_DESCRIPTION'] = "Improvement Area: " + tq13_open_clean

        df_filtered.loc[valid_intnr, 'CAMPAIGN'] = "CMP-01522-S7K7N3"
        df_filtered.loc[valid_intnr, 'ORIGIN'] = "Web"
        df_filtered.loc[valid_intnr, 'OWNER'] = r"FNBJNB01\Web"
        
        sub_region_col = 'V8013' if section_choice == 'PUBSC' else 'V13290'
        segment_col = 'V13290' if section_choice == 'PUBSC' else 'V44011'

        mapping_pairs = [
            ('PRIM_OFCR_IND', 'V8026'), ('OFFICER_NAME_AND_SURNAME', 'V8016'), 
            ('BUSINESS_NAME', 'V56011'), ('REGIONS', 'V12290'), 
            ('SUB_REGIONS', sub_region_col), ('SEGMENT', segment_col)
        ]

        for col_target, col_src in mapping_pairs:
            if col_src in df_filtered.columns:
                df_filtered.loc[valid_intnr, col_target] = df_filtered[col_src]

        def calculate_nps_bucket(score):
            if pd.isna(score): return None
            if score < 7: return "NPS - Detractor"
            elif score in [7, 8]: return "NPS - Passive"
            elif score > 8: return "NPS - Promoter"
            return None

        if 'Q14_1' in df_filtered.columns:
            df_filtered['FNB_NPS'] = df_filtered['Q14_1'].apply(calculate_nps_bucket)
            df_filtered['FNB_NPS_OPEN_ENDED'] = df_filtered.apply(lambda r: r['TQ14_1_OPEN'] if 'TQ14_1_OPEN' in df_filtered.columns and pd.notna(r.get('TQ14_1_OPEN')) and r['Q14_1'] < 7 else None, axis=1)
        if 'Q14_2' in df_filtered.columns:
            df_filtered['RM_BM_NPS'] = df_filtered['Q14_2'].apply(calculate_nps_bucket)
            df_filtered['RM_BM_NPS_OPEN_ENDED'] = df_filtered.apply(lambda r: r['TQ14_2_OPEN'] if 'TQ14_2_OPEN' in df_filtered.columns and pd.notna(r.get('TQ14_2_OPEN')) and r['Q14_2'] < 7 else None, axis=1)

        if section_choice == 'PUBSC':
            bank_columns = [('Q16_1_1', 'Absa'), ('Q16_1_2', 'Investec'), ('Q16_1_3', 'Nedbank'), ('Q16_1_4', 'Standard Bank'), ('Q16_1_5', 'Capitec'), ('Q16_1_6', 'Refused')]
            loop_cols = ['TQ16_1C6', 'TQ16_1C7', 'TQ16_1C8']
        else:
            bank_columns = [('Q16_1_1', 'Absa'), ('Q16_1_2', 'Capitec'), ('Q16_1_3', 'Investec'), ('Q16_1_4', 'Mercantile'), ('Q16_1_5', 'Nedbank'), ('Q16_1_6', 'Sasfin'), ('Q16_1_7', 'Standard Bank')]
            loop_cols = ['TQ16_1C8', 'TQ16_1C9', 'TQ16_1C10']
        
        switch_compiled = []
        for idx, row in df_filtered.iterrows():
            matched_banks = []
            for col_flag, bank_label in bank_columns:
                if col_flag in df_filtered.columns and row.get(col_flag) == 1:
                    matched_banks.append(bank_label)
            for loop_col in loop_cols:
                if loop_col in df_filtered.columns and pd.notna(row.get(loop_col)) and str(row[loop_col]).strip() != '':
                    matched_banks.append(str(row[loop_col]).strip())
            switch_compiled.append(",".join(matched_banks))
            
        df_filtered['WOULD_CONSIDER_SWITCH_TO'] = switch_compiled
        if 'TQ16_OPEN' in df_filtered.columns:
            df_filtered.loc[valid_intnr, 'REASON'] = df_filtered['TQ16_OPEN']

        if 'STIME_CLEAN' in df_filtered.columns:
            df_filtered['NYEAR'] = df_filtered['STIME_CLEAN'].str[:4]
            df_filtered['NMONTH'] = df_filtered['STIME_CLEAN'].str[4:6]
            df_filtered['NDAY'] = df_filtered['STIME_CLEAN'].str[6:8]
            df_filtered['RECORDED_DATE'] = df_filtered['NYEAR'] + "/" + df_filtered['NMONTH'] + "/" + df_filtered['NDAY']

        df_filtered['Qualifier'] = "Not Priority"
        if 'Q14_2' in df_filtered.columns:
            df_filtered.loc[df_filtered['Q14_2'] < 7, 'Qualifier'] = "Priority"
        if 'Q16' in df_filtered.columns:
            df_filtered.loc[df_filtered['Q16'] == 1, 'Qualifier'] = "Priority"

        case_desc_upper = df_filtered['CASE_DESCRIPTION'].fillna('').str.upper() if 'CASE_DESCRIPTION' in df_filtered.columns else pd.Series([""]*len(df_filtered))
        people_keywords = ['BM', 'BUSINESS MANAGER', 'BUSINESS BANKERS', 'PRIVATE BANKER', 'RM', 'RELATIONSHIP MANAGER', 'STAFF', 'CLIENTS']
        process_keywords = ['SYSTEM', 'PROCESS', 'SERVICE', 'DELAY', 'QUERY', 'ACCESS', 'APP']
        product_keywords = ['FEE', 'CHARGES', 'LOAN', 'ACCOUNT', 'INVESTMENT', 'CARD']
        none_keywords = ['NO IMPROVEMENT', 'NONE', 'SATISFIED', 'ALL GOOD', 'N/A']

        def contains_keywords(text, kw_list):
            return 1 if any(kw in text for kw in kw_list) else 0

        df_filtered['People_1'] = case_desc_upper.apply(lambda x: contains_keywords(x, people_keywords))
        df_filtered['PROCESS_1'] = case_desc_upper.apply(lambda x: contains_keywords(x, process_keywords))
        df_filtered['PRODUCT_1'] = case_desc_upper.apply(lambda x: contains_keywords(x, product_keywords))
        df_filtered['NONE_OVERRIDE'] = case_desc_upper.apply(lambda x: contains_keywords(x, none_keywords))

        def apply_triple_p_logic(row):
            if row.get('NONE_OVERRIDE') == 1: return "NONE"
            p, pp, pr = row.get('PRODUCT_1') == 1, row.get('People_1') == 1, row.get('PROCESS_1') == 1
            if pp and pr and p: return "ALL"
            if p and pr: return "PRODUCT & PROCESS"
            if p and pp: return "PRODUCT & PEOPLE"
            if pp and pr: return "PEOPLE & PROCESS"
            if p: return "PRODUCT ONLY"
            if pr: return "PROCESS ONLY"
            if pp: return "PEOPLE ONLY"
            return ""

        df_filtered['PRODUCT_PEOPLE_PROCESS'] = df_filtered.apply(apply_triple_p_logic, axis=1)
        df_filtered = df_filtered.sort_values(by='INTNR', ascending=True).copy()

        verbatim_cols = ['CASE_DESCRIPTION', 'FNB_NPS_OPEN_ENDED', 'RM_BM_NPS_OPEN_ENDED', 'WOULD_CONSIDER_SWITCH_TO', 'REASON']
        for col in verbatim_cols:
            if col in df_filtered.columns:
                df_filtered[col] = df_filtered[col].fillna('').astype(str).str.replace(',', '~', regex=False)

        df_priority = df_filtered[df_filtered['Qualifier'] == "Priority"].copy()

        keep_columns = [
            'PARENT_TYPE', 'WAVE', 'CLIENT_UCN', 'CLIENT_TYPE', 'COMPANY_CODE', 'CASE_SUBJECT',
            'REQUEST_CATEGORY', 'TOPIC', 'CASE_DESCRIPTION', 'PRODUCT_PEOPLE_PROCESS', 'CAMPAIGN',
            'ORIGIN', 'OWNER', 'PRIM_OFCR_IND', 'OFFICER_NAME_AND_SURNAME', 'BUSINESS_NAME',
            'REGIONS', 'SUB_REGIONS', 'SEGMENT', 'FNB_NPS', 'FNB_NPS_OPEN_ENDED', 'RM_BM_NPS',
            'RM_BM_NPS_OPEN_ENDED', 'WOULD_CONSIDER_SWITCH_TO', 'REASON', 'RECORDED_DATE'
        ]

        for c in keep_columns:
            if c not in df_priority.columns:
                df_priority[c] = ""

        base_priority_data = df_priority[keep_columns].copy()
        run_date_file = today.strftime("%Y_%m_%d")

        if section_choice == "Growth": prefix = "Business_Client_911"
        elif section_choice == "R10Mil": prefix = "Enterprise_Client_911"
        else: prefix = "PUBSC_Client_911"

        f1_data = base_priority_data[(base_priority_data.get('FNB_NPS') == "NPS - Detractor") | (base_priority_data.get('RM_BM_NPS') == "NPS - Detractor")]
        f2_data = f1_data.drop(columns=['PRODUCT_PEOPLE_PROCESS'], errors='ignore')
        f3_data = base_priority_data
        f4_data = base_priority_data.drop(columns=['PRODUCT_PEOPLE_PROCESS'], errors='ignore')

        return {
            "f1": (f1_data.to_csv(sep='|', index=False, encoding='utf-8-sig').encode('utf-8-sig'), f"{prefix}_NPS_D_classification_{run_date_file}.csv"),
            "f2": (f2_data.to_csv(sep='|', index=False, encoding='utf-8-sig').encode('utf-8-sig'), f"{prefix}_NPS_D_NO_classification_{run_date_file}.csv"),
            "f3": (f3_data.to_csv(sep='|', index=False, encoding='utf-8-sig').encode('utf-8-sig'), f"{prefix}_NPS_D_S_classification_{run_date_file}.csv"),
            "f4": (f4_data.to_csv(sep='|', index=False, encoding='utf-8-sig').encode('utf-8-sig'), f"{prefix}_NPS_D_S_NO_classification_{run_date_file}.csv"),
            "count": len(df_filtered)
        }
    except Exception as e:
        st.error(f"❌ Error in {section_choice}: {e}")
        return None
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)


# --- CONTROL ROOM STAGE TILES (CARDS) ---
st.subheader("⚡ Pipeline Execution Control Room")

col1, col2, col3 = st.columns(3)

# --- TILE 1: GROWTH ---
with col1:
    with st.container(border=True):
        st.markdown("### 🟢 Growth Section")
        st.caption("Target: Business Client Pipeline")
        file_growth = st.file_uploader("Upload GROW SAV (.sav)", type=["sav"], key="growth_file")
        
        if st.button("▶ Run Growth Stage", key="btn_growth", type="primary", use_container_width=True):
            if file_growth is None:
                st.error("Upload a SAV file first.")
            else:
                with st.spinner("Processing Growth..."):
                    res = run_pipeline(file_growth, "Growth")
                    if res:
                        st.success(f"Processed {res['count']} records!")
                        st.download_button("📥 Output 1", res['f1'][0], file_name=res['f1'][1], mime="text/csv", key="g1")
                        st.download_button("📥 Output 2", res['f2'][0], file_name=res['f2'][1], mime="text/csv", key="g2")
                        st.download_button("📥 Output 3", res['f3'][0], file_name=res['f3'][1], mime="text/csv", key="g3")
                        st.download_button("📥 Output 4", res['f4'][0], file_name=res['f4'][1], mime="text/csv", key="g4")

# --- TILE 2: R10MIL ---
with col2:
    with st.container(border=True):
        st.markdown("### 🔵 R10Mil Section")
        st.caption("Target: Enterprise Client Pipeline")
        file_r10 = st.file_uploader("Upload RMW SAV (.sav)", type=["sav"], key="r10_file")
        
        if st.button("▶ Run R10Mil Stage", key="btn_r10", type="primary", use_container_width=True):
            if file_r10 is None:
                st.error("Upload a SAV file first.")
            else:
                with st.spinner("Processing R10Mil..."):
                    res = run_pipeline(file_r10, "R10Mil")
                    if res:
                        st.success(f"Processed {res['count']} records!")
                        st.download_button("📥 Output 1", res['f1'][0], file_name=res['f1'][1], mime="text/csv", key="r1")
                        st.download_button("📥 Output 2", res['f2'][0], file_name=res['f2'][1], mime="text/csv", key="r2")
                        st.download_button("📥 Output 3", res['f3'][0], file_name=res['f3'][1], mime="text/csv", key="r3")
                        st.download_button("📥 Output 4", res['f4'][0], file_name=res['f4'][1], mime="text/csv", key="r4")

# --- TILE 3: PUBSC ---
with col3:
    with st.container(border=True):
        st.markdown("### 🟠 PUBSC Section")
        st.caption("Target: Public Sector Pipeline")
        file_pub = st.file_uploader("Upload PUBW SAV (.sav)", type=["sav"], key="pub_file")
        
        if st.button("▶ Run PUBSC Stage", key="btn_pub", type="primary", use_container_width=True):
            if file_pub is None:
                st.error("Upload a SAV file first.")
            else:
                with st.spinner("Processing PUBSC..."):
                    res = run_pipeline(file_pub, "PUBSC")
                    if res:
                        st.success(f"Processed {res['count']} records!")
                        st.download_button("📥 Output 1", res['f1'][0], file_name=res['f1'][1], mime="text/csv", key="p1")
                        st.download_button("📥 Output 2", res['f2'][0], file_name=res['f2'][1], mime="text/csv", key="p2")
                        st.download_button("📥 Output 3", res['f3'][0], file_name=res['f3'][1], mime="text/csv", key="p3")
                        st.download_button("📥 Output 4", res['f4'][0], file_name=res['f4'][1], mime="text/csv", key="p4")
