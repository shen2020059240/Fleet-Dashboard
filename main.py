# main.py
import streamlit as st
from utils.db import init_db
from views import dashboard, upload
import warnings

warnings.filterwarnings('ignore')

# 保证数据库文件及表结构初始化
init_db()

# 全局页面配置
st.set_page_config(page_title="集团车队系统", page_icon="🚚", layout="wide")

hide_streamlit_style = """
    <style>
    #MainMenu {visibility: hidden;} /* 隐藏右上角汉堡菜单 */
    header {visibility: hidden;} /* 隐藏顶部的 Fork/GitHub 区域 */
    footer {visibility: hidden;} /* 隐藏底部的 Streamlit 水印 */
    </style>
    """
st.markdown(hide_streamlit_style, unsafe_allow_html=True)

# 侧边栏基础路由 (第二/三阶段可升级为 st.navigation)
st.sidebar.title("🛠️ 导航")
page = st.sidebar.radio("请选择服务", ["📊 业务看板 (构建中)", "⚙️ 数据中心 (可用)"])

if page == "📊 业务看板 (构建中)":
    dashboard.render()
elif page == "⚙️ 数据中心 (可用)":
    upload.render()