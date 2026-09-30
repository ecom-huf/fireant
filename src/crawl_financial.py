import os
import time
import json
import requests
import pandas as pd
from pathlib import Path
from dotenv import load_dotenv

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

REPORT_TYPES = {
    1: "BalanceSheet",
    2: "IncomeStatement",
    3: "CashFlow_Direct",
    4: "CashFlow_Indirect"
}

EXCLUDED_SYMBOLS = {"VNINDEX", "VN30", "HNX", "UPCOM", "VN30F1M", "VN30F1Q", "VN30F2M"}


def load_symbols_from_kakata_csv() -> list:
    watchlist_file = ROOT_DIR / "watchlist" / "Kakata.csv"
    symbols = []

    if not watchlist_file.exists():
        print(f"❌ Không tìm thấy file: {watchlist_file}")
        return symbols

    try:
        df = pd.read_csv(watchlist_file)
        target_col = None
        for col in df.columns:
            if col.strip().lower() in ["symbol", "ticker"]:
                target_col = col
                break
        
        if target_col is None:
            target_col = df.columns[0]

        for s in df[target_col].dropna().astype(str):
            clean_symbol = s.strip().upper()
            if clean_symbol and clean_symbol not in EXCLUDED_SYMBOLS and clean_symbol not in symbols:
                symbols.append(clean_symbol)

        print(f"📖 Đã đọc {len(symbols)} mã cổ phiếu từ: {watchlist_file}")

    except Exception as e:
        print(f"❌ Lỗi khi đọc file {watchlist_file}: {e}")

    return symbols


def fetch_full_financial_report(symbol: str, report_type: int, year: int = 2026, quarter: int = 3, limit: int = 8) -> list:
    """
    Gọi API BCTC FireAnt kèm xử lý Fallback êm ái khi kỳ chỉ định chưa có BCTC.
    """
    url = f"https://restv2.fireant.vn/symbols/{symbol}/full-financial-reports"
    
    # Nếu đang chạy Full Rebuild hoặc cào chung, ưu tiên lấy lịch sử gần nhất từ API
    params = {"type": report_type, "limit": limit}
    if quarter > 0 and year > 0:
        params["year"] = year
        params["quarter"] = quarter

    try:
        response = requests.get(url, headers=HEADERS, params=params, timeout=15)
        if response.status_code == 200:
            data = response.json()
            if isinstance(data, list) and len(data) > 0:
                return data
        
        # Nếu chỉ định year/quarter bị 404 (do kỳ đó chưa ra BCTC) ➔ Thử bỏ year/quarter để lấy lịch sử
        if response.status_code in [400, 404] and "quarter" in params:
            fallback_params = {"type": report_type, "limit": limit}
            fallback_res = requests.get(url, headers=HEADERS, params=fallback_params, timeout=15)
            if fallback_res.status_code == 200:
                data = fallback_res.json()
                if isinstance(data, list):
                    return data
        
        # Chỉ in cảnh báo nếu cả 2 lần gọi đều thực sự thất bại
        if response.status_code == 401:
            print(f"  ❌ {symbol}: Token FireAnt hết hạn!")
        elif response.status_code not in [400, 404]:
            print(f"  ⚠ {symbol} (Type={report_type}): HTTP Status {response.status_code}")

    except Exception as e:
        print(f"  ❌ {symbol} (Type={report_type}): Lỗi kết nối - {e}")

    return []


def parse_financial_tree(items: list, report_type_id: int, period_mode: str) -> list:
    flat_records = []

    def _traverse(node_list):
        for item in node_list:
            node_id = item.get("id")
            name = item.get("name", "").strip()
            parent_id = item.get("parentID", -1)
            expanded = item.get("expanded", True)
            level = item.get("level", 1)
            field = item.get("field", None)
            values = item.get("values", [])

            flat_records.append({
                "report_type_id": report_type_id,
                "report_type_name": REPORT_TYPES.get(report_type_id, "Unknown"),
                "period_mode": period_mode,
                "id": node_id,
                "name": name,
                "parentID": parent_id,
                "expanded": expanded,
                "level": level,
                "field": field,
                "values_json": json.dumps(values, ensure_ascii=False)
            })

            if "children" in item and item["children"]:
                _traverse(item["children"])

    _traverse(items)
    return flat_records


def process_and_save_symbol_incremental(symbol: str, output_dir: Path, full_rebuild: bool = False):
    file_path = output_dir / f"{symbol}_financial_full.csv"
    existing_df = pd.DataFrame()

    if file_path.exists() and not full_rebuild:
        try:
            existing_df = pd.read_csv(file_path)
        except Exception:
            existing_df = pd.DataFrame()

    limit_quarter = 100 if full_rebuild or existing_df.empty else 8
    limit_year = 30 if full_rebuild or existing_df.empty else 4

    new_records = []

    for report_type_id in [1, 2, 3, 4]:
        # 1. Cào dữ liệu QUÝ
        q_data = fetch_full_financial_report(symbol, report_type=report_type_id, year=2026, quarter=3, limit=limit_quarter)
        if q_data:
            q_records = parse_financial_tree(q_data, report_type_id, period_mode="Quarter")
            new_records.extend(q_records)
        time.sleep(0.1)

        # 2. Cào dữ liệu NĂM
        y_data = fetch_full_financial_report(symbol, report_type=report_type_id, year=2026, quarter=0, limit=limit_year)
        if y_data:
            y_records = parse_financial_tree(y_data, report_type_id, period_mode="Year")
            new_records.extend(y_records)
        time.sleep(0.1)

    if not new_records:
        print(f"  ⚠ {symbol}: Không lấy được dữ liệu mới từ API.")
        return

    new_df = pd.DataFrame(new_records)
    new_df.insert(0, "symbol", symbol)

    if not existing_df.empty:
        combined_df = pd.concat([existing_df, new_df], ignore_index=True)
        dedup_cols = ["symbol", "report_type_id", "period_mode", "id"]
        final_df = combined_df.drop_duplicates(subset=dedup_cols, keep="last")
        print(f"  🟢 {symbol}: Cập nhật bổ sung thành công! (Tổng: {len(final_df)} chỉ tiêu)")
    else:
        final_df = new_df
        print(f"  🟢 {symbol}: Tạo mới thành công! ({len(final_df)} chỉ tiêu)")

    final_df.to_csv(file_path, index=False, encoding="utf-8-sig")


def main(full_rebuild: bool = False):
    symbols = load_symbols_from_kakata_csv()
    if not symbols:
        print("🛑 Dừng chương trình do không tìm thấy danh sách mã cổ phiếu.")
        return

    output_dir = ROOT_DIR / "data" / "financial_full"
    output_dir.mkdir(parents=True, exist_ok=True)

    mode_str = "Toàn bộ lịch sử" if full_rebuild else "Cập nhật bổ sung (Incremental)"
    print(f"🚀 Bắt đầu cào BCTC theo chế độ: [{mode_str}] cho {len(symbols)} mã...\n")

    for idx, symbol in enumerate(symbols, 1):
        print(f"[{idx}/{len(symbols)}]", end=" ")
        process_and_save_symbol_incremental(symbol, output_dir, full_rebuild=full_rebuild)

    print(f"\n✅ Hoàn tất cào dữ liệu BCTC! Dữ liệu đã lưu tại:\n   📁 {output_dir}")


if __name__ == "__main__":
    main(full_rebuild=False)