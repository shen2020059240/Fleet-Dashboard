# main.py 完整更新代码
import streamlit as st
from utils.db import init_db
from views import dashboard, upload
import warnings

warnings.filterwarnings('ignore')

# 保证数据库文件及表结构初始化
init_db()

# 全局页面配置
st.set_page_config(page_title="集团车队系统", page_icon="🚚", layout="wide")

# 隐藏 Streamlit 默认的右上角菜单、顶部区域、页脚以及云端强制水印
hide_streamlit_style = """
    <style>
    #MainMenu {visibility: hidden;}
    header {visibility: hidden;}
    footer {visibility: hidden;}
    iframe[title="Streamlit cloud badge"] {display: none !important;}
    #st-app-badge {display: none !important;}
    .viewerBadge_container {display: none !important;}
    </style>
    """
st.markdown(hide_streamlit_style, unsafe_allow_html=True)

# ================= 修改后的导航路由 =================
st.sidebar.title("🛠️ 导航")
page = st.sidebar.radio("请选择服务", [
    "🚛 Flatbed 运营看板",
    "🛢️ Oil Tanker 运营看板",
    "⚙️ 数据中心 (可用)"
])

if page == "🚛 Flatbed 运营看板":
    dashboard.render(business_line="Flatbed")
elif page == "🛢️ Oil Tanker 运营看板":
    dashboard.render(business_line="Oil Tanker")
elif page == "⚙️ 数据中心 (可用)":
    upload.render()