# parsers/tm_parser.py
import pandas as pd
import traceback
import streamlit as st
import toml


def parse(uploaded_file):
    try:
        config = toml.load("config.toml")
        hc_friends = config['fleet'].get('hc_friends', [])
        tm_name = config['companies']['tm_name']
        hc_name = config['companies']['hc_name']

        xls = pd.ExcelFile(uploaded_file)
        df = pd.read_excel(xls, sheet_name=xls.sheet_names[0])

        header_idx = df[df.iloc[:, 0] == 'Vehicle'].index
        if len(header_idx) == 0:
            st.error("未能找到 'Vehicle' 表头，请确认文件是否为合并报表格式。")
            return pd.DataFrame()

        h_idx = header_idx[0]
        df.columns = df.iloc[h_idx].tolist()
        df = df.iloc[h_idx + 1:].reset_index(drop=True)

        df_clean = df[['Vehicle', 'Driver', 'First Active Time', 'Total Mileage (km)']].copy()
        df_clean = df_clean.dropna(subset=['First Active Time', 'Total Mileage (km)'])
        df_clean = df_clean[df_clean['Driver'] != '--']

        df_clean['Date'] = pd.to_datetime(df_clean['First Active Time'], errors='coerce').dt.normalize()
        df_clean['Distance (km)'] = pd.to_numeric(df_clean['Total Mileage (km)'], errors='coerce')

        df_clean['Company_Type'] = df_clean['Vehicle'].apply(lambda v: hc_name if v in hc_friends else tm_name)
        df_clean['Vehicle_Type'] = 'Flatbed'

        return df_clean[['Date', 'Vehicle', 'Company_Type', 'Vehicle_Type', 'Distance (km)']].dropna(subset=['Date'])

    except Exception as e:
        traceback.print_exc()
        st.error(f"TM Flatbed 解析错误: {str(e)}\n请检查上传文件格式是否正确。")
        return pd.DataFrame()