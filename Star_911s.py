import streamlit as st
import pandas as pd
import pyreadstat
from datetime import datetime, timedelta
import os
import tempfile

st.set_page_config(
    page_title="Project Star: 911 Automation Dashboard",
    page_icon="⭐",
    layout="wide"
)

st.title("⭐ Project Star: 911 Automation Dashboard")
st.markdown("Select your project section, upload your master SPSS (`.sav`) file, choose your date window, and run the pipeline.")

# Section Selector in Sidebar
section_choice = st.sidebar.selectbox("Select Project Section:", ["Growth", "R10Mil"])

st.header(f"1. Upload Data ({section_choice} Section)")
uploaded_file = st.file_uploader(f"Upload Master SPSS Data File (.sav) for {section_choice}", type=["sav"])

st.header("2. Configure Date Window")
date_mode = st.radio("Select Date Filtering Mode:", ["Dynamic Past 7 Days (Auto Friday)", "Custom Date Range"])

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
    st.info(f"Targeting automatic window: **{last_friday.strftime('%Y-%m-%d')}** to **{today.strftime('%Y-%m-%d')}**")
else:
    col1, col2 = st.columns(2)
    with col1:
        start_date_input = st.date_input("Start Date", value=today - timedelta(days=7))
    with col2:
        end_date_input = st.date_input("End Date", value=today)
    
    last_friday = datetime.combine(start_date_input, datetime.min.time())
    today = datetime.combine(end_date_input, datetime.max.time())

# --- Run Pipeline Button ---
if st.button("🚀 Run Processing & Generate Reports", type="primary"):
    if uploaded_file is None:
        st.error("⚠️️ Please upload a valid SPSS (.sav) file first.")
    else:
        with st.spinner(f"Processing {section_choice} pipeline... Please wait."):
            with tempfile.NamedTemporaryFile(delete=False, suffix=".sav") as tmp_file:
                tmp_file.write(uploaded_file.getvalue())
                tmp_path = tmp_file.name

            try:
                # Load dataset
                df, meta = pyreadstat.read_sav(tmp_path)
                
                # 2. Select completed interviews only (V9999 == 1)
                if 'V9999' in df.columns:
                    df_filtered = df[df['V9999'] == 1].copy()
                else:
                    df_filtered = df.copy()
                    st.warning("Column 'V9999' not found. Skipping completion filter.")

                # Filter records by STIME
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
                else:
                    st.warning("Column 'STIME' not found. Skipping date range filtering.")

                if df_filtered.empty:
                    st.warning("⚠️ No records found matching the selected criteria.")
                else:
                    st.success(f"✅ Found {len(df_filtered)} records for this window in {section_choice}!")

                    # Transformations
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
                    
                    for col_target, col_src in [('PRIM_OFCR_IND', 'V8026'), ('OFFICER_NAME_AND_SURNAME', 'V8016'), 
                                                  ('BUSINESS_NAME', 'V56011'), ('REGIONS', 'V12290'), 
                                                  ('SUB_REGIONS', 'V13290'), ('SEGMENT', 'V44011')]:
                        if col_src in df_filtered.columns:
                            df_filtered.loc[valid_intnr, col_target] = df_filtered[col_src]

                    # NPS Buckets
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

                    # Bank switches
                    bank_columns = [('Q16_1_1', 'Absa'), ('Q16_1_2', 'Capitec'), ('Q16_1_3', 'Investec'),
                                    ('Q16_1_4', 'Mercantile'), ('Q16_1_5', 'Nedbank'), ('Q16_1_6', 'Sasfin'), ('Q16_1_7', 'Standard Bank')]
                    
                    switch_compiled = []
                    for idx, row in df_filtered.iterrows():
                        matched_banks = []
                        for col_flag, bank_label in bank_columns:
                            if col_flag in df_filtered.columns and row.get(col_flag) == 1:
                                matched_banks.append(bank_label)
                        for loop_col in ['TQ16_1C8', 'TQ16_1C9', 'TQ16_1C10']:
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

                    # Priority Qualifiers
                    df_filtered['Qualifier'] = "Not Priority"
                    if 'Q14_2' in df_filtered.columns:
                        df_filtered.loc[df_filtered['Q14_2'] < 7, 'Qualifier'] = "Priority"
                    if 'Q16' in df_filtered.columns:
                        df_filtered.loc[df_filtered['Q16'] == 1, 'Qualifier'] = "Priority"

                    # Text Categorization
                    case_desc_upper = df_filtered['CASE_DESCRIPTION'].fillna('').str.upper() if 'CASE_DESCRIPTION' in df_filtered.columns else pd.Series([""]*len(df_filtered))
                    people_keywords = [
                        'BM', 'BUSINESS MANAGER', 'BUSINESS MANAGERS', 'BUSINESS BANKER', 'BUSINESS BANKERS',
                        'PRIVATE BANKER', 'BUSINESS CONSULTANT', 'RM ', 'RELATIONSHIP MANAGER', 'TELLERS',
                        'CONSULTANT', 'BANKER', 'STAFF', 'REPRESENTATIVE', 'PERSONAL', 'HUMAN', 'MANAGEE',
                        'BROKERS', 'RELATIONSHIP', 'COMMUNICATE', 'TREATED', 'INTERACTION', 'PEOPLE', 'CONTACTS',
                        'CONTACT', 'COMMUNICATION', 'SOMEONE', 'CUSTOMER SERVICE', 'BM/RM', 'RM', 'PERSON',
                        'WELCOME', 'MANNER', 'WALK', 'HONESTY', 'TRUST', 'ATTENDING', 'PROMISED', 'UNDERSTAND', 'CLIENTS'
                    ]
                    process_keywords = [
                        'LETTER', 'SECURE', 'GUARANTEE', 'ACCESS', 'ACCESSIBLE', 'ACTION', 'ALLOWS', 'APPROVED',
                        'ASSIST', 'ATTENDED', 'ATTENTION', 'CHANGE', 'CONNECTIVITY', 'CUSTOMER', 'COMMUNICATION',
                        'DEBIT', 'DISRUPTING', 'DOCUMENTATION', 'EASIER', 'EASILY', 'ENQUIRIE', 'FEEDBACK',
                        'FINGER', 'FOLLOWING', 'FRAUD', 'FUNCTIONALITY', 'FUNDING', 'PROVIDE', 'INFORMATION', 
                        'ISSUES', 'LENDING', 'LONG', 'NETWORK', 'NOTIFICATION', 'NOTIFIED', 'OPENING', 'ORDER', 
                        'OTP', 'PERIOD', 'PREVENT', 'PROCESS', 'QUERIES', 'QUEUE', 'QUEUES', 'QUICKER', 'QUICKLY', 
                        'REGULATION', 'RESOLVE', 'RETURN', 'REVERSE', 'QUERY', 'RESOLUTION', 'SECURITY', 'SERVICE', 
                        'SETUP', 'SPAM', 'SPEED', 'SYSTEM', 'TIME', 'TRANSACTION', 'TRANSFER', 'TURNAROUND', 
                        'UNAUTHORISED', 'USER-FRIENDLY', 'WAITING', 'WORKING', 'FASTER', 'EXPIRE', 'QUICK', 
                        'SANITIZER', 'HELP', 'LINK', 'PROMISES', 'CONVENIENT', 'CLOSING', 'EFFICIENCY', 'URGENCY', 
                        'THROUGH', 'SUNDAY', 'SATURDAY', 'DESKS', 'INQUIRY', 'POINTS', 'VERIFYING MY ACCOUNT', 
                        'THE LAW ON CALL', 'IF THERE IS A DISPUTE'
                    ]
                    product_keywords = [
                        'SHARIAH', 'INVESTMENT', 'SOLUTION', 'EQUITIE', 'CASH', 'CHEQUES', 'MONEY', 'CARD', 
                        'FLEET', 'ONLINE BANKING', 'OVERDRAFT', 'BUSINESS BANKING', 'INVESTMENTS', 'INSURANCE', 
                        'APP', 'FNB BANKING APP', 'CREDIT APPLICATION', 'BANK CHARGES', 'BANK FEES', 
                        'BANKING COSTS', 'COSTS', 'BUSINESS ACCOUNT', 'CONTACT CENTRE', 'CALL CENTRE', 
                        'CALL ACCOUNTS', 'CALL ACCOUNT', 'INVESTMENT ACCOUNTS', 'PRICING', 'SPEED POINT', 
                        'TRANSACTION', 'FICA', 'ONLINE', 'MONEY MARKET', 'FOREX', 'CREDIT CARDS', 'PRODUCTS', 
                        'FOREIGN', 'E-BUCKS', 'PRIVATE BANKING', 'VEHICLE', 'VAF', 'CASH WITHDRAWAL', 
                        'E-WALLET', 'BUSINESS', 'PROPERTY', 'FINANCE', 'WESBANK', 'SHARER', 'TRADE', 
                        'BRANCHES', 'FACILITIES', 'CURRENCY', 'UIF', 'COVID', 'MERCHANT', 'ATM', 'PAY', 
                        'EBACKS', 'INTERNET', 'BANKING', 'LEVIES', 'COST', 'LOAN', 'EXPENSIVE', 'FEE', 
                        'E BUCKS', 'NEW ACCOUNT', 'FINANCING', 'CREDIT', 'LOANS', 'INTEREST', 'RATES', 
                        'FEES', 'CHARGE', 'TRAINING', 'ADVICE', 'INCONTACT', 'NOTIFICATIONS', 'BENEFITS', 
                        'REWARDS', 'EBUCKS', 'ACCOUNTS', 'STATEMENTS', 'TRANSACTIONS', 'PAYMENTS', 
                        'GIVING FUNDS FOR COMPANY ASSETS'
                    ]
                    none_keywords = [
                        'NO IMPROVEMENT', 'T THINK', 'DON?T KNOW', 'ALL FINE FROM MY SIDE', 'N/A', 'NOTHING', 
                        'NOTHING TO IMPROVE', 'ANYTHING', 'I AM SATISFIED', 'I HAVE NO ISSUES', 'NO COMMENT', 
                        'NONE', 'HAPPY WITH EVERYTHING', 'NO COMPLAINT AT THE MOMENT', 'SATISFIED', 'I AM HAPPY', 
                        'NO IMPROVEMENTS', 'ALL GOOD', 'ALL HAPPY', 'ALL IN ORDER', 'CANT THINK OF ANY', 
                        'DONT KNOW', 'FUCK', 'GOOD', 'I DO NOT HAVE', 'T HAVE', 'HAVE ANSWERS', 'ANY ISSUES', 
                        'NA', 'NOT APPLICABLE', 'NOT MUCH', 'NOT NOW', 'NOT SURE', 'NOT AT THE MOMENT', 
                        'NOT SURE OF ANY', 'NOT THAT I THINK OF', '-1', 'EVERYTHING', 'EXCELLENT', 'KNOW', 
                        'ALL IS FINE', 'ANY PROBLEM', 'NO ASPECTS', 'NO ASPECT FOR FNB TO IMPROVE ON',
                        'NO SINGLE IMPORTANT ASPECT THAT FNB  NEEDS TO IMPROVE ON', 'NO ASPECT', 
                        'NO IMPORTATNT ASPECT', 'NO IMPORTANT ASPECT', 'NO SINGLE MOST IMPORTANT ASPECT', 'NO IMPROVMENTS'
                    ]

                    def contains_keywords(text, kw_list):
                        return 1 if any(kw in text for kw in kw_list) else 0

                    df_filtered['People_1'] = case_desc_upper.apply(lambda x: contains_keywords(x, people_keywords))
                    df_filtered['PROCESS_1'] = case_desc_upper.apply(lambda x: contains_keywords(x, process_keywords))
                    df_filtered['PRODUCT_1'] = case_desc_upper.apply(lambda x: contains_keywords(x, product_keywords))
                    df_filtered['NONE_OVERRIDE'] = case_desc_upper.apply(lambda x: contains_keywords(x, none_keywords))

                    def apply_triple_p_logic(row):
                        if row.get('NONE_OVERRIDE') == 1:
                            return "NONE"
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

                    # Dynamic Prefix based on Section Choice
                    prefix = "Business_Client_911" if section_choice == "Growth" else "Enterprise_Client_911"

                    f1_data = base_priority_data[(base_priority_data.get('FNB_NPS') == "NPS - Detractor") | (base_priority_data.get('RM_BM_NPS') == "NPS - Detractor")]
                    f2_data = f1_data.drop(columns=['PRODUCT_PEOPLE_PROCESS'], errors='ignore')
                    f3_data = base_priority_data
                    f4_data = base_priority_data.drop(columns=['PRODUCT_PEOPLE_PROCESS'], errors='ignore')

                    st.success(f"🎉 Processing complete for **{section_choice}**! Download your output files below:")

                    col_d1, col_d2 = st.columns(2)
                    with col_d1:
                        st.download_button(
                            "📥 Download Output 1 (NPS D Classification)", 
                            f1_data.to_csv(sep='|', index=False, encoding='utf-8-sig').encode('utf-8-sig'), 
                            file_name=f"{prefix}_NPS_D_classification_{run_date_file}.csv", mime="text/csv"
                        )
                        st.download_button(
                            "📥 Download Output 2 (NPS D NO Classification)", 
                            f2_data.to_csv(sep='|', index=False, encoding='utf-8-sig').encode('utf-8-sig'), 
                            file_name=f"{prefix}_NPS_D_NO_classification_{run_date_file}.csv", mime="text/csv"
                        )
                    with col_d2:
                        st.download_button(
                            "📥 Download Output 3 (NPS D S Classification)", 
                            f3_data.to_csv(sep='|', index=False, encoding='utf-8-sig').encode('utf-8-sig'), 
                            file_name=f"{prefix}_NPS_D_S_classification_{run_date_file}.csv", mime="text/csv"
                        )
                        st.download_button(
                            "📥 Download Output 4 (NPS D S NO Classification)", 
                            f4_data.to_csv(sep='|', index=False, encoding='utf-8-sig').encode('utf-8-sig'), 
                            file_name=f"{prefix}_NPS_D_S_NO_classification_{run_date_file}.csv", mime="text/csv"
                        )

            except Exception as e:
                st.error(f"❌ An error occurred during processing: {e}")
            finally:
                if os.path.exists(tmp_path):
                    os.remove(tmp_path)
