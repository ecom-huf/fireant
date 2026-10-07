import os
import time
import json
import requests
import pandas as pd
from pathlib import Path
from dotenv import load_dotenv

# Đăng ký thư mục gốc dự án (Lùi 1 cấp từ src/ để ra thư mục root)
ROOT_DIR = Path(__file__).resolve().parent.parent
ENV_PATH = ROOT_DIR / ".env"
load_dotenv(dotenv_path=ENV_PATH)

FIREANT_TOKEN = os.getenv("FIREANT_TOKEN", "").strip()

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Origin": "https://fireant.vn",
    "Referer": "https://fireant.vn/",
    "Accept": "application/json, text/plain, */*"
}

if FIREANT_TOKEN:
    AUTH_HEADER = FIREANT_TOKEN if FIREANT_TOKEN.startswith("Bearer ") else f"Bearer {FIREANT_TOKEN}"
    HEADERS["Authorization"] = AUTH_HEADER

# Các Endpoint dữ liệu vĩ mô của FireAnt (Đã bổ sung Business, Taxes và InterestRate)
MACRO_ENDPOINTS = {
    "GDP": "https://restv2.fireant.vn/macro-data/GDP/info",
    "Prices": "https://restv2.fireant.vn/macro-data/Prices/info",
    "Consumer": "https://restv2.fireant.vn/macro-data/Consumer/info",
    "Trade": "https://restv2.fireant.vn/macro-data/Trade/info",
    "Labour": "https://restv2.fireant.vn/macro-data/Labour/info",
    "Money": "https://restv2.fireant.vn/macro-data/Money/info",
    "Taxes": "https://restv2.fireant.vn/macro-data/Taxes/info",
    "InterestRate": "https://restv2.fireant.vn/macro-data/InterestRate/info",
    "Business": "https://restv2.fireant.vn/macro-data/Business/info"
}

MACRO_TYPES_URL = "https://restv2.fireant.vn/macro-data/types"

# Thư mục lưu trữ dữ liệu vĩ mô: data/macro_data/ (cùng cấp với src/)
OUTPUT_DIR = ROOT_DIR / "data" / "macro_data"


def fetch_macro_types() -> pd.DataFrame:
    """Tải danh sách các loại chỉ tiêu vĩ mô từ FireAnt API."""
    print("🌐 Đang lấy danh mục chỉ tiêu vĩ mô (macro-data/types)...")
    try:
        response = requests.get(MACRO_TYPES_URL, headers=HEADERS, timeout=15)
        if response.status_code == 200:
            data = response.json()
            if data:
                df_types = pd.DataFrame(data)
                print(f"  └─ ✅ Lấy thành công {len(df_types)} loại chỉ tiêu vĩ mô.")
                return df_types
        else:
            print(f"  └─ ❌ Lỗi HTTP Status: {response.status_code}")
    except Exception as e:
        print(f"  └─ ❌ Lỗi kết nối khi lấy macro types: {e}")
    return pd.DataFrame()


def fetch_macro_endpoint_data(category_name: str, url: str) -> pd.DataFrame:
    """Tải dữ liệu vĩ mô theo từng phân nhóm (GDP, Prices, Money, Business...)."""
    print(f"🔄 Đang tải dữ liệu vĩ mô nhóm [{category_name}]...")
    try:
        response = requests.get(url, headers=HEADERS, timeout=15)
        if response.status_code == 200:
            data = response.json()
            if data:
                df = pd.DataFrame(data)
                df.insert(0, "category", category_name)
                print(f"  └─ 🟢 {category_name}: Lấy thành công {len(df)} bản ghi.")
                return df
            else:
                print(f"  └─ ⚠️ {category_name}: Không có dữ liệu trả về.")
        else:
            print(f"  └─ ❌ {category_name}: Lỗi HTTP Status {response.status_code}")
    except Exception as e:
        print(f"  └─ ❌ {category_name}: Lỗi kết nối - {e}")

    return pd.DataFrame()


def save_dataframe(df: pd.DataFrame, filename_stem: str, output_dir: Path):
    """Lưu dữ liệu ra cả 2 định dạng CSV (tiện đọc) và Parquet (tối ưu hiệu năng)."""
    if df.empty:
        return

    csv_path = output_dir / f"{filename_stem}.csv"
    parquet_path = output_dir / f"{filename_stem}.parquet"

    df_clean = df.copy()
    
    # Ép kiểu cột thời gian / ngày tháng nếu có
    for col in ["date", "time", "updatedAt", "createdAt"]:
        if col in df_clean.columns:
            df_clean[col] = pd.to_datetime(df_clean[col], errors="ignore")

    # 1. Lưu CSV
    df_clean.to_csv(csv_path, index=False, encoding="utf-8-sig")

    # 2. Lưu Parquet (Chuyển các cột dict/list thành json string nếu có để tránh lỗi PyArrow)
    for col in df_clean.columns:
        if df_clean[col].apply(lambda x: isinstance(x, (dict, list))).any():
            df_clean[col] = df_clean[col].apply(lambda x: json.dumps(x, ensure_ascii=False) if isinstance(x, (dict, list)) else x)

    df_clean.to_parquet(parquet_path, index=False, engine="pyarrow")
    print(f"  └─ 💾 Đã lưu dữ liệu vào:\n      • CSV: {csv_path}\n      • Parquet: {parquet_path}")


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    print(f"🚀 Bắt đầu cào dữ liệu vĩ mô FireAnt...")
    print(f"📂 Thư mục lưu trữ: {OUTPUT_DIR.resolve()}\n")

    # 1. Cào danh mục Macro Types
    df_types = fetch_macro_types()
    if not df_types.empty:
        save_dataframe(df_types, "macro_types", OUTPUT_DIR)
    time.sleep(0.5)

    # 2. Cào dữ liệu theo từng nhóm vĩ mô
    all_macro_dfs = []

    for category, url in MACRO_ENDPOINTS.items():
        df_cat = fetch_macro_endpoint_data(category, url)
        if not df_cat.empty:
            save_dataframe(df_cat, f"macro_{category}", OUTPUT_DIR)
            all_macro_dfs.append(df_cat)
        time.sleep(0.5)

    # 3. Gộp toàn bộ dữ liệu vĩ mô vào 1 file tổng duy nhất (macro_all_combined)
    if all_macro_dfs:
        combined_df = pd.concat(all_macro_dfs, ignore_index=True)
        print("\n📦 Đang lưu file tổng hợp dữ liệu vĩ mô...")
        save_dataframe(combined_df, "macro_all_combined", OUTPUT_DIR)

    print("\n✅ Hoàn tất cào và lưu trữ dữ liệu vĩ mô!")


if __name__ == "__main__":
    main()