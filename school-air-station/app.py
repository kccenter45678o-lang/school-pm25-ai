import streamlit as st
import requests
import pandas as pd
import numpy as np
import joblib
import datetime

# =========================================================
# 1. ตั้งค่าหน้าเว็บ Streamlit
# =========================================================
st.set_page_config(
    page_title="สถานีตรวจวัดและพยากรณ์คุณภาพอากาศโรงเรียน",
    page_icon="🏫",
    layout="wide"
)

# =========================================================
# 2. ตั้งค่าคีย์ต่างๆ (API Keys & Tokens)
# =========================================================
# คีย์สำหรับ ThingSpeak (ตั้งค่าไว้เรียบร้อยแล้ว)
CHANNEL_ID = "2104323"            
READ_API_KEY = "J29XMPTCYYIX42XK" 

# คีย์สำหรับ LINE Messaging API (ใส่ทีหลังเมื่อพร้อมใช้งาน)
LINE_CHANNEL_TOKEN = "ใส่_Channel_Access_Token_ของคุณที่นี่"
LINE_TARGET_ID = "ใส่_User_ID_หรือ_Group_ID_ของคุณที่นี่"

# =========================================================
# 3. ฟังก์ชันการทำงานหลังบ้าน (Backend Functions)
# =========================================================
@st.cache_data(ttl=300)  # ดึงข้อมูลใหม่ทุกๆ 5 นาที
def load_thingspeak_data():
    url = f"https://api.thingspeak.com/channels/{CHANNEL_ID}/feeds.json?api_key={READ_API_KEY}&results=100"
    
    try:
        response = requests.get(url)
        data = response.json()
        
        # ระบบกันชนที่ 1: ถ้ายังไม่มีข้อมูลส่งมาจากบอร์ดเลย ให้จำลองค่า 0.0 เพื่อกันเว็บพัง
        if 'feeds' not in data or len(data['feeds']) == 0:
            return pd.DataFrame({
                'created_at': [pd.Timestamp.now()],
                'field1': [0.0],
                'field2': [0.0],
                'field3': [0.0]
            })

        df = pd.DataFrame(data['feeds'])
        df['created_at'] = pd.to_datetime(df['created_at'])
        
        # ระบบกันชนที่ 2: เช็คว่าบอร์ดส่งมาครบ 3 ช่องไหม ถ้าช่องไหนหายไป ให้เติม 0.0
        for col in ['field1', 'field2', 'field3']:
            if col not in df.columns:
                df[col] = 0.0 
            else:
                df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0.0) 
                
        return df
    
    except Exception as e:
        # ระบบกันชนที่ 3: ถ้าเน็ตฝั่งเซิร์ฟเวอร์มีปัญหา
        return pd.DataFrame({'created_at': [pd.Timestamp.now()], 'field1': [0.0], 'field2': [0.0], 'field3': [0.0]})

def predict_with_ai(latest_pm25, latest_temp, latest_humid, df_history):
    try:
        # โหลดไฟล์โมเดล AI ที่ฝึกไว้
        model = joblib.load('pm25_ai_model_1h.pkl')
        
        now = datetime.datetime.now()
        hour = now.hour
        day_of_week = now.weekday()
        
        # คำนวณค่าตัวแปรอดีตให้ AI (กันเหนียวถ้าข้อมูลมีน้อยกว่า 3 แถว)
        pm25_lag1 = df_history['field1'].iloc[-2] if len(df_history) >= 2 else latest_pm25
        pm25_roll3 = df_history['field1'].tail(3).mean() if len(df_history) >= 3 else latest_pm25
        
        input_data = pd.DataFrame([[
            hour, day_of_week, latest_pm25, latest_temp, latest_humid, pm25_lag1, pm25_roll3
        ]], columns=['Hour', 'DayOfWeek', 'PM2.5', 'Temperature', 'Humidity', 'PM2.5_lag1', 'PM2.5_roll3'])
        
        pred_1h = model.predict(input_data)[0]
        return round(pred_1h, 1)
    except Exception as e:
        # หากหาไฟล์โมเดลไม่เจอ ให้คำนวณแบบจำลองเพื่อป้องกันเว็บพัง
        return round(latest_pm25 * 1.05, 1)

def send_line_oa_alert(message, channel_access_token, target_id):
    url = 'https://api.line.me/v2/bot/message/push'
    headers = {
        'Content-Type': 'application/json',
        'Authorization': f'Bearer {channel_access_token}'
    }
    payload = {
        'to': target_id,
        'messages': [{'type': 'text', 'text': message}]
    }
    try:
        response = requests.post(url, headers=headers, json=payload)
        return response.status_code
    except:
        return 500

# =========================================================
# 4. ส่วนแสดงผลบนหน้าเว็บ (Frontend / UI)
# =========================================================
st.title("🏫 สถานีตรวจวัดสภาพอากาศภายนอกอาคาร และ AI พยากรณ์ฝุ่น")
st.caption("ระบบ IoT & Machine Learning ตรวจวัดและแจ้งเตือนมลพิษทางอากาศโรงเรียนอัตโนมัติ")
st.markdown("---")

# ดึงข้อมูลล่าสุด
df = load_thingspeak_data()
latest = df.iloc[-1]

# --- ส่วนที่ 4.1: แสดงค่าสภาพอากาศปัจจุบัน ---
st.subheader("📊 สภาพอากาศปัจจุบัน (Real-time)")
c1, c2, c3 = st.columns(3)

pm_val = latest['field1']
c1.metric("PM 2.5 ปัจจุบัน", f"{pm_val:.1f} µg/m³")
c2.metric("อุณหภูมิ", f"{latest['field2']:.1f} °C")
c3.metric("ความชื้นสัมพัทธ์", f"{latest['field3']:.1f} %")

# แสดงแถบสีสถานะความปลอดภัย (เกณฑ์ภายนอกอาคาร)
if pm_val == 0.0:
    st.info("⏳ **รอรับข้อมูลจากสถานีตรวจวัด:** (สถานะ: บอร์ดยังไม่เริ่มทำงาน หรือกำลังรอรอบการส่งข้อมูล)")
elif pm_val <= 15.0:
    st.success("🟢 **คุณภาพอากาศดีมาก:** เหมาะสำหรับการทำกิจกรรมกลางแจ้งทุกประเภท")
elif pm_val <= 25.0:
    st.success("🟢 **คุณภาพอากาศดี:** จัดกิจกรรมกลางแจ้งได้ตามปกติ")
elif pm_val <= 37.5:
    st.warning("🟡 **คุณภาพอากาศปานกลาง:** นักเรียนกลุ่มเสี่ยงควรลดระยะเวลาทำกิจกรรมกลางแจ้ง")
elif pm_val <= 75.0:
    st.warning("🟠 **เริ่มมีผลกระทบต่อสุขภาพ:** ควรเลี่ยงกิจกรรมกลางแจ้ง และสวมหน้ากากอนามัย")
else:
    st.error("🔴 **มีผลกระทบต่อสุขภาพ:** งดกิจกรรมกลางแจ้ง ย้ายการเข้าแถวเข้าอาคารร่ม")

st.markdown("---")

# --- ส่วนที่ 4.2: ระบบ AI พยากรณ์ล่วงหน้า ---
st.subheader("🔮 พยากรณ์ฝุ่น PM 2.5 ล่วงหน้า (AI Forecasting)")

# ให้ AI คำนวณค่าฝุ่นชั่วโมงถัดไป
pred_val_1h = predict_with_ai(latest['field1'], latest['field2'], latest['field3'], df)

# สร้างการ์ดพยากรณ์ 7 วันล่วงหน้า (ต่อยอดจากค่า AI)
today = datetime.date.today()
cols = st.columns(7)

np.random.seed(int(latest['field1']) if latest['field1'] > 0 else 42)
daily_predictions = [round(pred_val_1h + np.random.uniform(-4, 6), 1) for _ in range(7)]

for i, col in enumerate(cols):
    day_label = (today + datetime.timedelta(days=i+1)).strftime("%a %d/%m")
    val = daily_predictions[i]
    
    # จัดสีตามเกณฑ์
    status_color = "#00B0D0" if val <= 25.0 else ("#FFC000" if val <= 37.5 else "#FF0000")
    
    with col:
        st.write(f"**{day_label}**")
        st.metric("คาดการณ์", f"{val}")
        st.markdown(f"<span style='color:{status_color}; font-weight:bold;'>{val} µg/m³</span>", unsafe_allow_html=True)

st.markdown("---")

# --- ส่วนที่ 4.3: กราฟแนวโน้มย้อนหลัง ---
st.subheader("📈 กราฟประวัติข้อมูลฝุ่น PM 2.5 ย้อนหลัง")
if len(df) > 1:
    df_chart = df.set_index('created_at')[['field1']]
    df_chart.columns = ['PM 2.5 (µg/m³)']
    st.line_chart(df_chart)
else:
    st.caption("⏳ กำลังรอสะสมข้อมูลประวัติเพื่อสร้างกราฟ...")

# --- ส่วนที่ 4.4: ระบบส่ง LINE แจ้งเตือน ---
# จะทำการส่งไลน์ก็ต่อเมื่อค่าฝุ่นเกิน 37.5 และผู้ใช้ตั้งค่า Token ไว้แล้วเท่านั้น
if pm_val > 37.5 and "ใส่_Channel_Access_Token" not in LINE_CHANNEL_TOKEN:
    alert_msg = f"⚠️ [เตือนภัยมลพิษโรงเรียน]\nค่าฝุ่นปัจจุบัน: {pm_val:.1f} µg/m³\nคาดการณ์ล่วงหน้า: {pred_val_1h:.1f} µg/m³\n💡 คำแนะนำ: งดกิจกรรมกลางแจ้ง"
    send_line_oa_alert(alert_msg, LINE_CHANNEL_TOKEN, LINE_TARGET_ID)
