import boto3
from pathlib import Path
from src.config import (
    R2_ENDPOINT_URL, R2_ACCESS_KEY_ID, R2_SECRET_ACCESS_KEY, 
    R2_BUCKET_NAME, PARQUET_DIR
)

def sync_to_cloud():
    """Đẩy toàn bộ file Parquet hiện tại lên Cloudflare R2 / AWS S3."""
    if not R2_ACCESS_KEY_ID or not R2_SECRET_ACCESS_KEY:
        print("⚠️ Chưa cấu hình R2/S3 Credentials trong .env. Bỏ qua bước Cloud Backup.")
        return

    try:
        s3_client = boto3.client(
            's3',
            endpoint_url=R2_ENDPOINT_URL,
            aws_access_key_id=R2_ACCESS_KEY_ID,
            aws_secret_access_key=R2_SECRET_ACCESS_KEY
        )
        
        print("☁️ Đang đồng bộ dữ liệu Parquet lên Cloud Storage...")
        count = 0
        for file_path in PARQUET_DIR.rglob("*.parquet"):
            relative_path = file_path.relative_to(PARQUET_DIR)
            object_name = f"price_1m/{relative_path.as_posix()}"
            
            s3_client.upload_file(str(file_path), R2_BUCKET_NAME, object_name)
            count += 1
            
        print(f"✅ Đồng bộ thành công {count} files lên Cloud!")
    except Exception as e:
        print(f"❌ Lỗi Cloud Backup: {e}")