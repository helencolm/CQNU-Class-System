import streamlit as st
import sqlite3
import pandas as pd
import datetime
import random
from streamlit_autorefresh import st_autorefresh

# ==========================================
# 1. 核心配置与时区设定
# ==========================================
DB_FILE = 'classroom_v2.db' 
ROWS = 9     
COLS = 10    
VIP_ROWS = 3 
TEACHER_PWD = "hfyadmin" 
CLASSES = ["25历史学1班", "25历史学2班", "25音乐学2班", "其他"]
BJ_TZ = datetime.timezone(datetime.timedelta(hours=8))

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
# 2. 数据库逻辑 (引入 IntegrityError 原子操作)
# ==========================================
def get_setting(key):
    conn = sqlite3.connect(DB_FILE); c = conn.cursor()
    c.execute("SELECT value FROM settings WHERE key=?", (key,)); res = c.fetchone()
    conn.close(); return res[0] if res else None

def update_setting(key, value):
    conn = sqlite3.connect(DB_FILE); c = conn.cursor()
    c.execute("UPDATE settings SET value=? WHERE key=?", (value, key)); conn.commit(); conn.close()

def clear_all_data():
    conn = sqlite3.connect(DB_FILE); c = conn.cursor()
    c.execute("DELETE FROM seats"); c.execute("DELETE FROM logs"); conn.commit(); conn.close()

def take_seat(row, col, stu_id, stu_name, class_name):
    conn = sqlite3.connect(DB_FILE); c = conn.cursor()
    time_str = datetime.datetime.now(BJ_TZ).strftime("%Y-%m-%d %H:%M:%S")
    points = 2 if row <= VIP_ROWS else 1
    action = f"入座 {row}排{col}座" if row > VIP_ROWS else f"抢占VIP {row}排{col}座"
    try:
        # ✅ 原子插入，利用数据库主键锁死位置，高并发下绝不重复
        c.execute("INSERT INTO seats VALUES (?, ?, ?, ?, ?, ?)", (row, col, stu_id, stu_name, class_name, time_str))
        c.execute("INSERT INTO logs VALUES (?, ?, ?, ?, ?, ?)", (time_str, stu_id, stu_name, class_name, action, points))
        conn.commit(); conn.close(); return True, points
    except sqlite3.IntegrityError:
        conn.close(); return False, 0

def add_bonus_points(stu_id, stu_name, class_name):
    conn = sqlite3.connect(DB_FILE); c = conn.cursor()
    time_str = datetime.datetime.now(BJ_TZ).strftime("%Y-%m-%d %H:%M:%S")
    c.execute("INSERT INTO logs VALUES (?, ?, ?, ?, ?, ?)", (time_str, stu_id, stu_name, class_name, "课堂主动答题", 2))
    conn.commit(); conn.close()

# ==========================================
# 3. 界面逻辑
# ==========================================
st.set_page_config(layout="wide", page_title="课堂签到加分系统")
view_mode = st.query_params.get("view", "student")
current_pin = get_setting('current_pin')
is_open = get_setting('class_open') == 'True'

if view_mode == "screen":
    # ------------------ 大屏端 (维持原有全彩热力图UI) ------------------
    st_autorefresh(interval=3000, limit=None, key="screen_refresh")
    col_main, col_side = st.columns([3, 1.2])
    with col_main:
        st.markdown("<h1 style='text-align: center;'>🎯 《学生心理与教育》课堂座位实时热力图</h1>", unsafe_allow_html=True)
        if is_open: st.markdown(f"<h3 style='text-align: center; color: #D32F2F;'>今日签到口令：【 {current_pin} 】</h3>", unsafe_allow_html=True)
        else: st.markdown("<h3 style='text-align: center; color: gray;'>🚫 签到通道已关闭</h3>", unsafe_allow_html=True)
        st.markdown("---")
        conn = sqlite3.connect(DB_FILE); seats_df = pd.read_sql_query("SELECT * FROM seats", conn)
        logs_df = pd.read_sql_query("SELECT student_id, SUM(points) as bonus_pts FROM logs WHERE action LIKE '%答题%' GROUP BY student_id", conn); conn.close()
        bonus_dict = dict(zip(logs_df['student_id'], logs_df['bonus_pts']))
        taken_seats = {(row['row'], row['col']): row for _, row in seats_df.iterrows()}
        for r in range(1, ROWS + 1):
            cols_layout = st.columns([1, 1, 0.4, 1, 1, 1, 1, 1, 1, 0.4, 1, 1])
            seat_col_indices = [0, 1, 3, 4, 5, 6, 7, 8, 10, 11]
            for c in range(1, COLS + 1):
                ui_idx = seat_col_indices[c-1]
                if (r, c) in taken_seats:
                    s = taken_seats[(r, c)]; b = bonus_dict.get(s['student_id'], 0); total = (2 if r <= VIP_ROWS else 1) + b
                    bg = "#D81B60" if b >= 4 else ("#FF9800" if b > 0 else ("#FBC02D" if r <= VIP_ROWS else "#4CAF50"))
                    txt = f"{'🔥' if b>=4 else '🌟' if b>0 else '🧑‍🎓'} {s['student_name']}<br>({total}分)"
                else:
                    bg = "#FFF59D" if r <= VIP_ROWS else "#E0E0E0"
                    txt = f"⭐ {r}-{c}" if r <= VIP_ROWS else f"{r}-{c}"
                cols_layout[ui_idx].markdown(f'<div style="background-color: {bg}; padding: 8px 2px; border-radius: 5px; text-align: center; margin-bottom: 8px; font-weight: bold; color: #333; font-size: 13px;">{txt}</div>', unsafe_allow_html=True)
    with col_side:
        st.header("🏆 排行榜单")
        conn = sqlite3.connect(DB_FILE); lb_df = pd.read_sql_query("SELECT student_name, SUM(points) as total_pts FROM logs GROUP BY student_name ORDER BY total_pts DESC LIMIT 5", conn); conn.close()
        if not lb_df.empty:
            for i, row in lb_df.iterrows():
                rank = i+1; color = ["#D32F2F", "#E64A19", "#F57C00", "#388E3C", "#388E3C"][min(i, 4)]
                t_label = ["👑 榜一", "🥈 榜二", "🥉 榜三", f"🏅 第 {rank} 名", f"🏅 第 {rank} 名"][min(i, 4)]
                st.markdown(f"<div style='background-color: #fff; border: 2px solid {color}; border-radius: 8px; padding: 10px; margin-bottom: 8px; display: flex; justify-content: space-between; align-items: center;'><span style='font-size: 16px; font-weight: bold; color: {color};'>{t_label}</span><span style='font-size: 18px; font-weight: bold;'>{row['student_name']} <span style='color: #D81B60;'>{row['total_pts']}分</span></span></div>", unsafe_allow_html=True)
        st.markdown("---"); st.subheader("📢 实时动态")
        conn = sqlite3.connect(DB_FILE); l_df = pd.read_sql_query("SELECT * FROM logs ORDER BY timestamp DESC LIMIT 6", conn); conn.close()
        if not l_df.empty:
            for _, r in l_df.iterrows():
                tm = r['timestamp'].split(" ")[1]; ac = r['action']; bc = "#D81B60" if "答题" in ac else ("#FBC02D" if "VIP" in ac else "#1E88E5")
                st.markdown(f"<div style='margin-bottom: 8px; padding: 8px; border-radius: 5px; background-color: #f8f9fa; border-left: 5px solid {bc};'><div style='font-size: 13px; font-weight: bold; color: #333;'>{'🔥' if '答题' in ac else '⭐' if 'VIP' in ac else '🧑‍🎓'} [{tm}] {r['student_name']}</div><div style='font-size: 13px; color: {bc}; margin-top: 2px;'>{ac} (+{r['points']})</div></div>", unsafe_allow_html=True)

elif view_mode == "admin":
    # ------------------ 教师端 ------------------
    st.title("⚙️ 教师管理后台")
    if st.text_input("请输入管理员密码", type="password") == TEACHER_PWD:
        st.success("✅ 身份验证成功")
        if st.button("🔄 生成新口令"): update_setting('current_pin', str(random.randint(1000, 9999))); st.rerun()
        conn = sqlite3.connect(DB_FILE); df = pd.read_sql_query("SELECT * FROM logs", conn)
        c = conn.cursor(); c.execute("SELECT class_name FROM seats ORDER BY timestamp ASC LIMIT 1"); cls_name = c.fetchone()
        conn.close(); f_name = f"class_logs_{datetime.datetime.now(BJ_TZ).strftime('%Y%m%d')}_{cls_name[0] if cls_name else '未知'}.csv"
        st.download_button("📊 下载日志 (CSV)", df.to_csv(index=False).encode('utf-8-sig'), f_name, "text/csv")
        if st.button("🗑️ 清空所有数据", type="primary"): clear_all_data(); st.rerun()

else:
    # ------------------ 学生端 (结构化重构版) ------------------
    st.title("🚀 《学生心理与教育》签到系统")
    if not is_open: st.error("🛑 老师已关闭签到/加分通道。"); st.stop()
    if 'logged_in' not in st.session_state: st.session_state.logged_in = False

    if not st.session_state.logged_in:
        with st.form("login_form"):
            cn = st.selectbox("学科与班级", CLASSES); sid = st.text_input("学号"); sn = st.text_input("姓名"); pin = st.text_input("口令")
            if st.form_submit_button("进入系统"):
                if pin == current_pin and sid and sn:
                    st.session_state.update({"class_name": cn, "stu_id": sid, "stu_name": sn, "logged_in": True}); st.rerun()
                else: st.error("❌ 信息不全或口令错误")
    else:
        st.success(f"你好，{st.session_state.stu_name}")
        st_autorefresh(interval=10000, limit=None, key="tab_refresh")
        tab1, tab2, tab3 = st.tabs(["🪑 抢占座位", "🙋 答题加分", "🏆 排行榜单"])
        with tab1:
            conn = sqlite3.connect(DB_FILE); seats_df = pd.read_sql_query("SELECT * FROM seats", conn); conn.close()
            my_seat = seats_df[seats_df['student_id'] == st.session_state.stu_id]
            if not my_seat.empty:
                st.info(f"✅ 你已入座：{my_seat.iloc[0]['row']}排-{my_seat.iloc[0]['col']}座")
            else:
                taken_set = set(zip(seats_df['row'], seats_df['col']))
                # ✅ 核心修改点：选项直接存储 (行, 列, 前缀) 的元组，不再存字符串
                available_seats = [None] 
                for r in range(1, ROWS + 1):
                    for c in range(1, COLS + 1):
                        if (r, c) not in taken_set:
                            prefix = "⭐[VIP区+2分]" if r <= VIP_ROWS else "🪑[普通区+1分]"
                            available_seats.append((r, c, prefix))
                
                with st.form("seat_form"):
                    # ✅ 核心修改点：通过 format_func 美化显示，但后台拿到的 x 是元组
                    selected = st.selectbox("请在下方选择你的准确位置：", 
                                          available_seats, 
                                          format_func=lambda x: f"{x[2]} {x[0]}排-{x[1]}座" if x else "-- 请先点击选择座位 --")
                    if st.form_submit_button("确认入座", type="primary"):
                        if selected is None:
                            st.warning("⚠️ 请选择一个具体的座位！")
                        else:
                            # ✅ 核心修改点：不再解析字符串，直接解包元组，万无一失
                            r_val, c_val, _ = selected
                            success, pts = take_seat(r_val, c_val, st.session_state.stu_id, st.session_state.stu_name, st.session_state.class_name)
                            if success: st.success(f"✅ 入座成功！获得 {pts} 分！"); st.rerun()
                            else: st.error("❌ 手慢了！该座位已被抢先占领，请刷新重选！")
        with tab2:
            if st.button("🙋 我回答了问题，加 2 分！", use_container_width=True):
                add_bonus_points(st.session_state.stu_id, st.session_state.stu_name, st.session_state.class_name); st.success("✅ 加分成功！")
        with tab3:
            st.subheader("🔥 实时排名")
            conn = sqlite3.connect(DB_FILE); lb_df = pd.read_sql_query("SELECT student_name, SUM(points) as total_pts FROM logs GROUP BY student_name ORDER BY total_pts DESC LIMIT 10", conn); conn.close()
            if not lb_df.empty:
                for i, row in lb_df.iterrows(): st.markdown(f"**第 {i+1} 名：** {row['student_name']} ({row['total_pts']}分)")
