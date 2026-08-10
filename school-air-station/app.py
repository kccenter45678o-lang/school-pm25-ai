import streamlit as st
import requests
import pandas as pd

# --- การตั้งค่า ThingSpeak ---
CHANNEL_ID = '2104323'
READ_API_KEY = 'J29XMPTCYYIX42XK'
URL = f"https://api.thingspeak.com/channels/{CHANNEL_ID}/feeds.json?api_key={READ_API_KEY}&results=1"

# --- สมการ Calibration (Shift to Cloud) ---
SLOPE_M = 0.85      
INTERCEPT_C = 2.5   
HUMIDITY_THRESHOLD = 70.0 
HUMIDITY_PENALTY = 0.25   

def calibrate_pm25(raw_pm25, humidity):
    """ฟังก์ชันชดเชยค่าความชื้นและปรับเทียบสมการ"""
    if pd.isna(raw_pm25) or pd.isna(humidity):
        return None
        
    if humidity > HUMIDITY_THRESHOLD:
        compensated_pm25 = raw_pm25 - ((humidity - HUMIDITY_THRESHOLD) * HUMIDITY_PENALTY)
        compensated_pm25 = max(compensated_pm25, raw_pm25 * 0.5) 
    else:
        compensated_pm25 = raw_pm25
        
    final_pm25 = (compensated_pm25 * SLOPE_M) + INTERCEPT_C
    return max(0, round(final_pm25, 2)) 

@st.cache_data(ttl=300)
def get_latest_data():
    """ดึงข้อมูลล่าสุดจาก ThingSpeak"""
    try:
        response = requests.get(URL)
        data = response.json()
        feeds = data.get('feeds', [])
        
        if feeds:
            latest = feeds[-1]
            raw_pm25 = float(latest.get('field1', 0) or 0)
            raw_pm10 = float(latest.get('field2', 0) or 0)
            temp = float(latest.get('field3', 0) or 0)
            hum = float(latest.get('field4', 0) or 0)
            
            calibrated_pm25 = calibrate_pm25(raw_pm25, hum)
            
            return {
                'time': latest.get('created_at'),
                'raw_pm25': raw_pm25,
                'calibrated_pm25': calibrated_pm25,
                'temp': temp,
                'humidity': hum
            }
    except Exception as e:
        st.error(f"Error fetching data: {e}")
    return None

@st.cache_data(ttl=3600)
def get_regional_pm25_forecast():
    """ดึงข้อมูลคาดการณ์ PM 2.5 ล่วงหน้า 7 วันในพื้นที่ ม.บูรพา จาก Open-Meteo"""
    LAT = 13.28
    LON = 100.92
    url = f"https://air-quality-api.open-meteo.com/v1/air-quality?latitude={LAT}&longitude={LON}&hourly=pm2_5&timezone=Asia%2FBangkok"
    
    try:
        response = requests.get(url)
        data = response.json()
        
        if 'hourly' in data:
            df = pd.DataFrame(data['hourly'])
            df['time'] = pd.to_datetime(df['time'])
            df['date'] = df['time'].dt.date
            
            daily_df = df.groupby('date').mean().reset_index()
            daily_df = daily_df.rename(columns={'pm2_5': 'Regional_PM25'})
            daily_df['Regional_PM25'] = daily_df['Regional_PM25'].round(2)
            return daily_df
    except Exception as e:
        st.error(f"Error fetching regional air quality: {e}")
    return None

# --- UI บน Streamlit ---
st.set_page_config(page_title="PM 2.5 Monitor - BUU", page_icon="🌊", layout="centered")

st.title("ศูนย์เฝ้าระวังคุณภาพอากาศ (PM 2.5) ม.บูรพา บางแสน 🌊")
st.markdown("ระบบใช้เทคนิค Shift to Cloud Calibration ชดเชยค่าความชื้นและปรับเทียบด้วยสมการคณิตศาสตร์")

current_data = get_latest_data()

if current_data:
    st.subheader("📍 ข้อมูลปัจจุบัน (Real-time)")
    
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric(label="PM 2.5 (ก่อนปรับแก้)", value=f"{current_data['raw_pm25']} µg/m³")
    with col2:
        st.metric(label="PM 2.5 (แม่นยำสูง)", value=f"{current_data['calibrated_pm25']} µg/m³", 
                  delta=f"{round(current_data['calibrated_pm25'] - current_data['raw_pm25'], 2)} (ชดเชย)")
    with col3:
        st.metric(label="อุณหภูมิ", value=f"{current_data['temp']} °C")
    with col4:
        st.metric(label="ความชื้นสัมพัทธ์", value=f"{current_data['humidity']} %")
        
    st.info(f"**สมการอ้างอิง:** y = {SLOPE_M}x + {INTERCEPT_C} | ชดเชยความชื้นเมื่อสูงกว่า {HUMIDITY_THRESHOLD}%")
else:
    st.warning("รอรับข้อมูลจาก ThingSpeak...")

st.divider()

# --- ส่วนพยากรณ์ 7 วันล่วงหน้า ---
st.subheader("🌍 คาดการณ์แนวโน้ม PM 2.5 ล่วงหน้า 7 วัน (พื้นที่โดยรอบ)")
st.markdown("อ้างอิงข้อมูลดาวเทียมและสถานีใกล้เคียงจาก Open-Meteo (พิกัด ม.บูรพา บางแสน)")

with st.spinner('กำลังดึงข้อมูลพยากรณ์คุณภาพอากาศระดับภูมิภาค...'):
    forecast_df = get_regional_pm25_forecast()
    
    if forecast_df is not None and not forecast_df.empty:
        forecast_df['date'] = pd.to_datetime(forecast_df['date']).dt.strftime('%Y-%m-%d')
        chart_data = forecast_df.set_index('date')[['Regional_PM25']]
        
        st.line_chart(chart_data, color="#1f77b4")
        
# เลือกระบุเฉพาะ 2 คอลัมน์ที่ต้องการจริงๆ ก่อนเปลี่ยนชื่อ
        display_df = forecast_df[['date', 'Regional_PM25']].copy()
        display_df.columns = ['วันที่', 'คาดการณ์ PM 2.5 พื้นที่โดยรอบ (µg/m³)']
        
        if current_data:
            st.success(f"💡 **เปรียบเทียบ:** ค่าฝุ่นจากเซนเซอร์ของเราตอนนี้คือ **{current_data['calibrated_pm25']} µg/m³**")
            
        st.dataframe(display_df, use_container_width=True)
    else:
        st.error("ไม่สามารถดึงข้อมูลคาดการณ์จากพื้นที่โดยรอบได้ในขณะนี้")
