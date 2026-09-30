import pandas as pd
import sqlite3
from pathlib import Path

# Đường dẫn tới thư mục data
DATA_DIR = Path("data")

# -------------------------------------------------------------------
# 1. ĐỌC DỮ LIỆU TỪ SQLITE DATABASE
# -------------------------------------------------------------------
print("=== 1. ĐỌC TỪ SQLITE DATABASE ===")
db_path = DATA_DIR / "financial_database.db"

# Cách 1A: Dùng pandas đọc trực tiếp qua câu lệnh SQL (Nhanh & Tiện nhất)
with sqlite3.connect(db_path) as conn:
    # Lấy 5 dòng đầu tiên của mã cổ phiếu FPT (hoặc bất kỳ mã nào)
    df_sql = pd.read_sql_query(
        "SELECT * FROM financial_reports WHERE symbol = 'FPT' LIMIT 5", 
        conn
    )
print("Dữ liệu từ SQLite (Mẫu FPT):")
print(df_sql.head())


# -------------------------------------------------------------------
# 2. ĐỌC DỮ LIỆU TỪ FILE PARQUET ĐƠN (Single File)
# -------------------------------------------------------------------
print("\n=== 2. ĐỌC TỪ FILE PARQUET ĐƠN ===")
parquet_single_path = DATA_DIR / "financial_parquet" / "all_financial_reports.parquet"

# Đọc toàn bộ file Parquet vào DataFrame
df_parquet = pd.read_parquet(parquet_single_path)
print(f"Tổng số dòng từ file Parquet đơn: {len(df_parquet):,}")

# Lọc dữ liệu nhanh trên DataFrame
df_fpt_parquet = df_parquet[df_parquet['symbol'] == 'FPT']
print("5 dòng đầu tiên của FPT từ Parquet:")
print(df_fpt_parquet.head())


# -------------------------------------------------------------------
# 3. ĐỌC DỮ LIỆU TỪ THƯ MỤC PARQUET PHÂN VÙNG (Partitioned by Symbol)
# -------------------------------------------------------------------
print("\n=== 3. ĐỌC TỪ PARQUET PHÂN VÙNG (BY SYMBOL) ===")
parquet_partition_dir = DATA_DIR / "financial_parquet" / "by_symbol"

# Cách 3A: Đọc toàn bộ các phân vùng
df_all_partitions = pd.read_parquet(parquet_partition_dir)
print(f"Tổng số dòng đọc từ tất cả các phân vùng: {len(df_all_partitions):,}")

# Cách 3B: Chỉ đọc đúng 1 phân vùng mã cổ phiếu cụ thể (Tối ưu bộ nhớ & Cực nhanh)
fpt_partition_path = parquet_partition_dir / "symbol=FPT"
if fpt_partition_path.exists():
    df_fpt_only = pd.read_parquet(fpt_partition_path)
    print("Dữ liệu chỉ từ phân vùng FPT:")
    print(df_fpt_only.head())