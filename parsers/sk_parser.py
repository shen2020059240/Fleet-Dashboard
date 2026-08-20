# parsers/sk_parser.py
import pandas as pd
import traceback
import streamlit as st
import toml


def parse(uploaded_file):
    try:
        config = toml.load("config.toml")
        company_name = config['companies']['sk_name']

        xls = pd.ExcelFile(uploaded_file)
        vehicle_sheets = [s for s in xls.sheet_names if not str(s).endswith(' - 2')]
        all_records = []

        for sheet in vehicle_sheets:
            df = pd.read_excel(xls, sheet_name=sheet, header=None)
            current_date = None
            for index, row in df.iterrows():
                val_0 = str(row[0]).strip()
                if val_0.startswith('report |'):
                    try:
                        date_str = val_0.split('|')[1].strip().split(' ')[0]
                        current_date = pd.to_datetime(date_str, format='%d.%m.%Y')
                    except:
                        current_date = None
                elif val_0 == 'In total:' and current_date is not None:
                    distance = pd.to_numeric(row[6], errors='coerce')
                    if pd.notna(distance):
                        all_records.append({
                            'Date': current_date,
                            'Vehicle': sheet,
                            'Company_Type': company_name,
                            'Vehicle_Type': 'Oil Tanker',
                            'Distance (km)': distance
                        })
                    current_date = None

        return pd.DataFrame(all_records)
    except Exception as e:
        traceback.print_exc()
        st.error(f"SK Oil Tanker 解析错误: {str(e)}\n请检查上传文件格式是否正确。")
        return pd.DataFrame()