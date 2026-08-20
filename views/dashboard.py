import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import timedelta
from utils.db import load_from_db

# 统一品牌颜色映射
COLOR_MAP = {
    'SK (公司自有)': '#1e293b',
    'TM (公司自有)': '#3b82f6',
    'HC (朋友车)': '#f97316'
}


def render():
    st.title("🚛 集团车队数字运营中心")

    df = load_from_db()
    if df.empty:
        st.info("⚠️ 数据库当前为空，请前往「数据中心」上传第一批报表进行初始化。")
        return

    # 提取数据库的极限边界时间
    global_min_date = df['Date'].min().date()
    global_max_date = df['Date'].max().date()

    # ==========================================
    # 🔍 筛选器区域
    # ==========================================
    with st.container(border=True):
        st.markdown("##### 🔍 基础筛选")
        c1, c2, c3, c4 = st.columns([1.5, 2, 2, 2])

        # --- 快捷日期选择 ---
        with c1:
            date_preset = st.selectbox(
                "⏱️ 快捷时间",
                options=["自定义范围", "本周", "本月", "近30天", "今年至今"],
                index=3
            )

            # 动态计算快捷时间 (预设锚点)
            start_date = global_min_date
            end_date = global_max_date

            if date_preset == "本周":
                start_date = end_date - timedelta(days=end_date.weekday())
            elif date_preset == "本月":
                start_date = end_date.replace(day=1)
            elif date_preset == "近30天":
                start_date = end_date - timedelta(days=30)
            elif date_preset == "今年至今":
                start_date = end_date.replace(month=1, day=1)

            if start_date < global_min_date:
                start_date = global_min_date

        # --- 自定义日期输入 ---
        with c2:
            date_range = st.date_input(
                "📅 选定日期范围",
                value=(start_date, end_date),
                min_value=global_min_date,
                max_value=global_max_date,
                disabled=(date_preset != "自定义范围")
            )

        # --- 车型筛选 ---
        all_vehicle_types = sorted(df['Vehicle_Type'].unique().tolist())
        with c3:
            selected_v_types = st.multiselect(
                "🚐 车辆类型 (不选默认全部)",
                options=all_vehicle_types,
                default=[]
            )

        # --- 公司归属 ---
        active_v_types = selected_v_types if selected_v_types else all_vehicle_types
        available_companies = sorted(df[df['Vehicle_Type'].isin(active_v_types)]['Company_Type'].unique().tolist())

        with c4:
            selected_companies = st.multiselect(
                "🏢 车辆归属 (不选默认全部)",
                options=available_companies,
                default=[]
            )

        # --- 高级筛选 (指定车辆) ---
        with st.expander("⚙️ 高级筛选 (指定特定车辆)"):
            active_companies = selected_companies if selected_companies else available_companies

            available_vehicles = sorted(
                df[
                    (df['Vehicle_Type'].isin(active_v_types)) &
                    (df['Company_Type'].isin(active_companies))
                    ]['Vehicle'].unique().tolist()
            )

            selected_vehicles = st.multiselect(
                "🚛 指定车辆 (不选默认展示全部)",
                options=available_vehicles,
                default=[]
            )

    # ==========================================
    # 🧮 数据过滤逻辑
    # ==========================================
    if len(date_range) == 2:
        current_start, current_end = date_range

        final_v_types = selected_v_types if selected_v_types else all_vehicle_types
        final_companies = selected_companies if selected_companies else available_companies
        final_vehicles = selected_vehicles if selected_vehicles else available_vehicles

        mask_current = (df['Date'].dt.date >= current_start) & \
                       (df['Date'].dt.date <= current_end) & \
                       (df['Vehicle_Type'].isin(final_v_types)) & \
                       (df['Company_Type'].isin(final_companies)) & \
                       (df['Vehicle'].isin(final_vehicles))

        df_current = df.loc[mask_current]

        if df_current.empty:
            st.warning("⚠️ 在当前筛选条件下没有数据。")
            return

        # 计算上一周期的对比数据
        period_length = (current_end - current_start).days + 1
        prev_end = current_start - timedelta(days=1)
        prev_start = prev_end - timedelta(days=period_length - 1)

        mask_prev = (df['Date'].dt.date >= prev_start) & \
                    (df['Date'].dt.date <= prev_end) & \
                    (df['Vehicle_Type'].isin(final_v_types)) & \
                    (df['Company_Type'].isin(final_companies)) & \
                    (df['Vehicle'].isin(final_vehicles))
        df_prev = df.loc[mask_prev]

        # ==========================================
        # 📈 核心 KPI 卡片区
        # ==========================================
        current_km = df_current['Distance (km)'].sum()
        prev_km = df_prev['Distance (km)'].sum()
        delta_km = current_km - prev_km if not df_prev.empty else 0

        current_cars = df_current['Vehicle'].nunique()
        prev_cars = df_prev['Vehicle'].nunique()
        delta_cars = current_cars - prev_cars if not df_prev.empty else 0

        avg_km_per_car = current_km / current_cars if current_cars > 0 else 0

        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("🛣️ 周期内总行驶里程", f"{current_km:,.1f} km", f"{delta_km:+,.1f} km (较上一等长周期)")
        with col2:
            st.metric("🚛 产生数据的车辆数", f"{current_cars} 辆", f"{delta_cars:+} 辆 (较上一等长周期)")
        with col3:
            st.metric("🎯 单车平均里程", f"{avg_km_per_car:,.1f} km", border=False)

        st.markdown("---")

        # ==========================================
        # 📊 图表区
        # ==========================================
        row1_col1, row1_col2 = st.columns([2.5, 1])

        with row1_col1:
            with st.container(border=True):
                if current_cars == 1:
                    # ===== 【单车模式】：展示专属日/月里程分析 =====
                    single_v_name = df_current['Vehicle'].iloc[0]
                    company = df_current['Company_Type'].iloc[0]
                    v_color = COLOR_MAP.get(company, '#3b82f6')

                    st.markdown(f"##### 📈 【{single_v_name}】专属里程分析")
                    tab_daily, tab_monthly = st.tabs(["📅 每日行驶明细", "🗓️ 各月累计汇总"])

                    with tab_daily:
                        fig_daily = px.line(
                            df_current, x='Date', y='Distance (km)', markers=True,
                            color_discrete_sequence=[v_color], height=300
                        )
                        fig_daily.update_layout(margin=dict(t=10, b=10, l=10, r=10), plot_bgcolor='rgba(0,0,0,0)')
                        st.plotly_chart(fig_daily, use_container_width=True)

                    with tab_monthly:
                        df_monthly = df_current.copy()
                        df_monthly['Month'] = df_monthly['Date'].dt.strftime('%Y-%m')  # 按月聚合
                        monthly_sum = df_monthly.groupby('Month')['Distance (km)'].sum().reset_index()
                        fig_monthly = px.bar(
                            monthly_sum, x='Month', y='Distance (km)', text_auto='.1f',
                            color_discrete_sequence=[v_color], height=300
                        )
                        fig_monthly.update_layout(margin=dict(t=10, b=10, l=10, r=10), plot_bgcolor='rgba(0,0,0,0)')
                        st.plotly_chart(fig_monthly, use_container_width=True)

                else:
                    # ===== 【多车模式】：维持原有的综合趋势堆叠图 =====
                    st.markdown("##### 📈 每日出勤趋势 (Time-Series Trend)")
                    trend_df = df_current.groupby(['Date', 'Company_Type'])['Distance (km)'].sum().reset_index()
                    fig_trend = px.area(
                        trend_df, x='Date', y='Distance (km)', color='Company_Type',
                        color_discrete_map=COLOR_MAP, height=350
                    )
                    fig_trend.update_layout(margin=dict(t=10, b=10, l=10, r=10), plot_bgcolor='rgba(0,0,0,0)')
                    st.plotly_chart(fig_trend, use_container_width=True)

        with row1_col2:
            with st.container(border=True):
                st.markdown("##### 🍩 车队贡献度")
                donut_df = df_current.groupby('Company_Type')['Distance (km)'].sum().reset_index()
                fig_donut = px.pie(
                    donut_df, values='Distance (km)', names='Company_Type',
                    hole=0.5, color='Company_Type', color_discrete_map=COLOR_MAP, height=350
                )
                fig_donut.update_layout(margin=dict(t=10, b=10, l=10, r=10), showlegend=False)
                fig_donut.update_traces(textposition='inside', textinfo='percent+label')
                st.plotly_chart(fig_donut, use_container_width=True)

        row2_col1, row2_col2 = st.columns([2.5, 1])

        # 汇总车辆排行数据
        vehicle_summary = df_current.groupby(['Company_Type', 'Vehicle'])['Distance (km)'].sum().reset_index()
        vehicle_summary = vehicle_summary.sort_values('Distance (km)', ascending=False)
        total_cars_in_summary = len(vehicle_summary)

        with row2_col1:
            if total_cars_in_summary == 1:
                # 只有 1 辆车时，隐藏排行榜，防止滑块报错
                with st.container(border=True):
                    st.markdown("##### 📊 车辆累计里程排行")
                    st.info("📌 当前处于单车分析模式，已自动折叠车队排行。")
            else:
                with st.container(border=True):
                    c_title, c_slider = st.columns([1, 1])
                    with c_title:
                        st.markdown("##### 📊 车辆累计里程排行")
                    with c_slider:
                        # 只有 >= 2 辆车时，min_value 设为 2
                        top_n = st.slider(
                            "拖动调整显示数量",
                            min_value=2,
                            max_value=total_cars_in_summary,
                            value=min(10, total_cars_in_summary),
                            step=1
                        )

                    top_vehicles_df = vehicle_summary.head(top_n)
                    fig_bar = px.bar(
                        top_vehicles_df.sort_values('Distance (km)', ascending=True),
                        x='Distance (km)', y='Vehicle', color='Company_Type',
                        color_discrete_map=COLOR_MAP, orientation='h', text_auto='.1f',
                        height=max(300, len(top_vehicles_df) * 30)
                    )
                    fig_bar.update_layout(
                        margin=dict(t=10, b=10, l=10, r=10),
                        plot_bgcolor='rgba(0,0,0,0)',
                        xaxis=dict(showgrid=True, gridcolor='#f1f5f9')
                    )
                    st.plotly_chart(fig_bar, use_container_width=True)

        # ==========================================
        # 📋 第三排：专业级数据明细表
        # ==========================================
        with st.container(border=True):
            st.markdown("##### 📋 原始数据明细")
            st.dataframe(
                df_current.sort_values(['Date', 'Vehicle'], ascending=[False, True]),
                use_container_width=True, hide_index=True,
                column_config={
                    "Date": st.column_config.DateColumn("行驶日期", format="YYYY-MM-DD"),
                    "Vehicle": st.column_config.TextColumn("车牌号", width="medium"),
                    "Company_Type": st.column_config.TextColumn("车辆归属"),
                    "Vehicle_Type": st.column_config.TextColumn("车型"),
                    "Distance (km)": st.column_config.NumberColumn(
                        "行驶里程 (km)",
                        format="%.1f"
                    )
                }
            )