# views/logistic.py
import streamlit as st
import pandas as pd
from utils.db import load_from_db, load_logistic_from_db


def render():
    st.title("🚚 TFM Flatbed 订单物流实时监控 (Function 2)")
    st.markdown("💡 智能引擎已替代 Excel 嵌套公式，直接关联云端核心数据库，自动执行实时里程累加与状态匹配。")

    # 获取全量数据
    df_fleet = load_from_db()
    df_log = load_logistic_from_db()

    if df_log.empty:
        st.warning("⚠️ 目前没有物流数据。请前往「数据中心」通道 C 上传脱敏报表。")
        return

    if df_fleet.empty:
        st.warning("⚠️ 车辆主数据库目前为空，无法计算里程跨度。")
        return

    with st.spinner("正在执行云端智能匹配与里程计算..."):
        # 1. 🌟 智能提取列名（不再写死固定位置，完美兼容你新增的 Reference No）
        # 只要列名里包含 'DATE'，系统就自动把它认作物流节点
        date_cols = [col for col in df_log.columns if 'DATE' in col.upper()]

        # 剩下的列（比如车牌号、订单号、客户等），系统全部打包保留
        other_cols = [col for col in df_log.columns if col not in date_cols and col not in ['行驶距离', '距离/状态']]

        # 永远将第一列视作车牌号用于匹配
        truck_col = other_cols[0]

        # 2. 清理主数据库的车牌格式（去除空格，强制大写，防止匹配失败）
        df_fleet['Vehicle_Clean'] = df_fleet['Vehicle'].astype(str).str.strip().str.upper()

        # 3. 核心计算逻辑
        def process_logistic_row(row):
            truck = str(row[truck_col]).strip().upper()
            dates = pd.to_datetime(row[date_cols], errors='coerce')
            valid_dates = dates.dropna()

            if len(valid_dates) == 0:
                return pd.Series(["暂未开始运输", "已下单但暂未开始运输"])

            start_date = valid_dates.min()
            end_date = valid_dates.max()

            status = ""
            if pd.notna(dates.iloc[6]):
                status = "已完成订单"
            elif pd.notna(dates.iloc[5]):
                status = "到卸货地点"
            elif pd.notna(dates.iloc[4]):
                status = "离开边境关口"
            elif pd.notna(dates.iloc[3]):
                status = "到边境关口"
            elif pd.notna(dates.iloc[2]):
                status = "装好货出发"
            elif pd.notna(dates.iloc[1]):
                status = "装货"
            elif pd.notna(dates.iloc[0]):
                status = "到装货地点"

            truck_mask = df_fleet['Vehicle_Clean'] == truck
            if not truck_mask.any():
                return pd.Series(["车牌号不相符", "车牌号不相符"])

            mask = truck_mask & (df_fleet['Date'] >= start_date) & (df_fleet['Date'] <= end_date)
            dist = df_fleet.loc[mask, 'Distance (km)'].sum()

            dist_str = f"{dist:.1f}"
            dist_status = f"{dist:.1f}公里 ({status})"

            return pd.Series([dist_str, dist_status])

        # 4. 批量执行并生成新列
        df_log[['行驶距离', '距离/状态']] = df_log.apply(process_logistic_row, axis=1)

        # ==========================================
        # 📊 界面展示渲染
        # ==========================================
        st.success(f"✅ 计算完成！共处理 {len(df_log)} 条在途订单。")

        # 将日期格式化为易读的字符串
        for col in date_cols:
            df_log[col] = df_log[col].dt.strftime('%Y-%m-%d').fillna('')

        # 🌟 动态重组表格展示顺序：所有其他列(含Reference No) + 计算结果 + 日期节点
        final_cols = other_cols + ['行驶距离', '距离/状态'] + date_cols
        df_display = df_log[final_cols]

        st.dataframe(
            df_display,
            use_container_width=True,
            hide_index=True,
            height=600
        )