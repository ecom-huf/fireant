import httpx
import asyncio
import datetime
from src.config import FIREANT_TOKEN
from src.wal_manager import ram_buffer, write_wal

async def backfill_missing_data(symbols: list[str], start_time: datetime.datetime, end_time: datetime.datetime):
    """Gọi REST API cào bù dữ liệu 1m trong khoảng thời gian đứt mạng."""
    print(f"🩹 [SELF-HEALING] Đang cào bù dữ liệu từ {start_time.strftime('%H:%M:%S')} đến {end_time.strftime('%H:%M:%S')}...")
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
        "Authorization": f"Bearer {FIREANT_TOKEN}" if not FIREANT_TOKEN.startswith("Bearer ") else FIREANT_TOKEN
    }

    async with httpx.AsyncClient() as client:
        for symbol in symbols:
            url = f"https://restv2.fireant.vn/symbols/{symbol}/historical-quotes"
            params = {
                "startDate": start_time.strftime("%Y-%m-%d"),
                "endDate": end_time.strftime("%Y-%m-%d"),
                "unit": "1m",
                "offset": 0,
                "limit": 500
            }
            try:
                res = await client.get(url, params=params, headers=headers, timeout=5.0)
                if res.status_code == 200:
                    data = res.json()
                    for item in data:
                        item_time = datetime.datetime.fromisoformat(item["date"].replace("Z", ""))
                        if start_time <= item_time <= end_time:
                            if symbol not in ram_buffer:
                                ram_buffer[symbol] = {}
                            ram_buffer[symbol][item["date"]] = item
                            write_wal(symbol, item)
            except Exception as e:
                print(f"❌ Lỗi cào bù cho {symbol}: {e}")
            
            await asyncio.sleep(0.02) # Throttle nhẹ

    print("✅ Đã hoàn tất cào bù dữ liệu thiếu!")