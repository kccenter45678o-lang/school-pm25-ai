import os
from nicegui import ui
import requests
import pandas as pd
from datetime import datetime

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
    """ฟังก์ชันชดเชยค่าความชื้นและปรับเทียบสมการ"""
    if pd.isna(raw_pm25) or pd.isna(humidity): return 0
    if humidity > HUMIDITY_THRESHOLD:
        compensated_pm25 = raw_pm25 - ((humidity - HUMIDITY_THRESHOLD) * HUMIDITY_PENALTY)
        compensated_pm25 = max(compensated_pm25, raw_pm25 * 0.5) 
    else:
        compensated_pm25 = raw_pm25
    final_pm25 = (compensated_pm25 * SLOPE_M) + INTERCEPT_C
    return max(0, round(final_pm25, 2)) 

# --- ฟังก์ชันดึงข้อมูล ---
def fetch_realtime_data():
    try:
        response = requests.get(URL)
        feeds = response.json().get('feeds', [])
        if feeds:
            latest = feeds[-1]
            raw_pm25 = float(latest.get('field1', 0) or 0)
            temp = float(latest.get('field3', 0) or 0)
            hum = float(latest.get('field4', 0) or 0)
            calibrated = calibrate_pm25(raw_pm25, hum)
            dt = datetime.strptime(latest.get('created_at'), "%Y-%m-%dT%H:%M:%SZ")
            return {"pm25_cal": calibrated, "pm25_raw": raw_pm25, "temp": temp, "hum": hum, "time": dt.strftime("%Y-%m-%d %H:%M:%S")}
    except Exception as e:
        print(f"Error fetching real-time: {e}")
    return None

def fetch_forecast_data():
    # อิงพิกัดจาก ม.บูรพา บางแสน
    LAT, LON = 13.28, 100.92
    url = f"https://air-quality-api.open-meteo.com/v1/air-quality?latitude={LAT}&longitude={LON}&hourly=pm2_5&timezone=Asia%2FBangkok"
    try:
        response = requests.get(url)
        data = response.json()
        if 'hourly' in data:
            df = pd.DataFrame(data['hourly'])
            df['time'] = pd.to_datetime(df['time'])
            df['date'] = df['time'].dt.date
            daily = df.groupby('date').mean().reset_index()
            daily['pm2_5'] = daily['pm2_5'].round(2)
            return daily
    except Exception as e:
        print(f"Error fetching forecast: {e}")
    return None

# ==========================================
# ส่วนของการสร้าง UI ด้วย NiceGUI
# ==========================================
ui.page_title('PM 2.5 Monitor | BUU')
ui.query('body').classes('bg-gradient-to-br from-blue-50 to-cyan-100 min-h-screen')

# Header
with ui.column().classes('w-full items-center pt-8 pb-4'):
    ui.label('ศูนย์เฝ้าระวังคุณภาพอากาศ ม.บูรพา บางแสน 🌊').classes('text-4xl font-extrabold text-blue-900 text-center')
    ui.label('ระบบตรวจวัดฝุ่น Real-time พร้อมเทคโนโลยีชดเชยความชื้น').classes('text-lg text-blue-700 mt-2 text-center')

# แบนเนอร์แจ้งเตือนสถานะ
status_banner = ui.label().classes('w-full text-center py-2 font-bold text-white rounded-lg shadow-md hidden max-w-4xl mx-auto mb-4')

# สร้าง Tabs
with ui.tabs().classes('w-full max-w-4xl mx-auto mt-4 text-blue-900 font-bold') as tabs:
    tab1 = ui.tab('📊 Real-time', icon='sensors')
    tab2 = ui.tab('🌍 พยากรณ์ 7 วัน', icon='timeline')
    tab3 = ui.tab('⚙️ ข้อมูลระบบ', icon='settings')

# เนื้อหาในแต่ละ Tab
with ui.tab_panels(tabs, value=tab1).classes('w-full max-w-4xl mx-auto bg-transparent'):
    
    # --- TAB 1: Real-time ---
    with ui.tab_panel(tab1):
        with ui.row().classes('w-full justify-center gap-6 mt-4'):
            # Card: PM 2.5 (ปรับแก้)
            with ui.card().classes('w-48 items-center rounded-2xl shadow-lg border-b-4 border-blue-500 bg-white/90 backdrop-blur-sm'):
                ui.label('PM 2.5 (แม่นยำสูง)').classes('text-sm text-gray-500 font-bold')
                lbl_pm25_cal = ui.label('--').classes('text-4xl font-bold text-blue-600 my-2')
                ui.label('µg/m³').classes('text-xs text-gray-400')
            
            # Card: PM 2.5 (ดิบ)
            with ui.card().classes('w-48 items-center rounded-2xl shadow-lg border-b-4 border-gray-400 bg-white/90 backdrop-blur-sm'):
                ui.label('PM 2.5 (ค่าดิบ)').classes('text-sm text-gray-500 font-bold')
                lbl_pm25_raw = ui.label('--').classes('text-4xl font-bold text-gray-600 my-2')
                ui.label('µg/m³').classes('text-xs text-gray-400')
            
            # Card: Temp
            with ui.card().classes('w-48 items-center rounded-2xl shadow-lg border-b-4 border-orange-400 bg-white/90 backdrop-blur-sm'):
                ui.label('อุณหภูมิ').classes('text-sm text-gray-500 font-bold')
                lbl_temp = ui.label('--').classes('text-4xl font-bold text-orange-500 my-2')
                ui.label('°C').classes('text-xs text-gray-400')
            
            # Card: Hum
            with ui.card().classes('w-48 items-center rounded-2xl shadow-lg border-b-4 border-cyan-400 bg-white/90 backdrop-blur-sm'):
                ui.label('ความชื้นสัมพัทธ์').classes('text-sm text-gray-500 font-bold')
                lbl_hum = ui.label('--').classes('text-4xl font-bold text-cyan-500 my-2')
                ui.label('%').classes('text-xs text-gray-400')
        
        lbl_time = ui.label('อัปเดตล่าสุด: กำลังโหลด...').classes('w-full text-center text-sm text-gray-500 mt-6')

    # --- TAB 2: Forecast ---
    with ui.tab_panel(tab2):
        ui.label('คาดการณ์พื้นที่ ม.บูรพา (อ้างอิง Open-Meteo)').classes('text-xl font-bold text-blue-900 mb-4')
        
        with ui.row().classes('w-full gap-4 items-stretch'):
            # กราฟ
            with ui.card().classes('flex-grow rounded-2xl shadow-lg p-4 bg-white/90'):
                chart = ui.echart({
                    'tooltip': {'trigger': 'axis'},
                    'xAxis': {'type': 'category', 'data': []},
                    'yAxis': {'type': 'value'},
                    'series': [{'data': [], 'type': 'line', 'smooth': True, 'areaStyle': {'opacity': 0.3}, 'itemStyle': {'color': '#0288d1'}}],
                }).classes('w-full h-80')
            
            # ตาราง
            with ui.card().classes('w-full sm:w-1/3 rounded-2xl shadow-lg p-4 bg-white/90'):
                table = ui.table(
                    columns=[
                        {'name': 'date', 'label': 'วันที่', 'field': 'date', 'align': 'left'},
                        {'name': 'pm2_5', 'label': 'PM 2.5', 'field': 'pm2_5', 'align': 'right'}
                    ],
                    rows=[], row_key='date'
                ).classes('w-full shadow-none')

    # --- TAB 3: System Info ---
    with ui.tab_panel(tab3):
        with ui.card().classes('w-full rounded-2xl shadow-lg p-6 bg-white/90'):
            ui.markdown(f'''
            ### สถาปัตยกรรมระบบ
            * **Hardware:** ESP32 + PMS5003 + BME280
            * **Cloud:** ThingSpeak (Channel {CHANNEL_ID})
            * **Algorithm:** Trimmed Mean (ESP32) + Shift to Cloud (Python)
            
            **สมการ Calibration:**
            `y = {SLOPE_M}x + {INTERCEPT_C}`
            *(ระบบจะเริ่มหักลบค่าความบวมน้ำเมื่อความชื้นสัมพัทธ์เกิน {HUMIDITY_THRESHOLD}%)*
            ''').classes('text-gray-700')

# ==========================================
# ฟังก์ชันอัปเดตข้อมูลบน UI 
# ==========================================
def update_ui():
    # อัปเดต Real-time
    rt_data = fetch_realtime_data()
    if rt_data:
        lbl_pm25_cal.set_text(f"{rt_data['pm25_cal']}")
        lbl_pm25_raw.set_text(f"{rt_data['pm25_raw']}")
        lbl_temp.set_text(f"{rt_data['temp']}")
        lbl_hum.set_text(f"{rt_data['hum']}")
        lbl_time.set_text(f"อัปเดตล่าสุด: {rt_data['time']}")
        
        # จัดการแจ้งเตือนสี
        pm = rt_data['pm25_cal']
        status_banner.classes(remove='hidden bg-green-500 bg-yellow-500 bg-orange-500 bg-red-600')
        if pm <= 15.0:
            status_banner.set_text('🟢 คุณภาพอากาศดีมาก: สามารถทำกิจกรรมกลางแจ้งได้ตามปกติ')
            status_banner.classes(add='bg-green-500')
        elif pm <= 37.5:
            status_banner.set_text('🟡 คุณภาพอากาศปานกลาง: ประชาชนทั่วไปทำกิจกรรมได้ กลุ่มเสี่ยงควรระวัง')
            status_banner.classes(add='bg-yellow-500')
        elif pm <= 75.0:
            status_banner.set_text('🟠 เริ่มมีผลกระทบต่อสุขภาพ: ควรลดระยะเวลาการทำกิจกรรมกลางแจ้ง')
            status_banner.classes(add='bg-orange-500')
        else:
            status_banner.set_text('🔴 มีผลกระทบต่อสุขภาพ: งดกิจกรรมกลางแจ้ง และสวมหน้ากาก N95 ทันที!')
            status_banner.classes(add='bg-red-600')

    # อัปเดต Forecast
    fc_data = fetch_forecast_data()
    if fc_data is not None:
        dates = fc_data['date'].astype(str).tolist()
        values = fc_data['pm2_5'].tolist()
        
        chart.options['xAxis']['data'] = dates
        chart.options['series'][0]['data'] = values
        chart.update()
        
        rows = [{'date': d, 'pm2_5': v} for d, v in zip(dates, values)]
        table.rows = rows
        table.update()

# เรียกทำงานครั้งแรก
update_ui()
# ตั้งเวลาให้อัปเดตอัตโนมัติทุกๆ 5 นาที (300 วินาที)
ui.timer(300.0, update_ui)

# สั่งรัน Web Server รองรับการทำงานบน Render
ui.run(
    title="PM 2.5 BUU", 
    host='0.0.0.0', 
    port=int(os.environ.get('PORT', 8080)), 
    favicon="🌊"
)
