import streamlit as st
import requests
import pandas as pd
import numpy as np
import joblib
import datetime

# =========================================================
# 1. ตั้งค่าหน้าเว็บ Streamlit
# =========================================================
st.set_page_config(page_title="ระบบแจ้งเตือนฝุ่น PM 2.5", page_icon="🏫", layout="wide")

st.markdown("""
    <style>
    .big-font { font-size:24px !important; font-weight: bold; color: #1E3A8A; }
    .status-box { padding: 20px; border-radius: 10px; text-align: center; margin-bottom: 20px; box-shadow: 2px 2px 10px rgba(0,0,0,0.05);}
    </style>
""", unsafe_allow_html=True)

# =========================================================
# 2. ตั้งค่าคีย์ต่างๆ 
# =========================================================
CHANNEL_ID = "2104323"            
READ_API_KEY = "J29XMPTCYYIX42XK" 

# =========================================================
# 3. ฟังก์ชันการทำงานหลังบ้าน (Backend)
# =========================================================
@st.cache_data(ttl=300) 
def load_thingspeak_data():
    url = f"https://api.thingspeak.com/channels/{CHANNEL_ID}/feeds.json?api_key={READ_API_KEY}&results=100"
    try:
        response = requests.get(url)
        data = response.json()
        if 'feeds' not in data or len(data['feeds']) == 0:
            return pd.DataFrame({'created_at': [pd.Timestamp.now()], 'field1': [0.0], 'field2': [0.0], 'field3': [0.0]})

        df = pd.DataFrame(data['feeds'])
        df['created_at'] = pd.to_datetime(df['created_at'])
        for col in ['field1', 'field2', 'field3']:
            if col not in df.columns:
                df[col] = 0.0 
            else:
                df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0.0) 
        return df
    except:
        return pd.DataFrame({'created_at': [pd.Timestamp.now()], 'field1': [0.0], 'field2': [0.0], 'field3': [0.0]})

@st.cache_data(ttl=3600) # ดึงพยากรณ์อากาศใหม่ทุก 1 ชั่วโมง
def get_7d_weather(lat=13.28, lon=100.92): # 📍 พิกัด ม.บูรพา บางแสน
    url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&daily=temperature_2m_max,relative_humidity_2m_mean,wind_speed_10m_max,rain_sum&timezone=Asia/Bangkok"
    try:
        res = requests.get(url)
        data = res.json()
        return pd.DataFrame(data['daily'])
    except:
        return None

# =========================================================
# 4. ส่วนแสดงผลบนหน้าเว็บ (UI Dashboard)
# =========================================================
st.image("https://images.unsplash.com/photo-1596324121712-5bbc14482174?q=80&w=1200&auto=format&fit=crop", use_container_width=True)
st.markdown("<p class='big-font'>🏫 ศูนย์เฝ้าระวังคุณภาพอากาศและ AI พยากรณ์ฝุ่น (ม.บูรพา)</p>", unsafe_allow_html=True)
st.caption("ระบบ IoT & Machine Learning ตรวจวัดและแจ้งเตือนมลพิษทางอากาศอัตโนมัติ")

df = load_thingspeak_data()
latest = df.iloc[-1]
pm_val = latest['field1']

tab1, tab2, tab3 = st.tabs(["📊 สภาพอากาศปัจจุบัน", "🔮 AI พยากรณ์ล่วงหน้า (7 วัน)", "📈 ประวัติย้อนหลัง"])

with tab1:
    st.subheader("สภาพอากาศ ณ เวลาปัจจุบัน (พื้นที่บางแสน)")
    if pm_val == 0.0:
        st.markdown("<div class='status-box' style='background-color: #e0e0e0; color: #555;'>⏳ <b>รอรับข้อมูลจากสถานีตรวจวัด</b> (บอร์ดยังไม่เริ่มทำงาน)</div>", unsafe_allow_html=True)
    elif pm_val <= 25.0:
        st.markdown("<div class='status-box' style='background-color: #d4edda; color: #155724;'>🟢 <b>คุณภาพอากาศดี:</b> จัดกิจกรรมกลางแจ้งได้ตามปกติ</div>", unsafe_allow_html=True)
    elif pm_val <= 37.5:
        st.markdown("<div class='status-box' style='background-color: #fff3cd; color: #856404;'>🟡 <b>ปานกลาง:</b> กลุ่มเสี่ยงควรลดระยะเวลาทำกิจกรรมกลางแจ้ง</div>", unsafe_allow_html=True)
    elif pm_val <= 75.0:
        st.markdown("<div class='status-box' style='background-color: #ffe8a1; color: #d35400;'>🟠 <b>เริ่มมีผลกระทบ:</b> ควรเลี่ยงกิจกรรมกลางแจ้ง และสวมหน้ากากอนามัย</div>", unsafe_allow_html=True)
    else:
        st.markdown("<div class='status-box' style='background-color: #f8d7da; color: #721c24;'>🔴 <b>อันตราย:</b> งดกิจกรรมกลางแจ้ง ย้ายเข้าอาคารร่มทันที</div>", unsafe_allow_html=True)

    c1, c2, c3 = st.columns(3)
    c1.metric("PM 2.5 (µg/m³)", f"{pm_val:.1f}")
    c2.metric("อุณหภูมิ (°C)", f"{latest['field2']:.1f}")
    c3.metric("ความชื้นสัมพัทธ์ (%)", f"{latest['field3']:.1f}")

with tab2:
    st.subheader("พยากรณ์ความเสี่ยงฝุ่น PM 2.5 (7 วันล่วงหน้า)")
    st.info("💡 ข้อมูลพยากรณ์อากาศบริเวณ ม.บูรพา บางแสน ถูกประมวลผลผ่านโมเดล AI เพื่อคาดการณ์ปริมาณฝุ่น")
    
    weather_df = get_7d_weather()
    
    if weather_df is not None:
        try:
            model_7d = joblib.load('pm25_ai_model_7d.pkl')
            X_forecast = weather_df[['temperature_2m_max', 'relative_humidity_2m_mean', 'wind_speed_10m_max', 'rain_sum']]
            predicted_pm25 = model_7d.predict(X_forecast)
            
            cols = st.columns(7)
            for i, col in enumerate(cols):
                day_label = pd.to_datetime(weather_df['time'][i]).strftime("%a %d/%m")
                val = round(predicted_pm25[i], 1)
                status_color = "#28a745" if val <= 25.0 else ("#ffc107" if val <= 37.5 else "#dc3545")
                
                with col:
                    st.markdown(f"<div style='text-align: center; padding: 10px; border: 1px solid #ddd; border-radius: 8px;'>"
                                f"<p style='margin:0; font-size: 14px;'>{day_label}</p>"
                                f"<h3 style='margin:0; color: {status_color};'>{val}</h3>"
                                f"<p style='margin:0; font-size: 12px; color: gray;'>µg/m³</p>"
                                f"</div>", unsafe_allow_html=True)
        except Exception as e:
            st.error("⚠️ ไม่พบไฟล์โมเดล AI (pm25_ai_model_7d.pkl) กรุณาตรวจสอบใน GitHub")
    else:
        st.error("⚠️ ไม่สามารถดึงข้อมูลพยากรณ์อากาศได้ในขณะนี้")

with tab3:
    st.subheader("กราฟแนวโน้มฝุ่นย้อนหลัง")
    if len(df) > 1:
        df_chart = df.set_index('created_at')[['field1']]
        df_chart.columns = ['PM 2.5']
        st.line_chart(df_chart, height=300)
    else:
        st.caption("⏳ กำลังรอสะสมข้อมูลเพื่อสร้างกราฟ...")
