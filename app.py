import streamlit as st
import requests
from bs4 import BeautifulSoup
import pandas as pd
import datetime
import json
from google.oauth2 import service_account
from googleapiclient.discovery import build

# --- Page Configuration ---
st.set_page_config(
    page_title="BigBasket Stock Dashboard",
    page_icon="🛒",
    layout="wide"
)

# --- Inline CSS Styles ---
st.markdown("""
<style>
    /* Navigation Bar */
    .navbar {
        background-color: #2c3e50;
        overflow: hidden;
        padding: 1rem;
        border-radius: 8px;
        margin-bottom: 2rem;
        display: flex;
        justify-content: space-between;
        align-items: center;
    }
    
    .navbar-brand {
        color: white;
        font-weight: bold;
        font-size: 1.5rem;
    }
    
    .navbar-links {
        display: flex;
        gap: 1.5rem;
    }
    
    .nav-link {
        color: white;
        text-decoration: none;
        font-size: 1rem;
        transition: color 0.3s;
    }
    
    .nav-link:hover {
        color: #3498db;
    }
    
    /* Input and Select Boxes */
    .stSelectbox > div > div > input {
        padding: 10px !important;
    }
    
    /* Buttons */
    .stButton > button {
        border-radius: 8px;
        padding: 8px 16px;
        font-weight: 500;
        transition: all 0.3s;
        background-color: #3498db;
        color: white;
        border: none;
    }
    
    .stButton > button:hover {
        transform: translateY(-2px);
        box-shadow: 0 4px 8px rgba(0,0,0,0.1);
        background-color: #2980b9;
    }
    
    /* Metrics Cards */
    .stMetric {
        border-radius: 8px;
        padding: 1rem;
        background-color: #f8f9fa;
        box-shadow: 0 2px 4px rgba(0,0,0,0.05);
    }
    
    /* Dataframe Styling */
    .dataframe {
        border-radius: 8px !important;
        box-shadow: 0 2px 8px rgba(0,0,0,0.1) !important;
    }
    
    /* Expander Styling */
    .stExpander {
        border-radius: 8px !important;
        border: 1px solid #e1e4e8 !important;
    }
    
    /* Custom Card Styling */
    .custom-card {
        border-radius: 8px;
        padding: 1.5rem;
        background-color: white;
        box-shadow: 0 2px 8px rgba(0,0,0,0.1);
        margin-bottom: 1.5rem;
    }
    
    /* Tab Styling */
    .stTabs [role="tablist"] {
        margin-bottom: 1rem;
    }
    
    .stTabs [role="tab"] {
        padding: 0.5rem 1rem;
        border-radius: 8px 8px 0 0;
    }
    
    .stTabs [aria-selected="true"] {
        background-color: #3498db;
        color: white;
    }
</style>
""", unsafe_allow_html=True)

# --- Google Sheets Setup with Streamlit Secrets ---
SCOPES = ['https://www.googleapis.com/auth/spreadsheets']
SPREADSHEET_ID = '1sgpXQJW9oUjMpAbDUYa7J3qZALY5hwFsJGlcd9cd-8c'

# Load service account credentials from Streamlit secrets
creds_dict = json.loads(st.secrets["google_sheets"]["SERVICE_ACCOUNT_JSON"])
creds = service_account.Credentials.from_service_account_info(creds_dict, scopes=SCOPES)
service = build('sheets', 'v4', credentials=creds)

# --- Navigation Bar ---
st.markdown("""
<nav class="navbar">
    <div class="navbar-brand">BigBasket Stock Dashboard</div>
    <div class="navbar-links">
        <a href="#" class="nav-link">Home</a>
        <a href="#" class="nav-link">Reports</a>
        <a href="#" class="nav-link">Settings</a>
    </div>
</nav>
""", unsafe_allow_html=True)

# --- Function Definitions ---
def fetch_brands_from_sheet1():
    result = service.spreadsheets().values().get(
        spreadsheetId=SPREADSHEET_ID,
        range='Sheet1'
    ).execute()
    values = result.get('values', [])
    if not values or len(values) < 2:
        return pd.DataFrame(columns=['Brand Name', 'Brand URL'])
    headers = values[0]
    data = values[1:]
    df = pd.DataFrame(data, columns=headers)
    return df[['Brand Name', 'Brand URL']]

def scrape_brand_data(brand_name, brand_url):
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36"
        }
        response = requests.get(brand_url, headers=headers, timeout=10)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.content, "html.parser")
        product_containers = soup.find_all('div', class_='SKUDeck___StyledDiv-sc-1e5d9gk-0 eA-dmzP')
        all_data = []

        if not product_containers:
            st.warning(f"No product containers found for {brand_name}. The page might require JavaScript rendering.")
            return pd.DataFrame()

        for container in product_containers:
            try:
                product_elem = container.find('h3', class_='block m-0 line-clamp-2 font-regular text-base leading-sm text-darkOnyx-800 pt-0.5 h-full')
                product_name = product_elem.text.strip() if product_elem else "N/A"
            except Exception:
                product_name = "N/A"
            
            try:
                price_elem = container.find('span', class_='Label-sc-15v1nk5-0 Pricing___StyledLabel-sc-pldi2d-1 gJxZPQ AypOi')
                price = price_elem.text.strip() if price_elem else "N/A"
            except Exception:
                price = "N/A"
            
            try:
                pack_elem = container.find('div', class_='py-1.5 xl:py-1')
                quantity = pack_elem.text.strip() if pack_elem else "N/A"
            except Exception:
                quantity = "N/A"
            
            try:
                stock_elem = container.find('span', class_='Label-sc-15v1nk5-0 Tags___StyledLabel2-sc-aeruf4-1 gJxZPQ gPgOvC')
                stock_availability = stock_elem.text.strip() if stock_elem else "In Stock"
            except Exception:
                stock_availability = "In Stock"
            
            try:
                product_url_elem = container.find('a', href=True)
                product_url = "https://www.bigbasket.com" + product_url_elem['href'] if product_url_elem else "N/A"
            except Exception:
                product_url = "N/A"
            
            timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            all_data.append({
                'Brand': brand_name,
                'Product Name': product_name,
                'Price': price,
                'Quantity': quantity,
                'Timestamp': timestamp,
                'Stock Availability': stock_availability,
                'Product URL': product_url
            })

        return pd.DataFrame(all_data)
    except requests.RequestException as e:
        st.error(f"Error scraping {brand_name}: {str(e)}")
        return pd.DataFrame()

def append_to_sheet2(df):
    if df.empty:
        return
    result = service.spreadsheets().values().get(
        spreadsheetId=SPREADSHEET_ID,
        range='Sheet2'
    ).execute()
    existing_values = result.get('values', [])
    
    if not existing_values:
        header = df.columns.tolist()
        data = df.values.tolist()
        sheet_data = [header] + data
    else:
        data = df.values.tolist()
        sheet_data = existing_values + data

    service.spreadsheets().values().update(
        spreadsheetId=SPREADSHEET_ID,
        range='Sheet2',
        valueInputOption='RAW',
        body={'values': sheet_data}
    ).execute()

def get_all_products(brand_name):
    result = service.spreadsheets().values().get(
        spreadsheetId=SPREADSHEET_ID,
        range='Sheet2'
    ).execute()
    values = result.get('values', [])
    if not values or len(values) < 2:
        return pd.DataFrame()
    
    headers = values[0]
    data = values[1:]
    df = pd.DataFrame(data, columns=headers)
    
    if 'Brand' not in df.columns:
        return pd.DataFrame()
    
    brand_products = df[df['Brand'] == brand_name]
    return brand_products

def get_out_of_stock_products(brand_name):
    brand_products = get_all_products(brand_name)
    if brand_products.empty or 'Stock Availability' not in brand_products.columns:
        return pd.DataFrame()
    
    out_of_stock = brand_products[brand_products['Stock Availability'] != 'In Stock']
    return out_of_stock

# --- Main App ---
st.title("🛒 BigBasket Stock Analysis Dashboard")
st.markdown("---")

# Fetch brand list and URLs from Sheet1
brands_df = fetch_brands_from_sheet1()
brand_list = brands_df['Brand Name'].tolist()

# Create tabs
tab1, tab2 = st.tabs(["Your Brand Analysis", "Competitor Brand Analysis"])

with tab1:
    st.subheader("Your Brand Analysis")
    
    # Autocomplete search for own brand
    own_brand = st.selectbox(
        "Search for your brand",
        options=brand_list,
        index=None,
        placeholder="Start typing to search...",
        key="own_brand_search"
    )
    
    if own_brand:
        brand_url = brands_df[brands_df['Brand Name'] == own_brand]['Brand URL'].iloc[0]
        
        col1, col2 = st.columns(2)
        with col1:
            if st.button("Scrape Current Data", key="own_scrape"):
                with st.spinner(f"Scraping current data for {own_brand}..."):
                    df = scrape_brand_data(own_brand, brand_url)
                    if not df.empty:
                        append_to_sheet2(df)
                        st.success(f"Scraped and saved current data for {own_brand}")
                    else:
                        st.warning(f"No data scraped for {own_brand}")
        
        with col2:
            if st.button("View Historical Data", key="own_history"):
                all_products = get_all_products(own_brand)
                if not all_products.empty:
                    st.subheader(f"All Products for {own_brand}")
                    st.dataframe(all_products, use_container_width=True)
                else:
                    st.warning(f"No historical data found for {own_brand}")
        
        # Display out of stock products
        out_of_stock_df = get_out_of_stock_products(own_brand)
        if not out_of_stock_df.empty:
            st.subheader(f"Out-of-Stock Products for {own_brand}")
            st.dataframe(
                out_of_stock_df,
                use_container_width=True,
                column_config={
                    "Product URL": st.column_config.LinkColumn("Product Link")
                }
            )
        else:
            st.info(f"No out-of-stock products found for {own_brand}")

with tab2:
    st.subheader("Competitor Brand Analysis")
    
    # Multiselect for competitor brands
    competitor_brands = st.multiselect(
        "Select competitor brands (max 5)",
        options=brand_list,
        default=None,
        placeholder="Start typing to search...",
        max_selections=5,
        key="comp_brands"
    )
    
    if competitor_brands:
        col1, col2 = st.columns(2)
        with col1:
            if st.button("Scrape Competitor Data", key="comp_scrape"):
                with st.spinner("Scraping competitor data..."):
                    for brand in competitor_brands:
                        brand_url = brands_df[brands_df['Brand Name'] == brand]['Brand URL'].iloc[0]
                        df = scrape_brand_data(brand, brand_url)
                        if not df.empty:
                            append_to_sheet2(df)
                    st.success(f"Scraped and saved data for {', '.join(competitor_brands)}")
        
        with col2:
            if st.button("View All Competitor Data", key="comp_history"):
                for brand in competitor_brands:
                    all_products = get_all_products(brand)
                    if not all_products.empty:
                        st.subheader(f"All Products for {brand}")
                        st.dataframe(all_products, use_container_width=True)
                    else:
                        st.warning(f"No data found for {brand}")
        
        # Display out of stock analysis for each competitor
        for brand in competitor_brands:
            st.markdown(f'<div class="custom-card">', unsafe_allow_html=True)
            st.subheader(f"Analysis for {brand}")
            
            out_of_stock_df = get_out_of_stock_products(brand)
            all_products_df = get_all_products(brand)
            
            if not all_products_df.empty:
                total_products = len(all_products_df)
                out_of_stock_count = len(out_of_stock_df)
                
                col1, col2, col3 = st.columns(3)
                col1.metric("Total Products", total_products)
                col2.metric("Out-of-Stock Products", out_of_stock_count)
                col3.metric("Out-of-Stock Percentage", 
                           f"{(out_of_stock_count/total_products*100):.1f}%" if total_products > 0 else "0%")
                
                if not out_of_stock_df.empty:
                    with st.expander(f"View Out-of-Stock Products for {brand}"):
                        st.dataframe(out_of_stock_df, use_container_width=True)
                else:
                    st.info(f"No out-of-stock products found for {brand}")
            else:
                st.warning(f"No products found for {brand}")
            st.markdown('</div>', unsafe_allow_html=True)

# Footer
st.markdown("---")
st.markdown(f"""
<div style="text-align: center; padding: 10px;">
    <p>BigBasket Stock Dashboard • Updated at {datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")}</p>
</div>
""", unsafe_allow_html=True)