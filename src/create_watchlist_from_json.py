import json
import csv
import re
import os

def clean_filename(name):
    # Loại bỏ hoặc thay thế các ký tự không hợp lệ trong tên file Windows/Linux
    return re.sub(r'[\\/*?:"<>|]', "", name).strip()

def json_to_csv(json_file_path, output_dir="watchlist"):
    # Tự động tạo thư mục nếu chưa tồn tại
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
        print(f"Đã tạo thư mục: {output_dir}")

    # Đọc dữ liệu từ file json
    with open(json_file_path, 'r', encoding='utf-8') as f:
        watchlists = json.load(f)
    
    # Lặp qua từng watchlist trong mảng JSON
    for item in watchlists:
        raw_name = item.get('name', 'unnamed')
        symbols = item.get('symbols', [])
        
        # Làm sạch tên file và ghép đường dẫn tới thư mục output
        clean_name = clean_filename(raw_name) + ".csv"
        file_path = os.path.join(output_dir, clean_name)
        
        # Ghi danh sách mã chứng khoán vào file CSV
        with open(file_path, 'w', newline='', encoding='utf-8-sig') as csv_file:
            writer = csv.writer(csv_file)
            # Ghi tiêu đề cột
            writer.writerow(["Symbol"])
            
            # Ghi các mã chứng khoán
            for symbol in symbols:
                writer.writerow([symbol])
                
        print(f"Đã tạo file: {file_path} ({len(symbols)} mã)")

if __name__ == "__main__":    
    json_to_csv("watchlist/lists.json")