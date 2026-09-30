import os
from pathlib import Path
from dotenv import load_dotenv

# --- ĐƯỜNG DẪN GỐC DỰ ÁN ---
ROOT_DIR = Path(__file__).resolve().parent.parent
ENV_PATH = ROOT_DIR / ".env"
load_dotenv(dotenv_path=ENV_PATH)

# --- CẤU HÌNH API FIREANT & TOKEN ---
FIREANT_TOKEN = os.getenv("FIREANT_TOKEN", "").strip()
AUTH_TOKEN = FIREANT_TOKEN.replace("Bearer ", "") if FIREANT_TOKEN.startswith("Bearer ") else FIREANT_TOKEN
FIREANT_API_URL = os.getenv("FIREANT_API_URL", "https://restv2.fireant.vn")

# --- ĐƯỜNG DẪN TẬP TRUNG (DÙNG NGUYÊN BẢN PATHLIB) ---
WATCHLIST_PATH = ROOT_DIR / "watchlist" / "Kakata.csv"

# Nếu muốn lưu ở ổ C: để tránh hết dung lượng, chỉ cần đổi ROOT_DIR / "data" thành Path("C:/fireant_data")
DATA_DIR = ROOT_DIR / "data"
WAL_FILE = DATA_DIR / "wal_temp.log"
PARQUET_DIR = DATA_DIR / "price_1m"

# Tự động tạo thư mục nếu chưa tồn tại
DATA_DIR.mkdir(parents=True, exist_ok=True)
PARQUET_DIR.mkdir(parents=True, exist_ok=True)

# --- CẤU HÌNH CLOUDFLARE R2 / S3 (TÙY CHỌN MỞ RỘNG) ---
R2_ENDPOINT_URL = os.getenv("R2_ENDPOINT_URL", "")
R2_ACCESS_KEY_ID = os.getenv("R2_ACCESS_KEY_ID", "")
R2_SECRET_ACCESS_KEY = os.getenv("R2_SECRET_ACCESS_KEY", "")
R2_BUCKET_NAME = os.getenv("R2_BUCKET_NAME", "financial-data")

# --- SCHEMA 27 CỘT CHUẨN FIREANT ---
FULL_COLUMNS = [
    "date", "symbol", "priceHigh", "priceLow", "priceOpen", "priceAverage", 
    "priceClose", "priceBasic", "totalVolume", "dealVolume", "putthroughVolume", 
    "totalValue", "putthroughValue", "buyForeignQuantity", "buyForeignValue", 
    "sellForeignQuantity", "sellForeignValue", "buyCount", "buyQuantity", 
    "sellCount", "sellQuantity", "adjRatio", "currentForeignRoom", 
    "propTradingNetDealValue", "propTradingNetPTValue", "propTradingNetValue", "unit"
]