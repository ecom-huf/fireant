import os
import re
import requests
import pandas as pd
from pathlib import Path
from dotenv import load_dotenv

# 1. Định vị thư mục gốc dự án và load file .env
ROOT_DIR = Path(__file__).resolve().parent.parent
ENV_PATH = ROOT_DIR / ".env"

load_dotenv(dotenv_path=ENV_PATH)

FIREANT_TOKEN = os.getenv("FIREANT_TOKEN", "").strip()

if not FIREANT_TOKEN:
    print(f"⚠️ Cảnh báo: Chưa tìm thấy FIREANT_TOKEN trong file: {ENV_PATH}")
else:
    print(f"🔑 Đã nạp thành công FIREANT_TOKEN từ: {ENV_PATH}")

# Chuẩn hóa Bearer Token Header
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

def sanitize_filename(name: str) -> str:
    """Làm sạch tên file, loại bỏ ký tự không hợp lệ"""
    name = re.sub(r'[\\/*?:"<>|]', '', name)
    name = name.strip().replace(' ', '_')
    return name if name else "watchlist_unnamed"

def fetch_and_save_watchlists():
    # URL chính xác chuẩn restv2
    url = "https://restv2.fireant.vn/me/watchlists"
    output_dir = ROOT_DIR / "watchlist"
    os.makedirs(output_dir, exist_ok=True)

    print(f"🔄 Đang gửi request tới {url}...")
    
    try:
        response = requests.get(url, headers=HEADERS, timeout=15)
        print ("errorrrr", response.json())
        if response.status_code == 200:
            data = response.json()
            
            if isinstance(data, dict):
                data = [data]
                
            if not data or len(data) == 0:
                print("⚠️ API trả về danh sách watchlist rỗng.")
                
                return

            print(f"📋 Tìm thấy {len(data)} watchlist từ tài khoản.\n")

            for idx, item in enumerate(data, 1):
                name = item.get("name", f"watchlist_{item.get('watchlistID', idx)}")
                symbols = item.get("symbols", [])

                if not isinstance(symbols, list):
                    symbols = []

                # Làm sạch danh sách mã
                clean_symbols = [s.strip().upper() for s in symbols if isinstance(s, str)]

                filename = f"{sanitize_filename(name)}.csv"
                output_csv = output_dir / filename

                # Tạo DataFrame chứa duy nhất cột 'symbol'
                df = pd.DataFrame({"symbol": clean_symbols})
                df.to_csv(output_csv, index=False, encoding="utf-8-sig")

                print(f"[{idx}/{len(data)}] 🟢 Watchlist '{name}' -> Đã lưu: {output_csv} ({len(df)} mã)")

            print(f"\n✅ Hoàn tất! Tất cả các file CSV đã được lưu vào: {output_dir}")

        elif response.status_code == 401:
            print("❌ Lỗi 401: Token không hợp lệ hoặc đã hết hạn. Hãy cập nhật lại FIREANT_TOKEN trong file .env!")
        else:
            print(f"⚠️ Lỗi HTTP {response.status_code}: {response.text}")

    except Exception as e:
        print(f"❌ Lỗi kết nối khi gọi API: {e}")

if __name__ == "__main__":
    fetch_and_save_watchlists()