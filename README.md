# 📈 Hệ Thống Thu Thập & Lưu Trữ Dữ Liệu Chứng Khoán Thời Gian Thực (FireAnt API)

Hệ thống tự động hóa quá trình thu thập dữ liệu nến $1\text{m}$ và dữ liệu lịch sử cho **292 mã cổ phiếu** từ API của FireAnt, áp dụng cơ chế bộ đệm RAM, Ghi nhật ký trước (Write-Ahead Logging - WAL) và lưu trữ tối ưu dưới dạng chuẩn **Parquet**.

---

## 🏗️ Kiến Trúc Hệ Thống (Architecture)

1. **Polling Engine (`src/main.py`)**:
   - Sử dụng `httpx.AsyncClient` kết hợp `asyncio` để cào dữ liệu bất đồng bộ 292 mã cổ phiếu song song theo chu kỳ.
2. **RAM Buffer & WAL (`src/wal_manager.py`)**:
   - Dữ liệu thu thập được cập nhật trực tiếp vào bộ nhớ RAM (`ram_buffer`).
   - Mỗi bản ghi nến được ghi tức thì vào file đệm `wal_temp.log` (Append mode) để chống mất dữ liệu khi hệ thống gặp sự cố (Crash/Power Loss).
3. **Parquet Storage Engine**:
   - Tự động chốt dữ liệu từ RAM xuống các file Parquet định kỳ (hoặc khi dừng chương trình `Ctrl + C`).
   - Dữ liệu được ép kiểu (Data Types) chuẩn hóa 27 cột, sắp xếp và loại bỏ trùng lặp (Upsert) theo mốc thời gian `date`.
4. **Historical & Daily Updater (`update_recent_5days.py`)**:
   - Công cụ bổ trợ kiểm tra và bù đắp dữ liệu nến cho 5 ngày gần nhất nếu trong file Parquet còn thiếu.

---

## 📁 Cấu Trúc Thư Mục (Project Structure)

```text
fireant/
├── .env                     # Chứa Token xác thực FIREANT_TOKEN
├── watchlist/
│   └── kakata.csv           # Danh sách 292 mã cổ phiếu cần theo dõi
├── src/
│   ├── config.py            # Cấu hình đường dẫn hệ thống (mặc định C:/fireant_data)
│   ├── main.py              # Script thu thập dữ liệu Real-time (Async Polling)
│   └── wal_manager.py       # Quản lý RAM Buffer, WAL Log và Flush Parquet
├── update_recent_5days.py   # Script kiểm tra & cập nhật bổ sung dữ liệu 5 ngày gần nhất
└── README.md                # Tài liệu hướng dẫn hệ thống