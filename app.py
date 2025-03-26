import streamlit as st
import requests
from bs4 import BeautifulSoup
import pandas as pd
import datetime
import json
from google.oauth2 import service_account
from googleapiclient.discovery import build

# --- Google Sheets Setup with Streamlit Secrets ---
SCOPES = ['https://www.googleapis.com/auth/spreadsheets']
SPREADSHEET_ID = '1sgpXQJW9oUjMpAbDUYa7J3qZALY5hwFsJGlcd9cd-8c'

creds_dict = json.loads(st.secrets["google_sheets"]["SERVICE_ACCOUNT_JSON"])
creds = service_account.Credentials.from_service_account_info(creds_dict, scopes=SCOPES)
service = build('sheets', 'v4', credentials=creds)

# --- Functions ---
def fetch_brands_from_sheet1():
    result = service.spreadsheets().values().get(spreadsheetId=SPREADSHEET_ID, range='Sheet1').execute()
    values = result.get('values', [])
    if not values or len(values) < 2:
        return pd.DataFrame(columns=['Brand Name', 'Brand URL'])
    headers = values[0]
    data = values[1:]
    df = pd.DataFrame(data, columns=headers)
    return df[['Brand Name', 'Brand URL']]

def scrape_brand_data(brand_name, brand_url):
    try:
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36"}
        response = requests.get(brand_url, headers=headers, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, "html.parser")
        product_containers = soup.find_all('div', class_='SKUDeck___StyledDiv-sc-1e5d9gk-0 eA-dmzP')
        all_data = []

        if not product_containers:
            st.warning(f"No product containers found for {brand_name}. The page might require JavaScript rendering.")
            return pd.DataFrame()

        for container in product_containers:
            product_name = container.find('h3', class_='block m-0 line-clamp-2 font-regular text-base leading-sm text-darkOnyx-800 pt-0.5 h-full').text.strip() if container.find('h3') else "N/A"
            price = container.find('span', class_='Label-sc-15v1nk5-0 Pricing___StyledLabel-sc-pldi2d-1 gJxZPQ AypOi').text.strip() if container.find('span', class_='Label-sc-15v1nk5-0 Pricing___StyledLabel-sc-pldi2d-1 gJxZPQ AypOi') else "N/A"
            quantity = container.find('div', class_='py-1.5 xl:py-1').text.strip() if container.find('div', class_='py-1.5 xl:py-1') else "N/A"
            stock_availability = container.find('span', class_='Label-sc-15v1nk5-0 Tags___StyledLabel2-sc-aeruf4-1 gJxZPQ gPgOvC').text.strip() if container.find('span', class_='Label-sc-15v1nk5-0 Tags___StyledLabel2-sc-aeruf4-1 gJxZPQ gPgOvC') else "In Stock"
            product_url = "https://www.bigbasket.com" + container.find('a', href=True)['href'] if container.find('a', href=True) else "N/A"
            timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            all_data.append({
                'Brand': brand_name, 'Product Name': product_name, 'Price': price, 'Quantity': quantity,
                'Timestamp': timestamp, 'Stock Availability': stock_availability, 'Product URL': product_url
            })
        return pd.DataFrame(all_data)
    except requests.RequestException as e:
        st.error(f"Error scraping {brand_name}: {str(e)}")
        return pd.DataFrame()

def append_to_sheet2(df):
    if df.empty:
        return
    result = service.spreadsheets().values().get(spreadsheetId=SPREADSHEET_ID, range='Sheet2').execute()
    existing_values = result.get('values', [])
    sheet_data = [df.columns.tolist()] + df.values.tolist() if not existing_values else existing_values + df.values.tolist()
    service.spreadsheets().values().update(spreadsheetId=SPREADSHEET_ID, range='Sheet2', valueInputOption='RAW', body={'values': sheet_data}).execute()

def get_out_of_stock_products(brand_name):
    result = service.spreadsheets().values().get(spreadsheetId=SPREADSHEET_ID, range='Sheet2').execute()
    values = result.get('values', [])
    if not values or len(values) < 2:
        return pd.DataFrame()
    df = pd.DataFrame(values[1:], columns=values[0])
    return df[(df['Brand'] == brand_name) & (df['Stock Availability'] != 'In Stock')] if 'Brand' in df.columns and 'Stock Availability' in df.columns else pd.DataFrame()

# --- Streamlit UI ---
st.set_page_config(page_title="BigBasket Stock Dashboard", layout="wide")

# Navbar
st.markdown("""
    <style>
    .navbar {
        background-color: #333;
        padding: 10px;
        color: white;
        display: flex;
        justify-content: space-between;
        align-items: center;
    }
    .navbar a {
        color: white;
        text-decoration: none;
        margin: 0 15px;
    }
    .navbar a:hover {
        color: #ddd;
    }
    </style>
    <div class="navbar">
        <div>BigBasket Stock Dashboard</div>
        <div>
            <a href="#">Home</a>
            <a href="#">About</a>
            <a href="#">Contact</a>
        </div>
    </div>
""", unsafe_allow_html=True)

# Centered Heading
st.markdown("<h1 style='text-align: center;'>BigBasket Stock Dashboard</h1>", unsafe_allow_html=True)

# Fetch brands
brands_df = fetch_brands_from_sheet1()
brand_list = brands_df['Brand Name'].tolist()

# Tabs
tab1, tab2 = st.tabs(["Own Brand Analysis", "Competitor Brand Analysis"])

# Own Brand Tab
with tab1:
    st.subheader("Your Brand")
    own_brand_input = st.text_input("Type your brand name", key="own_brand_input", help="Start typing to filter suggestions")
    filtered_brands = [b for b in brand_list if own_brand_input.lower() in b.lower()] if own_brand_input else brand_list
    selected_own_brand = st.selectbox("Select your brand", filtered_brands, key="own_brand_select", help="Filtered based on your input")
    
    if st.button("Analyze Own Brand", key="own_analyze"):
        brand_url = brands_df[brands_df['Brand Name'] == selected_own_brand]['Brand URL'].iloc[0] if selected_own_brand in brand_list else f"https://www.bigbasket.com/pb/{selected_own_brand.lower()}/"
        with st.spinner(f"Scraping data for {selected_own_brand}..."):
            df = scrape_brand_data(selected_own_brand, brand_url)
            if not df.empty:
                append_to_sheet2(df)
                st.success(f"Scraped and saved data for {selected_own_brand}")
            else:
                st.warning(f"No data scraped for {selected_own_brand}")
        
        out_of_stock_df = get_out_of_stock_products(selected_own_brand)
        if not out_of_stock_df.empty:
            st.write(f"Out-of-Stock Products for {selected_own_brand}:")
            st.dataframe(out_of_stock_df)  # Display all columns
        else:
            st.write(f"No out-of-stock products found for {selected_own_brand}.")

# Competitor Brand Tab
with tab2:
    st.subheader("Competitor Brands (up to 5)")
    competitor_brands = []
    for i in range(5):
        comp_input = st.text_input(f"Competitor Brand {i+1}", key=f"comp_input_{i}", help="Start typing to filter suggestions")
        filtered_comp_brands = [b for b in brand_list if comp_input.lower() in b.lower()] if comp_input else brand_list
        selected_comp_brand = st.selectbox(f"Select Competitor {i+1}", filtered_comp_brands, key=f"comp_select_{i}")
        competitor_brands.append(selected_comp_brand)

    if st.button("Analyze Competitor Brands", key="comp_analyze"):
        selected_brands = [b for b in competitor_brands if b]
        if selected_brands:
            with st.spinner("Scraping competitor data..."):
                for brand in selected_brands:
                    brand_url = brands_df[brands_df['Brand Name'] == brand]['Brand URL'].iloc[0] if brand in brand_list else f"https://www.bigbasket.com/pb/{brand.lower()}/"
                    df = scrape_brand_data(brand, brand_url)
                    if not df.empty:
                        append_to_sheet2(df)
                st.success(f"Scraped and saved data for {', '.join(selected_brands)}")
            
            for brand in selected_brands:
                out_of_stock_df = get_out_of_stock_products(brand)
                if not out_of_stock_df.empty:
                    st.write(f"Out-of-Stock Products for {brand}:")
                    st.dataframe(out_of_stock_df)  # Display all columns
                else:
                    st.write(f"No out-of-stock products found for {brand}.")
        else:
            st.warning("Please enter at least one competitor brand.")