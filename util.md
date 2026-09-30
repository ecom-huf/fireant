# Cấp quyền cho PowerShell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\venv\Scripts\activate
# các thư viên cần
python.exe -m pip install --upgrade pip

pip install "python-socketio[asyncio_client]" aiohttp pandas pyarrow python-dotenv

pip install -r requirements.txt

pip install streamlit streamlit-lightweight-charts pandas pyarrow

# git
git config --global user.email huflit.classroom@gmail.com
git config --global user.name "ecom-huf"

git add .
git commit -m "noi dung"
git push -u origin main

# Chạy chỉ Bước 2 (Không cào lại dữ liệu)
python run_pipeline.py --skip-crawl

# Chạy bình thường (Cào bổ sung + Chuyển đổi)
python run_pipeline.py

# Chạy lại từ đầu toàn bộ lịch sử (Full Rebuild)
python run_pipeline.py --full-rebuild

 