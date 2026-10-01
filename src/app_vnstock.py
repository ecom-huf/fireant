import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from vnstock3 import Vnstock  # Import thư viện lấy dữ liệu chứng khoán API
from streamlit_lightweight_charts import renderLightweightCharts
from streamlit_theme import st_theme

# Config trang Streamlit
st.set_page_config(
    page_title="TradingView Stock Chart",
    page_icon="📈",
    layout="wide"
)

# Phát hiện Theme Streamlit
theme = st_theme()
is_dark = True
if theme is not None:
    is_dark = (theme.get("base", "dark") == "dark")

# --- 1. DANH SÁCH MÃ CHỨNG KHOÁN (Mẫu) ---
POPULAR_SYMBOLS = ["TCB", "VCB", "SSI", "HPG", "VHM", "FPT", "MWG", "VIC", "VNM"]

# --- 2. HÀM TÍNH RSI CHUẨN TRADINGVIEW ---
def calculate_rsi(series: pd.Series, period: int = 14) -> pd.Series:
    delta = series.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(alpha=1/period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1/period, adjust=False).mean()
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))

# --- 3. HÀM LẤY DỮ LIỆU TỪ API TỰ ĐỘNG (CÓ CACHE) ---
# Dùng ttl=300 (5 phút) để tự động làm mới dữ liệu sau 5 phút, tránh gọi API quá nhiều
@st.cache_data(ttl=300, show_spinner="Đang tải dữ liệu từ API...")
def fetch_stock_data_api(symbol: str, days: int, len1: int, len2: int, rsi_period: int) -> pd.DataFrame:
    try:
        # Khởi tạo Vnstock
        stock = Vnstock().stock(symbol=symbol, source='VCI')
        
        # Tính ngày bắt đầu và kết thúc
        end_date = datetime.now().strftime('%Y-%m-%d')
        start_date = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')
        
        # Gọi API lấy lịch sử giá
        df = stock.quote.history(start=start_date, end=end_date, interval='1D')
        
        if df is None or df.empty:
            return pd.DataFrame()
            
        # Chuẩn hóa tên cột trả về từ API sang dạng chuẩn
        # vnstock trả về: time/time, open, high, low, close, volume
        df = df.rename(columns={'time': 'date'})
        df['date'] = pd.to_datetime(df['date'])
        df = df.sort_values('date').reset_index(drop=True)
        
        # Đảm bảo các cột giá là kiểu float
        for col in ['open', 'high', 'low', 'close', 'volume']:
            if col in df.columns:
                df[col] = df[col].astype(float)
                
        # Quy đổi giá về đơn vị VNĐ nếu API trả về theo nghìn VNĐ (Ví dụ: 35.5 -> 35500)
        if df['close'].max() < 1000:
            for col in ['open', 'high', 'low', 'close']:
                df[col] = df[col] * 1000

        # Tính toán đường MA và RSI
        df[f'MA_{len1}'] = df['close'].rolling(window=len1).mean()
        df[f'MA_{len2}'] = df['close'].rolling(window=len2).mean()
        df[f'RSI_{rsi_period}'] = calculate_rsi(df['close'], period=rsi_period)
        
        return df
    except Exception as e:
        st.error(f"Lỗi khi gọi API: {e}")
        return pd.DataFrame()

# --- 4. THANH CÔNG CỤ (TOOLBAR) ---
st.markdown("### 📈 TradingView Chart (Realtime API)")

tb_col1, tb_col2, tb_col3, tb_col4 = st.columns([1.0, 1.5, 1.5, 0.8])

with tb_col1:
    # Người dùng có thể chọn hoặc tự nhập mã CP bất kỳ
    symbol = st.selectbox("📌 Mã CP", POPULAR_SYMBOLS, index=0, label_visibility="collapsed").upper()

with tb_col2:
    time_frame_map = {
        "3 Tháng gần nhất": 90,
        "6 Tháng gần nhất": 180,
        "1 Năm gần nhất": 365,
        "3 Năm gần nhất": 1095
    }
    selected_tf = st.selectbox("⏱️ Khung thời gian", list(time_frame_map.keys()), index=2, label_visibility="collapsed")
    days_to_fetch = time_frame_map[selected_tf]

with tb_col3:
    with st.popover("📊 Chỉ báo & Thông số", use_container_width=True):
        st.markdown("**Cấu hình đường MA**")
        show_ma1 = st.checkbox("Hiển thị MA 1", value=True)
        ma1_len = st.number_input("Số phiên MA 1", min_value=1, max_value=200, value=20, step=1)
        
        show_ma2 = st.checkbox("Hiển thị MA 2", value=True)
        ma2_len = st.number_input("Số phiên MA 2", min_value=1, max_value=200, value=50, step=1)
        
        st.divider()
        st.markdown("**Cấu hình RSI**")
        show_rsi = st.checkbox("Hiển thị RSI", value=True)
        rsi_len = st.number_input("Chu kỳ RSI", min_value=2, max_value=100, value=14, step=1)

with tb_col4:
    # Nút bấm làm mới dữ liệu thủ công
    if st.button("🔄 LÀM MỚI", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

# Tải dữ liệu qua API
df_price = fetch_stock_data_api(symbol, days_to_fetch, ma1_len, ma2_len, rsi_len)

if df_price.empty:
    st.error(f"❌ Không thể tải dữ liệu cho mã **{symbol}**. Vui lòng kiểm tra lại mã cổ phiếu!")
    st.stop()

# Đổi định dạng timestamp cho Lightweight Charts
df_price['time'] = df_price['date'].astype('int64') // 10**9

# --- 5. HIỂN THỊ METRICS ---
last_row = df_price.iloc[-1]
prev_row = df_price.iloc[-2] if len(df_price) > 1 else last_row
change = last_row['close'] - prev_row['close']
pct_change = (change / prev_row['close']) * 100

m_col1, m_col2, m_col3, m_col4 = st.columns(4)
m_col1.metric("Mã Cổ Phiếu", symbol)
m_col2.metric("Giá Hiện Tại", f"{last_row['close']:,.0f} VNĐ", f"{change:+,.0f} VNĐ ({pct_change:+.2f}%)")
m_col3.metric("Cao Nhất (High)", f"{last_row['high']:,.0f} VNĐ")
m_col4.metric("Thấp Nhất (Low)", f"{last_row['low']:,.0f} VNĐ")

# --- 6. PHẦN VẼ BIỂU ĐỒ (Giữ nguyên cấu hình lightweight-charts) ---
candlestick_data = []
volume_data = []
ma1_data = []
ma2_data = []
rsi_data = []

for _, row in df_price.iterrows():
    t = int(row['time'])
    candlestick_data.append({
        "time": t, "open": float(row['open']), "high": float(row['high']),
        "low": float(row['low']), "close": float(row['close'])
    })
    color = "#26a69a" if row['close'] >= row['open'] else "#ef5350"
    volume_data.append({"time": t, "value": float(row['volume']), "color": color})

    if pd.notna(row[f'MA_{ma1_len}']):
        ma1_data.append({"time": t, "value": float(row[f'MA_{ma1_len}'])})
    if pd.notna(row[f'MA_{ma2_len}']):
        ma2_data.append({"time": t, "value": float(row[f'MA_{ma2_len}'])})
    if pd.notna(row[f'RSI_{rsi_len}']):
        rsi_data.append({"time": t, "value": float(row[f'RSI_{rsi_len}'])})

bg_color = "#131722" if is_dark else "#ffffff"
text_color = "#d1d4dc" if is_dark else "#000000"
grid_color = "rgba(42, 46, 57, 0.5)" if is_dark else "rgba(196, 196, 196, 0.2)"

main_chart_options = {
    "height": 450 if show_rsi else 600,
    "layout": {"textColor": text_color, "background": {"type": "solid", "color": bg_color}},
    "grid": {"vertLines": {"color": grid_color}, "horzLines": {"color": grid_color}},
    "timeScale": {"timeVisible": True, "secondsVisible": False}
}

main_series = [
    {
        "type": "Candlestick",
        "data": candlestick_data,
        "options": {"upColor": "#26a69a", "downColor": "#ef5350", "borderVisible": False, "wickUpColor": "#26a69a", "wickDownColor": "#ef5350"}
    },
    {
        "type": "Histogram",
        "data": volume_data,
        "options": {"priceFormat": {"type": "volume"}, "priceScaleId": ""},
        "priceScale": {"scaleMargins": {"top": 0.8, "bottom": 0}}
    }
]

if show_ma1:
    main_series.append({"type": "Line", "data": ma1_data, "options": {"color": "#2962FF", "lineWidth": 2, "title": f"MA {ma1_len}"}})
if show_ma2:
    main_series.append({"type": "Line", "data": ma2_data, "options": {"color": "#FF6D00", "lineWidth": 2, "title": f"MA {ma2_len}"}})

charts_to_render = [{"chart": main_chart_options, "series": main_series}]

if show_rsi:
    rsi_chart_options = {
        "height": 180,
        "layout": {"textColor": text_color, "background": {"type": "solid", "color": bg_color}},
        "grid": {"vertLines": {"color": grid_color}, "horzLines": {"color": grid_color}},
        "timeScale": {"timeVisible": True, "secondsVisible": False}
    }
    rsi_series = [{"type": "Line", "data": rsi_data, "options": {"color": "#9C27B0", "lineWidth": 2, "title": f"RSI ({rsi_len})}}]
    charts_to_render.append({"chart": rsi_chart_options, "series": rsi_series})

# Render Chart
renderLightweightCharts(charts_to_render, key=f"tv_api_{symbol}_{selected_tf}_{ma1_len}_{ma2_len}_{rsi_len}_{show_rsi}_{is_dark}")

with st.expander("📄 Dữ liệu chi tiết từ API"):
    st.dataframe(df_price.sort_values('date', ascending=False), use_container_width=True)