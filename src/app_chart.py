import streamlit as st
import pandas as pd
from pathlib import Path
from streamlit_lightweight_charts import renderLightweightCharts

st.set_page_config(layout="wide", page_title="Stock Chart TradingView")

st.title("📈 Biểu đồ Kỹ thuật Cổ phiếu (TradingView Style)")

PARQUET_DIR = Path("C:/fireant_data/price_parquet")

# 1. Lấy danh sách các mã cổ phiếu hiện có trong thư mục
if PARQUET_DIR.exists():
    available_files = list(PARQUET_DIR.glob("*.parquet"))
    symbols = [f.stem for f in available_files]
else:
    symbols = []

if not symbols:
    st.error("❌ Chưa tìm thấy dữ liệu Parquet trong thư mục C:/fireant_data/price_parquet")
    st.stop()

# 2. Selectbox chọn mã cổ phiếu
selected_symbol = st.sidebar.selectbox("Chọn mã cổ phiếu:", sorted(symbols))

# 3. Đọc dữ liệu từ file Parquet tương ứng
file_path = PARQUET_DIR / f"{selected_symbol}.parquet"
df = pd.read_parquet(file_path)

# Chuẩn hóa dữ liệu sang định dạng Lightweight Charts yêu cầu
df['date'] = pd.to_datetime(df['date'])
df = df.sort_values('date')

# Lightweight Charts cần mốc thời gian dạng timestamp (giây) hoặc chuỗi 'YYYY-MM-DD'
df['time'] = df['date'].astype('int64') // 10**9

# 4. Chuẩn bị dữ liệu nến (Candlestick)
candlestick_data = []
for _, row in df.iterrows():
    candlestick_data.append({
        "time": int(row['time']),
        "open": float(row['priceOpen']),
        "high": float(row['priceHigh']),
        "low": float(row['priceLow']),
        "close": float(row['priceClose']),
    })

# 5. Chuẩn bị dữ liệu Khối lượng (Volume)
volume_data = []
for _, row in df.iterrows():
    color = "#26a69a" if row['priceClose'] >= row['priceOpen'] else "#ef5350"
    volume_data.append({
        "time": int(row['time']),
        "value": float(row['totalVolume']),
        "color": color
    })

# 6. Cấu hình giao diện Biểu đồ TradingView
chart_options = {
    "height": 600,
    "layout": {
        "textColor": "black",
        "background": {"type": "solid", "color": "white"}
    },
    "grid": {
        "vertLines": {"color": "rgba(196, 196, 196, 0.2)"},
        "horzLines": {"color": "rgba(196, 196, 196, 0.2)"}
    },
    "timeScale": {
        "timeVisible": True,
        "secondsVisible": False
    }
}

series = [
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
        "options": {
            "priceFormat": {"type": "volume"},
            "priceScaleId": ""  # Cho khối lượng đè ở đáy chart
        },
        "priceScale": {
            "scaleMargins": {"top": 0.8, "bottom": 0}
        }
    }
]

# 7. Hiển thị Chart
renderLightweightCharts([{"chart": chart_options, "series": series}], key="stock_chart")