import streamlit as st
import pandas as pd


def render():
    st.title("⚖️ TFD & TFM 内部往来对账中心")
    st.markdown("💡 **智能对账引擎**：上传包含 `TFD` 和 `TFM` 两个 Sheet 的脱敏对账表，系统将自动核对成本与收入。")

    uploaded_file = st.file_uploader("📥 请上传对账 Excel 文件 (需包含 TFD 和 TFM sheet)", type=['xlsx'])

    if uploaded_file is not None:
        try:
            # 1. 读取两个 Sheet
            df_tfd = pd.read_excel(uploaded_file, sheet_name='TFD')
            df_tfm = pd.read_excel(uploaded_file, sheet_name='TFM')

            # 2. 设定“三把钥匙” (请确保这里的列名与你 Power Query 里的最终列名完全一致！)
            # 假设你已经把第三把钥匙改成了 'Date Arrived'
            join_keys = ['Reference number', 'HORSE NO', 'Date Arrived']

            # 3. 智能联表 (Merge)：使用 outer join 找出所有匹配和不匹配的单子
            # 为防止两边有相同的其他列名，加上 _TFD 和 _TFM 后缀
            merged_df = pd.merge(df_tfd, df_tfm, on=join_keys, how='outer', suffixes=('_TFD', '_TFM'))

            # 4. 业务逻辑计算 (如果匹配成功，计算 Margin)
            # 假设 TFM 的净收入列叫 'NET REVNEUE (USD)'，TFD 的成本叫 'Subcontract (Invoice amount) (USD)'
            # 注意：实际列名请根据你的表格精准替换
            if 'NET REVNEUE (USD)' in merged_df.columns and 'Subcontract\n (Invoice amount) \n(USD)' in merged_df.columns:
                merged_df['Margin (USD)'] = merged_df['NET REVNEUE (USD)'].fillna(0) - merged_df[
                    'Subcontract\n (Invoice amount) \n(USD)'].fillna(0)

            # 5. 异常状态标记 (单边账预警)
            def check_status(row):
                if pd.isna(row.get('Subcontract\n (Invoice amount) \n(USD)')):
                    return "⚠️ 仅有 TFM 收入 (无 TFD 成本)"
                elif pd.isna(row.get('NET REVNEUE (USD)')):
                    return "⚠️ 仅有 TFD 成本 (无 TFM 收入)"
                else:
                    return "✅ 匹配成功"

            merged_df['对账状态'] = merged_df.apply(check_status, axis=1)

            # 6. 前端展示
            st.success("✅ 数据联表对账完成！")

            # 统计面板
            col1, col2, col3 = st.columns(3)
            col1.metric("完美匹配单数", len(merged_df[merged_df['对账状态'] == "✅ 匹配成功"]))
            col2.metric("异常单边账 (缺成本)",
                        len(merged_df[merged_df['对账状态'] == "⚠️ 仅有 TFM 收入 (无 TFD 成本)"]))
            col3.metric("异常单边账 (缺收入)",
                        len(merged_df[merged_df['对账状态'] == "⚠️ 仅有 TFD 成本 (无 TFM 收入)"]))

            # 展示明细表，并将状态列前置
            cols = ['对账状态'] + [col for col in merged_df.columns if col != '对账状态']
            st.dataframe(merged_df[cols], use_container_width=True)

        except Exception as e:
            st.error(f"❌ 读取或对账时发生错误，请检查表名或列名是否完全一致。详细错误：{e}")