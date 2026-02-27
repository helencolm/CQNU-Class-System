import streamlit as st
import sqlite3
import pandas as pd
import datetime
import random
from streamlit_autorefresh import st_autorefresh

# ==========================================
# 1. 数据库初始化 (新增系统状态表)
# ==========================================
DB_FILE = 'classroom.db'
ROWS = 8     # 教室总排数
COLS = 8     # 每排座位数
VIP_ROWS = 3 # 前几排算VIP
TEACHER_PWD = "admin" # ⚠️ 教师后台密码，请自行修改

def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS seats
                 (row INTEGER, col INTEGER, student_id TEXT, student_name TEXT, timestamp TEXT, PRIMARY KEY(row, col))''')
    c.execute('''CREATE TABLE IF NOT EXISTS logs
                 (timestamp TEXT, student_id TEXT, student_name TEXT, action TEXT, points INTEGER)''')
    # 新增 settings 表，用于全班共享“动态口令”和“签到开关”
    c.execute('''CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT)''')
    
    # 初始化默认设置
    c.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('class_open', 'True')")
    c.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('current_pin', '8888')")
    conn.commit()
    conn.close()

init_db()

# ==========================================
# 2. 数据库读写辅助函数
# ==========================================
def get_setting(key):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT value FROM settings WHERE key=?", (key,))
    res = c.fetchone()
    conn.close()
    return res[0] if res else None

def update_setting(key, value):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("UPDATE settings SET value=? WHERE key=?", (value, key))
    conn.commit()
    conn.close()

def generate_new_pin():
    new_pin = str(random.randint(1000, 9999))
    update_setting('current_pin', new_pin)
    return new_pin

def clear_all_data():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("DELETE FROM seats")
    c.execute("DELETE FROM logs")
    conn.commit()
    conn.close()

def take_seat(row, col, stu_id, stu_name):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT student_id FROM seats WHERE row=? AND col=?", (row, col))
    if c.fetchone() is None:
        time_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        c.execute("INSERT INTO seats (row, col, student_id, student_name, timestamp) VALUES (?, ?, ?, ?, ?)", 
                  (row, col, stu_id, stu_name, time_str))
        
        points = 2 if row <= VIP_ROWS else 1
        action = f"抢占 {row}排{col}座"
        c.execute("INSERT INTO logs VALUES (?, ?, ?, ?, ?)", (time_str, stu_id, stu_name, action, points))
        conn.commit()
        conn.close()
        return True
    conn.close()
    return False

def add_bonus_points(stu_id, stu_name):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    time_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    c.execute("INSERT INTO logs VALUES (?, ?, ?, ?, ?)", (time_str, stu_id, stu_name, "课堂主动加分", 2))
    conn.commit()
    conn.close()

# ==========================================
# 3. 界面路由
# ==========================================
st.set_page_config(layout="wide", page_title="课堂互动空间")
query_params = st.query_params
view_mode = query_params.get("view", "student")

current_pin = get_setting('current_pin')
is_open = get_setting('class_open') == 'True'

if view_mode == "screen":
    # ------------------ 大屏端（投屏使用） ------------------
    st_autorefresh(interval=3000, limit=None, key="screen_refresh")
    
    col_main, col_side = st.columns([3, 1])
    
    with col_main:
        st.markdown("<h1 style='text-align: center;'>🎯 课堂座位实时看板</h1>", unsafe_allow_html=True)
        if is_open:
            st.markdown(f"<h3 style='text-align: center; color: #D32F2F;'>今日签到口令：【 {current_pin} 】</h3>", unsafe_allow_html=True)
        else:
            st.markdown("<h3 style='text-align: center; color: gray;'>🚫 本次签到已结束</h3>", unsafe_allow_html=True)
        st.markdown("---")
        
        conn = sqlite3.connect(DB_FILE)
        seats_df = pd.read_sql_query("SELECT * FROM seats", conn)
        conn.close()
        taken_seats = {(row['row'], row['col']): row['student_name'] for _, row in seats_df.iterrows()}
        
        for r in range(1, ROWS + 1):
            cols = st.columns(COLS)
            for c in range(1, COLS + 1):
                seat_status = taken_seats.get((r, c), "空座")
                if seat_status != "空座":
                    bg_color = "#4CAF50" # 被占：绿色
                    text = f"🧑‍🎓 {seat_status}"
                elif r <= VIP_ROWS:
                    bg_color = "#FFD700" # VIP：金色
                    text = f"{r}排{c}座"
                else:
                    bg_color = "#E0E0E0" # 普通：灰色
                    text = f"{r}排{c}座"
                
                html = f"""<div style="background-color: {bg_color}; padding: 10px; border-radius: 5px; 
                            text-align: center; margin-bottom: 10px; font-weight: bold; color: #333;">{text}</div>"""
                cols[c-1].markdown(html, unsafe_allow_html=True)

    with col_side:
        st.header("📢 实时加分榜")
        conn = sqlite3.connect(DB_FILE)
        logs_df = pd.read_sql_query("SELECT * FROM logs ORDER BY timestamp DESC LIMIT 10", conn)
        conn.close()
        if not logs_df.empty:
            for _, row in logs_df.iterrows():
                time_only = row['timestamp'].split(" ")[1]
                st.info(f"[{time_only}] **{row['student_name']}** {row['action']} (+{row['points']})")
        else:
            st.write("虚位以待...")

elif view_mode == "admin":
    # ------------------ 教师隐藏后台 ------------------
    st.title("⚙️ 教师管理后台")
    pwd_input = st.text_input("请输入管理员密码", type="password")
    
    if pwd_input == TEACHER_PWD:
        st.success("✅ 身份验证成功")
        
        st.subheader("1. 课堂控制")
        col1, col2 = st.columns(2)
        with col1:
            if st.button("🔄 生成新课堂口令（换一批数字）", use_container_width=True):
                new_p = generate_new_pin()
                st.success(f"新口令已生成：{new_p}，大屏幕将自动更新。")
        with col2:
            if is_open:
                if st.button("🛑 关闭签到通道（迟到者无法签到）", use_container_width=True):
                    update_setting('class_open', 'False')
                    st.rerun()
            else:
                if st.button("🟢 重新开放签到通道", use_container_width=True):
                    update_setting('class_open', 'True')
                    st.rerun()
                    
        st.markdown("---")
        st.subheader("2. 数据导出与重置 (下课操作)")
        conn = sqlite3.connect(DB_FILE)
        all_logs_df = pd.read_sql_query("SELECT * FROM logs", conn)
        all_seats_df = pd.read_sql_query("SELECT * FROM seats", conn)
        conn.close()
        
        st.download_button(
            label="📊 下载今日完整数据日志 (CSV)",
            data=all_logs_df.to_csv(index=False).encode('utf-8-sig'),
            file_name=f"class_logs_{datetime.datetime.now().strftime('%Y%m%d')}.csv",
            mime="text/csv",
            use_container_width=True
        )
        
        st.warning("⚠️ 下课后点击下方按钮，清空今天的数据，为下周上课做准备。")
        if st.button("🗑️ 清空所有座位和日志 (无法恢复)", type="primary"):
            clear_all_data()
            st.success("数据已清空！")
            st.rerun()

else:
    # ------------------ 学生端（手机扫码） ------------------
    st.title("🚀 课堂签到与加分系统")
    
    if not is_open:
        st.error("🛑 老师已关闭目前的签到/加分通道。")
        st.stop()
        
    if 'logged_in' not in st.session_state:
        st.session_state.logged_in = False

    if not st.session_state.logged_in:
        with st.form("login_form"):
            st.write("### 身份认证")
            stu_id = st.text_input("学号")
            stu_name = st.text_input("姓名")
            pin_input = st.text_input("请输入大屏幕上的【4位口令】（防代签）")
            submitted = st.form_submit_button("进入系统")
            
            if submitted:
                if pin_input != current_pin:
                    st.error("❌ 口令错误！请抬头看大屏幕。")
                elif not stu_id or not stu_name:
                    st.error("❌ 请填写完整的学号和姓名。")
                else:
                    st.session_state.stu_id = stu_id
                    st.session_state.stu_name = stu_name
                    st.session_state.logged_in = True
                    st.rerun()
    else:
        st.success(f"你好，{st.session_state.stu_name}！口令正确。")
        tab1, tab2 = st.tabs(["🪑 抢占座位", "🙋 答题加分"])
        
        with tab1:
            conn = sqlite3.connect(DB_FILE)
            seats_df = pd.read_sql_query("SELECT * FROM seats", conn)
            conn.close()
            taken_set = set(zip(seats_df['row'], seats_df['col']))
            
            # 检查自己是否已经签到过
            if st.session_state.stu_id in seats_df['student_id'].values:
                st.info("✅ 你已经成功入座，无需重复签到。请看大屏幕！")
            else:
                available_seats = []
                for r in range(1, ROWS + 1):
                    for c in range(1, COLS + 1):
                        if (r, c) not in taken_set:
                            prefix = "⭐[VIP区]" if r <= VIP_ROWS else "普通区"
                            available_seats.append(f"{prefix} {r}排-{c}座")
                
                if available_seats:
                    selected_seat = st.selectbox("选择你实际坐的位置：", available_seats)
                    if st.button("确认入座", type="primary"):
                        parts = selected_seat.split(" ")
                        r = int(parts[1].split("-")[0].replace("排", ""))
                        c = int(parts[1].split("-")[1].replace("座", ""))
                        if take_seat(r, c, st.session_state.stu_id, st.session_state.stu_name):
                            st.success("✅ 占座成功！")
                            st.rerun()
                        else:
                            st.error("手慢了，座位刚被抢走，请重新选择！")
                else:
                    st.warning("教室已经满座啦！")

        with tab2:
            st.write("### 课堂互动通道")
            st.warning("⚠️ 记录将在大屏幕公示。")
            if st.button("🙋 我刚回答了问题，加 2 分！", use_container_width=True):
                add_bonus_points(st.session_state.stu_id, st.session_state.stu_name)
                st.success("✅ 加分成功！")