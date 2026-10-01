import os
import glob
import streamlit as st
import pandas as pd
import numpy as np
from streamlit_lightweight_charts import renderLightweightCharts

# Config trang Streamlit
st.set_page_config(
    page_title="TradingView Stock Chart",
    page_icon="📈",
    layout="wide"
)

# --- 1. DỰ ĐOÁN VÀ LẤY DANH SÁCH MÃ TỪ THƯ MỤC PARQUET ---
DATA_DIR = os.path.join("data", "price_parquet")

@st.cache_data
def get_available_symbols():
    if not os.path.exists(DATA_DIR):
        return []
    # Tìm tất cả file .parquet trong thư mục
    files = glob.glob(os.path.join(DATA_DIR, "*.parquet"))
    symbols = [os.path.basename(f).replace(".parquet", "").upper() for f in files]
    return sorted(symbols)

AVAILABLE_SYMBOLS = get_available_symbols()

# --- 2. HÀM TÍNH RSI CHUẨN TRADINGVIEW ---
def calculate_rsi(series: pd.Series, period: int = 14) -> pd.Series:
    delta = series.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(alpha=1/period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1/period, adjust=False).mean()
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))

# --- 3. HÀM ĐỌC DỮ LIỆU TỪ FILE PARQUET ---
@st.cache_data
def load_parquet_data(symbol: str, len1: int, len2: int, rsi_period: int) -> pd.DataFrame:
    file_path = os.path.join(DATA_DIR, f"{symbol}.parquet")
    if not os.path.exists(file_path):
        # Thử tìm file chữ thường nếu file in hoa không thấy
        file_path = os.path.join(DATA_DIR, f"{symbol.lower()}.parquet")
        if not os.path.exists(file_path):
            return pd.DataFrame()
            
    try:
        df = pd.read_parquet(file_path)
        
        # Chuẩn hóa tên cột thành chữ thường
        df.columns = [str(col).lower() for col in df.columns]
        
        # Đảm bảo cột ngày đúng định dạng
        date_col = next((c for c in ['date', 'time', 'tradingdate'] if c in df.columns), None)
        if not date_col:
            return pd.DataFrame()
            
        df = df.rename(columns={date_col: 'date'})
        df['date'] = pd.to_datetime(df['date'])
        df = df.sort_values('date').reset_index(drop=True)
        
        # Đảm bảo kiểu dữ liệu số
        for col in ['open', 'high', 'low', 'close', 'volume']:
            if col in df.columns:
                df[col] = df[col].astype(float)
                
        # Quy đổi giá về đơn vị VNĐ nếu dữ liệu gốc theo nghìn VNĐ
        if df['close'].max() < 1000:
            for col in ['open', 'high', 'low', 'close']:
                df[col] = df[col] * 1000

        # Tính toán MA và RSI
        df[f'MA_{len1}'] = df['close'].rolling(window=len1).mean()
        df[f'MA_{len2}'] = df['close'].rolling(window=len2).mean()
        df[f'RSI_{rsi_period}'] = calculate_rsi(df['close'], period=rsi_period)
        
        return df
    except Exception as e:
        st.error(f"Lỗi khi đọc file Parquet: {e}")
        return pd.DataFrame()

# --- 4. THANH CÔNG CỤ (TOOLBAR) ---
st.markdown("### 📈 TradingView Chart (Local Parquet Data)")

tb_col1, tb_col2, tb_col3, tb_col4, tb_col5 = st.columns([1.2, 1.2, 1.2, 0.8, 0.8])

with tb_col1:
    if AVAILABLE_SYMBOLS:
        symbol = st.selectbox("📌 Chọn mã CP", AVAILABLE_SYMBOLS, index=0, label_visibility="collapsed")
    else:
        symbol = st.text_input("📌 Nhập mã CP", value="TCB", label_visibility="collapsed").upper()

with tb_col2:
    time_frame_map = {
        "Toàn bộ": 0,
        "3 Tháng gần nhất": 90,
        "6 Tháng gần nhất": 180,
        "1 Năm gần nhất": 365,
        "3 Năm gần nhất": 1095
    }
    selected_tf = st.selectbox("⏱️ Khung thời gian", list(time_frame_map.keys()), index=0, label_visibility="collapsed")
    days_filter = time_frame_map[selected_tf]

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
    # Nút bật/tắt chế độ Tối/Sáng thủ công
    is_dark = st.toggle("🌙 Chế độ tối", value=True)

with tb_col5:
    if st.button("🔄 Làm mới", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

# --- 5. TẢI VÀ LỌC DỮ LIỆU ---
df_price = load_parquet_data(symbol, ma1_len, ma2_len, rsi_len)

if df_price.empty:
    st.error(f"❌ Không tìm thấy file dữ liệu Parquet cho mã **{symbol}** tại thư mục `data/price_parquet/`!")
    st.stop()

# Lọc theo khung thời gian
if days_filter > 0:
    cutoff_date = df_price['date'].max() - pd.Timedelta(days=days_filter)
    df_chart = df_price[df_price['date'] >= cutoff_date].copy()
else:
    df_chart = df_price.copy()

# Đổi định dạng timestamp cho Lightweight Charts
df_chart['time'] = df_chart['date'].astype('int64') // 10**9

# --- 6. HIỂN THỊ METRICS THÔNG TIN GIAO DỊCH ---
last_row = df_chart.iloc[-1]
prev_row = df_chart.iloc[-2] if len(df_chart) > 1 else last_row
change = last_row['close'] - prev_row['close']
pct_change = (change / prev_row['close']) * 100 if prev_row['close'] > 0 else 0

m_col1, m_col2, m_col3, m_col4 = st.columns(4)
m_col1.metric("Mã Cổ Phiếu", symbol)
m_col2.metric("Giá Hiện Tại", f"{last_row['close']:,.0f} VNĐ", f"{change:+,.0f} VNĐ ({pct_change:+.2f}%)")
m_col3.metric("Cao Nhất (High)", f"{last_row['high']:,.0f} VNĐ")
m_col4.metric("Thấp Nhất (Low)", f"{last_row['low']:,.0f} VNĐ")

# --- 7. CHUẨN BỊ DỮ LIỆU VẼ BIỂU ĐỒ ---
candlestick_data = []
volume_data = []
ma1_data = []
ma2_data = []
rsi_data = []

for _, row in df_chart.iterrows():
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

# Thiết lập màu nền dựa theo nút Toggle
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
        "options": {
            "upColor": "#26a69a", 
            "downColor": "#ef5350", 
            "borderVisible": False, 
            "wickUpColor": "#26a69a", 
            "wickDownColor": "#ef5350"
        }
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
    rsi_series = [{"type": "Line", "data": rsi_data, "options": {"color": "#9C27B0", "lineWidth": 2, "title": f"RSI ({rsi_len})"}}]
    charts_to_render.append({"chart": rsi_chart_options, "series": rsi_series})

# Render Chart
renderLightweightCharts(charts_to_render, key=f"tv_chart_{symbol}_{selected_tf}_{ma1_len}_{ma2_len}_{rsi_len}_{show_rsi}_{show_ma1}_{show_ma2}_{is_dark}")

# --- 8. BẢNG DỮ LIỆU CHI TIẾT ---
with st.expander("📄 Dữ liệu chi tiết Parquet"):
    st.dataframe(df_chart.sort_values('date', ascending=False), use_container_width=True)