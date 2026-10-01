import asyncio
import datetime
import os
import pandas as pd
import httpx

# Import các hằng số đường dẫn & Token chuẩn từ config.py
from src.config import WATCHLIST_PATH, WAL_FILE, PARQUET_DIR, FIREANT_TOKEN
# Import các hàm và bộ nhớ RAM từ wal_manager.py
from src.wal_manager import ram_buffer, write_wal, flush_ram_to_parquet


def load_watchlist(file_path=WATCHLIST_PATH) -> list:
    """Đọc danh sách mã cổ phiếu từ đường dẫn hằng số WATCHLIST_PATH."""
    if not os.path.exists(file_path):
        print(f"❌ File {file_path} không tồn tại!")
        return []
    
    try:
        df = pd.read_csv(file_path)
        for col in ['symbol', 'Symbol', 'ticker', 'Ticker']:
            if col in df.columns:
                symbols = df[col].dropna().astype(str).str.strip().tolist()
                return [s.upper() for s in symbols if s]
        
        symbols = df.iloc[:, 0].dropna().astype(str).str.strip().tolist()
        return [s.upper() for s in symbols if s]
    except Exception as e:
        print(f"❌ Lỗi khi đọc {file_path}: {e}")
        return []


def is_trading_hours() -> bool:
    """
    Kiểm tra thời gian hiện tại có nằm trong phiên giao dịch hay không (09:00 - 15:00, T2-T6).
    """
    now = datetime.datetime.now()
    if now.weekday() >= 5:
        return False
        
    start_time = datetime.time(9, 0, 0)
    end_time = datetime.time(15, 0, 0)
    
    return start_time <= now.time() <= end_time


def update_ram_buffer(symbol: str, data: list):
    """Ghi đệm dữ liệu trực tiếp vào ram_buffer và sử dụng hàm write_wal từ wal_manager."""
    if not data:
        return
    
    if symbol not in ram_buffer:
        ram_buffer[symbol] = {}
    
    for item in data:
        candle_date = item.get('date')
        if candle_date:
            ram_buffer[symbol][candle_date] = item
            try:
                write_wal(symbol, item)
            except Exception as e:
                print(f"❌ Lỗi ghi WAL ({WAL_FILE}): {e}")


async def fetch_symbol_data(client: httpx.AsyncClient, symbol: str, headers: dict):
    """Gửi Request lấy dữ liệu nến 1m mới nhất của 1 mã cổ phiếu."""
    url = f"https://restv2.fireant.vn/symbols/{symbol}/historical-quotes"
    today_str = datetime.date.today().strftime("%Y-%m-%d")
    
    params = {
        "startDate": today_str,
        "endDate": today_str,
        "unit": "1m",
        "offset": 0,
        "limit": 5
    }
    try:
        res = await client.get(url, params=params, headers=headers, timeout=5.0)
        if res.status_code == 200:
            data = res.json()
            if isinstance(data, list) and len(data) > 0:
                update_ram_buffer(symbol, data)
                print(f"✅ {symbol}: Đã ghi {len(data)} bản ghi vào RAM/WAL")
        elif res.status_code == 401:
            print("❌ Lỗi 401: Token FireAnt đã hết hạn!")
    except Exception as e:
        print(f"⚠️ Lỗi {symbol}: {e}")


async def polling_loop(headers: dict):
    """
    Vòng lặp thu thập dữ liệu bất đồng bộ liên tục.
    Tự động reload lại watchlist/Kakata.csv mỗi chu kỳ để cập nhật danh sách mã mới nhất.
    """
    print(f"🚀 Bắt đầu luồng thu thập dữ liệu bất đồng bộ...")
    async with httpx.AsyncClient(limits=httpx.Limits(max_connections=50)) as client:
        count = 0
        while True:
            # Kiểm tra khung giờ giao dịch
            if not is_trading_hours():
                now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                print(f"⏰ [{now_str}] Outside market hours (09:00 - 15:00, T2-T6). Tạm dừng polling, chờ 30s...")
                
                if ram_buffer:
                    flush_ram_to_parquet()
                    
                await asyncio.sleep(30)
                continue

            # ĐỌC LẠI WATCHLIST ĐỂ TỰ ĐỘNG ĐỒNG BỘ NẾU CÓ THAY ĐỔI FILE CSV
            symbols = load_watchlist(WATCHLIST_PATH)
            if not symbols:
                print("⚠️ Watchlist trống hoặc không đọc được file. Đang chờ 10s...")
                await asyncio.sleep(10)
                continue

            start_time = datetime.datetime.now()
            tasks = [fetch_symbol_data(client, symbol, headers) for symbol in symbols]
            await asyncio.gather(*tasks)
            
            elapsed = (datetime.datetime.now() - start_time).total_seconds()
            print(f"⚡ Hoàn tất chu kỳ Polling cho {len(symbols)} mã (Thời gian: {elapsed:.2f}s)")
            
            count += 1
            # Flush dữ liệu ra Parquet theo chu kỳ mỗi 10 chu kỳ (~ 50s)
            if count % 10 == 0:
                flush_ram_to_parquet()

            await asyncio.sleep(5)


async def main():
    symbols = load_watchlist(WATCHLIST_PATH)
    if not symbols:
        print(f"🛑 Không tìm thấy danh sách mã tại {WATCHLIST_PATH}. Hệ thống dừng!")
        return
        
    print(f"✅ Đã kết nối Watchlist ({WATCHLIST_PATH}): Khởi tạo ban đầu với {len(symbols)} mã.")
    
    token = FIREANT_TOKEN if FIREANT_TOKEN.startswith("Bearer ") else f"Bearer {FIREANT_TOKEN}"
    headers = {"Authorization": token}
    
    # Bắt đầu vòng lặp polling
    await polling_loop(headers)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n🛑 Đang dừng hệ thống an toàn...")
        flush_ram_to_parquet()