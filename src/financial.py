import pathlib
import re
import pandas as pd
import plotly.express as px
import streamlit as st

st.set_page_config(page_title="Phân Tích BCTC - Financial Parquet", layout="wide")
st.title("📊 Báo Cáo Tài Chính Theo Năm & Chỉ Số")


@st.cache_data
def load_financial_parquet_data():
    current_dir = pathlib.Path(__file__).parent.resolve()

    # Tìm đường dẫn đến thư mục chứa dữ liệu parquet
    path = current_dir.parent / "data" / "financial_parquet"
    if not path.exists():
        path = current_dir.parent / "data" / "financial_full"

    if not path.exists():
        st.error(f"Không tìm thấy thư mục dữ liệu tại: `{path}`")
        return pd.DataFrame()

    parquet_files = list(path.rglob("*.parquet")) + list(path.rglob("*.PARQUET"))
    parquet_files = list(set(parquet_files))

    if not parquet_files:
        st.warning(f"Thư mục `{path}` không chứa tệp `.parquet` nào.")
        return pd.DataFrame()

    data_list = []
    for file in parquet_files:
        try:
            df_temp = pd.read_parquet(file)

            # Lấy tên mã cổ phiếu từ đường dẫn tệp hoặc tên tệp
            symbol_match = re.search(r"symbol=([A-Za-z0-9]+)", str(file))
            if symbol_match:
                ticker_val = symbol_match.group(1).upper()
            else:
                ticker_val = file.name.split("_")[0].upper()

            if "ticker" not in df_temp.columns and "symbol" not in df_temp.columns:
                df_temp["ticker"] = ticker_val
            elif "symbol" in df_temp.columns and "ticker" not in df_temp.columns:
                df_temp["ticker"] = df_temp["symbol"]

            data_list.append(df_temp)
        except Exception as e:
            st.warning(f"Không thể đọc tệp {file.name}: {e}")

    if data_list:
        return pd.concat(data_list, ignore_index=True)
    return pd.DataFrame()


df = load_financial_parquet_data()

if not df.empty:
    df.columns = df.columns.astype(str)

    st.sidebar.header("⚙️ Bộ Lọc Dữ Liệu")
    cols = df.columns.tolist()

    # Tự động nhận diện cột Ticker và Năm
    ticker_col = (
        "ticker"
        if "ticker" in cols
        else st.sidebar.selectbox("Cột Mã Cổ Phiếu:", cols)
    )

    keywords = ["year", "nam", "period", "date"]
    year_candidates = [c for c in cols if any(k in c.lower() for k in keywords)]

    year_col = st.sidebar.selectbox(
        "Cột Năm/Thời Gian:",
        cols,
        index=cols.index(year_candidates[0]) if year_candidates else 0,
    )

    df[ticker_col] = df[ticker_col].astype(str)
    tickers_list = sorted(df[ticker_col].unique().tolist())

    # Chọn mặc định mã đầu tiên hoặc FPT
    default_ticker = [t for t in ["FPT"] if t in tickers_list] or (
        tickers_list[:1] if tickers_list else []
    )

    selected_tickers = st.sidebar.multiselect(
        "Chọn Mã Cổ Phiếu (So sánh/Trực quan):",
        tickers_list,
        default=default_ticker,
    )

    years_list = sorted(df[year_col].dropna().unique().tolist())
    if years_list:
        selected_years = st.sidebar.select_slider(
            "Khoảng Năm:",
            options=years_list,
            value=(years_list[0], years_list[-1]),
        )
        filtered_df = df[
            (df[ticker_col].isin(selected_tickers))
            & (df[year_col] >= selected_years[0])
            & (df[year_col] <= selected_years[1])
        ]
    else:
        filtered_df = df[df[ticker_col].isin(selected_tickers)]

    # Lọc lấy các cột chứa chỉ số tài chính kiểu số
    numeric_cols = df.select_dtypes(
        include=["float64", "int64", "float32", "int32"]
    ).columns.tolist()
    if year_col in numeric_cols:
        numeric_cols.remove(year_col)

    # Giao diện các Tab chính
    tab_bctc, tab_line, tab_bar = st.tabs(
        ["📄 Bảng BCTC Theo Năm", "📈 Biểu Đồ Xu Hướng", "📊 Biểu Đồ So Sánh"]
    )

    # ================= TAB 1: BCTC Dạng Bảng Chuẩn =================
    with tab_bctc:
        st.subheader("📋 Báo Cáo Tài Chính Tổng Hợp")

        col_select1, col_select2 = st.columns([1, 3])

        with col_select1:
            selected_single_ticker = st.selectbox(
                "Chọn Mã Cổ Phiếu:",
                options=tickers_list,
                index=tickers_list.index(selected_tickers[0])
                if selected_tickers
                else 0,
            )

        with col_select2:
            # Cho phép chọn chỉ số (mặc định chọn toàn bộ)
            selected_metrics_list = st.multiselect(
                "Lọc Tiêu Chí / Chỉ Số Cần Hiển Thị:",
                options=numeric_cols,
                default=numeric_cols,
            )

        # Lọc dữ liệu cho mã được chọn và khoảng thời gian đã chọn
        df_single = df[
            (df[ticker_col] == selected_single_ticker)
            & (df[year_col] >= selected_years[0])
            & (df[year_col] <= selected_years[1])
        ].copy()

        if not df_single.empty and selected_metrics_list:
            # Xử lý trường hợp có nhiều bản ghi trùng lặp trong cùng 1 năm
            df_single = df_single.groupby(year_col, as_index=False).first()

            # Chuyển đổi dữ liệu từ dạng rộng (Wide) sang dạng dọc (Long)
            df_melted = df_single.melt(
                id_vars=[year_col],
                value_vars=selected_metrics_list,
                var_name="Tiêu Chí / Chỉ Số",
                value_name="Giá Trị",
            )

            # Xoay bảng dữ liệu (Pivot): Tiêu chí ở Dòng, Năm ở Cột
            bctc_pivot = df_melted.pivot_table(
                index="Tiêu Chí / Chỉ Số",
                columns=year_col,
                values="Giá Trị",
                aggfunc="first",
            )

            # Sắp xếp các năm tăng dần trên các cột
            bctc_pivot = bctc_pivot.reindex(
                columns=sorted(bctc_pivot.columns)
            )

            # Hiển thị bảng dữ liệu định dạng số chuẩn tài chính
            st.dataframe(
                bctc_pivot.style.format(
                    "{:,.2f}", na_rep="-"
                ),
                use_container_width=True,
                height=600,
            )
        else:
            st.info("Vui lòng chọn mã cổ phiếu và ít nhất một chỉ số để hiển thị BCTC.")

    # ================= TAB 2: Biểu Đồ Xu Hướng =================
    with tab_line:
        st.subheader("📈 Xu Hướng Chỉ Số Qua Các Năm")
        selected_metric = st.selectbox(
            "Chọn Chỉ Số Cần Xem Xu Hướng:", numeric_cols, key="line_metric"
        )

        if selected_metric and not filtered_df.empty:
            fig_line = px.line(
                filtered_df,
                x=year_col,
                y=selected_metric,
                color=ticker_col,
                markers=True,
                title=f"Xu Hướng {selected_metric} Qua Các Năm",
            )
            fig_line.update_layout(hovermode="x unified")
            st.plotly_chart(fig_line, use_container_width=True)

    # ================= TAB 3: Biểu Đồ So Sánh =================
    with tab_bar:
        st.subheader("📊 So Sánh Giữa Các Cổ Phiếu")
        selected_metric_bar = st.selectbox(
            "Chọn Chỉ Số Cần So Sánh:", numeric_cols, key="bar_metric"
        )

        if selected_metric_bar and not filtered_df.empty:
            fig_bar = px.bar(
                filtered_df,
                x=year_col,
                y=selected_metric_bar,
                color=ticker_col,
                barmode="group",
                title=f"So Sánh {selected_metric_bar} Giữa Các Mã Cổ Phiếu Được Chọn",
            )
            st.plotly_chart(fig_bar, use_container_width=True)