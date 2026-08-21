import streamlit as st
import pandas as pd
import numpy as np


def render():
    st.title("⚖️ TFD & TFM 内部往来对账中心")
    st.markdown("💡 **智能对账引擎**：以 TFD 成本表为基准，精准核对 TFM 收入表的 10 项核心业财数据。")

    uploaded_file = st.file_uploader("📥 请上传对账 Excel 文件 (需包含 TFD 和 TFM sheet)", type=['xlsx'])

    if uploaded_file is not None:
        try:
            # 1. 读取数据并清理可能存在的列名换行符（防止因 Excel 里的 Alt+Enter 导致找不到列）
            df_tfd = pd.read_excel(uploaded_file, sheet_name='TFD')
            df_tfm = pd.read_excel(uploaded_file, sheet_name='TFM')
            df_tfd.columns = df_tfd.columns.str.replace('\n', ' ').str.strip()
            df_tfm.columns = df_tfm.columns.str.replace('\n', ' ').str.strip()

            # 2. 设定联表唯一键（使用销售期间作为财务对账基准）
            join_keys = ['Reference number', 'HORSE NO', '销售期间']

            # 为了防止报错，检查这三个键是否都在
            missing_keys = [k for k in join_keys if k not in df_tfd.columns or k not in df_tfm.columns]
            if missing_keys:
                st.error(f"❌ 缺少核心联表键: {missing_keys}，请检查表格。")
                return

            # 3. 智能联表 (Merge)
            merged_df = pd.merge(df_tfd, df_tfm, on=join_keys, how='outer', suffixes=('_TFD', '_TFM'))

            # 4. 单边账基础预警 (检查某一边是否完全没有数据)
            def check_status(row):
                # 借助 TFM/TFD 独有的列来判断是否是单边账
                if pd.isna(row.get('Subcontractor')):  # TFD 里特有的列
                    return "⚠️ 仅有 TFM (缺 TFD 成本)"
                elif pd.isna(row.get('TFM - Customer Name')):  # TFM 里特有的列
                    return "⚠️ 仅有 TFD (缺 TFM 收入)"
                else:
                    return "✅ 匹配成功"

            merged_df['对账状态'] = merged_df.apply(check_status, axis=1)

            # 5. 核心：10列深度数据比对 (仅针对匹配成功的单子)
            matched_df = merged_df[merged_df['对账状态'] == "✅ 匹配成功"].copy()

            # 定义 10 对需要比对的列 { '前端展示简称': ('TFM列名', 'TFD列名', '类型') }
            # 注意：我根据你截图里的列名去掉了换行符
            compare_map = {
                'Tonnage Status': ('TONNAGE for Revenue status', 'TONNAGE for Subcon Cost status', 'text'),
                'Load/Off': ('TONNAGE for Revenue (LOAD / OFF)', 'TONNAGE for Subcon Cost (LOAD / OFF)', 'text'),
                'Quantity': ('Quantity for Revenue (MT / days)', 'Quantity for Subcon Cost', 'num'),
                'Qty Adj': ('Quantity for Revenue (MT / days) Adjustment', 'Quantity for Subcon Cost Adjustment',
                            'num'),
                'Adj Qty': ('Adjusted Quantity for Revenue (MT / days)', 'Adjusted Quantity for Subcon Cost', 'num'),
                'Price Status': ('Unit price for Revenue status', 'Unit costs for Subcon status', 'text'),
                'Unit Price': ('Unit price (USD)', 'Subcontract (unit costs) (USD)', 'num'),
                'Follow Up': ('Price information to be follow up', 'Price information to be follow up_1', 'text'),
                'Adj USD': ('Revenue adjustment (USD)', 'Subcontract Adjustment (USD)', 'num'),
                'Total USD': ('NET REVNEUE (USD)', 'Subcontract (Invoice amount) (USD)', 'num')
            }

            diff_records = []

            for index, row in matched_df.iterrows():
                has_diff = False
                diff_row = {
                    'Reference number': row['Reference number'],
                    'HORSE NO': row['HORSE NO'],
                    '销售期间': row['销售期间']
                }

                # 遍历 10 个指标
                for short_name, (col_tfm, col_tfd, col_type) in compare_map.items():
                    val_tfm = row.get(col_tfm)
                    val_tfd = row.get(col_tfd)

                    if col_type == 'num':
                        # 数值相减 (TFM - TFD)
                        tfm_num = float(val_tfm) if pd.notna(val_tfm) else 0.0
                        tfd_num = float(val_tfd) if pd.notna(val_tfd) else 0.0
                        diff = round(tfm_num - tfd_num, 2)
                        if diff != 0:
                            has_diff = True
                        diff_row[f"{short_name} (TFM-TFD)"] = diff
                    else:
                        # 文本比对
                        val_tfm = str(val_tfm).strip() if pd.notna(val_tfm) else ""
                        val_tfd = str(val_tfd).strip() if pd.notna(val_tfd) else ""
                        if val_tfm != val_tfd:
                            has_diff = True
                        diff_row[
                            f"{short_name} 差异"] = f"TFM:{val_tfm} | TFD:{val_tfd}" if val_tfm != val_tfd else "一致"

                # 只要这 10 个指标里有任何一个不一样，就把这单抓出来
                if has_diff:
                    diff_records.append(diff_row)

            diff_df = pd.DataFrame(diff_records)

            # 6. 前端展示面板
            st.success("✅ 数据联表与深度校验完成！")

            # 顶层统计
            col1, col2, col3 = st.columns(3)
            col1.metric("总单数", len(merged_df))
            col2.metric("单边账 (需排查)", len(merged_df[merged_df['对账状态'] != "✅ 匹配成功"]))
            col3.metric("匹配但有数据差异的单数", len(diff_df) if not diff_df.empty else 0)

            # 选项卡展示
            tab1, tab2, tab3 = st.tabs(["🔍 TFM 数据差异明细 (核心)", "⚠️ 单边账明细", "📊 完整全景表"])

            with tab1:
                st.markdown("### 🔍 匹配单据的数据差异 (TFM 录入错误/不一致)")
                st.info(
                    "💡 这里的单子是**已经成功匹配**的，但下面的 10 项业务数据 TFM 与 TFD 不一致。数值类展示的是 `差异 = TFM - TFD` (非0即错)；文本类展示了两边的具体填写内容。")
                if not diff_df.empty:
                    # 使用 pandas style 高亮非 0 或非一致的内容
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
            st.error(f"❌ 读取或对账时发生错误。这通常是因为表格里的列名与代码里预设的不一致。详细错误：{e}")
