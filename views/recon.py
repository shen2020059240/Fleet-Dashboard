import streamlit as st
import pandas as pd
import numpy as np


def render():
    st.title("⚖️ TFD & TFM 内部往来对账中心")
    st.markdown("💡 **智能对账引擎**：以 TFD 成本表为基准，精准核对 TFM 收入表的 10 项核心业财数据。")

    uploaded_file = st.file_uploader("📥 请上传对账 Excel 文件 (需包含 TFD 和 TFM sheet)", type=['xlsx'])

    if uploaded_file is not None:
        try:
            # 1. 读取数据并清理表头（防止换行和前后多余空格）
            df_tfd = pd.read_excel(uploaded_file, sheet_name='TFD')
            df_tfm = pd.read_excel(uploaded_file, sheet_name='TFM')
            df_tfd.columns = df_tfd.columns.str.replace('\n', ' ').str.strip()
            df_tfm.columns = df_tfm.columns.str.replace('\n', ' ').str.strip()

            # 2. 设定联表唯一键
            join_keys = ['Reference number', 'HORSE NO', '销售期间']

            # 3. 联表键预检拦截
            missing_keys = [k for k in join_keys if k not in df_tfd.columns or k not in df_tfm.columns]
            if missing_keys:
                st.error(f"❌ 严重错误：两张表中缺少核心联表键 {missing_keys}。请检查原表。")
                return

            # 4. 智能联表 (Merge)
            merged_df = pd.merge(df_tfd, df_tfm, on=join_keys, how='outer', suffixes=('_TFD', '_TFM'))

            def check_status(row):
                if pd.isna(row.get('Subcontractor')):
                    return "⚠️ 仅有 TFM (缺 TFD 成本)"
                elif pd.isna(row.get('TFM - Customer Name')):
                    return "⚠️ 仅有 TFD (缺 TFM 收入)"
                else:
                    return "✅ 匹配成功"

            merged_df['对账状态'] = merged_df.apply(check_status, axis=1)
            matched_df = merged_df[merged_df['对账状态'] == "✅ 匹配成功"].copy()

            # 5. 定义比对字典
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

            # 🌟 新增防弹机制 1：【列名雷达扫描】
            # 在比对前，提前确认这 20 个列名是否100%都能在表里找到，找不到直接报警并停止运行，防止出现隐性错账！
            missing_cols = []
            for tfm_col, tfd_col, _ in compare_map.values():
                if tfm_col not in matched_df.columns:
                    missing_cols.append(tfm_col)
                if tfd_col not in matched_df.columns:
                    missing_cols.append(tfd_col)

            if missing_cols:
                st.error(f"🛑 **雷达拦截**：对账被迫中止！在上传的文件中找不到以下列名：\n{list(set(missing_cols))}")
                st.info("💡 请返回 Excel (Power Query)，检查这些列名的拼写是否和系统设定完全一致（注意空格和大小写）。")
                return  # 找不到列就立刻停止，绝不瞎算

            # 6. 开始深度比对
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
                        # 🌟 新增防弹机制 2：【文本智能降噪】
                        # 强制把文本转成字符串，去除前后空格，并全部转成大写再进行比较。
                        # 这样 'Done' 和 'done ' 就会被判定为完全一样，大幅减少虚假报错！
                        clean_tfm = str(val_tfm).strip().upper() if pd.notna(val_tfm) else ""
                        clean_tfd = str(val_tfd).strip().upper() if pd.notna(val_tfd) else ""

                        if clean_tfm != clean_tfd:
                            has_diff = True

                        # 展示时依然显示业务员填的原始模样，方便溯源
                        orig_tfm = str(val_tfm).strip() if pd.notna(val_tfm) else ""
                        orig_tfd = str(val_tfd).strip() if pd.notna(val_tfd) else ""
                        diff_row[
                            f"{short_name} 差异"] = f"TFM: {orig_tfm} | TFD: {orig_tfd}" if clean_tfm != clean_tfd else "一致"

                if has_diff:
                    diff_records.append(diff_row)

            diff_df = pd.DataFrame(diff_records)

            # 7. 前端展示面板
            st.success("✅ 数据联表与深度校验完成！")

            col1, col2, col3 = st.columns(3)
            col1.metric("总单数", len(merged_df))
            col2.metric("单边账 (需排查)", len(merged_df[merged_df['对账状态'] != "✅ 匹配成功"]))
            col3.metric("匹配但有数据差异的单数", len(diff_df) if not diff_df.empty else 0)

            tab1, tab2, tab3 = st.tabs(["🔍 TFM 数据差异明细 (核心)", "⚠️ 单边账明细", "📊 完整全景表"])

            with tab1:
                st.markdown("### 🔍 匹配单据的数据差异 (TFM 录入错误/不一致)")
                st.info(
                    "💡 这里的单子是**已经成功匹配**的，但下面的 10 项业务数据 TFM 与 TFD 不一致。数值类展示的是 `差异 = TFM - TFD` (非0即错)；文本类展示了两边的具体填写内容。")
                if not diff_df.empty:
                    st.dataframe(diff_df, use_container_width=True)
                else:
                    st.success("🎉 太棒了！所有匹配上的单据，10 项核心数据 TFM 与 TFD 完全一致！")

            with tab2:
                st.markdown("### ⚠️ 单边账明细 (找不到对应单据)")
                error_df = merged_df[merged_df['对账状态'] != "✅ 匹配成功"]
                st.dataframe(error_df[['对账状态', 'Reference number', 'HORSE NO', '销售期间']],
                             use_container_width=True)

            with tab3:
                st.markdown("### 📊 原始合并明细 (供导出)")
                cols = ['对账状态', 'Reference number', 'HORSE NO', '销售期间'] + [c for c in merged_df.columns if
                                                                                   c not in ['对账状态',
                                                                                             'Reference number',
                                                                                             'HORSE NO', '销售期间']]
                st.dataframe(merged_df[cols], use_container_width=True)

        except Exception as e:
            st.error(f"❌ 系统发生严重错误：{e}")