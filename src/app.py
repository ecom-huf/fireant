import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from vnstock import stock_historical_data  # Sử dụng gói vnstock chuẩn
from streamlit_lightweight_charts import renderLightweightCharts

# Config trang Streamlit
st.set_page_config(
    page_title="TradingView Stock Chart",
    page_icon="📈",
    layout="wide"
)

# Danh sách mã chứng khoán phổ biến
POPULAR_SYMBOLS = [
    "TCB", "VCB", "SSI", "HPG", "VHM", "FPT", "MWG", "VIC", "VNM", 
    "MBB", "ACB", "STB", "VPB", "MSN", "GAS", "VRE", "DGC", "PNJ"
]

# --- 1. HÀM TÍNH RSI CHUẨN TRADINGVIEW ---
def calculate_rsi(series: pd.Series, period: int = 14) -> pd.Series:
    delta = series.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(alpha=1/period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1/period, adjust=False).mean()
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))

# --- 2. HÀM LẤY DỮ LIỆU TỪ API VNSTOCK ---
@st.cache_data(ttl=300, show_spinner="Đang tải dữ liệu từ sàn...")
def fetch_stock_data_api(symbol: str, days: int, len1: int, len2: int, rsi_period: int) -> pd.DataFrame:
    try:
        end_date = datetime.now().strftime('%Y-%m-%d')
        start_date = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')
        
        # Gọi API vnstock lấy lịch sử giá
        df = stock_historical_data(
            symbol=symbol, 
            start_date=start_date, 
            end_date=end_date, 
            resolution='1D', 
            source='DNSE'
        )
        
        if df is None or df.empty:
            return pd.DataFrame()
            
        # Đổi tên cột chuẩn hóa
        df = df.rename(columns={
            'TradingDate': 'date', 
            'Open': 'open', 
            'High': 'high', 
            'Low': 'low', 
            'Close': 'close', 
            'Volume': 'volume'
        })
        
        df['date'] = pd.to_datetime(df['date'])
        df = df.sort_values('date').reset_index(drop=True)
        
        # Chuyển đổi kiểu dữ liệu số
        for col in ['open', 'high', 'low', 'close', 'volume']:
            if col in df.columns:
                df[col] = df[col].astype(float)
                
        # Quy đổi giá về đơn vị VNĐ nếu API trả về đơn vị 1,000 VNĐ
        if df['close'].max() < 1000:
            for col in ['open', 'high', 'low', 'close']:
                df[col] = df[col] * 1000

        # Tính toán đường MA và RSI
        df[f'MA_{len1}'] = df['close'].rolling(window=len1).mean()
        df[f'MA_{len2}'] = df['close'].rolling(window=len2).mean()
        df[f'RSI_{rsi_period}'] = calculate_rsi(df['close'], period=rsi_period)
        
        return df
    except Exception as e:
        st.error(f"❌ Lỗi khi kết nối dữ liệu: {e}")
        return pd.DataFrame()

# --- 3. THANH CÔNG CỤ (TOOLBAR) ---
st.markdown("### 📈 TradingView Chart")

tb_col1, tb_col2, tb_col3, tb_col4, tb_col5 = st.columns([1.0, 1.2, 1.2, 0.8, 0.8])

with tb_col1:
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
    # Nút bật/tắt Giao diện Tối/Sáng thủ công cực kỳ ổn định
    is_dark = st.toggle("🌙 Chế độ tối", value=True)

with tb_col5:
    if st.button("🔄 Làm mới", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

# --- 4. TẢI VÀ LỌC DỮ LIỆU ---
df_price = fetch_stock_data_api(symbol, days_to_fetch, ma1_len, ma2_len, rsi_len)

if df_price.empty:
    st.warning(f"⚠️ Không tìm thấy dữ liệu cho mã **{symbol}**. Vui lòng kiểm tra lại mã cổ phiếu.")
    st.stop()

# Đổi định dạng timestamp cho Lightweight Charts
df_price['time'] = df_price['date'].astype('int64') // 10**9

# --- 5. HIỂN THỊ METRICS THÔNG TIN GIAO DỊCH ---
last_row = df_price.iloc[-1]
prev_row = df_price.iloc[-2] if len(df_price) > 1 else last_row
change = last_row['close'] - prev_row['close']
pct_change = (change / prev_row['close']) * 100

m_col1, m_col2, m_col3, m_col4 = st.columns(4)
m_col1.metric("Mã Cổ Phiếu", symbol)
m_col2.metric("Giá Hiện Tại", f"{last_row['close']:,.0f} VNĐ", f"{change:+,.0f} VNĐ ({pct_change:+.2f}%)")
m_col3.metric("Cao Nhất (High)", f"{last_row['high']:,.0f} VNĐ")
m_col4.metric("Thấp Nhất (Low)", f"{last_row['low']:,.0f} VNĐ")

# --- 6. CHUẨN BỊ DỮ LIỆU VẼ BIỂU ĐỒ ---
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

# Thiết lập màu nền dựa vào nút toggle
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

# --- 7. BẢNG DỮ LIỆU CHI TIẾT ---
with st.expander("📄 Dữ liệu chi tiết từ API"):
    st.dataframe(df_price.sort_values('date', ascending=False), use_container_width=True)