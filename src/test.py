import pandas as pd
df = pd.read_parquet("data/price_parquet/FPT.parquet")
print("Cột trong file:", df.columns.tolist())
print("Kiểu dữ liệu:\n", df.dtypes)
print("5 dòng đầu:\n", df.head())