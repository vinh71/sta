import streamlit as st
import pandas as pd
import numpy as np
import requests
from io import BytesIO
from pathlib import Path


@st.cache_data(show_spinner=True)
def load_data(excel_path: str) -> pd.DataFrame:
    """
    Đọc dữ liệu từ:
    - Đường dẫn local (nếu excel_path không rỗng)
    - Hoặc URL Google Sheets (nếu excel_path rỗng)
    """
    GSHEET_URL = (
        "https://docs.google.com/spreadsheets/d/"
        "1UgZ3gP8Ubbgb8-lMYGWnBSvl1jCfIE4Q/export?format=xlsx"
    )

    try:
        if excel_path:
            path = Path(excel_path)
            if not path.exists():
                st.error(f"File dữ liệu không tồn tại: {path}")
                return pd.DataFrame()
            df = pd.read_excel(path, engine="openpyxl")
        else:
            # Đọc từ Google Sheets (xuất xlsx)
            resp = requests.get(GSHEET_URL)
            resp.raise_for_status()
            df = pd.read_excel(BytesIO(resp.content), engine="openpyxl")
    except Exception as e:
        st.error(f"Lỗi khi đọc dữ liệu: {e}")
        return pd.DataFrame()

    # Chuẩn hóa một số cột quan trọng nếu tồn tại
    # Định lượng -> numeric
    if "Định lượng" in df.columns:
        df["Định_lượng_numeric"] = pd.to_numeric(df["Định lượng"], errors="coerce")
    else:
        df["Định_lượng_numeric"] = np.nan

    # VALUE EXL VAT, VOLUME -> numeric
    if "VALUE EXL VAT" in df.columns:
        df["VALUE_EXL_VAT_numeric"] = pd.to_numeric(df["VALUE EXL VAT"], errors="coerce")
    else:
        df["VALUE_EXL_VAT_numeric"] = np.nan

    if "VOLUME" in df.columns:
        df["VOLUME_numeric"] = pd.to_numeric(df["VOLUME"], errors="coerce")
    else:
        df["VOLUME_numeric"] = np.nan

    # Tính Unit_Price nếu chưa có
    if "Unit_Price" not in df.columns:
        with np.errstate(divide="ignore", invalid="ignore"):
            df["Unit_Price"] = df["VALUE_EXL_VAT_numeric"] / df["VOLUME_numeric"]

    # Chuẩn hóa UNIT để lọc KG nếu cần
    if "UNIT" in df.columns:
        df["UNIT_normalized"] = df["UNIT"].astype(str).str.strip().str.upper()
    else:
        df["UNIT_normalized"] = np.nan

    return df


def filter_data(
    df: pd.DataFrame,
    p1_values,
    p2_values,
    brand_values,
    month_values,
    dinh_luong_range,
    only_kg: bool,
    remove_related_true: bool,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    if df.empty:
        return df, df

    mask = pd.Series(True, index=df.index)

    if p1_values and "P1" in df.columns:
        mask &= df["P1"].isin(p1_values)

    if p2_values and "P2" in df.columns:
        mask &= df["P2"].isin(p2_values)

    if brand_values and "BRAND" in df.columns:
        mask &= df["BRAND"].isin(brand_values)

    if month_values and "Month" in df.columns:
        mask &= df["Month"].isin(month_values)

    # Định lượng range
    if "Định_lượng_numeric" in df.columns and dinh_luong_range is not None:
        lo, hi = dinh_luong_range
        mask &= df["Định_lượng_numeric"].between(lo, hi)

    # Chỉ lấy UNIT là KG
    if only_kg and "UNIT_normalized" in df.columns:
        kg_variants = ["KG", "KILOGRAM", "KILO", "KGS"]
        mask &= df["UNIT_normalized"].isin(kg_variants)

    # Loại bỏ RELATED = TRUE
    if remove_related_true and "RELATED" in df.columns:
        mask &= ~(
            (df["RELATED"] == True)
            | (df["RELATED"] == "TRUE")
            | (df["RELATED"] == 1)
            | (df["RELATED"] == 1.0)
        )

    filtered_all = df[mask].copy()

    # Loại bỏ các giao dịch không tính được Unit_Price (dùng cho bảng giá)
    filtered_valid = filtered_all
    if "Unit_Price" in filtered_valid.columns:
        filtered_valid = filtered_valid[filtered_valid["Unit_Price"].notna()].copy()

    return filtered_valid, filtered_all


def calculate_price_stats(group: pd.DataFrame) -> pd.Series:
    prices = group["Unit_Price"].dropna()
    if len(prices) == 0:
        return pd.Series(
            {
                "Price_Highest": np.nan,
                "Price_Lowest": np.nan,
                "Price_Avg_Formula": np.nan,
                "Transaction_Count": 0,
            }
        )

    # Loại bỏ 5% nhiễu đầu và cuối (nếu đủ dữ liệu)
    n_remove = max(1, int(len(prices) * 0.05))
    prices_cleaned = prices.sort_values()
    if len(prices_cleaned) > 2 * n_remove:
        prices_cleaned = prices_cleaned.iloc[n_remove:-n_remove]

    total_value = group["VALUE_EXL_VAT_numeric"].sum()
    total_volume = group["VOLUME_numeric"].sum()
    avg_price_formula = total_value / total_volume if total_volume > 0 else np.nan

    return pd.Series(
        {
            "Price_Highest": prices_cleaned.max() if len(prices_cleaned) > 0 else np.nan,
            "Price_Lowest": prices_cleaned.min() if len(prices_cleaned) > 0 else np.nan,
            "Price_Avg_Formula": avg_price_formula,
            "Transaction_Count": len(group),
        }
    )


def main():
    st.set_page_config(
        page_title="Stavian Market Dashboard",
        layout="wide",
    )

    st.title("Bảng giá thị trường và thống kê sellers")
    st.caption(
        "Dashboard tương tác cho phép lọc theo P1, P2, BRAND, Định lượng, Month và xem bảng giá thị trường, doanh thu theo seller."
    )

    # Sidebar: chọn file dữ liệu (mặc định là Database_updated_2112.xlsx trong cùng thư mục)
    default_path = "Database_updated_2112.xlsx"
    st.sidebar.header("Thiết lập dữ liệu")
    data_path = st.sidebar.text_input("Đường dẫn file Excel dữ liệu", value=default_path)

    df = load_data(data_path)
    if df.empty:
        st.stop()

    st.sidebar.header("Bộ lọc")

    # P1 filter
    p1_options = sorted(df["P1"].dropna().unique()) if "P1" in df.columns else []
    # Không chọn sẵn để tránh áp filter mặc định
    p1_values = st.sidebar.multiselect("P1", options=p1_options, default=[])

    # P2 filter
    p2_options = sorted(df["P2"].dropna().unique()) if "P2" in df.columns else []
    p2_values = st.sidebar.multiselect("P2", options=p2_options, default=[])

    # BRAND filter
    brand_options = sorted(df["BRAND"].dropna().unique()) if "BRAND" in df.columns else []
    brand_values = st.sidebar.multiselect(
        "BRAND", options=brand_options, default=[]
    )

    # Month filter
    month_options = sorted(df["Month"].dropna().unique()) if "Month" in df.columns else []
    month_values = st.sidebar.multiselect(
        "Tháng", options=month_options, default=[]
    )

    # Tùy chọn bật filter định lượng
    dinh_luong_range = None
    enable_dl_filter = st.sidebar.checkbox("Bật filter Định lượng (gsm)", value=False)
    if enable_dl_filter and df["Định_lượng_numeric"].notna().any():
        dl_min = int(df["Định_lượng_numeric"].min())
        dl_max = int(df["Định_lượng_numeric"].max())
        dinh_luong_range = st.sidebar.slider(
            "Định lượng (gsm)",
            min_value=dl_min,
            max_value=dl_max,
            value=(dl_min, dl_max),
        )

    only_kg = st.sidebar.checkbox("Chỉ lấy đơn vị KG", value=True)
    remove_related_true = st.sidebar.checkbox("Loại bỏ RELATED = TRUE", value=True)

    filtered_valid, filtered_all = filter_data(
        df,
        p1_values=p1_values,
        p2_values=p2_values,
        brand_values=brand_values,
        month_values=month_values,
        dinh_luong_range=dinh_luong_range,
        only_kg=only_kg,
        remove_related_true=remove_related_true,
    )

    st.subheader("Tổng quan dữ liệu sau khi lọc")
    col1, col2, col3, col4 = st.columns(4)
    # Số dòng không loại bỏ các giao dịch thiếu Unit_Price
    col1.metric("Số dòng", f"{len(filtered_all):,}")
    if "SELLER ID" in filtered_all.columns:
        col2.metric("Số sellers", f"{filtered_all['SELLER ID'].nunique():,}")
    elif "SELLER" in filtered_all.columns:
        col2.metric("Số sellers", f"{filtered_all['SELLER'].nunique():,}")
    if "BUYER NAME" in filtered_all.columns:
        col3.metric("Số buyers", f"{filtered_all['BUYER NAME'].nunique():,}")
    if "Month" in filtered_all.columns:
        col4.metric("Số tháng", f"{filtered_all['Month'].nunique():,}")

    if filtered_valid.empty:
        st.warning("Không có dữ liệu sau khi áp dụng các bộ lọc.")
        st.stop()

    # Bảng giá thị trường theo Seller x Month
    st.markdown("### Bảng giá theo Seller và Tháng")
    if {"SELLER", "Month", "Unit_Price"}.issubset(filtered_valid.columns):
        price_stats = (
            filtered_valid.groupby(["SELLER", "Month"])
            .apply(calculate_price_stats)
            .reset_index()
        )

        # Làm tròn để hiển thị
        for col in ["Price_Highest", "Price_Lowest", "Price_Avg_Formula"]:
            price_stats[col] = price_stats[col].round(0)

        st.dataframe(
            price_stats.sort_values(["Month", "SELLER"]),
            use_container_width=True,
        )
    else:
        st.info("Thiếu một trong các cột: SELLER, Month, Unit_Price.")

    # Giá thị trường (trung bình các sellers) theo tháng
    st.markdown("### Giá thị trường (trung bình các sellers) theo tháng")
    if {"SELLER", "Month"}.issubset(filtered_valid.columns):
        market_rows = []
        for m in sorted(filtered_valid["Month"].dropna().unique()):
            month_data = filtered_valid[filtered_valid["Month"] == m]
            seller_stats = (
                month_data.groupby("SELLER")
                .apply(calculate_price_stats)
                .reset_index()
            )
            if len(seller_stats) == 0:
                continue
            market_rows.append(
                {
                    "Month": m,
                    "Price_Highest": seller_stats["Price_Highest"].mean(),
                    "Price_Avg_Formula": seller_stats["Price_Avg_Formula"].mean(),
                    "Price_Lowest": seller_stats["Price_Lowest"].mean(),
                }
            )

        if market_rows:
            market_df = pd.DataFrame(market_rows)
            market_df[["Price_Highest", "Price_Avg_Formula", "Price_Lowest"]] = (
                market_df[["Price_Highest", "Price_Avg_Formula", "Price_Lowest"]].round(
                    0
                )
            )
            st.dataframe(
                market_df.sort_values("Month"),
                use_container_width=True,
            )
        else:
            st.info("Không có đủ dữ liệu để tính giá thị trường.")

    # Thống kê doanh thu sellers
    st.markdown("### Thống kê doanh thu của các sellers")
    if "SELLER" in filtered_valid.columns:
        seller_stats = (
            filtered_valid.groupby("SELLER").agg(
                Total_Value=("VALUE_EXL_VAT_numeric", "sum"),
                Total_Volume=("VOLUME_numeric", "sum"),
                Invoice_Count=("INV NO.", "nunique")
                if "INV NO." in filtered_valid.columns
                else ("Unit_Price", "count"),
                Buyer_Count=("BUYER NAME", "nunique")
                if "BUYER NAME" in filtered_valid.columns
                else ("Unit_Price", "count"),
            )
        ).reset_index()

        seller_stats["Total_Value"] = seller_stats["Total_Value"].round(0).astype("Int64")
        seller_stats["Total_Volume"] = (
            seller_stats["Total_Volume"].round(0).astype("Int64")
        )

        st.dataframe(
            seller_stats.sort_values("Total_Value", ascending=False),
            use_container_width=True,
        )

        # Nút tải xuống
        csv_bytes = seller_stats.to_csv(index=False).encode("utf-8-sig")
        st.download_button(
            label="Tải thống kê sellers (CSV)",
            data=csv_bytes,
            file_name="seller_stats_filtered.csv",
            mime="text/csv",
        )
    else:
        st.info("Thiếu cột SELLER trong dữ liệu.")


if __name__ == "__main__":
    main()


