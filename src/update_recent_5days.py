import os
import time
import datetime
import argparse
import requests
import pandas as pd
from pathlib import Path
from dotenv import load_dotenv

# Đăng ký thư mục gốc dự án (Lùi 1 cấp từ src/ để ra thư mục root)
ROOT_DIR = Path(__file__).resolve().parent.parent
ENV_PATH = ROOT_DIR / ".env"

# Đường dẫn thư mục lưu parquet mặc định: data/price_parquet/ (cùng cấp với src/)
DEFAULT_OUTPUT_DIR = ROOT_DIR / "data" / "price_parquet"
DEFAULT_CSV_PATH = ROOT_DIR / "watchlist" / "kakata.csv"

load_dotenv(dotenv_path=ENV_PATH)
FIREANT_TOKEN = os.getenv("FIREANT_TOKEN", "").strip()

AUTH_HEADER = FIREANT_TOKEN if FIREANT_TOKEN.startswith("Bearer ") else f"Bearer {FIREANT_TOKEN}"

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

INT_COLS = [
    "totalVolume", "dealVolume", "putthroughVolume", "buyForeignQuantity", 
    "sellForeignQuantity", "buyCount", "buyQuantity", "sellCount", "sellQuantity"
]

FLOAT_COLS = [
    "priceHigh", "priceLow", "priceOpen", "priceAverage", "priceClose", "priceBasic",
    "totalValue", "putthroughValue", "buyForeignValue", "sellForeignValue",
    "adjRatio", "currentForeignRoom", "propTradingNetDealValue", 
    "propTradingNetPTValue", "propTradingNetValue", "unit"
]

def fetch_historical_price(symbol: str, start_date: str, end_date: str) -> pd.DataFrame:
    """Tải dữ liệu giá từ FireAnt REST API v2."""
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
                time.sleep(0.3)
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
        return df[FULL_COLUMNS]

    return pd.DataFrame()

def prepare_and_save_parquet(df: pd.DataFrame, output_filepath: Path):
    """Chuẩn hóa Data Types và ghi/cập nhật xuống file Parquet."""
    df_clean = df.copy()
    
    df_clean['date'] = pd.to_datetime(df_clean['date'])
    
    for col in INT_COLS:
        df_clean[col] = pd.to_numeric(df_clean[col], errors='coerce').fillna(0).astype('int64')
        
    for col in FLOAT_COLS:
        df_clean[col] = pd.to_numeric(df_clean[col], errors='coerce').astype('float64')

    # Loại bỏ dữ liệu trùng lặp theo cột date và lấy bản ghi mới nhất
    df_clean = df_clean.drop_duplicates(subset=['date'], keep='last')
    df_clean = df_clean.sort_values(by='date', ascending=True).reset_index(drop=True)

    df_clean.to_parquet(output_filepath, index=False, engine='pyarrow')

def update_symbol_5days(symbol: str, target_dates: list, output_dir: Path):
    """Kiểm tra file Parquet của mã cổ phiếu và cập nhật các ngày còn thiếu trong 5 ngày gần nhất."""
    parquet_path = output_dir / f"{symbol}.parquet"
    existing_df = pd.DataFrame()
    existing_dates = set()

    # 1. Kiểm tra xem file Parquet đã tồn tại chưa
    if parquet_path.exists():
        try:
            existing_df = pd.read_parquet(parquet_path)
            if 'date' in existing_df.columns:
                # Trích xuất danh sách các ngày đã có dưới dạng chuỗi 'YYYY-MM-DD'
                existing_dates = set(pd.to_datetime(existing_df['date']).dt.strftime('%Y-%m-%d'))
        except Exception as e:
            print(f"⚠️ Không đọc được file Parquet cũ của {symbol}: {e}")

    # 2. Lọc ra danh sách những ngày CHƯA CÓ trong file Parquet
    missing_dates = [d for d in target_dates if d not in existing_dates]

    if not missing_dates:
        print(f"  └─ 🟢 {symbol}: Dữ liệu 5 ngày gần nhất đã đầy đủ. Bỏ qua!")
        return

    # Xác định khoảng ngày cần gửi API request (Từ ngày thiếu nhỏ nhất đến ngày thiếu lớn nhất)
    start_missing = min(missing_dates)
    end_missing = max(missing_dates)
    
    print(f"  └─ 🔄 {symbol}: Đang tải bổ sung dữ liệu từ {start_missing} đến {end_missing}...")

    # 3. Cào dữ liệu cho khoảng ngày còn thiếu
    new_df = fetch_historical_price(symbol, start_date=start_missing, end_date=end_missing)

    if not new_df.empty:
        new_df['symbol'] = symbol
        
        # 4. Nếu đã có dữ liệu cũ -> Tiến hành Gộp (Upsert)
        if not existing_df.empty:
            combined_df = pd.concat([existing_df, new_df], ignore_index=True)
        else:
            combined_df = new_df

        # Save lại file Parquet đã được đồng bộ
        prepare_and_save_parquet(combined_df, parquet_path)
        print(f"  └─ ✅ {symbol}: Đã cập nhật xong dữ liệu vào: {parquet_path}")
    else:
        print(f"  └─ ⚠️ {symbol}: Không lấy được dữ liệu mới từ FireAnt cho các ngày thiếu.")

def main():
    parser = argparse.ArgumentParser(description="Cập nhật dữ liệu Parquet 5 ngày gần nhất")
    parser.add_argument("--csv", type=str, default=str(DEFAULT_CSV_PATH), help="Đường dẫn file CSV watchlist")
    parser.add_argument("--output_dir", type=str, default=str(DEFAULT_OUTPUT_DIR), help="Thư mục lưu file Parquet")
    args = parser.parse_args()

    csv_path = Path(args.csv)
    output_dir = Path(args.output_dir)

    if not csv_path.exists():
        print(f"❌ Không tìm thấy file CSV: {csv_path}")
        return

    # Tạo danh sách 5 ngày gần nhất tính từ ngày hôm nay (YYYY-MM-DD)
    today = datetime.date.today()
    target_dates = [(today - datetime.timedelta(days=i)).strftime("%Y-%m-%d") for i in range(5)]
    target_dates.sort()  # Sắp xếp theo thứ tự thời gian tăng dần

    print(f"📂 Thư mục lưu dữ liệu Parquet: {output_dir.resolve()}")
    print(f"📅 5 ngày gần nhất cần kiểm tra: {target_dates}")

    df_watchlist = pd.read_csv(csv_path)
    # Tìm cột chứa ký hiệu mã cổ phiếu
    symbol_col = next((col for col in ['Symbol', 'symbol', 'ticker', 'Ticker'] if col in df_watchlist.columns), df_watchlist.columns[0])
    symbols = df_watchlist[symbol_col].dropna().astype(str).str.strip().str.upper().tolist()

    # Tự động tạo thư mục lưu trữ nếu chưa có
    output_dir.mkdir(parents=True, exist_ok=True)

    for idx, symbol in enumerate(symbols, 1):
        print(f"[{idx}/{len(symbols)}] Đang kiểm tra mã: {symbol}")
        update_symbol_5days(symbol, target_dates, output_dir)
        time.sleep(0.5)

    print("\n✅ Hoàn tất quá trình kiểm tra và cập nhật dữ liệu Parquet!")

if __name__ == "__main__":
    main()