# views/upload.py
import streamlit as st
from utils.db import save_to_db, DB_FILE
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

    if os.path.exists(DB_FILE):
        st.divider()
        st.caption(f"🛡️ 核心数据库运行正常 | 引擎: SQLite | 本地路径: `{DB_FILE}`")