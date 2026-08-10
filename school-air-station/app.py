import streamlit as st
import requests
import pandas as pd

# --- 1. การตั้งค่าหน้าเว็บ ---
st.set_page_config(
    page_title="PM 2.5 Monitor | BUU", 
    page_icon="🌊", 
    layout="wide",
    initial_sidebar_state="collapsed"
)

# --- 2. ตกแต่ง UI ด้วย CSS (Card & Background) ---
custom_css = """
<style>
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    
    /* เปลี่ยนสีพื้นหลังของเว็บให้เป็นสีเทาอ่อนๆ เพื่อให้การ์ดดูโดดเด่น */
    .stApp {
        background-color: #f8f9fa;
    }
    
    /* ตกแต่งกล่องตัวเลข (Metric) ให้เป็นรูปแบบการ์ดมีเงา */
    div[data-testid="metric-container"] {
        background-color: #ffffff;
        border: 1px solid #e0e0e0;
        padding: 15px 20px;
        border-radius: 12px;
        box-shadow: 0 4px 6px rgba(0,0,0,0.05);
        border-left: 5px solid #3498db; /* แถบสีฟ้าด้านซ้าย */
        transition: transform 0.2s;
    }
    div[data-testid="metric-container"]:hover {
        transform: translateY(-3px); /* ลูกเล่นขยับเมื่อเอาเมาส์ชี้ */
    }
</style>
"""
st.markdown(custom_css, unsafe_allow_html=True)

# --- การตั้งค่า ThingSpeak ---
CHANNEL_ID = '2104323'
READ_API_KEY = 'J29XMPTCYYIX42XK'
URL = f"https://api.thingspeak.com/channels/{CHANNEL_ID}/feeds.json?api_key={READ_API_KEY}&results=1"

# --- สมการ Calibration ---
SLOPE_M = 0.85      
INTERCEPT_C = 2.5   
HUMIDITY_THRESHOLD = 70.0 
HUMIDITY_PENALTY = 0.25   

def calibrate_pm25(raw_pm25, humidity):
    """ฟังก์ชันชดเชยค่าความชื้น"""
    if pd.isna(raw_pm25) or pd.isna(humidity): return None
    if humidity > HUMIDITY_THRESHOLD:
        compensated_pm25 = raw_pm25 - ((humidity - HUMIDITY_THRESHOLD) * HUMIDITY_PENALTY)
        compensated_pm25 = max(compensated_pm25, raw_pm25 * 0.5) 
    else:
        compensated_pm25 = raw_pm25
    final_pm25 = (compensated_pm25 * SLOPE_M) + INTERCEPT_C
    return max(0, round(final_pm25, 2)) 

@st.cache_data(ttl=300)
def get_latest_data():
    try:
        response = requests.get(URL)
        data = response.json()
        feeds = data.get('feeds', [])
        if feeds:
            latest = feeds[-1]
            raw_pm25 = float(latest.get('field1', 0) or 0)
            hum = float(latest.get('field4', 0) or 0)
            calibrated_pm25 = calibrate_pm25(raw_pm25, hum)
            return {
                'time': latest.get('created_at'),
                'raw_pm25': raw_pm25,
                'calibrated_pm25': calibrated_pm25,
                'temp': float(latest.get('field3', 0) or 0),
                'humidity': hum
            }
    except Exception as e:
        st.error(f"ระบบไม่สามารถดึงข้อมูลได้: {e}")
    return None

@st.cache_data(ttl=3600)
def get_regional_pm25_forecast():
    LAT, LON = 13.28, 100.92
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
        st.error(f"ไม่สามารถดึงข้อมูลพยากรณ์ได้: {e}")
    return None

# --- ฟังก์ชันแต่งสีตาราง ---
def color_pm25_level(val):
    """เปลี่ยนสีพื้นหลังตารางตามค่าฝุ่น"""
    if val <= 15.0:
        return 'background-color: #d4edda; color: #155724;' # เขียวอ่อน
    elif val <= 37.5:
        return 'background-color: #fff3cd; color: #856404;' # เหลืองอ่อน
    elif val <= 75.0:
        return 'background-color: #ffe8cc; color: #e67e22;' # ส้ม
    else:
        return 'background-color: #f8d7da; color: #721c24;' # แดงอ่อน

# --- UI หลัก ---
st.title("ศูนย์เฝ้าระวังคุณภาพอากาศ ม.บูรพา บางแสน 🌊")
st.markdown("**ระบบตรวจวัดฝุ่น PM 2.5 Real-time พร้อมเทคโนโลยีชดเชยความชื้น (Shift to Cloud Calibration)**")

tab1, tab2, tab3 = st.tabs(["📊 สถิติปัจจุบัน (Real-time)", "🌍 พยากรณ์ล่วงหน้า 7 วัน", "⚙️ ข้อมูลเชิงเทคนิค"])

current_data = get_latest_data()

with tab1:
    if current_data:
        pm_val = current_data['calibrated_pm25']
        
        # แจ้งเตือนสถานะ
        if pm_val <= 15.0: st.success("🟢 **คุณภาพอากาศดีมาก:** สามารถทำกิจกรรมกลางแจ้งได้ตามปกติ")
        elif pm_val <= 37.5: st.info("🟡 **คุณภาพอากาศปานกลาง:** ประชาชนทั่วไปทำกิจกรรมกลางแจ้งได้ กลุ่มเสี่ยงควรระวัง")
        elif pm_val <= 75.0: st.warning("🟠 **เริ่มมีผลกระทบต่อสุขภาพ:** ควรลดระยะเวลาการทำกิจกรรมกลางแจ้ง")
        else: st.error("🔴 **มีผลกระทบต่อสุขภาพ:** งดกิจกรรมกลางแจ้ง และสวมหน้ากากอนามัย N95 ทันที!")

        st.write("") # เว้นบรรทัด
        
        # กล่องข้อมูล (Cards)
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric(label="PM 2.5 (ปรับแก้แล้ว)", value=f"{pm_val} µg/m³", delta=f"{round(pm_val - current_data['raw_pm25'], 2)} (ชดเชย)")
        with col2:
            st.metric(label="PM 2.5 (ค่าดิบ)", value=f"{current_data['raw_pm25']} µg/m³")
        with col3:
            st.metric(label="อุณหภูมิ", value=f"{current_data['temp']} °C")
        with col4:
            st.metric(label="ความชื้นสัมพัทธ์", value=f"{current_data['humidity']} %")
            
        st.write("")
        st.caption(f"อัปเดตข้อมูลล่าสุดเมื่อ: {pd.to_datetime(current_data['time']).tz_convert('Asia/Bangkok').strftime('%Y-%m-%d %H:%M:%S')}")
    else:
        st.warning("กำลังรอการเชื่อมต่อข้อมูลจากสถานีตรวจวัด (ThingSpeak)...")

with tab2:
    st.subheader("พยากรณ์แนวโน้ม PM 2.5 พื้นที่โดยรอบ (อิงพิกัด ม.บูรพา)")
    st.markdown("ข้อมูลประเมินสภาพอากาศระดับภูมิภาคล่วงหน้า จากระบบดาวเทียม Open-Meteo")
    
    with st.spinner('กำลังโหลดข้อมูลพยากรณ์...'):
        forecast_df = get_regional_pm25_forecast()
        
        if forecast_df is not None and not forecast_df.empty:
            forecast_df['date'] = pd.to_datetime(forecast_df['date']).dt.strftime('%Y-%m-%d')
            
            # แบ่งหน้าจอครึ่งซ้ายขวา ให้กราฟและตารางอยู่คู่กัน (จะได้ไม่โล่ง)
            left_col, right_col = st.columns([6, 4])
            
            with left_col:
                chart_data = forecast_df.set_index('date')[['Regional_PM25']]
                st.area_chart(chart_data, color="#3498db")
                
            with right_col:
                display_df = forecast_df[['date', 'Regional_PM25']].copy()
                display_df.columns = ['วันที่คาดการณ์', 'ค่า PM 2.5 (µg/m³)']
                
                # นำฟังก์ชันแต่งสีมาใส่ตาราง
                styled_df = display_df.style.map(color_pm25_level, subset=['ค่า PM 2.5 (µg/m³)'])
                
                # แสดงตารางแบบซ่อนหมายเลขบรรทัด
                st.dataframe(styled_df, use_container_width=True, hide_index=True)

with tab3:
    st.subheader("ข้อมูลสถาปัตยกรรมระบบ (System Architecture)")
    st.markdown("""
    * **ฮาร์ดแวร์:** ESP32 Board + PMS5003 + BME280
    * **การกรองสัญญาณดิบ:** อัลกอริทึม Trimmed Mean 
    * **Cloud Database:** ThingSpeak
    """)
    st.info(f"**สมการ (Calibration):** y = {SLOPE_M}x + {INTERCEPT_C} | หักลบไอน้ำเมื่อความชื้นสูงเกิน {HUMIDITY_THRESHOLD}%")
