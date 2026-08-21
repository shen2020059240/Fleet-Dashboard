import streamlit as st
import pandas as pd
import numpy as np
import io  # 用于在内存中生成 Excel 文件


def render():
    st.title("⚖️ TFD & TFM 内部往来对账中心")
    st.markdown("💡 **智能对账引擎**：以 TFD 成本表为基准，精准核对 TFM 收入表的核心业财数据。")

    uploaded_file = st.file_uploader("📥 请上传对账 Excel 文件 (需包含 TFD 和 TFM sheet)", type=['xlsx'])

    if uploaded_file is not None:
        try:
            # 1. 读取数据并清理表头（防止换行和前后多余空格）
            df_tfd = pd.read_excel(uploaded_file, sheet_name='TFD')
            df_tfm = pd.read_excel(uploaded_file, sheet_name='TFM')
            df_tfd.columns = df_tfd.columns.str.replace('\n', ' ').str.strip()
            df_tfm.columns = df_tfm.columns.str.replace('\n', ' ').str.strip()

            # ================= 🌟 新增：日期格式专项清洗 =================
            # 把 销售期间 洗成清爽的 YYYY-MM
            if '销售期间' in df_tfd.columns:
                df_tfd['销售期间'] = pd.to_datetime(df_tfd['销售期间'], errors='coerce').dt.strftime('%Y-%m')
            if '销售期间' in df_tfm.columns:
                df_tfm['销售期间'] = pd.to_datetime(df_tfm['销售期间'], errors='coerce').dt.strftime('%Y-%m')

            # 把 Date Arrived 也洗成 YYYY-MM-DD，防止因为带了时分秒导致被误判为“不一致”
            if 'Date Arrived' in df_tfd.columns:
                df_tfd['Date Arrived'] = pd.to_datetime(df_tfd['Date Arrived'], errors='coerce').dt.strftime('%Y-%m-%d')
            if 'Date Arrived' in df_tfm.columns:
                df_tfm['Date Arrived'] = pd.to_datetime(df_tfm['Date Arrived'], errors='coerce').dt.strftime('%Y-%m-%d')

            # 2. 设定联表唯一键
            join_keys = ['Reference number', 'HORSE NO', '销售期间']

            missing_keys = [k for k in join_keys if k not in df_tfd.columns or k not in df_tfm.columns]
            if missing_keys:
                st.error(f"❌ 严重错误：两张表中缺少核心联表键 {missing_keys}。请检查原表。")
                return

            # 3. 智能联表 (Merge)
            merged_df = pd.merge(df_tfd, df_tfm, on=join_keys, how='outer', suffixes=('_TFD', '_TFM'))

            def check_status(row):
                if pd.isna(row.get('Subcontractor')):
                    return "⚠️ 仅有 TFM (缺 TFD 成本)"
                elif pd.isna(row.get('TFM - Customer Name')):
                    return "⚠️ 仅有 TFD (缺 TFM 收入)"
                else:
                    return "✅ 匹配成功"

            merged_df['对账状态'] = merged_df.apply(check_status, axis=1)

            # 标记 Date Arrived 是否存在差异，方便后续导出标红
            if 'Date Arrived_TFD' in merged_df.columns and 'Date Arrived_TFM' in merged_df.columns:
                merged_df['到达日期差异'] = merged_df.apply(
                    lambda r: "异常" if pd.notna(r['Date Arrived_TFD']) and pd.notna(r['Date Arrived_TFM']) and str(
                        r['Date Arrived_TFD']) != str(r['Date Arrived_TFM']) else "正常",
                    axis=1
                )

            matched_df = merged_df[merged_df['对账状态'] == "✅ 匹配成功"].copy()

            # 4. 定义比对字典
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

            # 拦截缺失列
            missing_cols = []
            for tfm_col, tfd_col, _ in compare_map.values():
                if tfm_col not in matched_df.columns:
                    missing_cols.append(tfm_col)
                if tfd_col not in matched_df.columns:
                    missing_cols.append(tfd_col)

            if missing_cols:
                st.error(f"🛑 **雷达拦截**：对账被迫中止！在上传的文件中找不到以下列名：\n{list(set(missing_cols))}")
                return

                # 5. 开始深度比对
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

            # ================= 6. 前端展示面板 =================
            st.success("✅ 数据联表与深度校验完成！")

            st.markdown("### 📊 业财大盘总览 (Financial Overview)")
            total_revenue = df_tfm['NET REVNEUE (USD)'].sum() if 'NET REVNEUE (USD)' in df_tfm.columns else 0
            total_cogs = df_tfd['Subcon Total'].sum() if 'Subcon Total' in df_tfd.columns else 0
            total_margin = total_revenue - total_cogs

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

            # ================= 🌟 新增：带颜色格式的 Excel 导出引擎 =================
            def to_excel_with_highlights(df):
                output = io.BytesIO()
                # 使用 xlsxwriter 引擎生成真实的 Excel 文件
                writer = pd.ExcelWriter(output, engine='xlsxwriter')
                df.to_excel(writer, index=False, sheet_name='数据部待修清单')

                workbook = writer.book
                worksheet = writer.sheets['数据部待修清单']

                # 定义红色高亮格式（浅红底，深红字）
                red_format = workbook.add_format({'bg_color': '#FFC7CE', 'font_color': '#9C0006'})

                # 遍历数据，如果到达日期异常，整行标红
                if '到达日期差异' in df.columns:
                    diff_col_idx = df.columns.get_loc('到达日期差异')
                    for row_num in range(len(df)):
                        if df.iloc[row_num, diff_col_idx] == "异常":
                            worksheet.set_row(row_num + 1, None, red_format)

                writer.close()
                return output.getvalue()

            # 将重组后的列放好（状态前置）
            cols_to_export = ['对账状态', '到达日期差异', 'Reference number', 'HORSE NO', '销售期间',
                              'Date Arrived_TFD', 'Date Arrived_TFM']
            cols_to_export += [c for c in merged_df.columns if c not in cols_to_export]
            final_export_df = merged_df[cols_to_export]

            excel_data = to_excel_with_highlights(final_export_df)

            st.download_button(
                label="📥 导出全景核对表给数据部 (Excel格式，日期错误已自动标红)",
                data=excel_data,
                file_name="对账全景核对表_带高亮.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                type="primary"
            )
            st.markdown("<br>", unsafe_allow_html=True)  # 留点空隙

            # 选项卡展示
            tab1, tab2, tab3 = st.tabs(["🔍 TFM 数据差异明细 (核心)", "⚠️ 单边账明细", "📊 完整全景表"])
            with tab1:
                st.info(
                    "💡 这里的单子是**已经成功匹配**的，但下面的 10 项业务数据 TFM 与 TFD 不一致。数值类展示的是 `差异 = TFM - TFD` (非0即错)；文本类展示了两边的具体填写内容。")
                if not diff_df.empty:
                    st.dataframe(diff_df, use_container_width=True)
                else:
                    st.success("🎉 太棒了！所有匹配上的单据，10 项核心数据 TFM 与 TFD 完全一致！")

            with tab2:
                error_df = merged_df[merged_df['对账状态'] != "✅ 匹配成功"]
                st.dataframe(error_df[['对账状态', 'Reference number', 'HORSE NO', '销售期间']],
                             use_container_width=True)

            with tab3:
                st.dataframe(final_export_df, use_container_width=True)

        except Exception as e:
            st.error(f"❌ 系统发生严重错误：{e}")