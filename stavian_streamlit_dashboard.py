import streamlit as st
import pandas as pd
import numpy as np
import requests
from io import BytesIO
from pathlib import Path


# URL tải thẳng từ OneDrive/SharePoint
# File ID từ link SharePoint
FILE_ID = "IQAQAcg4aM2VT72GrMwPOZHYAToD1lpS-cKsOzmT3xoj91I"
BASE_URL = "https://stneuedu-my.sharepoint.com/personal/11230786_st_neu_edu_vn"

# Thử nhiều format URL khác nhau để tải file
ONEDRIVE_URLS = [
    # Format 1: :x:/r/ với ?download=1
    f"https://stneuedu-my.sharepoint.com/:x:/r/personal/11230786_st_neu_edu_vn/{FILE_ID}?download=1",
    # Format 2: :x:/e/ với ?download=1  
    f"https://stneuedu-my.sharepoint.com/:x:/e/personal/11230786_st_neu_edu_vn/{FILE_ID}?download=1",
    # Format 3: :x:/g/ với ?download=1
    f"https://stneuedu-my.sharepoint.com/:x:/g/personal/11230786_st_neu_edu_vn/{FILE_ID}?download=1",
    # Format 4: Link gốc với ?download=1
    f"https://stneuedu-my.sharepoint.com/:x:/g/personal/11230786_st_neu_edu_vn/{FILE_ID}?e=qa2xF1&download=1",
]


@st.cache_data(show_spinner=True)
def load_data(excel_path: str | None = None) -> pd.DataFrame:
    """
    Đọc dữ liệu:
    - Nếu excel_path có giá trị: ưu tiên đọc local (chỉ khi chạy trên máy có file).
    - Nếu excel_path rỗng: đọc từ OneDrive link tải thẳng. Nếu lỗi, thử URL ALT.
    """
    try:
        if excel_path:
            path = Path(excel_path)
            if not path.exists():
                st.error(f"File dữ liệu không tồn tại: {path}")
                return pd.DataFrame()
            df = pd.read_excel(path, engine="openpyxl")
        else:
            # Headers để giả lập browser request, tránh lỗi 403
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                'Accept': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet, application/vnd.ms-excel, */*'
            }
            
            last_error = None
            # Thử từng format URL cho đến khi tìm được format hoạt động
            for url_idx, url in enumerate(ONEDRIVE_URLS):
                try:
                    # Cho phép redirect và kiểm tra response
                    resp = requests.get(url, headers=headers, allow_redirects=True, timeout=30)
                    resp.raise_for_status()
                    
                    # Kiểm tra content-type để đảm bảo là file Excel
                    content_type = resp.headers.get('Content-Type', '').lower()
                    
                    # Kiểm tra nếu response là HTML (thường là trang đăng nhập hoặc lỗi)
                    if 'html' in content_type:
                        # Kiểm tra nội dung để xác nhận là HTML
                        content_preview = resp.content[:500].decode('utf-8', errors='ignore').lower()
                        if '<html' in content_preview or '<!doctype' in content_preview:
                            last_error = f"URL {url_idx + 1} trả về HTML thay vì file Excel"
                            continue  # Thử URL tiếp theo
                    
                    # Thử đọc file Excel
                    try:
                        df = pd.read_excel(BytesIO(resp.content), engine="openpyxl")
                        if not df.empty:
                            st.success(f"Đã tải dữ liệu thành công từ URL format {url_idx + 1}")
                            return df
                    except Exception as excel_error:
                        last_error = f"URL {url_idx + 1}: Không thể đọc file Excel - {str(excel_error)}"
                        continue  # Thử URL tiếp theo
                        
                except requests.exceptions.RequestException as req_error:
                    last_error = f"URL {url_idx + 1}: Lỗi kết nối - {str(req_error)}"
                    continue  # Thử URL tiếp theo
                except Exception as e:
                    last_error = f"URL {url_idx + 1}: {str(e)}"
                    continue  # Thử URL tiếp theo
            
            # Nếu tất cả URL đều thất bại
            st.error(f"Không thể tải dữ liệu từ SharePoint. Đã thử {len(ONEDRIVE_URLS)} format URL khác nhau.")
            st.info("💡 Gợi ý: Vui lòng kiểm tra:\n"
                   "- Link SharePoint có quyền truy cập công khai không\n"
                   "- Thử lấy link download trực tiếp từ SharePoint (Right-click file → Copy link → Chọn 'Anyone with the link')\n"
                   "- Hoặc upload file lên nơi khác có link download công khai")
            if last_error:
                st.warning(f"Lỗi cuối cùng: {last_error}")
            return pd.DataFrame()
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


def get_filtered_data_for_options(
    df: pd.DataFrame,
    p1_values,
    p2_values,
    brand_values,
    month_values,
    city_values,
    only_kg: bool,
    remove_related_true: bool,
    remove_related_false: bool,
) -> pd.DataFrame:
    """
    Lấy dữ liệu đã được filter bởi các filter đã chọn (trừ định lượng).
    Dùng để tính min/max cho các filter khác phụ thuộc vào nhau.
    """
    if df.empty:
        return df
    
    mask = pd.Series(True, index=df.index)
    
    if p1_values and "P1" in df.columns:
        mask &= df["P1"].isin(p1_values)
    
    if p2_values and "P2" in df.columns:
        mask &= df["P2"].isin(p2_values)
    
    if brand_values and "BRAND" in df.columns:
        mask &= df["BRAND"].isin(brand_values)
    
    if month_values and "Month" in df.columns:
        mask &= df["Month"].isin(month_values)
    
    if city_values and "REGION" in df.columns:
        mask &= df["REGION"].isin(city_values)
    
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
    
    # Loại bỏ RELATED = FALSE
    if remove_related_false and "RELATED" in df.columns:
        mask &= ~(
            (df["RELATED"] == False)
            | (df["RELATED"] == "FALSE")
            | (df["RELATED"] == 0)
            | (df["RELATED"] == 0.0)
        )
    
    return df[mask].copy()


def filter_data(
    df: pd.DataFrame,
    p1_values,
    p2_values,
    brand_values,
    month_values,
    city_values,
    dinh_luong_range,
    only_kg: bool,
    remove_related_true: bool,
    remove_related_false: bool,
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

    if city_values and "REGION" in df.columns:
        mask &= df["REGION"].isin(city_values)

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

    # Loại bỏ RELATED = FALSE
    if remove_related_false and "RELATED" in df.columns:
        mask &= ~(
            (df["RELATED"] == False)
            | (df["RELATED"] == "FALSE")
            | (df["RELATED"] == 0)
            | (df["RELATED"] == 0.0)
        )

    filtered_all = df[mask].copy()

    # Loại bỏ các giao dịch không tính được Unit_Price (dùng cho bảng giá)
    filtered_valid = filtered_all
    if "Unit_Price" in filtered_valid.columns:
        filtered_valid = filtered_valid[filtered_valid["Unit_Price"].notna()].copy()

    return filtered_valid, filtered_all


def create_column_filter_ui(df: pd.DataFrame, table_name: str, numeric_cols: list, text_cols: list = None, include_unit_price_filter: bool = False) -> dict:
    """
    Tạo UI filter cho các cột số ngay trên bảng.
    
    Args:
        df: DataFrame để lấy min/max values
        table_name: Tên bảng (dùng làm key cho session state)
        numeric_cols: Danh sách các cột số cần filter
        text_cols: Danh sách các cột text cần filter (optional)
        include_unit_price_filter: Có thêm filter Unit_Price với slider và input không (optional)
    
    Returns:
        Dictionary chứa filter config
    """
    filter_config = {}
    
    # Tạo expander cho filter
    with st.expander("🔍 Filter", expanded=False):
        cols = st.columns(min(len(numeric_cols), 4))  # Tối đa 4 cột mỗi hàng
        
        for idx, col_name in enumerate(numeric_cols):
            if col_name not in df.columns:
                continue
                
            col_idx = idx % 4
            with cols[col_idx]:
                st.write(f"**{col_name}**")
                
                filter_type = st.selectbox(
                    f"Loại filter:",
                    ["Không filter", "Greater than (>)", "Less than (<)", "Between"],
                    key=f"filter_type_{table_name}_{col_name}"
                )
                
                if filter_type != "Không filter":
                    if filter_type == "Greater than (>)":
                        col_min_val = float(df[col_name].min()) if df[col_name].notna().any() else 0.0
                        filter_value_str = st.text_input(
                            f"Giá trị:",
                            value=str(int(col_min_val)) if col_min_val == int(col_min_val) else str(col_min_val),
                            key=f"filter_value_{table_name}_{col_name}",
                            help="Nhập số (có thể nhập nhiều số cùng lúc)"
                        )
                        try:
                            filter_value = float(filter_value_str) if filter_value_str else col_min_val
                            filter_config[col_name] = {"type": filter_type, "value": filter_value}
                        except ValueError:
                            st.warning("Vui lòng nhập số hợp lệ")
                    elif filter_type == "Less than (<)":
                        col_max_val = float(df[col_name].max()) if df[col_name].notna().any() else 1000000.0
                        filter_value_str = st.text_input(
                            f"Giá trị:",
                            value=str(int(col_max_val)) if col_max_val == int(col_max_val) else str(col_max_val),
                            key=f"filter_value_{table_name}_{col_name}",
                            help="Nhập số (có thể nhập nhiều số cùng lúc)"
                        )
                        try:
                            filter_value = float(filter_value_str) if filter_value_str else col_max_val
                            filter_config[col_name] = {"type": filter_type, "value": filter_value}
                        except ValueError:
                            st.warning("Vui lòng nhập số hợp lệ")
                    elif filter_type == "Between":
                        col_min_val = float(df[col_name].min()) if df[col_name].notna().any() else 0.0
                        col_max_val = float(df[col_name].max()) if df[col_name].notna().any() else 1000000.0
                        col_min_str = st.text_input(
                            f"Từ:",
                            value=str(int(col_min_val)) if col_min_val == int(col_min_val) else str(col_min_val),
                            key=f"filter_min_{table_name}_{col_name}",
                            help="Nhập số (có thể nhập nhiều số cùng lúc)"
                        )
                        col_max_str = st.text_input(
                            f"Đến:",
                            value=str(int(col_max_val)) if col_max_val == int(col_max_val) else str(col_max_val),
                            key=f"filter_max_{table_name}_{col_name}",
                            help="Nhập số (có thể nhập nhiều số cùng lúc)"
                        )
                        try:
                            col_min = float(col_min_str) if col_min_str else col_min_val
                            col_max = float(col_max_str) if col_max_str else col_max_val
                            filter_config[col_name] = {"type": "Between", "min": col_min, "max": col_max}
                        except ValueError:
                            st.warning("Vui lòng nhập số hợp lệ")
        
        # Thêm filter text nếu có
        if text_cols:
            text_filters = create_text_filter_ui(df, table_name, text_cols)
            filter_config.update(text_filters)
        
        # Thêm filter Unit_Price với slider và input nếu có
        if include_unit_price_filter:
            unit_price_filter = create_unit_price_filter_ui(df, table_name)
            filter_config.update(unit_price_filter)
    
    return filter_config


def format_number_with_commas(value):
    """
    Format số với dấu phẩy ngăn cách hàng nghìn.
    Ví dụ: 1000 -> "1,000", 282909.5 -> "282,909.5", 282909.50 -> "282,909.5"
    """
    if pd.isna(value):
        return ""
    try:
        # Chuyển sang float để xử lý
        float_val = float(value)
        
        # Nếu là số nguyên, format không có phần thập phân
        if float_val.is_integer():
            return f"{int(float_val):,}"
        else:
            # Nếu là số thập phân, format với phần thập phân (tối đa 2 chữ số)
            formatted = f"{float_val:,.2f}"
            # Loại bỏ số 0 thừa ở cuối
            if '.' in formatted:
                formatted = formatted.rstrip('0').rstrip('.')
            return formatted
    except (ValueError, TypeError, AttributeError):
        return str(value)


def format_dataframe_numbers(df: pd.DataFrame, numeric_cols: list) -> pd.DataFrame:
    """
    Format các cột số trong DataFrame với dấu phẩy ngăn cách hàng nghìn.
    Tạo bản copy để không ảnh hưởng đến dữ liệu gốc.
    """
    df_formatted = df.copy()
    for col in numeric_cols:
        if col in df_formatted.columns:
            df_formatted[col] = df_formatted[col].apply(format_number_with_commas)
    return df_formatted


def create_unit_price_filter_ui(df: pd.DataFrame, table_name: str) -> dict:
    """
    Tạo UI filter cho Unit_Price với slider và 2 input đồng bộ.
    
    Args:
        df: DataFrame để lấy min/max values
        table_name: Tên bảng (dùng làm key cho session state)
    
    Returns:
        Dictionary chứa filter config cho Unit_Price
    """
    filter_config = {}
    
    if "Unit_Price_Avg" not in df.columns:
        return filter_config
    
    # Lấy min/max của Unit_Price_Avg
    unit_price_min = float(df["Unit_Price_Avg"].min()) if df["Unit_Price_Avg"].notna().any() else 0.0
    unit_price_max = float(df["Unit_Price_Avg"].max()) if df["Unit_Price_Avg"].notna().any() else 1000000.0
    
    # Làm tròn min/max
    unit_price_min = int(unit_price_min)
    unit_price_max = int(unit_price_max)
    
    st.markdown("---")
    st.markdown("**Filter Unit_Price_Avg:**")
    
    # Khởi tạo session state nếu chưa có
    slider_key = f"unit_price_slider_{table_name}"
    min_input_key = f"unit_price_min_input_{table_name}"
    max_input_key = f"unit_price_max_input_{table_name}"
    
    if slider_key not in st.session_state:
        st.session_state[slider_key] = (unit_price_min, unit_price_max)
    if min_input_key not in st.session_state:
        st.session_state[min_input_key] = unit_price_min
    if max_input_key not in st.session_state:
        st.session_state[max_input_key] = unit_price_max
    
    # Lấy giá trị hiện tại từ session state để khởi tạo widget
    current_slider_value = st.session_state[slider_key]
    current_min_input = st.session_state[min_input_key]
    current_max_input = st.session_state[max_input_key]
    
    # Kiểm tra và reset giá trị nếu nằm ngoài phạm vi hợp lệ
    if current_min_input < unit_price_min or current_min_input > unit_price_max:
        current_min_input = unit_price_min
        st.session_state[min_input_key] = current_min_input
    if current_max_input < unit_price_min or current_max_input > unit_price_max:
        current_max_input = unit_price_max
        st.session_state[max_input_key] = current_max_input
    if (current_slider_value[0] < unit_price_min or current_slider_value[0] > unit_price_max or
        current_slider_value[1] < unit_price_min or current_slider_value[1] > unit_price_max):
        current_slider_value = (unit_price_min, unit_price_max)
        st.session_state[slider_key] = current_slider_value
    
    # Xác định giá trị để hiển thị cho slider: ưu tiên input nếu đã thay đổi
    slider_init_value = (current_min_input, current_max_input)
    if min_input_key in st.session_state and max_input_key in st.session_state:
        input_min = st.session_state[min_input_key]
        input_max = st.session_state[max_input_key]
        # Đảm bảo giá trị nằm trong phạm vi hợp lệ
        input_min = max(unit_price_min, min(input_min, unit_price_max))
        input_max = max(unit_price_min, min(input_max, unit_price_max))
        # Đảm bảo min <= max
        if input_min > input_max:
            input_min = input_max
        if input_max < input_min:
            input_max = input_min
        slider_init_value = (int(input_min), int(input_max))
    
    # Đảm bảo slider_init_value nằm trong phạm vi
    slider_init_value = (
        max(unit_price_min, min(slider_init_value[0], unit_price_max)),
        max(unit_price_min, min(slider_init_value[1], unit_price_max))
    )
    
    # Tạo 2 cột: một cho slider, một cho input
    col1, col2 = st.columns([2, 1])
    
    with col1:
        # Slider
        slider_value = st.slider(
            "Khoảng giá Unit_Price_Avg:",
            min_value=unit_price_min,
            max_value=unit_price_max,
            value=slider_init_value,
            key=slider_key,
            help="Kéo thanh để chọn khoảng giá"
        )
    
    with col2:
        # Input cho giá trị min - sử dụng giá trị từ slider (đã được đảm bảo hợp lệ)
        min_input_value = max(unit_price_min, min(int(slider_value[0]), unit_price_max))
        min_input = st.number_input(
            "Từ:",
            min_value=unit_price_min,
            max_value=unit_price_max,
            value=min_input_value,
            key=min_input_key,
            help="Giá trị giới hạn dưới"
        )
        
        # Input cho giá trị max - sử dụng giá trị từ slider
        max_input = st.number_input(
            "Đến:",
            min_value=unit_price_min,
            max_value=unit_price_max,
            value=int(slider_value[1]),
            key=max_input_key,
            help="Giá trị giới hạn trên"
        )
        
        # Đảm bảo min <= max (chỉ hiển thị cảnh báo)
        if min_input > max_input:
            st.warning("Giá trị 'Từ' không được lớn hơn giá trị 'Đến'")
        if max_input < min_input:
            st.warning("Giá trị 'Đến' không được nhỏ hơn giá trị 'Từ'")
    
    # Sử dụng giá trị từ slider làm giá trị chính
    # Nếu input khác với slider, sử dụng input (sẽ được đồng bộ tự động ở lần rerun tiếp theo)
    if min_input != slider_value[0] or max_input != slider_value[1]:
        # Input đã được thay đổi, sử dụng giá trị từ input (đã được đảm bảo min <= max)
        final_min = min(min_input, max_input)
        final_max = max(min_input, max_input)
    else:
        # Sử dụng giá trị từ slider
        final_min = slider_value[0]
        final_max = slider_value[1]
    
    # Áp dụng filter
    if final_min != unit_price_min or final_max != unit_price_max:
        filter_config["Unit_Price_Avg"] = {
            "type": "Between",
            "min": float(final_min),
            "max": float(final_max)
        }
    
    return filter_config


def create_text_filter_ui(df: pd.DataFrame, table_name: str, text_cols: list) -> dict:
    """
    Tạo UI filter cho các cột text (SELLER, BUYER NAME).
    Hiển thị trong cùng expander với filter số (gọi từ trong expander).
    SELLER và BUYER NAME có mối liên hệ với nhau - khi chọn một bên, 
    danh sách bên kia sẽ được lọc theo các giá trị có liên quan.
    
    Args:
        df: DataFrame để lấy danh sách giá trị
        table_name: Tên bảng (dùng làm key cho session state)
        text_cols: Danh sách các cột text cần filter
    
    Returns:
        Dictionary chứa filter config
    """
    filter_config = {}
    
    if not text_cols:
        return filter_config
    
    # Hiển thị trong expander filter (cùng với filter số)
    st.markdown("---")
    st.markdown("**Filter theo tên:**")
    
    # Kiểm tra xem có cả SELLER và BUYER NAME không
    has_seller = "SELLER" in text_cols and "SELLER" in df.columns
    has_buyer = "BUYER NAME" in text_cols and "BUYER NAME" in df.columns
    
    # Tạo 2 cột cho SELLER và BUYER NAME
    filter_cols = st.columns(len(text_cols))
    
    # Lấy giá trị đã chọn từ session state (nếu có)
    selected_sellers = []
    selected_buyers = []
    
    if has_seller:
        seller_key = f"filter_text_{table_name}_SELLER"
        if seller_key in st.session_state:
            selected_sellers = st.session_state[seller_key]
    
    if has_buyer:
        buyer_key = f"filter_text_{table_name}_BUYER NAME"
        if buyer_key in st.session_state:
            selected_buyers = st.session_state[buyer_key]
    
    # Xử lý filter SELLER
    if has_seller:
        with filter_cols[0]:
            # Lọc danh sách SELLER dựa trên BUYER NAME đã chọn
            df_for_seller = df.copy()
            if selected_buyers:
                df_for_seller = df_for_seller[df_for_seller["BUYER NAME"].isin(selected_buyers)]
            
            seller_options = sorted(df_for_seller["SELLER"].dropna().unique().tolist())
            
            if len(seller_options) > 0:
                selected_sellers = st.multiselect(
                    "SELLER:",
                    options=seller_options,
                    default=selected_sellers if selected_sellers else [],
                    key=f"filter_text_{table_name}_SELLER",
                    help="Chọn các SELLER muốn hiển thị (sẽ tự động lọc theo BUYER NAME đã chọn)"
                )
                
                if selected_sellers:
                    filter_config["SELLER"] = {"type": "in", "values": selected_sellers}
    
    # Xử lý filter BUYER NAME
    if has_buyer:
        buyer_col_idx = 1 if has_seller else 0
        with filter_cols[buyer_col_idx]:
            # Lọc danh sách BUYER NAME dựa trên SELLER đã chọn
            df_for_buyer = df.copy()
            if selected_sellers:
                df_for_buyer = df_for_buyer[df_for_buyer["SELLER"].isin(selected_sellers)]
            
            buyer_options = sorted(df_for_buyer["BUYER NAME"].dropna().unique().tolist())
            
            if len(buyer_options) > 0:
                selected_buyers = st.multiselect(
                    "BUYER NAME:",
                    options=buyer_options,
                    default=selected_buyers if selected_buyers else [],
                    key=f"filter_text_{table_name}_BUYER NAME",
                    help="Chọn các BUYER NAME muốn hiển thị (sẽ tự động lọc theo SELLER đã chọn)"
                )
                
                if selected_buyers:
                    filter_config["BUYER NAME"] = {"type": "in", "values": selected_buyers}
    
    return filter_config


def apply_column_filters(df: pd.DataFrame, filters: dict) -> pd.DataFrame:
    """
    Áp dụng các Filter vào dataframe.
    
    Args:
        df: DataFrame cần filter
        filters: Dictionary chứa thông tin filter, format:
            {column_name: {"type": "Greater than (>)" | "Less than (<)" | "Between" | "in", 
                           "value": float (cho > và <) hoặc "min": float, "max": float (cho Between) hoặc "values": list (cho in)}}
    
    Returns:
        DataFrame đã được filter
    """
    df_filtered = df.copy()
    
    for col, filter_info in filters.items():
        if col not in df_filtered.columns:
            continue
            
        if filter_info["type"] == "Greater than (>)":
            df_filtered = df_filtered[df_filtered[col] > filter_info["value"]]
        elif filter_info["type"] == "Less than (<)":
            df_filtered = df_filtered[df_filtered[col] < filter_info["value"]]
        elif filter_info["type"] == "Between":
            df_filtered = df_filtered[
                df_filtered[col].between(filter_info["min"], filter_info["max"])
            ]
        elif filter_info["type"] == "in":
            df_filtered = df_filtered[df_filtered[col].isin(filter_info["values"])]
    
    return df_filtered


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

    st.title("DASHBOARD PHÂN TÍCH GIÁ THỊ TRƯỜNG")
    st.caption(
        "Dashboard tương tác cho phép lọc theo P1, P2, BRAND, Region, Định lượng, Month và xem bảng giá thị trường, thống kê doanh thu theo seller và buyer."
    )
    
    # CSS để căn phải các cột số, căn trái cột đầu tiên
    st.markdown("""
    <style>
    /* Căn phải tất cả các cột trừ cột đầu tiên - dùng nhiều selector */
    div[data-testid="stDataFrame"] table tbody tr td:not(:first-child),
    div[data-testid="stDataFrame"] table thead tr th:not(:first-child),
    div[data-testid="stDataFrame"] table tbody td:not(:first-child),
    div[data-testid="stDataFrame"] table thead th:not(:first-child),
    div[data-testid="stDataFrame"] table td:not(:first-child),
    div[data-testid="stDataFrame"] table th:not(:first-child) {
        text-align: right !important;
    }
    /* Căn trái cho cột đầu tiên (SELLER) */
    div[data-testid="stDataFrame"] table tbody tr td:first-child,
    div[data-testid="stDataFrame"] table thead tr th:first-child,
    div[data-testid="stDataFrame"] table td:first-child,
    div[data-testid="stDataFrame"] table th:first-child {
        text-align: left !important;
    }
    /* Đổi màu tiêu đề "Tổng quan dữ liệu sau khi lọc" và "Bảng giá theo Seller và Tháng" */
    div[data-testid="stMarkdownContainer"] h3,
    h3[data-testid="stMarkdownContainer"] {
        color: #009793 !important;
    }
    /* Đổi màu cho subheader */
    div[data-testid="stMarkdownContainer"] h2 {
        color: #009793 !important;
    }
    /* Hoạt tiết màu xanh - Border accent cho tiêu đề */
    div[data-testid="stMarkdownContainer"] h2,
    div[data-testid="stMarkdownContainer"] h3 {
        border-left: 4px solid #009793 !important;
        padding-left: 12px !important;
        margin-top: 20px !important;
        margin-bottom: 15px !important;
    }
    /* Hoạt tiết - Border top cho title */
    h1 {
        border-top: 3px solid #009793 !important;
        padding-top: 15px !important;
        margin-bottom: 10px !important;
    }
    /* Hoạt tiết - Background subtle cho metrics */
    div[data-testid="stMetricValue"] {
        color: #009793 !important;
    }
    /* Hoạt tiết - Divider line */
    .divider-line {
        height: 2px;
        background: linear-gradient(to right, #009793, transparent);
        margin: 20px 0;
        border: none;
    }
    /* Hoạt tiết - Border accent cho các section */
    div[data-testid="stDataFrame"] {
        border-top: 2px solid #009793;
        padding-top: 10px;
        margin-top: 10px;
    }
    /* Hoạt tiết - Styling cho metrics */
    div[data-testid="stMetricContainer"] {
        border-left: 3px solid #009793;
        padding-left: 10px;
        margin: 5px 0;
    }
    /* Hoạt tiết - Hover effect cho buttons */
    div[data-testid="stDownloadButton"] button {
        border: 2px solid #009793 !important;
        color: #009793 !important;
    }
    div[data-testid="stDownloadButton"] button:hover {
        background-color: #009793 !important;
        color: white !important;
    }
    </style>
    """, unsafe_allow_html=True)

    # Sidebar: thông tin bộ dữ liệu (chỉ hiển thị text, không có input)
    st.sidebar.header("Thiết lập dữ liệu")
    st.sidebar.write("Bộ dữ liệu: **Database_updated_2112.xlsx** ")

    # Luôn đọc dữ liệu từ OneDrive (hoặc local khi chạy trên máy anh nếu truyền đường dẫn khác vào load_data)
    df = load_data(None)
    if df.empty:
        st.stop()

    st.sidebar.header("Bộ lọc")

    # P1 filter
    p1_options = sorted(df["P1"].dropna().unique()) if "P1" in df.columns else []
    # Không chọn sẵn để tránh áp filter mặc định
    p1_values = st.sidebar.multiselect("P1", options=p1_options, default=[])

    # P2 filter phụ thuộc vào lựa chọn P1
    if "P2" in df.columns:
        if p1_values:
            # Lọc tạm theo P1 đã chọn để lấy danh sách P2 tương ứng
            df_for_p2 = df[df["P1"].isin(p1_values)]
        else:
            df_for_p2 = df
        p2_options = sorted(df_for_p2["P2"].dropna().unique())
    else:
        p2_options = []
    p2_values = st.sidebar.multiselect("P2", options=p2_options, default=[])

    # BRAND filter phụ thuộc vào P1 và P2
    if "BRAND" in df.columns:
        df_for_brand = df
        if p1_values:
            df_for_brand = df_for_brand[df_for_brand["P1"].isin(p1_values)]
        if p2_values:
            df_for_brand = df_for_brand[df_for_brand["P2"].isin(p2_values)]
        brand_options = sorted(df_for_brand["BRAND"].dropna().unique())
    else:
        brand_options = []
    brand_values = st.sidebar.multiselect("BRAND", options=brand_options, default=[])

    # Khởi tạo month_values và city_values từ session state (nếu có) để tránh lỗi UnboundLocalError
    month_values = st.session_state.get("month_values", [])
    city_values = st.session_state.get("city_values", [])

    # Khởi tạo các checkbox từ session state để sử dụng trong tính toán (sẽ hiển thị sau)
    only_kg = st.session_state.get("only_kg", False)
    remove_related_true = st.session_state.get("remove_related_true", False)
    remove_related_false = st.session_state.get("remove_related_false", False)

    # Region filter phụ thuộc vào P1, P2, BRAND, Month
    if "REGION" in df.columns:
        # Region phụ thuộc vào Month (nếu có)
        df_for_city = get_filtered_data_for_options(
            df, p1_values, p2_values, brand_values, month_values if month_values else [], [], 
            only_kg, remove_related_true, remove_related_false
        )
        city_options = sorted(df_for_city["REGION"].dropna().unique())
        
        # Loại bỏ các city_values không hợp lệ
        if city_values:
            city_values = [c for c in city_values if c in city_options]
    else:
        city_options = []
    city_values = st.sidebar.multiselect(
        "Region", options=city_options, default=city_values if city_values else []
    )
    # Lưu vào session state
    st.session_state.city_values = city_values

    # Month filter phụ thuộc vào P1, P2, BRAND, Region
    # Month phụ thuộc vào Region để khi chọn Region, Month options sẽ thu hẹp lại
    if "Month" in df.columns:
        # Month phụ thuộc vào Region (nếu có)
        df_for_month = get_filtered_data_for_options(
            df, p1_values, p2_values, brand_values, [], city_values if city_values else [], 
            only_kg, remove_related_true, remove_related_false
        )
        month_options = sorted(df_for_month["Month"].dropna().unique())
        
        # Loại bỏ các month_values không hợp lệ
        if month_values:
            month_values = [m for m in month_values if m in month_options]
    else:
        month_options = []
    month_values = st.sidebar.multiselect(
        "Tháng", options=month_options, default=month_values if month_values else []
    )
    # Lưu vào session state
    st.session_state.month_values = month_values

    # Mặc định không tích filter nào; anh tự chọn khi cần
    # Hiển thị các checkbox sau Region và Tháng
    only_kg = st.sidebar.checkbox("Chỉ lấy đơn vị KG", value=only_kg)
    st.session_state.only_kg = only_kg
    remove_related_true = st.sidebar.checkbox("Loại RELATED ", value=remove_related_true)
    st.session_state.remove_related_true = remove_related_true
    remove_related_false = st.sidebar.checkbox("Xem RELATED", value=remove_related_false)
    st.session_state.remove_related_false = remove_related_false

    # Tùy chọn bật filter định lượng - phụ thuộc vào tất cả các filter khác
    dinh_luong_range = None
    enable_dl_filter = st.sidebar.checkbox("Bật filter Định lượng (gsm)", value=False)
    if enable_dl_filter:
        # Lấy dữ liệu đã được filter bởi tất cả các filter khác (trừ định lượng)
        df_for_dinh_luong = get_filtered_data_for_options(
            df, p1_values, p2_values, brand_values, month_values, city_values, 
            only_kg, remove_related_true, remove_related_false
        )
        
        if "Định_lượng_numeric" in df_for_dinh_luong.columns and df_for_dinh_luong["Định_lượng_numeric"].notna().any():
            dl_min = int(df_for_dinh_luong["Định_lượng_numeric"].min())
            dl_max = int(df_for_dinh_luong["Định_lượng_numeric"].max())
            
            # Key cho slider để quản lý session state
            slider_key = "dinh_luong_slider"
            
            # Kiểm tra và reset giá trị nếu nằm ngoài phạm vi
            if slider_key in st.session_state:
                old_value = st.session_state[slider_key]
                # Nếu giá trị cũ nằm ngoài phạm vi mới, reset về giá trị mặc định
                if old_value[0] < dl_min or old_value[0] > dl_max or old_value[1] < dl_min or old_value[1] > dl_max:
                    st.session_state[slider_key] = (dl_min, dl_max)
            
            # Lấy giá trị hiện tại hoặc giá trị mặc định
            current_value = st.session_state.get(slider_key, (dl_min, dl_max))
            # Đảm bảo giá trị nằm trong phạm vi
            current_value = (max(dl_min, min(current_value[0], dl_max)), max(dl_min, min(current_value[1], dl_max)))
            
            dinh_luong_range = st.sidebar.slider(
                "Định lượng (gsm)",
                min_value=dl_min,
                max_value=dl_max,
                value=current_value,
                key=slider_key,
            )

    filtered_valid, filtered_all = filter_data(
        df,
        p1_values=p1_values,
        p2_values=p2_values,
        brand_values=brand_values,
        month_values=month_values,
        city_values=city_values,
        dinh_luong_range=dinh_luong_range,
        only_kg=only_kg,
        remove_related_true=remove_related_true,
        remove_related_false=remove_related_false,
    )

    st.markdown('<h2 style="color: #009793;">Tổng quan dữ liệu </h2>', unsafe_allow_html=True)
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
        col4.metric("Thời lượng (tháng)", f"{filtered_all['Month'].nunique():,}")

    if filtered_valid.empty:
        st.warning("Không có dữ liệu sau khi áp dụng các bộ lọc.")
        st.stop()

    # Divider line
    st.markdown('<hr style="border: none; height: 2px; background: linear-gradient(to right, #009793, transparent); margin: 25px 0;">', unsafe_allow_html=True)

    # Giá thị trường (trung bình các sellers) theo tháng
    st.markdown('<h3 style="color: #009793;">1. Giá thị trường (trung bình các sellers) theo tháng</h3>', unsafe_allow_html=True)
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
            
            # Tạo filter UI ngay trên bảng
            numeric_cols = ["Price_Highest", "Price_Avg_Formula", "Price_Lowest"]
            filters = create_column_filter_ui(market_df, "Giá thị trường theo tháng", numeric_cols)
            
            # Áp dụng Filter nếu có
            market_df_filtered = market_df.copy()
            if filters:  # Chỉ áp dụng nếu có filter được thiết lập
                market_df_filtered = apply_column_filters(market_df_filtered, filters)
            
            # Sort trước khi format (sort theo số, không phải string)
            market_df_sorted = market_df_filtered.sort_values("Month")
            
            # Format số với dấu phẩy ngăn cách hàng nghìn để hiển thị
            market_df_display = format_dataframe_numbers(
                market_df_sorted,
                ["Price_Highest", "Price_Avg_Formula", "Price_Lowest"]
            )
            
            st.dataframe(
                market_df_display,
                use_container_width=True,
            )
            
            # CSS để căn phải các cột số
            st.markdown("""
            <style>
            /* Căn phải tất cả các cột trừ cột đầu tiên */
            div[data-testid="stDataFrame"] table tbody tr td:not(:first-child),
            div[data-testid="stDataFrame"] table thead tr th:not(:first-child),
            div[data-testid="stDataFrame"] table tbody td:not(:first-child),
            div[data-testid="stDataFrame"] table thead th:not(:first-child) {
                text-align: right !important;
            }
            /* Căn trái cho cột đầu tiên */
            div[data-testid="stDataFrame"] table tbody tr td:first-child,
            div[data-testid="stDataFrame"] table thead tr th:first-child {
                text-align: left !important;
            }
            </style>
            """, unsafe_allow_html=True)
            
            # Hiển thị số dòng sau filter
            if len(market_df_filtered) < len(market_df):
                st.caption(f"📊 Đã lọc từ {len(market_df):,} dòng xuống còn {len(market_df_filtered):,} dòng")
        else:
            st.info("Không có đủ dữ liệu để tính giá thị trường.")

    # Divider line
    st.markdown('<hr style="border: none; height: 2px; background: linear-gradient(to right, #009793, transparent); margin: 25px 0;">', unsafe_allow_html=True)

    # Bảng giá thị trường theo Seller x Month
    st.markdown('<h3 style="color: #009793;">2. Bảng giá theo Seller và Tháng</h3>', unsafe_allow_html=True)
    if {"SELLER", "Month", "Unit_Price"}.issubset(filtered_valid.columns):
        price_stats = (
            filtered_valid.groupby(["SELLER", "Month"])
            .apply(calculate_price_stats)
            .reset_index()
        )

        # Làm tròn để hiển thị
        for col in ["Price_Highest", "Price_Lowest", "Price_Avg_Formula"]:
            price_stats[col] = price_stats[col].round(0)

        # Tạo filter UI ngay trên bảng
        numeric_cols = ["Price_Highest", "Price_Lowest", "Price_Avg_Formula", "Transaction_Count"]
        filters = create_column_filter_ui(price_stats, "Bảng giá theo Seller và Tháng", numeric_cols)
        
        # Áp dụng Filter nếu có
        price_stats_filtered = price_stats.copy()
        if filters:  # Chỉ áp dụng nếu có filter được thiết lập
            price_stats_filtered = apply_column_filters(price_stats_filtered, filters)

        # Sort trước khi format (sort theo số, không phải string)
        price_stats_sorted = price_stats_filtered.sort_values(["Month", "SELLER"])
        
        # Format số với dấu phẩy ngăn cách hàng nghìn để hiển thị
        price_stats_display = format_dataframe_numbers(
            price_stats_sorted, 
            ["Price_Highest", "Price_Lowest", "Price_Avg_Formula", "Transaction_Count"]
        )

        st.dataframe(
            price_stats_display,
            use_container_width=True,
        )
        
        # CSS để căn phải các cột số - áp dụng ngay sau bảng với selector cụ thể
        st.markdown("""
        <style>
        /* Căn phải cho cột Month (cột thứ 2) */
        div[data-testid="stDataFrame"] table tbody tr td:nth-child(2),
        div[data-testid="stDataFrame"] table thead tr th:nth-child(2) {
            text-align: right !important;
        }
        /* Căn phải cho các cột số (từ cột thứ 3 trở đi) */
        div[data-testid="stDataFrame"] table tbody tr td:nth-child(3),
        div[data-testid="stDataFrame"] table thead tr th:nth-child(3),
        div[data-testid="stDataFrame"] table tbody tr td:nth-child(4),
        div[data-testid="stDataFrame"] table thead tr th:nth-child(4),
        div[data-testid="stDataFrame"] table tbody tr td:nth-child(5),
        div[data-testid="stDataFrame"] table thead tr th:nth-child(5),
        div[data-testid="stDataFrame"] table tbody tr td:nth-child(6),
        div[data-testid="stDataFrame"] table thead tr th:nth-child(6),
        div[data-testid="stDataFrame"] table tbody tr td:nth-child(7),
        div[data-testid="stDataFrame"] table thead tr th:nth-child(7) {
            text-align: right !important;
        }
        /* Căn trái cho cột đầu tiên (SELLER) */
        div[data-testid="stDataFrame"] table tbody tr td:first-child,
        div[data-testid="stDataFrame"] table thead tr th:first-child {
            text-align: left !important;
        }
        </style>
        """, unsafe_allow_html=True)
        
        # Hiển thị số dòng sau filter
        if len(price_stats_filtered) < len(price_stats):
            st.caption(f"📊 Đã lọc từ {len(price_stats):,} dòng xuống còn {len(price_stats_filtered):,} dòng")
    else:
        st.info("Thiếu một trong các cột: SELLER, Month, Unit_Price.")

    # Divider line
    st.markdown('<hr style="border: none; height: 2px; background: linear-gradient(to right, #009793, transparent); margin: 25px 0;">', unsafe_allow_html=True)

    # Thống kê doanh thu sellers (dùng toàn bộ dữ liệu sau filter, không loại dòng thiếu Unit_Price)
    st.markdown("### 3. Thống kê doanh thu của các sellers")
    if "SELLER" in filtered_all.columns:
        df_seller = filtered_all.copy()

        # Tạo khóa hóa đơn duy nhất theo SELLER, BUYER NAME, DATE, INV NO.
        if {"INV NO.", "SELLER", "BUYER NAME", "DATE"}.issubset(df_seller.columns):
            df_seller["Invoice_Key"] = (
                df_seller["INV NO."].astype(str)
                + "|"
                + df_seller["SELLER"].astype(str)
                + "|"
                + df_seller["BUYER NAME"].astype(str)
                + "|"
                + df_seller["DATE"].astype(str)
            )
            invoice_agg = ("Invoice_Key", "nunique")
        elif "INV NO." in df_seller.columns:
            # Fallback: chỉ đảm bảo unique theo INV NO.
            invoice_agg = ("INV NO.", "nunique")
        else:
            # Fallback cuối cùng: đếm số dòng
            invoice_agg = ("SELLER", "size")

        seller_stats = (
            df_seller.groupby("SELLER").agg(
                Total_Value=("VALUE_EXL_VAT_numeric", "sum")
                if "VALUE_EXL_VAT_numeric" in df_seller.columns
                else ("SELLER", "size"),
                Total_Volume=("VOLUME_numeric", "sum")
                if "VOLUME_numeric" in df_seller.columns
                else ("SELLER", "size"),
                Invoice_Count=invoice_agg,
                Buyer_Count=("BUYER NAME", "nunique")
                if "BUYER NAME" in df_seller.columns
                else ("SELLER", "size"),
            )
        ).reset_index()

        seller_stats["Total_Value"] = seller_stats["Total_Value"].round(0).astype("Int64")
        seller_stats["Total_Volume"] = (
            seller_stats["Total_Volume"].round(0).astype("Int64")
        )

        # Tạo filter UI ngay trên bảng
        numeric_cols = ["Total_Value", "Total_Volume", "Invoice_Count", "Buyer_Count"]
        filters = create_column_filter_ui(seller_stats, "Thống kê doanh thu sellers", numeric_cols)

        # Áp dụng Filter nếu có
        seller_stats_filtered = seller_stats.copy()
        if filters:  # Chỉ áp dụng nếu có filter được thiết lập
            seller_stats_filtered = apply_column_filters(seller_stats_filtered, filters)

        # Sort trước khi format (sort theo số, không phải string)
        seller_stats_sorted = seller_stats_filtered.sort_values("Total_Value", ascending=False)
        
        # Format số với dấu phẩy ngăn cách hàng nghìn để hiển thị
        seller_stats_display = format_dataframe_numbers(
            seller_stats_sorted,
            ["Total_Value", "Total_Volume", "Invoice_Count", "Buyer_Count"]
        )

        st.dataframe(
            seller_stats_display,
            use_container_width=True,
        )
        
        # CSS để căn phải các cột số
        st.markdown("""
        <style>
        /* Căn phải tất cả các cột trừ cột đầu tiên */
        div[data-testid="stDataFrame"] table tbody tr td:not(:first-child),
        div[data-testid="stDataFrame"] table thead tr th:not(:first-child),
        div[data-testid="stDataFrame"] table tbody td:not(:first-child),
        div[data-testid="stDataFrame"] table thead th:not(:first-child) {
            text-align: right !important;
        }
        /* Căn trái cho cột đầu tiên (SELLER) */
        div[data-testid="stDataFrame"] table tbody tr td:first-child,
        div[data-testid="stDataFrame"] table thead tr th:first-child {
            text-align: left !important;
        }
        </style>
        """, unsafe_allow_html=True)
        
        # Hiển thị số dòng sau filter
        if len(seller_stats_filtered) < len(seller_stats):
            st.caption(f"📊 Đã lọc từ {len(seller_stats):,} dòng xuống còn {len(seller_stats_filtered):,} dòng")

        # Nút tải xuống (tải dữ liệu đã filter)
        csv_bytes = seller_stats_filtered.to_csv(index=False).encode("utf-8-sig")
        st.download_button(
            label="Tải thống kê sellers (CSV)",
            data=csv_bytes,
            file_name="seller_stats_filtered.csv",
            mime="text/csv",
        )
    else:
        st.info("Thiếu cột SELLER trong dữ liệu.")

    # Divider line
    st.markdown('<hr style="border: none; height: 2px; background: linear-gradient(to right, #009793, transparent); margin: 25px 0;">', unsafe_allow_html=True)

    # Thống kê buyers (dùng toàn bộ dữ liệu sau filter)
    st.markdown("### 4. Thống kê buyers")
    if "BUYER NAME" in filtered_all.columns:
        df_buyer = filtered_all.copy()

        # Tạo khóa hóa đơn duy nhất theo SELLER, BUYER NAME, DATE, INV NO.
        if {"INV NO.", "SELLER", "BUYER NAME", "DATE"}.issubset(df_buyer.columns):
            df_buyer["Invoice_Key"] = (
                df_buyer["INV NO."].astype(str)
                + "|"
                + df_buyer["SELLER"].astype(str)
                + "|"
                + df_buyer["BUYER NAME"].astype(str)
                + "|"
                + df_buyer["DATE"].astype(str)
            )
            invoice_agg = ("Invoice_Key", "nunique")
        elif "INV NO." in df_buyer.columns:
            # Fallback: chỉ đảm bảo unique theo INV NO.
            invoice_agg = ("INV NO.", "nunique")
        else:
            # Fallback cuối cùng: đếm số dòng
            invoice_agg = ("BUYER NAME", "size")

        # Groupby theo SELLER và BUYER NAME
        if "SELLER" in df_buyer.columns:
            buyer_stats = (
                df_buyer.groupby(["SELLER", "BUYER NAME"]).agg(
                    Total_Value=("VALUE_EXL_VAT_numeric", "sum")
                    if "VALUE_EXL_VAT_numeric" in df_buyer.columns
                    else ("BUYER NAME", "size"),
                    Total_Volume=("VOLUME_numeric", "sum")
                    if "VOLUME_numeric" in df_buyer.columns
                    else ("BUYER NAME", "size"),
                    Invoice_Count=invoice_agg,
                    Month_Count=("Month", "nunique")
                    if "Month" in df_buyer.columns
                    else ("BUYER NAME", "size"),
                )
            ).reset_index()
            
            # Tính Unit_Price_Avg = Total_Value / Total_Volume
            buyer_stats["Unit_Price_Avg"] = (
                buyer_stats["Total_Value"] / buyer_stats["Total_Volume"]
            ).replace([np.inf, -np.inf], np.nan)
            
            # Sắp xếp lại thứ tự cột: SELLER, BUYER NAME, Total_Value, Total_Volume, Unit_Price_Avg, Invoice_Count, Month_Count
            buyer_stats = buyer_stats[["SELLER", "BUYER NAME", "Total_Value", "Total_Volume", "Unit_Price_Avg", "Invoice_Count", "Month_Count"]]
        else:
            # Fallback nếu không có SELLER
            buyer_stats = (
                df_buyer.groupby("BUYER NAME").agg(
                    Total_Value=("VALUE_EXL_VAT_numeric", "sum")
                    if "VALUE_EXL_VAT_numeric" in df_buyer.columns
                    else ("BUYER NAME", "size"),
                    Total_Volume=("VOLUME_numeric", "sum")
                    if "VOLUME_numeric" in df_buyer.columns
                    else ("BUYER NAME", "size"),
                    Invoice_Count=invoice_agg,
                    Month_Count=("Month", "nunique")
                    if "Month" in df_buyer.columns
                    else ("BUYER NAME", "size"),
                )
            ).reset_index()
            
            # Tính Unit_Price_Avg = Total_Value / Total_Volume
            buyer_stats["Unit_Price_Avg"] = (
                buyer_stats["Total_Value"] / buyer_stats["Total_Volume"]
            ).replace([np.inf, -np.inf], np.nan)

        buyer_stats["Total_Value"] = buyer_stats["Total_Value"].round(0).astype("Int64")
        buyer_stats["Total_Volume"] = (
            buyer_stats["Total_Volume"].round(0).astype("Int64")
        )
        # Làm tròn Unit_Price_Avg
        buyer_stats["Unit_Price_Avg"] = buyer_stats["Unit_Price_Avg"].round(0)

        # Tạo filter UI ngay trên bảng
        # Loại Unit_Price_Avg khỏi numeric_cols vì sẽ có filter riêng với slider
        numeric_cols = ["Total_Value", "Total_Volume", "Invoice_Count", "Month_Count"]
        
        # Thêm filter text cho SELLER và BUYER NAME
        text_cols = []
        if "SELLER" in buyer_stats.columns:
            text_cols.append("SELLER")
        if "BUYER NAME" in buyer_stats.columns:
            text_cols.append("BUYER NAME")
        
        # Gọi hàm filter với cả numeric và text cols, và filter Unit_Price với slider
        filters = create_column_filter_ui(buyer_stats, "Thống kê buyers", numeric_cols, text_cols, include_unit_price_filter=True)

        # Áp dụng Filter nếu có
        buyer_stats_filtered = buyer_stats.copy()
        if filters:  # Chỉ áp dụng nếu có filter được thiết lập
            buyer_stats_filtered = apply_column_filters(buyer_stats_filtered, filters)

        # Sort trước khi format (sort theo số, không phải string)
        buyer_stats_sorted = buyer_stats_filtered.sort_values("Total_Value", ascending=False)
        
        # Format số với dấu phẩy ngăn cách hàng nghìn để hiển thị
        buyer_stats_display = format_dataframe_numbers(
            buyer_stats_sorted,
            ["Total_Value", "Total_Volume", "Unit_Price_Avg", "Invoice_Count", "Month_Count"]
        )

        st.dataframe(
            buyer_stats_display,
            use_container_width=True,
        )
        
        # CSS để căn phải các cột số, căn trái SELLER và BUYER NAME
        st.markdown("""
        <style>
        /* Căn phải các cột số (từ cột thứ 3 trở đi) */
        div[data-testid="stDataFrame"] table tbody tr td:nth-child(n+3),
        div[data-testid="stDataFrame"] table thead tr th:nth-child(n+3) {
            text-align: right !important;
        }
        /* Căn trái cho cột SELLER (cột đầu tiên) và BUYER NAME (cột thứ 2) */
        div[data-testid="stDataFrame"] table tbody tr td:first-child,
        div[data-testid="stDataFrame"] table thead tr th:first-child,
        div[data-testid="stDataFrame"] table tbody tr td:nth-child(2),
        div[data-testid="stDataFrame"] table thead tr th:nth-child(2) {
            text-align: left !important;
        }
        </style>
        """, unsafe_allow_html=True)
        
        # Hiển thị số dòng sau filter
        if len(buyer_stats_filtered) < len(buyer_stats):
            st.caption(f"📊 Đã lọc từ {len(buyer_stats):,} dòng xuống còn {len(buyer_stats_filtered):,} dòng")

        # Nút tải xuống (tải dữ liệu đã filter)
        csv_bytes_buyer = buyer_stats_filtered.to_csv(index=False).encode("utf-8-sig")
        st.download_button(
            label="Tải thống kê buyers (CSV)",
            data=csv_bytes_buyer,
            file_name="buyer_stats_filtered.csv",
            mime="text/csv",
        )
    else:
        st.info("Thiếu cột BUYER NAME trong dữ liệu.")


if __name__ == "__main__":
    main()


