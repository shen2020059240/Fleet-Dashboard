# views/upload.py
import streamlit as st
import pandas as pd
from utils.db import save_to_db, save_logistic_to_db, DB_FILE
from parsers import sk_parser, tm_parser
import os


def render():
    st.title("⚙️ 数据中心 (上传与维护)")
    st.markdown("💡 **智能防重系统启动中**：上传时间重叠的文件会自动防冲突并记录日志，入库前会自动生成 `.db` 备份文件。")

    col1, col2 = st.columns(2)

    with col1:
        with st.container(border=True):
            st.markdown("<h3 style='color:#0284c7;'>🛏️ 通道 A: 平板车数据</h3>", unsafe_allow_html=True)
            st.caption("适用: TM 公司 / HC 朋友车")
            flatbed_file = st.file_uploader("请上传合并报表 (.xlsx)", type=['xlsx'], key="up_fb")

            if flatbed_file and st.button("🚀 验证并入库 (Flatbed)", use_container_width=True):
                with st.spinner("执行清洗与 SQLite 写入..."):
                    df_fb = tm_parser.parse(flatbed_file)
                    success, msg = save_to_db(df_fb)
                    if success:
                        st.success(f"✅ 入库成功！新增/更新 {len(df_fb)} 条明细。")
                    else:
                        st.error(f"❌ {msg}")

    with col2:
        with st.container(border=True):
            st.markdown("<h3 style='color:#1e293b;'>🛢️ 通道 B: 油罐车数据</h3>", unsafe_allow_html=True)
            st.caption("适用: SK 公司自有车")
            tanker_file = st.file_uploader("请上传日报表日志 (.xlsx)", type=['xlsx'], key="up_ot")

            if tanker_file and st.button("🚀 验证并入库 (Tanker)", use_container_width=True):
                with st.spinner("执行清洗与 SQLite 写入..."):
                    df_ot = sk_parser.parse(tanker_file)
                    success, msg = save_to_db(df_ot)
                    if success:
                        st.success(f"✅ 入库成功！新增/更新 {len(df_ot)} 条明细。")
                    else:
                        st.error(f"❌ {msg}")

    # ==========================================
    # 📦 新增的 通道 C (Function 2)
    # ==========================================
    with st.container(border=True):
        st.markdown("<h3 style='color:#10b981;'>📦 通道 C: 订单物流状态更新 (Function 2)</h3>", unsafe_allow_html=True)
        st.caption("适用: 通过 Power Query 提取出的脱敏模板 (Logistic_Upload_Template.xlsx)")
        logistic_file = st.file_uploader("请上传脱敏物流节点报表 (.xlsx)", type=['xlsx'], key="up_log")

        if logistic_file and st.button("🚀 验证并覆盖更新 (全量刷新)", use_container_width=True):
            with st.spinner("正在读取并更新云端物流数据库..."):
                try:
                    # 直接读取用户上传的文件
                    df_log = pd.read_excel(logistic_file)

                    # 简单清洗：去除全空的行
                    df_log = df_log.dropna(how='all')

                    success, msg = save_logistic_to_db(df_log)
                    if success:
                        st.success(f"✅ 更新成功！当前数据库包含 {len(df_log)} 条物流追踪记录。")
                    else:
                        st.error(f"❌ {msg}")
                except Exception as e:
                    st.error(f"❌ 文件解析失败: {str(e)}")

    if os.path.exists(DB_FILE):
        st.divider()
        st.caption(f"🛡️ 核心数据库运行正常 | 引擎: SQLite | 本地路径: `{DB_FILE}`")