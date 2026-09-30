import os
import asyncio
import pandas as pd
import socketio
from pathlib import Path

# 1. Đọc Watchlist từ file CSV
CSV_FILE = Path("watchlist/Kakata.csv")

def load_watchlist(filepath: Path) -> list:
    if not filepath.exists():
        print(f"⚠️ File {filepath} không tồn tại! Dùng watchlist dự phòng.")
        return ["HPG", "SSI", "FTS", "VNM", "TCB", "VHM"]
    
    df = pd.read_csv(filepath)
    # Tự động tìm cột chứa mã (hỗ trợ nhiều tên cột phổ biến)
    col_name = None
    for candidate in ['symbol', 'ticker', 'code', 'Mã', 'ma']:
        if candidate in df.columns:
            col_name = candidate
            break
            
    if col_name:
        symbols = df[col_name].dropna().astype(str).str.strip().str.upper().tolist()
    else:
        # Nếu không có header trùng khớp, lấy mặc định cột đầu tiên (index 0)
        symbols = df.iloc[:, 0].dropna().astype(str).str.strip().str.upper().tolist()
        
    return list(set(symbols)) # Lấy danh sách mã duy nhất (remove duplicate)

# Load danh sách 300 mã từ CSV
watchlist = load_watchlist(CSV_FILE)

# 2. Khởi tạo Socket.IO Client
sio = socketio.AsyncClient()

@sio.event
async def connect():
    print("🟢 Đã kết nối Socket.IO Server!")
    
    # Gửi đăng ký danh sách mã vừa đọc từ CSV
    payload = {
        "symbols": watchlist,
        "channels": ["rawTick", "quote"]
    }
    await sio.emit("subscribe", payload)
    print(f"📡 Đã Subscribe thành công cho {len(watchlist)} mã từ Kakata.csv")