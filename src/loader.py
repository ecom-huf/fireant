import pandas as pd
from pathlib import Path
from src.config import WATCHLIST_PATH

def load_watchlist(filepath: Path = WATCHLIST_PATH) -> list[str]:
    """Đọc và chuẩn hóa danh sách mã cổ phiếu từ file CSV."""
    if not filepath.exists():
        print(f"⚠️ File {filepath} không tồn tại! Sử dụng watchlist dự phòng.")
        return ["HPG", "SSI", "FTS", "VNM", "TCB", "VHM"]
    
    try:
        df = pd.read_csv(filepath)
        col_name = None
        for candidate in ['symbol', 'ticker', 'code', 'Mã', 'ma', 'Symbol']:
            if candidate in df.columns:
                col_name = candidate
                break
                
        if col_name:
            symbols = df[col_name].dropna().astype(str).str.strip().str.upper().tolist()
        else:
            symbols = df.iloc[:, 0].dropna().astype(str).str.strip().str.upper().tolist()
            
        unique_symbols = list(set(symbols))
        print(f"✅ Đã tải thành công {len(unique_symbols)} mã từ {filepath.name}")
        return unique_symbols
    except Exception as e:
        print(f"❌ Lỗi khi đọc file watchlist: {e}")
        return ["HPG", "SSI", "FTS", "VNM"]