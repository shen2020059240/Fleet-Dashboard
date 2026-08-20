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
        # 1. 提取动态列名（锁定第1列为车牌，第2到8列为物流节点）
        truck_col = df_log.columns[0]
        date_cols = df_log.columns[1:8]

        # 2. 清理主数据库的车牌格式（去除空格，强制大写，防止匹配失败）
        df_fleet['Vehicle_Clean'] = df_fleet['Vehicle'].astype(str).str.strip().str.upper()

        # 3. 核心计算逻辑 (完全替代复杂的 Excel 公式)
        def process_logistic_row(row):
            truck = str(row[truck_col]).strip().upper()
            dates = pd.to_datetime(row[date_cols], errors='coerce')
            valid_dates = dates.dropna()

            # 对应 Excel 的 IF(COUNT(AH87:AN87)=0, "暂未开始运输", ...)
            if len(valid_dates) == 0:
                return pd.Series(["暂未开始运输", "已下单但暂未开始运输"])

            start_date = valid_dates.min()
            end_date = valid_dates.max()

            # 对应 Excel 的 CHOOSE(MATCH(1,0/(AH87:AM87<>"")), ...)
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

            # 对应 Excel 的 COUNTIF(..., "车牌号不相符")
            truck_mask = df_fleet['Vehicle_Clean'] == truck
            if not truck_mask.any():
                return pd.Series(["车牌号不相符", "车牌号不相符"])

            # 对应 Excel 的 SUMIFS (按车牌号、大于等于开始日期、小于等于结束日期汇总)
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

        # 将日期格式化为易读的字符串，去除多余的时分秒
        for col in date_cols:
            df_log[col] = df_log[col].dt.strftime('%Y-%m-%d').fillna('')

        # 调整表头显示顺序，将计算结果紧挨着车牌号展示
        final_cols = [truck_col, '行驶距离', '距离/状态'] + list(date_cols)
        df_display = df_log[final_cols]

        st.dataframe(
            df_display,
            use_container_width=True,
            hide_index=True,
            height=600
        )