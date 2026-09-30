import json
import pandas as pd
import datetime
from src.config import WAL_FILE, PARQUET_DIR, FULL_COLUMNS

# Bộ nhớ tạm trên RAM
ram_buffer = {}

def write_wal(symbol: str, candle_data: dict):
    """Ghi nhanh một bản ghi nến vào file WAL (Append mode)."""
    log_entry = {
        "symbol": symbol,
        "candle": candle_data,
        "ts": datetime.datetime.now().isoformat()
    }
    with open(WAL_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(log_entry) + "\n")

def recover_from_wal():
    """Khôi phục dữ liệu RAM từ file WAL nếu ứng dụng vừa bị Crash."""
    if not WAL_FILE.exists():
        return
    
    print("🔄 Đang khôi phục dữ liệu RAM từ file WAL...")
    recovered_count = 0
    try:
        with open(WAL_FILE, "r", encoding="utf-8") as f:
            for line in f:
                if not line.strip():
                    continue
                entry = json.loads(line)
                sym = entry["symbol"]
                candle = entry["candle"]
                
                if sym not in ram_buffer:
                    ram_buffer[sym] = {}
                ram_buffer[sym][candle["date"]] = candle
                recovered_count += 1
        print(f"✅ Đã khôi phục thành công {recovered_count} bản ghi vào RAM!")
    except Exception as e:
        print(f"⚠️ Lỗi trong quá trình đọc file WAL: {e}")

def flush_ram_to_parquet():
    """
    Ghi chốt dữ liệu từ RAM xuống file Parquet 27 cột.
    Tự động kiểm tra và tạo mới thư mục cho Symbol nếu chưa có.
    """
    if not ram_buffer:
        return
        
    today_str = datetime.date.today().strftime("%Y-%m-%d")
    print(f"💾 [{datetime.datetime.now().strftime('%H:%M:%S')}] Đang Flush dữ liệu RAM xuống Parquet...")

    for symbol, candles in ram_buffer.items():
        if not candles:
            continue
        
        # ------------------------------------------------------------------
        # KIỂM TRA VÀ TẠO THƯ MỤC CỦA SYMBOL LƯU DỮ LIỆU
        # Ví dụ: data/price_1m/HPG
        # ------------------------------------------------------------------
        symbol_dir = PARQUET_DIR / symbol
        
        # Checking: Nếu thư mục chưa tồn tại -> mkdir sẽ tự động tạo mới
        # exist_ok=True: Nếu đã tồn tại thì bỏ qua không báo lỗi
        # parents=True: Tạo đầy đủ các thư mục cha nếu chưa có
        symbol_dir.mkdir(parents=True, exist_ok=True)
        # ------------------------------------------------------------------

        df = pd.DataFrame(list(candles.values()))
        
        # Ép khung 27 cột chuẩn FULL_COLUMNS
        df = df.reindex(columns=FULL_COLUMNS)
        df['date'] = pd.to_datetime(df['date'])
        
        numeric_cols = [col for col in FULL_COLUMNS if col not in ['date', 'symbol']]
        df[numeric_cols] = df[numeric_cols].apply(pd.to_numeric, errors='coerce').fillna(0)

        # Đường dẫn file parquet ngày hôm nay
        file_path = symbol_dir / f"{today_str}.parquet"

        # Đọc dữ liệu cũ nếu file Parquet ngày hôm nay đã tồn tại (Upsert)
        if file_path.exists():
            df_old = pd.read_parquet(file_path)
            df = pd.concat([df_old, df], ignore_index=True).drop_duplicates(subset=['date'], keep='last')

        df.sort_values(by='date').to_parquet(file_path, index=False, engine='pyarrow')

    # Làm sạch file WAL sau khi đã ghi xuống đĩa an toàn
    with open(WAL_FILE, "w", encoding="utf-8") as f:
        f.truncate(0)
        
    print("🧹 Đã hoàn tất Flush & làm sạch file WAL.")