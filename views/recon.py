import streamlit as st
import pandas as pd
import numpy as np
import io
import sqlite3

# 初始化共享数据库连接 (Streamlit 会在运行目录下自动生成这个 db 文件)
conn = sqlite3.connect('shared_recon_center.db', check_same_thread=False)


def render():
    st.title("⚖️ TFD & TFM 内部往来对账中心")
    st.markdown("💡 **智能对账引擎**：上传对账表并一键发布，全团队均可在线查看与下载最新结果。")

    # ================= 1. 定义通用展示看板模块 (供实时计算和云端读取共用) =================
    def display_shared_dashboard(merged_df, diff_df, final_export_df, is_from_cloud=False):
        if is_from_cloud:
            st.info("☁️ **当前状态：云端共享模式** (展示的是最新发布的对账结果。如需更新，请在上方上传新表格)")
        else:
            st.success("✅ 数据联表与深度校验完成！")

        # --- 财务大盘数据提取与安全计算 ---
        rev_col = 'NET REVNEUE (USD)'
        cogs_col = 'Subcon Total'

        # 强制转为数字，防止带空格的字符干扰计算
        total_revenue = pd.to_numeric(merged_df[rev_col], errors='coerce').sum() if rev_col in merged_df.columns else 0
        total_cogs = pd.to_numeric(merged_df[cogs_col], errors='coerce').sum() if cogs_col in merged_df.columns else 0
        total_margin = total_revenue - total_cogs

        st.markdown("### 📊 业财大盘总览 (Financial Overview)")
        dash1, dash2, dash3 = st.columns(3)
        dash1.metric(label="💰 TFM 总收入 (NET REVENUE)", value=f"${total_revenue:,.2f}")
        dash2.metric(label="💸 TFD 总成本 (Subcon Total)", value=f"${total_cogs:,.2f}")
        dash3.metric(label="📈 账面总毛利 (Margin)", value=f"${total_margin:,.2f}")
        st.divider()

        st.markdown("### 📦 订单异常拦截统计")
        col1, col2, col3 = st.columns(3)
        col1.metric("总处理单数", len(merged_df))
        col2.metric("⚠️ 彻底漏单 (单边账)", len(merged_df[merged_df['对账状态'] != "✅ 匹配成功"]))
        col3.metric("🔍 需人工核对的瑕疵单", len(diff_df) if not diff_df.empty else 0)

        # --- 标红高亮 Excel 导出引擎 ---
        def to_excel_with_highlights(df):
            output = io.BytesIO()
            writer = pd.ExcelWriter(output, engine='xlsxwriter')
            df.to_excel(writer, index=False, sheet_name='数据部待修清单')

            workbook = writer.book
            worksheet = writer.sheets['数据部待修清单']
            red_format = workbook.add_format({'bg_color': '#FFC7CE', 'font_color': '#9C0006'})

            # 金额千分位格式 (Excel 内部)
            money_format = workbook.add_format({'num_format': '#,##0.00'})

            if '到达日期差异' in df.columns:
                diff_col_idx = df.columns.get_loc('到达日期差异')
                for row_num in range(len(df)):
                    if df.iloc[row_num, diff_col_idx] == "异常":
                        worksheet.set_row(row_num + 1, None, red_format)

            # 给 Excel 里的金额列加上千分位
            for col_idx, col_name in enumerate(df.columns):
                if any(k in col_name.upper() for k in ['USD', 'TOTAL', 'PRICE', 'REVENUE', 'COST', 'ADJ']):
                    worksheet.set_column(col_idx, col_idx, 12, money_format)

            writer.close()
            return output.getvalue()

        excel_data = to_excel_with_highlights(final_export_df)

        col_btn1, col_btn2 = st.columns([1, 1])
        with col_btn1:
            st.download_button(
                label="📥 导出全景核对表 (日期错误自动标红)",
                data=excel_data,
                file_name="对账全景核对表_带高亮.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                type="primary"
            )

        # 🌟 云端发布按钮 (仅在非云端模式下显示)
        if not is_from_cloud:
            with col_btn2:
                if st.button("🚀 发布本次结果到云端 (共享给同事)"):
                    with st.spinner("正在写入云端数据库..."):
                        # 确保存入数据库前强制转为字符串防报错，部分纯数字列保持 numeric
                        merged_df.to_sql("shared_merged", conn, if_exists="replace", index=False)
                        diff_df.to_sql("shared_diff", conn, if_exists="replace", index=False)
                        final_export_df.to_sql("shared_export", conn, if_exists="replace", index=False)
                        st.toast("🎉 发布成功！同事访问系统即可查看！")

        st.markdown("<br>", unsafe_allow_html=True)

        # --- 智能千分位配置器 (专门用于 Streamlit 网页展示) ---
        def get_column_config(df):
            config = {}
            for col in df.columns:
                # 只要列名包含这些关键字，且数据类型是数字，就自动格式化为千分位
                if any(k in col.upper() for k in
                       ['USD', 'TOTAL', 'PRICE', 'REVENUE', 'COST', 'ADJ', 'QUANTITY', 'QTY']):
                    if pd.api.types.is_numeric_dtype(df[col]):
                        config[col] = st.column_config.NumberColumn(format="%,.2f")
            return config

        # --- 明细 Tab 展示 ---
        tab1, tab2, tab3 = st.tabs(["🔍 TFM 数据差异明细 (核心)", "⚠️ 单边账明细", "📊 完整全景表"])
        with tab1:
            if not diff_df.empty:
                st.dataframe(diff_df, column_config=get_column_config(diff_df), use_container_width=True)
            else:
                st.success("🎉 太棒了！所有匹配上的单据数据完全一致！")

        with tab2:
            error_df = merged_df[merged_df['对账状态'] != "✅ 匹配成功"]
            st.dataframe(error_df[['对账状态', 'Reference number', 'HORSE NO', '销售期间']], use_container_width=True)

        with tab3:
            st.dataframe(final_export_df, column_config=get_column_config(final_export_df), use_container_width=True)

    # ================= 2. 主页面逻辑 (上传 or 读取) =================
    uploaded_file = st.file_uploader("📥 第一步：请上传最新对账 Excel 文件 (将覆盖云端历史数据)", type=['xlsx'])

    if uploaded_file is not None:
        try:
            # 读取并清洗
            df_tfd = pd.read_excel(uploaded_file, sheet_name='TFD')
            df_tfm = pd.read_excel(uploaded_file, sheet_name='TFM')
            df_tfd.columns = df_tfd.columns.str.replace('\n', ' ').str.strip()
            df_tfm.columns = df_tfm.columns.str.replace('\n', ' ').str.strip()

            # 日期清洗 YYYY-MM
            if '销售期间' in df_tfd.columns:
                df_tfd['销售期间'] = pd.to_datetime(df_tfd['销售期间'], errors='coerce').dt.strftime('%Y-%m')
            if '销售期间' in df_tfm.columns:
                df_tfm['销售期间'] = pd.to_datetime(df_tfm['销售期间'], errors='coerce').dt.strftime('%Y-%m')

            # 日期清洗 YYYY-MM-DD
            if 'Date Arrived' in df_tfd.columns:
                df_tfd['Date Arrived'] = pd.to_datetime(df_tfd['Date Arrived'], errors='coerce').dt.strftime('%Y-%m-%d')
            if 'Date Arrived' in df_tfm.columns:
                df_tfm['Date Arrived'] = pd.to_datetime(df_tfm['Date Arrived'], errors='coerce').dt.strftime('%Y-%m-%d')

            join_keys = ['Reference number', 'HORSE NO', '销售期间']
            missing_keys = [k for k in join_keys if k not in df_tfd.columns or k not in df_tfm.columns]
            if missing_keys:
                st.error(f"❌ 严重错误：两张表中缺少核心联表键 {missing_keys}")
                return

            # 联表
            merged_df = pd.merge(df_tfd, df_tfm, on=join_keys, how='outer', suffixes=('_TFD', '_TFM'))

            def check_status(row):
                if pd.isna(row.get('Subcontractor')):
                    return "⚠️ 仅有 TFM (缺 TFD 成本)"
                elif pd.isna(row.get('TFM - Customer Name')):
                    return "⚠️ 仅有 TFD (缺 TFM 收入)"
                else:
                    return "✅ 匹配成功"

            merged_df['对账状态'] = merged_df.apply(check_status, axis=1)

            if 'Date Arrived_TFD' in merged_df.columns and 'Date Arrived_TFM' in merged_df.columns:
                merged_df['到达日期差异'] = merged_df.apply(
                    lambda r: "异常" if pd.notna(r['Date Arrived_TFD']) and pd.notna(r['Date Arrived_TFM']) and str(
                        r['Date Arrived_TFD']) != str(r['Date Arrived_TFM']) else "正常",
                    axis=1
                )

            matched_df = merged_df[merged_df['对账状态'] == "✅ 匹配成功"].copy()

            compare_map = {
                'Tonnage Status': ('TONNAGE for Revenue status', 'TONNAGE for Subcon Cost status', 'text'),
                'Load/Off': ('TONNAGE for Revenue (LOAD / OFF)', 'TONNAGE for Subcon Cost (LOAD / OFF)', 'text'),
                'Quantity': ('Quantity for Revenue (MT / days)', 'Quantity for Subcon Cost', 'num'),
                'Qty Adj': ('Quantity for Revenue (MT / days) Adjustment', 'Quantity for Subcon Cost Adjustment',
                            'num'),
                'Adj Qty': ('Adjusted Quantity for Revenue (MT / days)', 'Adjusted Quantity for Subcon Cost', 'num'),
                'Price Status': ('Unit price for Revenue status', 'Unit costs for Subcon status', 'text'),
                'Unit Price': ('Unit price (USD)', 'Subcon Unit Cost', 'num'),
                'Follow Up': ('Price information to be follow up', 'Price information to be follow up_1', 'text'),
                'Adj USD': ('Revenue adjustment (USD)', 'Subcon Adj', 'num'),
                'Total USD': ('NET REVNEUE (USD)', 'Subcon Total', 'num')
            }

            diff_records = []
            for index, row in matched_df.iterrows():
                has_diff = False
                diff_row = {
                    'Reference number': row['Reference number'],
                    'HORSE NO': row['HORSE NO'],
                    '销售期间': row['销售期间']
                }

                for short_name, (col_tfm, col_tfd, col_type) in compare_map.items():
                    val_tfm = row.get(col_tfm)
                    val_tfd = row.get(col_tfd)

                    if col_type == 'num':
                        tfm_num = float(val_tfm) if pd.notna(val_tfm) else 0.0
                        tfd_num = float(val_tfd) if pd.notna(val_tfd) else 0.0
                        diff = round(tfm_num - tfd_num, 2)
                        if diff != 0:
                            has_diff = True
                        diff_row[f"{short_name} (TFM-TFD)"] = diff
                    else:
                        clean_tfm = str(val_tfm).strip().upper() if pd.notna(val_tfm) else ""
                        clean_tfd = str(val_tfd).strip().upper() if pd.notna(val_tfd) else ""
                        if clean_tfm != clean_tfd:
                            has_diff = True

                        orig_tfm = str(val_tfm).strip() if pd.notna(val_tfm) else ""
                        orig_tfd = str(val_tfd).strip() if pd.notna(val_tfd) else ""
                        diff_row[
                            f"{short_name} 差异"] = f"TFM: {orig_tfm} | TFD: {orig_tfd}" if clean_tfm != clean_tfd else "一致"

                if has_diff:
                    diff_records.append(diff_row)

            diff_df = pd.DataFrame(diff_records)

            # 导出列重组
            cols_to_export = ['对账状态', '到达日期差异', 'Reference number', 'HORSE NO', '销售期间',
                              'Date Arrived_TFD', 'Date Arrived_TFM']
            cols_to_export += [c for c in merged_df.columns if c not in cols_to_export]
            final_export_df = merged_df[cols_to_export]

            # 渲染共享面板 (实时上传模式)
            display_shared_dashboard(merged_df, diff_df, final_export_df, is_from_cloud=False)

        except Exception as e:
            st.error(f"❌ 系统发生严重错误：{e}")

    else:
        # 如果没有上传文件，尝试从云端数据库读取同事发布的最新数据
        try:
            db_merged_df = pd.read_sql("SELECT * FROM shared_merged", conn)
            db_diff_df = pd.read_sql("SELECT * FROM shared_diff", conn)
            db_final_export_df = pd.read_sql("SELECT * FROM shared_export", conn)

            # 渲染共享面板 (云端读取模式)
            display_shared_dashboard(db_merged_df, db_diff_df, db_final_export_df, is_from_cloud=True)

        except Exception:
            # 如果数据库还是空的（还没人上传过）
            st.info("👆 系统当前没有缓存任何对账数据，请上传表格以开启对账。")