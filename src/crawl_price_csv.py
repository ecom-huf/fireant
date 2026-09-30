import os
import time
import datetime
import argparse
import requests
import pandas as pd
from pathlib import Path
from dotenv import load_dotenv

# Xác định đường dẫn tuyệt đối tới thư mục gốc dự án (chứa thư mục src)
# Path(__file__).resolve().parent.parent -> nhảy từ src/crawl_price_csv.py lên thư mục gốc
ROOT_DIR = Path(__file__).resolve().parent.parent
ENV_PATH = ROOT_DIR / ".env"

# Load file .env chính xác từ thư mục gốc
load_dotenv(dotenv_path=ENV_PATH)

# Lấy token từ file .env
FIREANT_TOKEN = os.getenv("FIREANT_TOKEN", "").strip()

if not FIREANT_TOKEN:
    print(f"⚠️ Cảnh báo: Không tìm thấy FIREANT_TOKEN trong file: {ENV_PATH}")
else:
    print(f"🔑 Đã nạp thành công FIREANT_TOKEN từ: {ENV_PATH}")

# Chuẩn hóa Token
if FIREANT_TOKEN.startswith("Bearer "):
    AUTH_HEADER = FIREANT_TOKEN
else:
    AUTH_HEADER = f"Bearer {FIREANT_TOKEN}"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
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

def fetch_full_historical_price(symbol: str, start_date: str, end_date: str) -> pd.DataFrame:
    url = f"https://restv2.fireant.vn/symbols/{symbol}/historical-quotes"
    all_records = []
    offset = 0
    limit = 500

    while True:
        params = {
            "startDate": start_date,
            "endDate": end_date,
            "offset": offset,
            "limit": limit
        }

        try:
            response = requests.get(url, headers=HEADERS, params=params, timeout=15)
            if response.status_code == 200:
                data = response.json()
                if not data or len(data) == 0:
                    break
                
                all_records.extend(data)
                
                if len(data) < limit:
                    break
                
                offset += limit
                time.sleep(0.5)
            elif response.status_code == 401:
                print(f"❌ Lỗi 401: Token chưa đúng hoặc đã hết hạn. Hãy cập nhật lại token trong file .env.")
                break
            else:
                print(f"⚠️ Lỗi HTTP {response.status_code} khi tải mã {symbol}")
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

def main():
    parser = argparse.ArgumentParser(description="Crawl đầy đủ dữ liệu giá từ FireAnt restv2 API")
    parser.add_argument("--csv", type=str, default="watchlist/kakata.csv", help="Đường dẫn file CSV chứa danh sách mã cổ phiếu")
    parser.add_argument("--start", type=str, default="2000-01-01", help="Ngày bắt đầu crawl (Định dạng YYYY-MM-DD)")
    parser.add_argument("--output_dir", type=str, default="data/price", help="Thư mục lưu trữ kết quả")
    
    args = parser.parse_args()

    if not os.path.exists(args.csv):
        print(f"❌ Không tìm thấy file CSV danh sách mã: {args.csv}")
        return

    df_watchlist = pd.read_csv(args.csv)
    if 'Symbol' not in df_watchlist.columns:
        print("❌ File CSV danh sách cần có cột tên là 'symbol'")
        return

    symbols = df_watchlist['Symbol'].dropna().astype(str).str.strip().str.upper().tolist()
    print(f"📋 Tìm thấy {len(symbols)} mã cổ phiếu: {', '.join(symbols)}")

    today_str = datetime.date.today().strftime("%Y-%m-%d")
    print(f"📅 Ngày bắt đầu: {args.start} | Ngày kết thúc (Hôm nay): {today_str}\n")

    os.makedirs(args.output_dir, exist_ok=True)

    for idx, symbol in enumerate(symbols, 1):
        print(f"[{idx}/{len(symbols)}] Đang tải dữ liệu cho mã: {symbol}...")
        
        df_price = fetch_full_historical_price(symbol, start_date=args.start, end_date=today_str)

        if not df_price.empty:
            df_price['symbol'] = symbol

            df_price['date_dt'] = pd.to_datetime(df_price['date'])
            df_price = df_price.sort_values(by='date_dt', ascending=True).drop(columns=['date_dt'])

            output_csv = os.path.join(args.output_dir, f"{symbol}_price_full.csv")
            df_price.to_csv(output_csv, index=False, encoding='utf-8-sig')

            output_json = os.path.join(args.output_dir, f"{symbol}_price_full.json")
            df_price.to_json(output_json, orient="records", indent=2, force_ascii=False)

            print(f"  └─ 🟢 Đã lưu {len(df_price)} bản ghi vào: {output_csv} và {output_json}")
        else:
            print(f"  └─ 🔴 Không lấy được dữ liệu cho mã {symbol}")

        time.sleep(1)

    print("\n✅ Hoàn tất quá trình crawl dữ liệu!")

if __name__ == "__main__":
    main()