import sqlite3
import pandas as pd
import matplotlib.pyplot as plt
from pathlib import Path

# Cấu hình giao diện biểu đồ
plt.style.use('seaborn-v0_8-whitegrid')
plt.rcParams['font.sans-serif'] = 'Arial'
plt.rcParams['axes.unicode_minus'] = False


def plot_financial_performance_with_growth(
    symbol: str, 
    db_path: str = "data/financial_database.db", 
    top_n_periods: int = 8,
    growth_type: str = "YoY"  # Lựa chọn: 'YoY' (Tăng trưởng cùng kỳ) hoặc 'QoQ' (Tăng trưởng quý liền kề)
):
    """
    Đọc dữ liệu BCTC từ bảng phẳng SQLite, tính toán tốc độ tăng trưởng YoY/QoQ và vẽ biểu đồ kết hợp.
    
    Parameters:
        symbol (str): Mã cổ phiếu (VD: 'FPT', 'HPG', 'VNM').
        db_path (str): Đường dẫn tới file SQLite database.
        top_n_periods (int): Số kỳ gần nhất hiển thị trên biểu đồ (mặc định 8 quý).
        growth_type (str): 'YoY' (So với cùng kỳ năm trước) hoặc 'QoQ' (So với quý liền kề).
    """
    symbol = symbol.upper()
    growth_type = growth_type.upper()
    
    if not Path(db_path).exists():
        print(f"❌ File database không tồn tại tại đường dẫn: {db_path}")
        return

    # Lấy thêm dữ liệu lùi về quá khứ để tính tỷ lệ tăng trưởng YoY/QoQ không bị NaN ở các quý đầu
    fetch_limit = top_n_periods + 4 if growth_type == "YoY" else top_n_periods + 1

    # Truy vấn từ cấu trúc BẢNG PHẲNG SQLite
    query = f"""
        SELECT 
            period,
            year,
            quarter,
            MAX(CASE 
                WHEN LOWER(item_name) LIKE '%doanh thu thuần%' 
                THEN value END) AS revenue,
            MAX(CASE 
                WHEN LOWER(item_name) LIKE '%lợi nhuận sau thuế của công ty mẹ%' 
                  OR LOWER(item_name) LIKE '%lợi nhuận sau thuế thu nhập%' 
                THEN value END) AS net_profit
        FROM financial_reports
        WHERE symbol = '{symbol}' AND period_mode = 'Quarter'
        GROUP BY year, quarter, period
        ORDER BY year DESC, quarter DESC
        LIMIT {fetch_limit};
    """

    with sqlite3.connect(db_path) as conn:
        try:
            df = pd.read_sql_query(query, conn)
        except Exception as e:
            print(f"❌ Lỗi khi truy vấn dữ liệu cho {symbol}: {e}")
            return

    if df.empty:
        print(f"⚠️ Không tìm thấy dữ liệu BCTC cho mã cổ phiếu: {symbol}")
        return

    # Sắp xếp thứ tự thời gian tăng dần (từ cũ -> mới)
    df = df.sort_values(by=['year', 'quarter']).reset_index(drop=True)

    # 1. TÍNH TOÁN TỐC ĐỘ TĂNG TRƯỞNG (%)
    if growth_type == "YoY":
        # YoY: So sánh với cùng kỳ năm trước (lùi 4 quý)
        df['revenue_growth'] = df['revenue'].pct_change(periods=4) * 100
        df['net_profit_growth'] = df['net_profit'].pct_change(periods=4) * 100
        growth_title = "CÙNG KỲ NĂM TRƯỚC (YoY)"
    else:
        # QoQ: So sánh với quý liền kề trước đó (lùi 1 quý)
        df['revenue_growth'] = df['revenue'].pct_change(periods=1) * 100
        df['net_profit_growth'] = df['net_profit'].pct_change(periods=1) * 100
        growth_title = "QUÝ LIỀN KỀ (QoQ)"

    # Cắt lấy đúng top_n_periods kỳ gần nhất để vẽ
    df_plot = df.tail(top_n_periods).reset_index(drop=True)

    # Quy đổi về Tỷ VNĐ
    df_plot['revenue_billion'] = df_plot['revenue'] / 1e9
    df_plot['net_profit_billion'] = df_plot['net_profit'] / 1e9

    # 2. KHỞI TẠO BIỂU ĐỒ 2 SUBPLOT (Số tuyệt đối ở trên & Tỷ lệ % tăng trưởng ở dưới)
    fig, (ax1, ax3) = plt.subplots(
        2, 1, figsize=(11, 8), dpi=120, sharex=True, 
        gridspec_kw={'height_ratios': [2.2, 1]}
    )

    # --- SUBPLOT 1: Doanh thu & Lợi nhuận (Tỷ VNĐ) ---
    bars = ax1.bar(
        df_plot['period'], df_plot['revenue_billion'], 
        color='#1f77b4', alpha=0.8, width=0.4, label='Doanh thu thuần (Tỷ VNĐ)'
    )
    ax1.set_ylabel('Doanh thu (Tỷ VNĐ)', color='#1f77b4', fontsize=10, fontweight='bold')
    ax1.tick_params(axis='y', labelcolor='#1f77b4')

    ax2 = ax1.twinx()
    ax2.plot(
        df_plot['period'], df_plot['net_profit_billion'], 
        color='#2ca02c', marker='o', linewidth=2, label='LNST (Tỷ VNĐ)'
    )
    ax2.set_ylabel('Lợi nhuận (Tỷ VNĐ)', color='#2ca02c', fontsize=10, fontweight='bold')
    ax2.tick_params(axis='y', labelcolor='#2ca02c')

    # Nhãn số liệu cho Doanh thu & Lợi nhuận
    for bar in bars:
        h = bar.get_height()
        if not pd.isna(h) and h != 0:
            ax1.annotate(f'{h:,.0f}', (bar.get_x() + bar.get_width()/2, h), xytext=(0, 3), 
                         textcoords="offset points", ha='center', va='bottom', fontsize=8)

    for i, txt in enumerate(df_plot['net_profit_billion']):
        if not pd.isna(txt):
            ax2.annotate(f'{txt:,.0f}', (df_plot['period'][i], txt), xytext=(0, 5), 
                         textcoords="offset points", ha='center', va='bottom', fontsize=8, color='#1e711e', fontweight='bold')

    ax1.set_title(f'KẾT QUẢ KINH DOANH & TỐC ĐỘ TĂNG TRƯỞNG {growth_title} - MÃ [{symbol}]', fontsize=12, fontweight='bold', pad=12)

    # --- SUBPLOT 2: Tốc độ tăng trưởng % (YoY/QoQ) ---
    ax3.plot(df_plot['period'], df_plot['revenue_growth'], color='#ff7f0e', marker='s', linestyle='--', linewidth=1.8, label='Tăng trưởng Doanh thu (%)')
    ax3.plot(df_plot['period'], df_plot['net_profit_growth'], color='#d62728', marker='^', linestyle='-', linewidth=2, label='Tăng trưởng LNST (%)')
    ax3.axhline(0, color='gray', linestyle=':', linewidth=1)  # Mốc 0%
    
    ax3.set_ylabel('Tăng trưởng (%)', fontsize=10, fontweight='bold')
    ax3.set_xlabel('Kỳ Báo Cáo', fontsize=10, labelpad=8)
    ax3.tick_params(axis='x', rotation=30)

    # Nhãn số liệu cho Tỷ lệ % tăng trưởng
    for i in range(len(df_plot)):
        rev_g = df_plot['revenue_growth'][i]
        np_g = df_plot['net_profit_growth'][i]
        
        if not pd.isna(rev_g):
            ax3.annotate(f'{rev_g:+.1f}%', (df_plot['period'][i], rev_g), xytext=(0, -12), 
                         textcoords="offset points", ha='center', va='top', fontsize=8, color='#cc6600')
        if not pd.isna(np_g):
            ax3.annotate(f'{np_g:+.1f}%', (df_plot['period'][i], np_g), xytext=(0, 6), 
                         textcoords="offset points", ha='center', va='bottom', fontsize=8, color='#a71d1d', fontweight='bold')

    # Hiển thị chú thích (Legend)
    lines_1, labels_1 = ax1.get_legend_handles_labels()
    lines_2, labels_2 = ax2.get_legend_handles_labels()
    ax1.legend(lines_1 + lines_2, labels_1 + labels_2, loc='upper left', frameon=True)
    ax3.legend(loc='upper left', frameon=True)

    plt.tight_layout()
    plt.show()


if __name__ == "__main__":
    # Test thử trên mã FPT với dữ liệu phẳng từ SQLite
    plot_financial_performance_with_growth(symbol='FPT', db_path='data/financial_database.db', top_n_periods=8, growth_type='YoY')