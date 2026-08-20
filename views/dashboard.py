import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import timedelta
from utils.db import load_from_db

# 核心业务维度：按车型区分颜色
VEHICLE_TYPE_COLORS = {
    'Flatbed': '#3b82f6',  # 蓝色代表平板车
    'Oil Tanker': '#f97316'  # 橙色代表油罐车
}


def render():
    st.title("🚛 集团车队数字运营中心")

    df = load_from_db()
    if df.empty:
        st.info("⚠️ 数据库当前为空，请前往「数据中心」上传第一批报表进行初始化。")
        return

    global_min_date = df['Date'].min().date()
    global_max_date = df['Date'].max().date()

    # ==========================================
    # 🔍 筛选器区域 (极简布局)
    # ==========================================
    with st.container(border=True):
        c1, c2, c3, c4 = st.columns([1.5, 2, 2, 2])

        with c1:
            date_preset = st.selectbox(
                "⏱️ 快捷时间",
                options=["近30天", "本周", "本月", "今年至今", "自定义范围"],
                index=0
            )

            start_date, end_date = global_min_date, global_max_date
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

        with c2:
            date_range = st.date_input(
                "📅 选定日期范围",
                value=(start_date, end_date),
                min_value=global_min_date,
                max_value=global_max_date,
                disabled=(date_preset != "自定义范围")
            )

        all_vehicle_types = sorted(df['Vehicle_Type'].unique().tolist())
        with c3:
            selected_v_types = st.multiselect("🚐 业务线 (Flatbed / Tanker)", options=all_vehicle_types, default=[])

        # 高级筛选悬浮折叠，保持主界面清爽
        active_v_types = selected_v_types if selected_v_types else all_vehicle_types
        available_vehicles = sorted(df[df['Vehicle_Type'].isin(active_v_types)]['Vehicle'].unique().tolist())

        with c4:
            selected_vehicles = st.multiselect("🚛 搜索特定车辆 (选填)", options=available_vehicles, default=[])

    # ==========================================
    # 🧮 数据过滤逻辑
    # ==========================================
    if len(date_range) == 2:
        current_start, current_end = date_range
        final_v_types = selected_v_types if selected_v_types else all_vehicle_types
        final_vehicles = selected_vehicles if selected_vehicles else available_vehicles

        mask_current = (df['Date'].dt.date >= current_start) & \
                       (df['Date'].dt.date <= current_end) & \
                       (df['Vehicle_Type'].isin(final_v_types)) & \
                       (df['Vehicle'].isin(final_vehicles))
        df_current = df.loc[mask_current]

        if df_current.empty:
            st.warning("⚠️ 在当前筛选条件下没有数据。")
            return

        # 核心 KPI 计算
        current_km = df_current['Distance (km)'].sum()
        current_cars = df_current['Vehicle'].nunique()
        avg_km_per_car = current_km / current_cars if current_cars > 0 else 0

        col1, col2, col3 = st.columns(3)
        col1.metric("🛣️ 周期内总行驶里程", f"{current_km:,.1f} km")
        col2.metric("🚛 产生数据的活跃车辆", f"{current_cars} 辆")
        col3.metric("🎯 单车平均里程", f"{avg_km_per_car:,.1f} km")
        st.markdown("---")

        # ==========================================
        # 📈 全屏图表区 (动态单多车视图)
        # ==========================================
        if current_cars == 1:
            # 【单车模式】
            single_v_name = df_current['Vehicle'].iloc[0]
            v_type = df_current['Vehicle_Type'].iloc[0]
            v_color = VEHICLE_TYPE_COLORS.get(v_type, '#3b82f6')

            st.markdown(f"#### 🎯 【{single_v_name}】专属里程分析报表")
            tab_monthly, tab_daily = st.tabs(["🗓️ 各月累计汇总", "📅 每日行驶明细"])

            with tab_monthly:
                df_monthly = df_current.copy()
                df_monthly['Month'] = df_monthly['Date'].dt.strftime('%Y-%m')
                monthly_sum = df_monthly.groupby('Month')['Distance (km)'].sum().reset_index()
                fig_monthly = px.bar(
                    monthly_sum, x='Month', y='Distance (km)', text_auto='.1f',
                    color_discrete_sequence=[v_color], height=400
                )
                fig_monthly.update_layout(margin=dict(t=20, b=20, l=10, r=10), plot_bgcolor='rgba(0,0,0,0)')
                st.plotly_chart(fig_monthly, use_container_width=True)

            with tab_daily:
                fig_daily = px.area(
                    df_current, x='Date', y='Distance (km)', markers=True,
                    color_discrete_sequence=[v_color], height=400
                )
                fig_daily.update_layout(margin=dict(t=20, b=20, l=10, r=10), plot_bgcolor='rgba(0,0,0,0)')
                st.plotly_chart(fig_daily, use_container_width=True)

        else:
            # 【多车/全盘模式】
            tab_trend, tab_util, tab_rank = st.tabs(["📈 业务线里程趋势", "🔥 车队出勤率趋势", "🏆 车辆累计里程排行"])

            with tab_trend:
                # 按车型(Flatbed/Tanker)拆分的每日总里程
                trend_df = df_current.groupby(['Date', 'Vehicle_Type'])['Distance (km)'].sum().reset_index()
                fig_trend = px.area(
                    trend_df, x='Date', y='Distance (km)', color='Vehicle_Type',
                    color_discrete_map=VEHICLE_TYPE_COLORS, height=450
                )
                fig_trend.update_layout(
                    margin=dict(t=20, b=20, l=10, r=10), plot_bgcolor='rgba(0,0,0,0)',
                    legend_title_text='业务线 (Vehicle Type)'
                )
                st.plotly_chart(fig_trend, use_container_width=True)

            with tab_util:
                # 计算每天的出勤、闲置以及总车数
                daily_usage = df_current.groupby('Date')['Vehicle'].nunique().reset_index(name='出勤车辆')
                daily_usage['总车辆数'] = current_cars
                daily_usage['闲置空车'] = current_cars - daily_usage['出勤车辆']
                daily_usage['出勤率'] = (daily_usage['出勤车辆'] / current_cars * 100).round(1).astype(str) + '%'

                # 转换数据格式以适配堆叠面积图
                util_melted = daily_usage.melt(
                    id_vars=['Date', '出勤率', '总车辆数'],
                    value_vars=['出勤车辆', '闲置空车'],
                    var_name='状态',
                    value_name='车辆数'
                )

                # 渲染堆叠面积图 (绿色代表健康出勤，浅灰代表闲置浪费)
                fig_util = px.area(
                    util_melted, x='Date', y='车辆数', color='状态',
                    color_discrete_map={'出勤车辆': '#10b981', '闲置空车': '#e2e8f0'},
                    category_orders={'状态': ['出勤车辆', '闲置空车']},  # 确保出勤在底层，闲置在顶层
                    hover_data={'出勤率': True, '总车辆数': True},
                    height=450
                )

                # 优化视觉交互
                fig_util.update_layout(
                    margin=dict(t=20, b=20, l=10, r=10),
                    plot_bgcolor='rgba(0,0,0,0)',
                    yaxis=dict(title="车辆数 (辆)"),
                    legend_title_text='',
                    hovermode='x unified'  # 鼠标悬浮时出现贯穿整条垂直线的综合信息提示框
                )
                st.plotly_chart(fig_util, use_container_width=True)

            with tab_rank:
                vehicle_summary = df_current.groupby(['Vehicle_Type', 'Vehicle'])['Distance (km)'].sum().reset_index()
                vehicle_summary = vehicle_summary.sort_values('Distance (km)', ascending=False)
                total_cars_in_summary = len(vehicle_summary)

                c_title, c_slider = st.columns([2, 1])
                with c_slider:
                    top_n = st.slider("调整显示数量", min_value=1, max_value=total_cars_in_summary,
                                      value=min(15, total_cars_in_summary), step=1)

                top_vehicles_df = vehicle_summary.head(top_n)
                fig_bar = px.bar(
                    top_vehicles_df.sort_values('Distance (km)', ascending=True),
                    x='Distance (km)', y='Vehicle', color='Vehicle_Type',
                    color_discrete_map=VEHICLE_TYPE_COLORS, orientation='h', text_auto='.1f',
                    height=max(350, len(top_vehicles_df) * 35)
                )
                fig_bar.update_layout(margin=dict(t=10, b=10, l=10, r=10), plot_bgcolor='rgba(0,0,0,0)')
                st.plotly_chart(fig_bar, use_container_width=True)

        # ==========================================
        # 📋 隐藏的原始数据明细 (按需展开)
        # ==========================================
        st.markdown("<br>", unsafe_allow_html=True)
        with st.expander("📂 点击展开查看 / 下载原始数据明细"):
            st.dataframe(
                df_current.sort_values(['Date', 'Vehicle'], ascending=[False, True]),
                use_container_width=True, hide_index=True, height=400,
                column_config={
                    "Date": st.column_config.DateColumn("行驶日期", format="YYYY-MM-DD"),
                    "Vehicle": st.column_config.TextColumn("车牌号"),
                    "Company_Type": st.column_config.TextColumn("车辆归属"),
                    "Vehicle_Type": st.column_config.TextColumn("业务线 (车型)"),
                    "Distance (km)": st.column_config.NumberColumn("行驶里程 (km)", format="%.1f")
                }
            )