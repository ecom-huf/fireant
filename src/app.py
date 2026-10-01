import streamlit as st
import pandas as pd
import numpy as np
from pathlib import Path
from streamlit_lightweight_charts import renderLightweightCharts
from streamlit_theme import st_theme  # Import thư viện lấy theme Streamlit

# Config trang Streamlit
st.set_page_config(
    page_title="TradingView Stock Chart",
    page_icon="📈",
    layout="wide"
)

# --- TỰ ĐỘNG PHÁT HIỆN THEME CỦA STREAMLIT ---
theme = st_theme()

# Mặc định là Dark nếu chưa lấy được theme
is_dark = True
if theme is not None:
    # streamlit-theme trả về dict chứa thông tin base theme ('dark' hoặc 'light')
    base_theme = theme.get("base", "dark")
    is_dark = (base_theme == "dark")

PRICE_DIR = Path("data/price_parquet")

def get_available_symbols():
    if not PRICE_DIR.exists():
        return []
    files = list(PRICE_DIR.glob("*.parquet"))
    symbols = [f.stem.upper() for f in files]
    return sorted(symbols)

symbols = get_available_symbols()

if not symbols:
    st.error(f"❌ Không tìm thấy dữ liệu Parquet trong thư mục `{PRICE_DIR}`")
    st.stop()

# --- 1. THANH CÔNG CỤ (TOOLBAR) TINH GỌN ---
st.markdown("### 📈 TradingView Chart")

# Bỏ cột chuyển màu thủ công, tối ưu lại tỷ lệ cột
tb_col1, tb_col2, tb_col3 = st.columns([1.0, 1.5, 1.5])

with tb_col1:
    symbol = st.selectbox("📌 Mã CP", symbols, label_visibility="collapsed")

with tb_col2:
    time_frame = st.selectbox(
        "⏱️ Khung thời gian",
        options=["1 Năm gần nhất", "6 Tháng gần nhất", "3 Tháng gần nhất", "Tất cả lịch sử"],
        index=0,
        label_visibility="collapsed"
    )

with tb_col3:
    with st.popover("📊 Chỉ báo & Thông số", use_container_width=True):
        st.markdown("**Cấu hình đường MA**")
        show_ma1 = st.checkbox("Hiển thị MA 1", value=True)
        ma1_len = st.number_input("Số phiên MA 1 (ví dụ: 20)", min_value=1, max_value=200, value=20, step=1)
        
        show_ma2 = st.checkbox("Hiển thị MA 2", value=True)
        ma2_len = st.number_input("Số phiên MA 2 (ví dụ: 50)", min_value=1, max_value=200, value=50, step=1)
        
        st.divider()
        st.markdown("**Cấu hình RSI**")
        show_rsi = st.checkbox("Hiển thị RSI", value=True)
        rsi_len = st.number_input("Chu kỳ RSI (ví dụ: 14)", min_value=2, max_value=100, value=14, step=1)


# --- 2. HÀM TÍNH RSI CHUẨN TRADINGVIEW ---
def calculate_rsi(series: pd.Series, period: int = 14) -> pd.Series:
    delta = series.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)

    avg_gain = gain.ewm(alpha=1/period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1/period, adjust=False).mean()

    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    return rsi


# --- 3. HÀM TẢI VÀ CHUẨN HÓA DỮ LIỆU ---
@st.cache_data(ttl=60)
def load_chart_data(sym: str, len1: int, len2: int, rsi_period: int) -> pd.DataFrame:
    file_path = PRICE_DIR / f"{sym}.parquet"
    if not file_path.exists():
        return pd.DataFrame()

    df = pd.read_parquet(file_path)
    if df.empty:
        return df

    column_mapping = {
        'priceOpen': 'open',
        'priceHigh': 'high',
        'priceLow': 'low',
        'priceClose': 'close',
        'totalVolume': 'volume',
        'dealVolume': 'volume'
    }
    for old_col, new_col in column_mapping.items():
        if old_col in df.columns and new_col not in df.columns:
            df[new_col] = df[old_col]

    unit = df['unit'].iloc[0] if 'unit' in df.columns else 1000
    for col in ['open', 'high', 'low', 'close']:
        if col in df.columns:
            df[col] = df[col] * (unit if df[col].max() < 1000 else 1)

    df['date'] = pd.to_datetime(df['date'])
    df = df.sort_values('date').reset_index(drop=True)

    df[f'MA_{len1}'] = df['close'].rolling(window=len1).mean()
    df[f'MA_{len2}'] = df['close'].rolling(window=len2).mean()
    df[f'RSI_{rsi_period}'] = calculate_rsi(df['close'], period=rsi_period)

    return df

df_price = load_chart_data(symbol, ma1_len, ma2_len, rsi_len)

if df_price.empty:
    st.error(f"❌ Không có dữ liệu giá cho mã {symbol}")
    st.stop()

# --- 4. LỌC DỮ LIỆU THEO KHUNG THỜI GIAN ---
latest_date = df_price['date'].max()

if time_frame == "1 Năm gần nhất":
    df_price = df_price[df_price['date'] >= (latest_date - pd.Timedelta(days=365))]
elif time_frame == "6 Tháng gần nhất":
    df_price = df_price[df_price['date'] >= (latest_date - pd.Timedelta(days=180))]
elif time_frame == "3 Tháng gần nhất":
    df_price = df_price[df_price['date'] >= (latest_date - pd.Timedelta(days=90))]

df_price = df_price.reset_index(drop=True)
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

# --- 6. CHUẨN BỊ DỮ LIỆU BẢN VẼ ---
candlestick_data = []
volume_data = []
ma1_data = []
ma2_data = []
rsi_data = []

for _, row in df_price.iterrows():
    t = int(row['time'])
    
    candlestick_data.append({
        "time": t,
        "open": float(row['open']),
        "high": float(row['high']),
        "low": float(row['low']),
        "close": float(row['close']),
    })
    
    color = "#26a69a" if row['close'] >= row['open'] else "#ef5350"
    if 'volume' in row:
        volume_data.append({"time": t, "value": float(row['volume']), "color": color})

    if pd.notna(row[f'MA_{ma1_len}']):
        ma1_data.append({"time": t, "value": float(row[f'MA_{ma1_len}'])})

    if pd.notna(row[f'MA_{ma2_len}']):
        ma2_data.append({"time": t, "value": float(row[f'MA_{ma2_len}'])})

    if pd.notna(row[f'RSI_{rsi_len}']):
        rsi_data.append({"time": t, "value": float(row[f'RSI_{rsi_len}'])})

# Tự động gán màu biểu đồ theo theme đã tự phát hiện
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
    
    rsi_series = [
        {
            "type": "Line",
            "data": rsi_data,
            "options": {"color": "#9C27B0", "lineWidth": 2, "title": f"RSI ({rsi_len})"}
        }
    ]
    
    charts_to_render.append({"chart": rsi_chart_options, "series": rsi_series})

# --- 7. RENDER BIỂU ĐỒ ---
renderLightweightCharts(charts_to_render, key=f"tv_chart_{symbol}_{time_frame}_{ma1_len}_{ma2_len}_{rsi_len}_{show_rsi}_{show_ma1}_{show_ma2}_{is_dark}")

# --- 8. BẢNG DỮ LIỆU LỊCH SỬ ---
with st.expander("📄 Xem dữ liệu chi tiết dạng bảng"):
    st.dataframe(df_price.sort_values('date', ascending=False), use_container_width=True)