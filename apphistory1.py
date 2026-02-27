import streamlit as st
import sqlite3
import pandas as pd
import datetime
import random
from streamlit_autorefresh import st_autorefresh

# ==========================================
# 1. 核心配置与数据库初始化
# ==========================================
# 【修复1】更换数据库名称，抛弃旧的冲突数据，建立全新 6 列数据库
DB_FILE = 'classroom_v2.db' 
ROWS = 9     
COLS = 10    
VIP_ROWS = 3 
TEACHER_PWD = "admin" 
CLASSES = ["25历史学1班", "25历史学2班", "25音乐学2班", "其他"]

def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS seats
                 (row INTEGER, col INTEGER, student_id TEXT, student_name TEXT, class_name TEXT, timestamp TEXT, PRIMARY KEY(row, col))''')
    c.execute('''CREATE TABLE IF NOT EXISTS logs
                 (timestamp TEXT, student_id TEXT, student_name TEXT, class_name TEXT, action TEXT, points INTEGER)''')
    c.execute('''CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT)''')
    
    c.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('class_open', 'True')")
    c.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('current_pin', '8888')")
    conn.commit()
    conn.close()

init_db()

# ==========================================
# 2. 数据库读写逻辑
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

def take_seat(row, col, stu_id, stu_name, class_name):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT student_id FROM seats WHERE row=? AND col=?", (row, col))
    if c.fetchone() is None:
        time_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        c.execute("INSERT INTO seats VALUES (?, ?, ?, ?, ?, ?)", 
                  (row, col, stu_id, stu_name, class_name, time_str))
        
        points = 2 if row <= VIP_ROWS else 1
        action = f"入座 {row}排{col}座" if row > VIP_ROWS else f"抢占VIP {row}排{col}座"
        c.execute("INSERT INTO logs VALUES (?, ?, ?, ?, ?, ?)", 
                  (time_str, stu_id, stu_name, class_name, action, points))
        conn.commit()
        conn.close()
        return True, points
    conn.close()
    return False, 0

def add_bonus_points(stu_id, stu_name, class_name):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    time_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    c.execute("INSERT INTO logs VALUES (?, ?, ?, ?, ?, ?)", 
              (time_str, stu_id, stu_name, class_name, "课堂主动答题", 2))
    conn.commit()
    conn.close()

# ==========================================
# 3. 界面渲染路由
# ==========================================
st.set_page_config(layout="wide", page_title="课堂互动空间")
query_params = st.query_params
view_mode = query_params.get("view", "student")

current_pin = get_setting('current_pin')
is_open = get_setting('class_open') == 'True'

if view_mode == "screen":
    # ------------------ 大屏端（完美还原 2-6-2 布局 + 互动区） ------------------
    st_autorefresh(interval=3000, limit=None, key="screen_refresh")
    
    # 【修复2】恢复大屏幕的左右 3:1 分栏结构
    col_main, col_side = st.columns([3, 1])
    
    with col_main:
        st.markdown("<h1 style='text-align: center;'>🎯 课堂座位实时看板</h1>", unsafe_allow_html=True)
        if is_open:
            st.markdown(f"<h3 style='text-align: center; color: #D32F2F;'>今日签到口令：【 {current_pin} 】</h3>", unsafe_allow_html=True)
        else:
            st.markdown("<h3 style='text-align: center; color: gray;'>🚫 签到通道已关闭</h3>", unsafe_allow_html=True)
        st.markdown("---")
        
        conn = sqlite3.connect(DB_FILE)
        seats_df = pd.read_sql_query("SELECT * FROM seats", conn)
        conn.close()
        taken_seats = {(row['row'], row['col']): row['student_name'] for _, row in seats_df.iterrows()}
        
        # 渲染 2-6-2 布局
        for r in range(1, ROWS + 1):
            cols_layout = st.columns([1, 1, 0.4, 1, 1, 1, 1, 1, 1, 0.4, 1, 1])
            seat_col_indices = [0, 1, 3, 4, 5, 6, 7, 8, 10, 11]
            
            for c in range(1, COLS + 1):
                ui_col_index = seat_col_indices[c-1]
                seat_status = taken_seats.get((r, c), "空座")
                
                if seat_status != "空座":
                    bg_color = "#1E88E5" if r > VIP_ROWS else "#4CAF50" 
                    text = f"🧑‍🎓 {seat_status}"
                elif r <= VIP_ROWS:
                    bg_color = "#FDD835" 
                    text = f"⭐ {r}-{c}"
                else:
                    bg_color = "#E0E0E0" 
                    text = f"{r}-{c}"
                
                html = f"""<div style="background-color: {bg_color}; padding: 8px 2px; border-radius: 5px; 
                            text-align: center; margin-bottom: 8px; font-weight: bold; color: #333; font-size: 13px;">{text}</div>"""
                cols_layout[ui_col_index].markdown(html, unsafe_allow_html=True)

    # 恢复大屏幕右侧的实时加分榜
    with col_side:
        st.header("📢 实时加分榜")
        conn = sqlite3.connect(DB_FILE)
        logs_df = pd.read_sql_query("SELECT * FROM logs ORDER BY timestamp DESC LIMIT 15", conn)
        conn.close()
        if not logs_df.empty:
            for _, row in logs_df.iterrows():
                time_only = row['timestamp'].split(" ")[1]
                st.info(f"[{time_only}] **{row['student_name']}** ({row['class_name'][:3]})\n\n{row['action']} (+{row['points']})")
        else:
            st.write("坐等第一位发言的同学...")

elif view_mode == "admin":
    # ------------------ 教师隐藏后台 ------------------
    st.title("⚙️ 教师管理后台")
    pwd_input = st.text_input("请输入管理员密码", type="password")
    
    if pwd_input == TEACHER_PWD:
        st.success("✅ 身份验证成功")
        
        st.subheader("1. 课堂控制")
        col1, col2 = st.columns(2)
        with col1:
            if st.button("🔄 生成新课堂口令", use_container_width=True):
                new_p = generate_new_pin()
                st.success(f"新口令已生成：{new_p}")
        with col2:
            if is_open:
                if st.button("🛑 关闭签到通道（迟到防刷）", use_container_width=True):
                    update_setting('class_open', 'False')
                    st.rerun()
            else:
                if st.button("🟢 重新开放签到", use_container_width=True):
                    update_setting('class_open', 'True')
                    st.rerun()
                    
        st.markdown("---")
        st.subheader("2. 数据导出与重置 (下课必点！)")
        conn = sqlite3.connect(DB_FILE)
        all_logs_df = pd.read_sql_query("SELECT * FROM logs", conn)
        conn.close()
        
        st.download_button(
            label="📊 下载今日完整数据日志 (CSV)",
            data=all_logs_df.to_csv(index=False).encode('utf-8-sig'),
            file_name=f"class_logs_{datetime.datetime.now().strftime('%Y%m%d')}.csv",
            mime="text/csv",
            use_container_width=True
        )
        
        st.warning("⚠️ 导出数据后，请清空数据，迎接下一节课的其他班级。")
        if st.button("🗑️ 清空所有座位和日志 (无法恢复)", type="primary"):
            clear_all_data()
            st.success("数据已清空，大屏幕已重置为全新状态！")
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
        # 【优化】开启 clear_on_submit=False 让浏览器更容易记住表单内容
        with st.form("login_form", clear_on_submit=False):
            st.write("### 身份认证")
            class_name = st.selectbox("学科与班级", CLASSES)
            stu_id = st.text_input("学号 (浏览器会自动记忆)")
            stu_name = st.text_input("姓名 (浏览器会自动记忆)")
            pin_input = st.text_input("大屏幕【4位口令】")
            submitted = st.form_submit_button("进入系统")
            
            if submitted:
                if pin_input != current_pin:
                    st.error("❌ 口令错误！请抬头看大屏幕。")
                elif not stu_id or not stu_name:
                    st.error("❌ 请填写完整的学号和姓名。")
                else:
                    st.session_state.class_name = class_name
                    st.session_state.stu_id = stu_id
                    st.session_state.stu_name = stu_name
                    st.session_state.logged_in = True
                    st.rerun()
    else:
        st.success(f"你好，{st.session_state.stu_name} ({st.session_state.class_name})")
        tab1, tab2 = st.tabs(["🪑 抢占座位", "🙋 答题加分"])
        
        with tab1:
            conn = sqlite3.connect(DB_FILE)
            seats_df = pd.read_sql_query("SELECT * FROM seats", conn)
            conn.close()
            taken_set = set(zip(seats_df['row'], seats_df['col']))
            
            if st.session_state.stu_id in seats_df['student_id'].values:
                st.info("✅ 你已经签到入座，平时分已记录。")
            else:
                available_seats = []
                for r in range(1, ROWS + 1):
                    for c in range(1, COLS + 1):
                        if (r, c) not in taken_set:
                            prefix = "⭐[VIP区+2分]" if r <= VIP_ROWS else "🪑[普通区+1分]"
                            available_seats.append(f"{prefix} {r}排-{c}座")
                
                if available_seats:
                    selected_seat = st.selectbox("选择你实际坐的位置：", available_seats)
                    if st.button("确认入座", type="primary"):
                        parts = selected_seat.split(" ")
                        r = int(parts[1].split("-")[0].replace("排", ""))
                        c = int(parts[1].split("-")[1].replace("座", ""))
                        
                        success, gained_points = take_seat(r, c, st.session_state.stu_id, st.session_state.stu_name, st.session_state.class_name)
                        if success:
                            st.success(f"✅ 入座成功！获得 {gained_points} 分！")
                            if gained_points == 2: st.balloons()
                            st.rerun()
                        else:
                            st.error("座位刚被抢走，请重选！")
                else:
                    st.warning("教室已满座啦！")

        with tab2:
            st.markdown("回答问题后，点击下方按钮自助加分。")
            if st.button("🙋 我刚回答了问题，加 2 分！", use_container_width=True):
                add_bonus_points(st.session_state.stu_id, st.session_state.stu_name, st.session_state.class_name)
                st.success("✅ 加分成功！积分已上墙。")
                
        # ------------------ 手机端：颜色编码日志看板 ------------------
        st.markdown("---")
        st.subheader("📊 课堂实时动态")
        st_autorefresh(interval=5000, limit=None, key="student_refresh")
        
        conn = sqlite3.connect(DB_FILE)
        logs_df = pd.read_sql_query("SELECT * FROM logs ORDER BY timestamp DESC LIMIT 8", conn)
        conn.close()
        
        for _, row in logs_df.iterrows():
            time_only = row['timestamp'].split(" ")[1]
            action = row['action']
            
            if "答题" in action:
                display_text = f"🔥 <span style='color: #D81B60; font-weight: bold;'>[{row['class_name'][:3]}] {row['student_name']} {action} (+{row['points']})</span>"
            elif "VIP" in action:
                display_text = f"⭐ <span style='color: #FDD835; font-weight: bold;'>[{row['class_name'][:3]}] {row['student_name']} {action} (+{row['points']})</span>"
            else:
                display_text = f"🧑‍🎓 <span style='color: #1E88E5;'>[{row['class_name'][:3]}] {row['student_name']} {action} (+{row['points']})</span>"
                
            st.markdown(f"[{time_only}] {display_text}", unsafe_allow_html=True)
