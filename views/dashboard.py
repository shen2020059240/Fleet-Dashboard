import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import timedelta
from utils.db import load_from_db


def render(business_line):
    # 根据传入的业务线，动态设置页面标题和主色调
    if business_line == "Flatbed":
        st.title("🚛 Flatbed (平板车) 数字运营中心")
        primary_color = '#3b82f6'  # 蓝色
    else:
        st.title("🛢️ Oil Tanker (油罐车) 数字运营中心")
        primary_color = '#f97316'  # 橙色

    # 1. 加载并直接过滤出当前业务线的数据
    df_raw = load_from_db()
    if df_raw.empty:
        st.info("⚠️ 数据库当前为空，请前往「数据中心」上传报表进行初始化。")
        return

    df = df_raw[df_raw['Vehicle_Type'] == business_line].copy()
    if df.empty:
        st.info(f"⚠️ 数据库中暂无 {business_line} 业务线的数据。")
        return

    global_min_date = df['Date'].min().date()
    global_max_date = df['Date'].max().date()

    # ==========================================
    # 🔍 筛选器区域
    # ==========================================
    with st.container(border=True):
        c1, c2, c3 = st.columns([1.5, 2, 2])

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

        # 车辆选择下拉框
        available_vehicles = sorted(df['Vehicle'].unique().tolist())
        with c3:
            selected_vehicles = st.multiselect("🚛 搜索特定车辆 (不选默认全部)", options=available_vehicles, default=[])

    # ==========================================
    # 🧮 数据过滤逻辑
    # ==========================================
    if len(date_range) == 2:
        current_start, current_end = date_range
        final_vehicles = selected_vehicles if selected_vehicles else available_vehicles

        mask_current = (df['Date'].dt.date >= current_start) & \
                       (df['Date'].dt.date <= current_end) & \
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
            st.markdown(f"#### 🎯 【{single_v_name}】专属里程分析报表")
            tab_monthly, tab_daily = st.tabs(["🗓️ 各月累计汇总", "📅 每日行驶明细"])

            with tab_monthly:
                df_monthly = df_current.copy()
                df_monthly['Month'] = df_monthly['Date'].dt.strftime('%Y-%m')
                monthly_sum = df_monthly.groupby('Month')['Distance (km)'].sum().reset_index()

                fig_monthly = px.bar(
                    monthly_sum, x='Month', y='Distance (km)', text_auto='.1f',
                    color_discrete_sequence=[primary_color], height=400
                )

                # 强制将X轴设为离散类别，并限制柱子最大宽度
                fig_monthly.update_xaxes(type='category')
                fig_monthly.update_traces(width=0.3)

                fig_monthly.update_layout(
                    margin=dict(t=20, b=20, l=10, r=10),
                    plot_bgcolor='rgba(0,0,0,0)',
                    yaxis=dict(title="月度总里程 (km)")
                )
                st.plotly_chart(fig_monthly, use_container_width=True)

            with tab_daily:
                # 智能判断：如果天数超过45天，自动隐藏柱子上的数字
                is_dense = len(df_current) > 45

                fig_daily = px.bar(
                    df_current, x='Date', y='Distance (km)',
                    color_discrete_sequence=[primary_color],
                    text_auto=False if is_dense else '.0f',
                    height=400
                )

                if not is_dense:
                    fig_daily.update_traces(textposition="outside", cliponaxis=False)

                fig_daily.update_layout(
                    margin=dict(t=30, b=20, l=10, r=10),
                    plot_bgcolor='rgba(0,0,0,0)',
                    yaxis=dict(title="当日行驶里程 (km)", showgrid=True, gridcolor='#f1f5f9'),
                    xaxis=dict(title="")
                )
                fig_daily.update_traces(hovertemplate="日期: %{x}<br>里程: %{y:.1f} km<extra></extra>")
                st.plotly_chart(fig_daily, use_container_width=True)

        else:
            # 【多车/全盘模式】
            tab_trend, tab_util, tab_rank = st.tabs(
                ["📈 车队里程出勤趋势", "🔥 车辆出勤率 (闲置分析)", "🏆 车辆累计里程排行"])

            with tab_trend:
                trend_df = df_current.groupby('Date')['Distance (km)'].sum().reset_index()

                # 智能判断：如果天数超过45天，自动隐藏柱子上的数字
                is_dense = len(trend_df) > 45

                fig_trend = px.bar(
                    trend_df, x='Date', y='Distance (km)',
                    color_discrete_sequence=[primary_color],
                    text_auto=False if is_dense else '.0f',
                    height=350
                )

                if not is_dense:
                    fig_trend.update_traces(textposition="outside", cliponaxis=False)

                fig_trend.update_layout(
                    margin=dict(t=30, b=10, l=10, r=10),
                    plot_bgcolor='rgba(0,0,0,0)',
                    yaxis=dict(title="当日总里程 (km)", showgrid=True, gridcolor='#f1f5f9'),
                    xaxis=dict(title="")
                )
                fig_trend.update_traces(hovertemplate="日期: %{x}<br>总里程: %{y:.1f} km<extra></extra>")
                st.plotly_chart(fig_trend, use_container_width=True)

                # 直观数据表格
                st.markdown("###### 📅 每日里程汇总表 (按日期倒序)")
                table_df = trend_df.sort_values('Date', ascending=False).copy()
                table_df['Date'] = table_df['Date'].dt.strftime('%Y-%m-%d')

                st.dataframe(
                    table_df,
                    use_container_width=True,
                    hide_index=True,
                    column_config={
                        "Date": st.column_config.TextColumn("运营日期"),
                        "Distance (km)": st.column_config.NumberColumn("当日总行驶里程 (km)", format="%.1f")
                    }
                )

            with tab_util:
                daily_usage = df_current.groupby('Date')['Vehicle'].nunique().reset_index(name='出勤车辆')
                daily_usage['总车辆数'] = current_cars
                daily_usage['闲置空车'] = current_cars - daily_usage['出勤车辆']
                daily_usage['出勤率'] = (daily_usage['出勤车辆'] / current_cars * 100).round(1).astype(str) + '%'

                util_melted = daily_usage.melt(
                    id_vars=['Date', '出勤率', '总车辆数'],
                    value_vars=['出勤车辆', '闲置空车'],
                    var_name='状态',
                    value_name='车辆数'
                )

                # 健康色调：干活的是主题色，闲置的是浅灰
                fig_util = px.area(
                    util_melted, x='Date', y='车辆数', color='状态',
                    color_discrete_map={'出勤车辆': '#10b981', '闲置空车': '#e2e8f0'},
                    category_orders={'状态': ['出勤车辆', '闲置空车']},
                    hover_data={'出勤率': True, '总车辆数': True},
                    height=450
                )

                fig_util.update_layout(
                    margin=dict(t=20, b=20, l=10, r=10),
                    plot_bgcolor='rgba(0,0,0,0)',
                    yaxis=dict(title="车辆数 (辆)"),
                    legend_title_text='',
                    hovermode='x unified'
                )
                st.plotly_chart(fig_util, use_container_width=True)

            with tab_rank:
                vehicle_summary = df_current.groupby('Vehicle')['Distance (km)'].sum().reset_index()
                vehicle_summary = vehicle_summary.sort_values('Distance (km)', ascending=False)
                total_cars_in_summary = len(vehicle_summary)

                c_title, c_slider = st.columns([2, 1])
                with c_slider:
                    top_n = st.slider("调整显示数量", min_value=1, max_value=total_cars_in_summary,
                                      value=min(15, total_cars_in_summary), step=1)

                top_vehicles_df = vehicle_summary.head(top_n)
                fig_bar = px.bar(
                    top_vehicles_df.sort_values('Distance (km)', ascending=True),
                    x='Distance (km)', y='Vehicle',
                    color_discrete_sequence=[primary_color], orientation='h', text_auto='.1f',
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
                    "Distance (km)": st.column_config.NumberColumn("行驶里程 (km)", format="%.1f")
                }
            )