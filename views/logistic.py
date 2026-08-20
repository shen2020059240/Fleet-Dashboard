# views/logistic.py
import streamlit as st
import pandas as pd
import re
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
        # 1. 🌟 智能提取列名 (识别时间节点与其他信息)
        date_cols = [col for col in df_log.columns if 'DATE' in col.upper() and 'ORDER' not in col.upper()]
        order_date_col = next((col for col in df_log.columns if 'ORDER' in col.upper() and 'DATE' in col.upper()), None)
        other_cols = [col for col in df_log.columns if col not in date_cols and col not in ['行驶距离', '距离/状态']]

        # 🌟 智能定位车牌列
        truck_col = other_cols[0] if other_cols else None
        for col in other_cols:
            if any(keyword in col.upper() for keyword in ['HORSE', 'TRUCK', 'VEHICLE', '车牌']):
                truck_col = col
                break

        if not truck_col:
            st.error("❌ 无法在上传的表格中找到车牌号，请确保车牌列包含 HORSE, TRUCK 或 VEHICLE 等字眼。")
            return

        # 2. 🌟 终极模糊匹配：只提取数字进行对比！
        df_fleet['Vehicle_Digits'] = df_fleet['Vehicle'].astype(str).str.replace(r'\D+', '', regex=True)

        # 3. 核心计算逻辑
        def process_logistic_row(row):
            # 过滤早于 2025-10-01 的订单
            if order_date_col and pd.notna(row[order_date_col]):
                order_date = pd.to_datetime(row[order_date_col], errors='coerce')
                if pd.notna(order_date) and order_date < pd.Timestamp('2025-10-01'):
                    return pd.Series(["不适用", "不适用"])

            truck_raw = str(row[truck_col])
            truck_digits = re.sub(r'\D+', '', truck_raw)

            dates = pd.to_datetime(row[date_cols], errors='coerce')
            valid_dates = dates.dropna()

            if len(valid_dates) == 0:
                return pd.Series(["暂未开始运输", "已下单但暂未开始运输"])

            start_date = valid_dates.min()
            end_date = valid_dates.max()

            # 🌟 修复 IndexError: 动态适应实际抓取到的日期列数量 (安全气囊)
            status = ""
            n = len(dates)
            if n > 6 and pd.notna(dates.iloc[6]):
                status = "已完成订单"
            elif n > 5 and pd.notna(dates.iloc[5]):
                status = "到卸货地点"
            elif n > 4 and pd.notna(dates.iloc[4]):
                status = "离开边境关口"
            elif n > 3 and pd.notna(dates.iloc[3]):
                status = "到边境关口"
            elif n > 2 and pd.notna(dates.iloc[2]):
                status = "装好货出发"
            elif n > 1 and pd.notna(dates.iloc[1]):
                status = "装货"
            elif n > 0 and pd.notna(dates.iloc[0]):
                status = "到装货地点"

            if not truck_digits:
                return pd.Series(["车牌无法识别数字", "车牌无法识别数字"])

            truck_mask = df_fleet['Vehicle_Digits'] == truck_digits

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

        for col in date_cols:
            df_log[col] = pd.to_datetime(df_log[col], errors='coerce').dt.strftime('%Y-%m-%d').fillna('')

        if order_date_col:
            df_log[order_date_col] = pd.to_datetime(df_log[order_date_col], errors='coerce').dt.strftime(
                '%Y-%m-%d').fillna('')

        final_cols = other_cols + ['行驶距离', '距离/状态'] + date_cols
        df_display = df_log[final_cols]

        st.dataframe(
            df_display,
            use_container_width=True,
            hide_index=True,
            height=600
        )