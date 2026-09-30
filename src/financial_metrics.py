import sqlite3
import pandas as pd
import numpy as np
from pathlib import Path
from typing import Union, List, Dict, Optional


class FinancialMetricsCalculator:
    """
    Mô-đun trích xuất dữ liệu BCTC từ SQLite và đọc dữ liệu giá cổ phiếu từ Parquet 
    để tính toán các chỉ số tài chính và định giá (P/E, P/B, EPS TTM, ROE, ROA).
    """
    
    def __init__(self, db_path: str = "data/financial_database.db", price_dir: str = "data/price_parquet"):
        self.db_path = Path(db_path)
        self.price_dir = Path(price_dir)
        
        if not self.db_path.exists():
            raise FileNotFoundError(f"❌ Không tìm thấy database tại: {db_path}")

    def _get_connection(self):
        return sqlite3.connect(self.db_path)

    def load_stock_price(self, symbol: str) -> pd.DataFrame:
        symbol = symbol.upper()
        parquet_files = list(self.price_dir.glob(f"{symbol}.parquet")) + \
                        list(self.price_dir.glob(f"{symbol.lower()}.parquet"))
        
        if not parquet_files:
            return pd.DataFrame()

        try:
            df_price = pd.read_parquet(parquet_files[0])
            df_price['date'] = pd.to_datetime(df_price['date'])
            
            if 'priceClose' in df_price.columns:
                close_series = df_price['priceClose']
            elif 'close' in df_price.columns:
                close_series = df_price['close']
            else:
                return pd.DataFrame()

            unit_multiplier = df_price['unit'] if 'unit' in df_price.columns else 1000.0
            df_price['close_vnd'] = close_series * unit_multiplier

            return df_price[['date', 'close_vnd']].sort_values('date').reset_index(drop=True)
            
        except Exception as e:
            print(f"⚠️ Lỗi khi đọc file parquet giá của {symbol}: {e}")
            return pd.DataFrame()

    def get_price_at_date(self, df_price: pd.DataFrame, target_date: str) -> Optional[float]:
        if df_price.empty or 'date' not in df_price.columns or 'close_vnd' not in df_price.columns:
            return None

        target_dt = pd.to_datetime(target_date)
        price_dates = df_price['date'].dt.tz_localize(None) if df_price['date'].dt.tz is not None else df_price['date']
        valid_prices = df_price[price_dates <= target_dt]
        
        if not valid_prices.empty:
            return float(valid_prices.iloc[-1]['close_vnd'])
        return None

    def fetch_raw_flat_data(self, symbol: str, period_mode: str = 'Quarter', limit: int = 20) -> pd.DataFrame:
        symbol = symbol.upper()
        query = f"""
            SELECT 
                period,
                year,
                quarter,
                MAX(CASE WHEN LOWER(item_name) LIKE '%doanh thu thuần%' THEN value END) AS revenue,
                MAX(CASE WHEN LOWER(item_name) LIKE '%lợi nhuận gộp%' THEN value END) AS gross_profit,
                MAX(CASE WHEN LOWER(item_name) LIKE '%lợi nhuận thuần từ hoạt động kinh doanh%' THEN value END) AS operating_profit,
                MAX(CASE WHEN LOWER(item_name) LIKE '%lợi nhuận sau thuế của công ty mẹ%' 
                          OR LOWER(item_name) LIKE '%lợi nhuận sau thuế thu nhập%' THEN value END) AS net_profit,
                MAX(CASE WHEN LOWER(item_name) LIKE '%tổng cộng tài sản%' THEN value END) AS total_assets,
                MAX(CASE WHEN LOWER(item_name) LIKE '%vốn chủ sở hữu%' THEN value END) AS total_equity,
                MAX(CASE WHEN LOWER(item_name) LIKE '%nợ phải trả%' THEN value END) AS total_liabilities,
                MAX(CASE WHEN LOWER(item_name) LIKE '%cổ phiếu%lưu hành%' 
                          OR LOWER(item_name) LIKE '%số lượng cổ phiếu%' 
                          OR LOWER(item_name) LIKE '%cổ phiếu phổ thông%' 
                          OR LOWER(item_name) LIKE '%khối lượng cổ phiếu%' THEN value END) AS shares_outstanding
            FROM financial_reports
            WHERE symbol = '{symbol}' AND period_mode = '{period_mode}'
            GROUP BY year, quarter, period
            ORDER BY year ASC, quarter ASC;
        """
        
        with self._get_connection() as conn:
            df = pd.read_sql_query(query, conn)
            
        return df.tail(limit).reset_index(drop=True) if not df.empty else pd.DataFrame()

    def calculate_indicators(
        self, 
        symbol: str, 
        period_mode: str = 'Quarter', 
        limit: int = 12,
        shares_outstanding_override: Optional[float] = None
    ) -> pd.DataFrame:
        df = self.fetch_raw_flat_data(symbol=symbol, period_mode=period_mode, limit=limit + 4)
        if df.empty:
            print(f"⚠️ Không có dữ liệu BCTC cho mã {symbol}")
            return pd.DataFrame()

        # Fallback số lượng cổ phiếu lưu hành nếu DB trống
        if shares_outstanding_override is not None:
            df['shares_outstanding'] = shares_outstanding_override
        else:
            default_shares = {
                'FPT': 1460000000,
                'HPG': 6398000000,
                'MWG': 1462000000
            }
            fallback_val = default_shares.get(symbol.upper(), np.nan)
            df['shares_outstanding'] = df['shares_outstanding'].fillna(fallback_val)

        # 1. BIÊN LỢI NHUẬN & SỨC SINH LỜI
        df['gross_margin'] = (df['gross_profit'] / df['revenue']) * 100
        df['operating_margin'] = (df['operating_profit'] / df['revenue']) * 100
        df['net_margin'] = (df['net_profit'] / df['revenue']) * 100

        avg_assets = (df['total_assets'] + df['total_assets'].shift(1)) / 2
        avg_equity = (df['total_equity'] + df['total_equity'].shift(1)) / 2
        annual_factor = 4 if period_mode == 'Quarter' else 1
        
        df['roa'] = (df['net_profit'] / avg_assets) * 100 * annual_factor
        df['roe'] = (df['net_profit'] / avg_equity) * 100 * annual_factor

        # 2. TĂNG TRƯỞNG & CƠ CẤU NỢ
        if period_mode == 'Quarter':
            df['revenue_growth_yoy'] = df['revenue'].pct_change(periods=4) * 100
            df['net_profit_growth_yoy'] = df['net_profit'].pct_change(periods=4) * 100
            df['net_profit_ttm'] = df['net_profit'].rolling(window=4).sum()
        else:
            df['revenue_growth_yoy'] = df['revenue'].pct_change(periods=1) * 100
            df['net_profit_growth_yoy'] = df['net_profit'].pct_change(periods=1) * 100
            df['net_profit_ttm'] = df['net_profit']

        df['debt_to_equity'] = df['total_liabilities'] / df['total_equity']

        # 3. KHỚP GIÁ TỪ PARQUET ĐỂ TÍNH P/E, P/B
        df_price = self.load_stock_price(symbol)
        quarter_end_dates = {1: '-03-31', 2: '-06-30', 3: '-09-30', 4: '-12-31'}
        
        market_prices = []
        for _, row in df.iterrows():
            if period_mode == 'Quarter':
                period_end_str = f"{int(row['year'])}{quarter_end_dates.get(int(row['quarter']), '-12-31')}"
            else:
                period_end_str = f"{int(row['year'])}-12-31"
            
            p = self.get_price_at_date(df_price, period_end_str)
            market_prices.append(p)

        df['market_price'] = market_prices
        df['eps_ttm'] = df['net_profit_ttm'] / df['shares_outstanding']
        df['bvps'] = df['total_equity'] / df['shares_outstanding']

        df['pe_ratio'] = df['market_price'] / df['eps_ttm']
        df['pb_ratio'] = df['market_price'] / df['bvps']

        df_final = df.tail(limit).reset_index(drop=True)
        df_final.insert(0, 'symbol', symbol.upper())
        
        return df_final

    def export_metrics_for_model(self, symbols: List[str], period_mode: str = 'Quarter', limit: int = 4) -> pd.DataFrame:
        all_metrics = []
        for symbol in symbols:
            df_sym = self.calculate_indicators(symbol=symbol, period_mode=period_mode, limit=limit)
            if not df_sym.empty:
                all_metrics.append(df_sym)

        return pd.concat(all_metrics, ignore_index=True) if all_metrics else pd.DataFrame()

    def export_to_parquet(
        self, 
        symbols: List[str], 
        output_path: str = "data/output/financial_metrics_dataset.parquet", 
        period_mode: str = 'Quarter', 
        limit: int = 20
    ) -> str:
        """
        Xuất toàn bộ chỉ số tài chính hợp nhất cho danh sách mã cổ phiếu ra file Parquet.
        
        Parameters:
            symbols (List[str]): Danh sách mã cổ phiếu.
            output_path (str): Đường dẫn lưu file parquet output.
            period_mode (str): 'Quarter' hoặc 'Year'.
            limit (int): Số lượng kỳ gần nhất muốn xuất.
            
        Returns:
            str: Đường dẫn file Parquet đã xuất thành công.
        """
        df_dataset = self.export_metrics_for_model(symbols=symbols, period_mode=period_mode, limit=limit)
        
        if df_dataset.empty:
            print("⚠️ Không có dữ liệu để xuất Parquet.")
            return ""

        output_file = Path(output_path)
        # Tự động tạo thư mục nếu chưa tồn tại
        output_file.parent.mkdir(parents=True, exist_ok=True)

        # Xuất file dạng Parquet
        df_dataset.to_parquet(output_file, index=False, engine='pyarrow')
        print(f"✅ Đã xuất thành công Dataset {len(df_dataset)} dòng ra: {output_file.resolve()}")
        
        return str(output_file.resolve())


# ==========================================
# CHẠY THỬ HÀM XUẤT PARQUET
# ==========================================
if __name__ == "__main__":
    calculator = FinancialMetricsCalculator(
        db_path="data/financial_database.db",
        price_dir="data/price_parquet"
    )

    watchlist = ['FPT', 'HPG', 'MWG']
    
    # Xuất toàn bộ chỉ số ra file Parquet
    saved_path = calculator.export_to_parquet(
        symbols=watchlist, 
        output_path="data/output/financial_metrics_dataset.parquet",
        limit=12
    )

    # Đọc lại thử file vừa xuất
    if saved_path:
        df_check = pd.read_parquet(saved_path)
        print("\n🔍 Kiểm tra 5 dòng đầu file Parquet vừa tạo:")
        print(df_check[['symbol', 'period', 'market_price', 'eps_ttm', 'pe_ratio', 'pb_ratio', 'roe']].head())