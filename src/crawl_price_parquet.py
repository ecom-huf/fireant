import os
import time
import datetime
import argparse
import requests
import pandas as pd
from pathlib import Path
from dotenv import load_dotenv

ROOT_DIR = Path(__file__).resolve().parent.parent
ENV_PATH = ROOT_DIR / ".env"

load_dotenv(dotenv_path=ENV_PATH)
FIREANT_TOKEN = os.getenv("FIREANT_TOKEN", "").strip()

if FIREANT_TOKEN.startswith("Bearer "):
    AUTH_HEADER = FIREANT_TOKEN
else:
    AUTH_HEADER = f"Bearer {FIREANT_TOKEN}"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
    "Authorization": AUTH_HEADER,
    "Origin": "https://fireant.vn",
    "Referer": "https://fireant.vn/"
}

FULL_COLUMNS = [
    "date", "symbol", "priceHigh", "priceLow", "priceOpen", "priceAverage", 
    "priceClose", "priceBasic", "totalVolume", "dealVolume", "putthroughVolume", 
    "totalValue", "putthroughValue", "buyForeignQuantity", "buyForeignValue", 
    "sellForeignQuantity", "sellForeignValue", "buyCount", "buyQuantity", 
    "sellCount", "sellQuantity", "adjRatio", "currentForeignRoom", 
    "propTradingNetDealValue", "propTradingNetPTValue", "propTradingNetValue", "unit"
]

# Các cột số nguyên (Integer)
INT_COLS = [
    "totalVolume", "dealVolume", "putthroughVolume", "buyForeignQuantity", 
    "sellForeignQuantity", "buyCount", "buyQuantity", "sellCount", "sellQuantity"
]

# Các cột số thực (Float)
FLOAT_COLS = [
    "priceHigh", "priceLow", "priceOpen", "priceAverage", "priceClose", "priceBasic",
    "totalValue", "putthroughValue", "buyForeignValue", "sellForeignValue",
    "adjRatio", "currentForeignRoom", "propTradingNetDealValue", 
    "propTradingNetPTValue", "propTradingNetValue", "unit"
]

def fetch_full_historical_price(symbol: str, start_date: str, end_date: str) -> pd.DataFrame:
    url = f"https://restv2.fireant.vn/symbols/{symbol}/historical-quotes"
    all_records = []
    offset = 0
    limit = 500

    while True:
        params = {"startDate": start_date, "endDate": end_date, "offset": offset, "limit": limit}
        try:
            response = requests.get(url, headers=HEADERS, params=params, timeout=15)
            if response.status_code == 200:
                data = response.json()
                if not data:
                    break
                all_records.extend(data)
                if len(data) < limit:
                    break
                offset += limit
                time.sleep(0.5)
            else:
                break
        except Exception as e:
            print(f"❌ Lỗi kết nối khi tải mã {symbol}: {e}")
            break

    if all_records:
        df = pd.DataFrame(all_records)
        for col in FULL_COLUMNS:
            if col not in df.columns:
                df[col] = None
        df = df[FULL_COLUMNS]
        return df

    return pd.DataFrame()

def prepare_and_save_parquet(df: pd.DataFrame, output_filepath: str):
    """
    Chuẩn hóa dữ liệu (Data Types) và lưu thành file Parquet tối ưu.
    """
    df_clean = df.copy()
    
    # 1. Chuyển cột date về kiểu datetime chuẩn
    df_clean['date'] = pd.to_datetime(df_clean['date'])
    
    # 2. Ép kiểu dữ liệu dạng số để tối ưu dung lượng và tốc độ tính toán
    for col in INT_COLS:
        df_clean[col] = pd.to_numeric(df_clean[col], errors='coerce').fillna(0).astype('int64')
        
    for col in FLOAT_COLS:
        df_clean[col] = pd.to_numeric(df_clean[col], errors='coerce').astype('float64')

    # 3. Sắp xếp theo ngày tăng dần
    df_clean = df_clean.sort_values(by='date', ascending=True).reset_index(drop=True)

    # 4. Lưu ra file Parquet (sử dụng nén snappy mặc định)
    df_clean.to_parquet(output_filepath, index=False, engine='pyarrow')

def main():
    parser = argparse.ArgumentParser(description="Crawl dữ liệu giá và lưu dạng Parquet")
    parser.add_argument("--csv", type=str, default="watchlist/kakata.csv", help="Đường dẫn file CSV watchlist")
    parser.add_argument("--start", type=str, default="2000-01-01", help="Ngày bắt đầu (YYYY-MM-DD)")
    parser.add_argument("--output_dir", type=str, default="data/price_parquet", help="Thư mục lưu Parquet")
    
    args = parser.parse_args()

    if not os.path.exists(args.csv):
        print(f"❌ Không tìm thấy file CSV: {args.csv}")
        return

    df_watchlist = pd.read_csv(args.csv)
    symbols = df_watchlist['Symbol'].dropna().astype(str).str.strip().str.upper().tolist()
    today_str = datetime.date.today().strftime("%Y-%m-%d")

    os.makedirs(args.output_dir, exist_ok=True)

    for idx, symbol in enumerate(symbols, 1):
        print(f"[{idx}/{len(symbols)}] Đang tải dữ liệu cho mã: {symbol}...")
        df_price = fetch_full_historical_price(symbol, start_date=args.start, end_date=today_str)

        if not df_price.empty:
            df_price['symbol'] = symbol
            
            output_parquet = os.path.join(args.output_dir, f"{symbol}.parquet")
            prepare_and_save_parquet(df_price, output_parquet)

            print(f"  └─ 🟢 Đã lưu {len(df_price)} bản ghi Parquet vào: {output_parquet}")
        else:
            print(f"  └─ 🔴 Không lấy được dữ liệu cho mã {symbol}")

        time.sleep(1)

    print("\n✅ Hoàn tất quá trình cào và lưu trữ Parquet!")

if __name__ == "__main__":
    main()