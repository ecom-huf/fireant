import os
import json
import sqlite3
import pandas as pd
from pathlib import Path

# Đường dẫn thư mục dữ liệu
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
RAW_CSV_DIR = DATA_DIR / "financial_full"
PARQUET_DIR = DATA_DIR / "financial_parquet"
DB_PATH = DATA_DIR / "financial_database.db"


def flatten_financial_data(df_raw: pd.DataFrame) -> pd.DataFrame:
    """
    Bung (normalize) cột values_json trong DataFrame thành các dòng chi tiết theo từng năm / quý.
    """
    flat_records = []

    for _, row in df_raw.iterrows():
        symbol = row.get('symbol')
        report_type_id = row.get('report_type_id')
        report_type_name = row.get('report_type_name')
        period_mode = row.get('period_mode')
        item_id = row.get('id')
        item_name = row.get('name')
        field = row.get('field')

        # Xử lý giá trị values_json
        val_json = row.get('values_json')
        if isinstance(val_json, str):
            try:
                values_list = json.loads(val_json)
            except Exception:
                values_list = []
        elif isinstance(val_json, list):
            values_list = val_json
        else:
            values_list = []

        # Lặp qua từng kỳ trong mảng JSON
        for val_item in values_list:
            if not isinstance(val_item, dict):
                continue

            year = val_item.get('year')
            quarter = val_item.get('quarter', 0)
            value = val_item.get('value')

            # Tạo chuỗi kỳ báo cáo chuẩn (VD: 2024-Q1 hoặc 2024-FY)
            period = f"{year}-Q{quarter}" if quarter and quarter > 0 else f"{year}"

            flat_records.append({
                'symbol': symbol,
                'period_mode': period_mode,
                'year': year,
                'quarter': quarter,
                'period': period,
                'item_id': item_id,
                'item_name': item_name,
                'field': field,
                'value': value,
                'report_type_id': report_type_id,
                'report_type_name': report_type_name
            })

    return pd.DataFrame(flat_records)


def main():
    print("🚀 Bắt đầu quá trình chuyển đổi dữ liệu BCTC...")

    # 1. Đọc tất cả các file CSV trong thư mục RAW_CSV_DIR
    csv_files = list(RAW_CSV_DIR.glob("*.csv"))
    if not csv_files:
        print(f"⚠️ Không tìm thấy file CSV nào tại thư mục: {RAW_CSV_DIR}")
        return

    print(f"📂 Tìm thấy {len(csv_files)} file CSV BCTC. Đang tổng hợp dữ liệu thô...")
    df_list = []
    for file in csv_files:
        try:
            df_temp = pd.read_csv(file)
            df_list.append(df_temp)
        except Exception as e:
            print(f"⚠️ Lỗi đọc file {file.name}: {e}")

    if not df_list:
        print("❌ Không đọc được dữ liệu từ các file CSV.")
        return

    df_raw = pd.concat(df_list, ignore_index=True)
    print(f"✅ Tổng hợp thành công {len(df_raw):,} dòng dữ liệu thô.")

    # 2. Phẳng hóa dữ liệu từ values_json
    print("🔄 Đang tiến hành phẳng hóa cột values_json thành từng kỳ (year/quarter)...")
    df_flat = flatten_financial_data(df_raw)
    print(f"✅ Phẳng hóa thành công! Tổng số bản ghi phẳng: {len(df_flat):,} dòng.")

    # 3. Lưu vào SQLite Database
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(DB_PATH) as conn:
        # Lưu bảng phẳng
        df_flat.to_sql("financial_reports", conn, if_exists="replace", index=False)

        # Tạo Index giúp tìm kiếm theo Symbol và Kỳ báo cáo nhanh gấp trăm lần
        conn.execute("CREATE INDEX IF NOT EXISTS idx_symbol_item ON financial_reports (symbol, item_id);")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_period ON financial_reports (symbol, year, quarter);")

    print(f"🟢 [SQLite Database] Đã lưu dữ liệu phẳng vào: {DB_PATH}")

    # 4. Lưu ra Parquet (Dạng file đơn & Dạng phân vùng by_symbol)
    PARQUET_DIR.mkdir(parents=True, exist_ok=True)
    
    # Single Parquet File
    single_parquet_path = PARQUET_DIR / "all_financial_reports.parquet"
    df_flat.to_parquet(single_parquet_path, index=False)
    print(f"🟢 [Parquet Single File] Đã lưu tại: {single_parquet_path}")

    # Partitioned Parquet Directory
    partition_dir = PARQUET_DIR / "by_symbol"
    df_flat.to_parquet(partition_dir, partition_cols=['symbol'], index=False)
    print(f"🟢 [Parquet Partitioned] Đã phân vùng theo symbol tại: {partition_dir}")

    print("\n🎉 Mọi thao tác chuyển đổi phẳng đã hoàn tất thành công!")


if __name__ == "__main__":
    main()