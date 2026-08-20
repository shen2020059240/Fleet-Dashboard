# utils/db.py
import sqlite3
import pandas as pd
import os
import shutil
from datetime import datetime
import traceback
import streamlit as st

DB_FILE = "master_fleet_data.db"
BACKUP_DIR = "backups"


def init_db():
    """初始化数据库与备份文件夹，建立联合唯一索引防重叠"""
    os.makedirs(BACKUP_DIR, exist_ok=True)
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    # 建立 Date 和 Vehicle 的联合唯一索引
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS fleet_records (
            Date TEXT,
            Vehicle TEXT,
            Company_Type TEXT,
            Vehicle_Type TEXT,
            Distance_km REAL,
            UNIQUE(Date, Vehicle)
        )
    ''')
    conn.commit()
    conn.close()


def backup_db():
    """入库前自动备份旧数据库"""
    if os.path.exists(DB_FILE):
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = os.path.join(BACKUP_DIR, f"backup_{timestamp}.db")
        shutil.copy2(DB_FILE, backup_path)


def save_to_db(df):
    """保存清洗后的数据至 SQLite"""
    if df.empty:
        return False, "清洗后的数据为空"

    try:
        backup_db()  # 触发自动备份
        conn = sqlite3.connect(DB_FILE)

        # 转换 Date 格式，方便存入 SQLite
        df_save = df.copy()
        df_save['Date'] = df_save['Date'].dt.strftime('%Y-%m-%d')

        # 将数据写入临时表
        df_save.to_sql('temp_records', conn, if_exists='replace', index=False)

        # INSERT OR REPLACE：如果“同一天+同一辆车”有数据，则覆盖最新里程
        insert_query = '''
            INSERT OR REPLACE INTO fleet_records (Date, Vehicle, Company_Type, Vehicle_Type, Distance_km)
            SELECT Date, Vehicle, Company_Type, Vehicle_Type, "Distance (km)" FROM temp_records
        '''
        conn.execute(insert_query)
        conn.commit()
        conn.close()

        # 清除加载缓存，确保前端看板能立即看到新数据
        load_from_db.clear()
        return True, "写入成功"

    except Exception as e:
        # 全局异常捕获
        traceback.print_exc()
        return False, f"数据库写入异常: {str(e)}"


@st.cache_data(ttl=300)
def load_from_db():
    """读取全量数据并提供缓存"""
    if not os.path.exists(DB_FILE):
        return pd.DataFrame()

    try:
        conn = sqlite3.connect(DB_FILE)
        df = pd.read_sql("SELECT * FROM fleet_records", conn)
        conn.close()

        if not df.empty:
            df['Date'] = pd.to_datetime(df['Date'])
            df.rename(columns={'Distance_km': 'Distance (km)'}, inplace=True)
        return df
    except Exception as e:
        traceback.print_exc()
        st.error(f"数据库读取异常: {str(e)}")
        return pd.DataFrame()


def save_logistic_to_db(df):
    """保存订单物流跟踪数据至 SQLite（全量覆盖模式）"""
    if df.empty:
        return False, "上传的物流数据为空"

    try:
        backup_db()  # 依然触发你的神仙自动备份机制，保障安全！
        conn = sqlite3.connect(DB_FILE)

        # 直接使用 replace 模式全量覆盖，保证云端数据和你的 Excel 母表永远完全一致
        df.to_sql('logistic_records', conn, if_exists='replace', index=False)

        conn.commit()
        conn.close()

        # 清除缓存，让前端马上刷新
        if 'load_logistic_from_db' in globals():
            load_logistic_from_db.clear()
        return True, "物流节点数据覆盖写入成功"
    except Exception as e:
        traceback.print_exc()
        return False, f"数据库写入异常: {str(e)}"


@st.cache_data(ttl=300)
def load_logistic_from_db():
    """读取物流节点全量数据，并提供缓存"""
    if not os.path.exists(DB_FILE):
        return pd.DataFrame()

    try:
        conn = sqlite3.connect(DB_FILE)
        # 先检查一下这张新表建好了没有
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='logistic_records'")
        if not cursor.fetchone():
            conn.close()
            return pd.DataFrame()

        df = pd.read_sql("SELECT * FROM logistic_records", conn)
        conn.close()

        # 智能把包含 "DATE" 字眼的列全部转换为标准时间格式
        for col in df.columns:
            if 'DATE' in col.upper():
                df[col] = pd.to_datetime(df[col], errors='coerce')

        return df
    except Exception as e:
        traceback.print_exc()
        st.error(f"物流数据读取异常: {str(e)}")
        return pd.DataFrame()