# main.py
import streamlit as st
from utils.db import init_db
from views import dashboard, upload
import warnings

warnings.filterwarnings('ignore')

# 保证数据库文件及表结构初始化
init_db()
# 全局页面配置

# 隐藏 Streamlit 默认的右上角菜单、顶部区域、页脚以及云端强制水印
hide_streamlit_style = """
    <style>
    #MainMenu {visibility: hidden;} /* 隐藏右上角汉堡菜单 */
    header {visibility: hidden;} /* 隐藏顶部的 Fork/GitHub 区域 */
    footer {visibility: hidden;} /* 隐藏底部的 Streamlit 水印 */
    /* 彻底隐藏 Streamlit Cloud 强制注入的悬浮徽章（包含头像和红条） */
    iframe[title="Streamlit cloud badge"] {display: none !important;}
    #st-app-badge {display: none !important;}
    .viewerBadge_container {display: none !important;}
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