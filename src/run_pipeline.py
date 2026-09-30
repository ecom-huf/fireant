import os
import sys
import time
import argparse
from pathlib import Path

# Thêm thư mục gốc dự án và thư mục src vào sys.path để tránh lỗi import
BASE_DIR = Path(__file__).resolve().parent
ROOT_DIR = BASE_DIR if (BASE_DIR / "src").exists() else BASE_DIR.parent
SRC_DIR = ROOT_DIR / "src"

for path in [str(ROOT_DIR), str(SRC_DIR)]:
    if path not in sys.path:
        sys.path.insert(0, path)

# Import các module cào và chuyển đổi dữ liệu
try:
    from crawl_financial import main as run_crawler
except ImportError:
    from src.crawl_financial import main as run_crawler

try:
    from convert_financial import main as run_converter
except ImportError:
    try:
        from convert_to_parquet_sqlite import main as run_converter
    except ImportError:
        from src.convert_financial import main as run_converter


def parse_arguments():
    """Đọc tham số truyền từ dòng lệnh"""
    parser = argparse.ArgumentParser(description="Pipeline cào và chuyển đổi dữ liệu Báo cáo tài chính.")
    parser.add_argument(
        "--full-rebuild",
        action="store_true",
        help="Cào lại toàn bộ lịch sử BCTC từ đầu thay vì chỉ cào bổ sung quý mới."
    )
    parser.add_argument(
        "--skip-crawl",
        action="store_true",
        help="Bỏ qua bước cào dữ liệu (Bước 1), chỉ thực hiện chuyển đổi Parquet/SQLite (Bước 2)."
    )
    return parser.parse_args()


def run_pipeline(full_rebuild: bool = False, skip_crawl: bool = False):
    start_time = time.time()
    
    if skip_crawl:
        mode_label = "CHỈ CHUYỂN ĐỔI DỮ LIỆU (SKIP CRAWL)"
    elif full_rebuild:
        mode_label = "CÀO LẠI TOÀN BỘ (FULL REBUILD)"
    else:
        mode_label = "CẬP NHẬT BỔ SUNG QUÝ MỚI (INCREMENTAL)"
    
    print("=" * 65)
    print(f"🚀 BẮT ĐẦU PIPELINE TỔNG HỢP BCTC - CHẾ ĐỘ: [{mode_label}]")
    print("=" * 65)

    # BƯỚC 1: Cào dữ liệu từ API FireAnt xuất ra CSV
    if not skip_crawl:
        print("\n--- BƯỚC 1: CÀO DỮ LIỆU BCTC TỪ FIREANT THÀNH CSV ---")
        try:
            run_crawler(full_rebuild=full_rebuild)
        except Exception as e:
            print(f"❌ Lỗi nghiêm trọng tại Bước 1 (Cào dữ liệu): {e}")
            return
    else:
        print("\n⏭  Bỏ qua BƯỚC 1 (Sử dụng dữ liệu CSV sẵn có trong thư mục data/).")

    # BƯỚC 2: Chuyển đổi CSV sang Parquet và SQLite Database
    print("\n--- BƯỚC 2: CHUYỂN ĐỔI DỮ LIỆU SANG PARQUET VÀ SQLITE ---")
    try:
        run_converter()
    except Exception as e:
        print(f"❌ Lỗi nghiêm trọng tại Bước 2 (Chuyển đổi dữ liệu): {e}")
        return

    elapsed_time = round(time.time() - start_time, 2)
    print("\n" + "=" * 65)
    print(f"✅ HOÀN THÀNH TOÀN BỘ QUY TRÌNH TRONG {elapsed_time} GIÂY!")
    print("=" * 65)


def main():
    args = parse_arguments()
    # Chú ý: dùng args.skip_crawl (dấu gạch dưới) thay vì args.skip-crawl
    run_pipeline(full_rebuild=args.full_rebuild, skip_crawl=args.skip_crawl)


if __name__ == "__main__":
    main()