import streamlit as st
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup
import pandas as pd
import datetime
import json
from google.oauth2 import service_account
from googleapiclient.discovery import build

# --- Google Sheets Setup with Streamlit Secrets ---
SCOPES = ['https://www.googleapis.com/auth/spreadsheets']
SPREADSHEET_ID = '1sgpXQJW9oUjMpAbDUYa7J3qZALY5hwFsJGlcd9cd-8c'

# Load service account credentials from Streamlit secrets
creds_dict = json.loads(st.secrets["google_sheets"]["SERVICE_ACCOUNT_JSON"])
creds = service_account.Credentials.from_service_account_info(creds_dict, scopes=SCOPES)
service = build('sheets', 'v4', credentials=creds)

# Function to fetch brands from Sheet1
def fetch_brands_from_sheet1():
    result = service.spreadsheets().values().get(
        spreadsheetId=SPREADSHEET_ID,
        range='Sheet1'  # Assumes Sheet1 has 'Brand Name' in column A
    ).execute()
    values = result.get('values', [])
    if not values or len(values) < 2:  # Check if there's data beyond header
        return []
    headers = values[0]
    data = values[1:]
    df = pd.DataFrame(data, columns=headers)
    return df['Brand Name'].tolist()  # Return list of brand names

# Function to scrape brand data
def scrape_brand_data(brand_name):
    options = Options()
    options.add_argument("--headless")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("start-maximized")
    options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/110.0.0.0 Safari/537.36")

    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
    base_url = f"https://www.bigbasket.com/pb/{brand_name.lower()}/"
    driver.get(base_url)

    soup = BeautifulSoup(driver.page_source, "html.parser")
    product_containers = soup.find_all('div', class_='SKUDeck___StyledDiv-sc-1e5d9gk-0 eA-dmzP')
    all_data = []

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

    driver.quit()
    return pd.DataFrame(all_data)

# Function to append data to Sheet2
def append_to_sheet2(df):
    # Fetch existing data from Sheet2
    result = service.spreadsheets().values().get(
        spreadsheetId=SPREADSHEET_ID,
        range='Sheet2'
    ).execute()
    existing_values = result.get('values', [])
    
    # Prepare new data
    if not existing_values:  # If Sheet2 is empty, include headers
        header = df.columns.tolist()
        data = df.values.tolist()
        sheet_data = [header] + data
    else:  # Append only data rows
        data = df.values.tolist()
        sheet_data = existing_values + data

    # Write to Sheet2
    service.spreadsheets().values().update(
        spreadsheetId=SPREADSHEET_ID,
        range='Sheet2',
        valueInputOption='RAW',
        body={'values': sheet_data}
    ).execute()

# Function to fetch and filter out-of-stock products
def get_out_of_stock_products(brand_name):
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
    # Filter for the specific brand and out-of-stock items
    out_of_stock = df[(df['Brand'] == brand_name) & (df['Stock Availability'] != 'In Stock')]
    return out_of_stock

# --- Streamlit UI ---
st.title("BigBasket Stock Dashboard")

# Fetch brand list from Sheet1
brand_list = fetch_brands_from_sheet1()

# Create tabs
tab1, tab2 = st.tabs(["Your Brand", "Competitor Brands"])

# Tab 1: Own Brand
with tab1:
    st.subheader("Your Brand")
    own_brand_input = st.text_input("Type your brand name", key="own_brand")
    if own_brand_input:
        suggestions = [b for b in brand_list if own_brand_input.lower() in b.lower()]
        own_brand = st.selectbox("Select your brand", suggestions, key="own_select")
        
        if st.button("Submit", key="own_submit"):
            with st.spinner(f"Scraping data for {own_brand}..."):
                df = scrape_brand_data(own_brand)
                append_to_sheet2(df)
                st.success(f"Scraped and saved data for {own_brand}")
            
            out_of_stock_df = get_out_of_stock_products(own_brand)
            if not out_of_stock_df.empty:
                st.write(f"Out-of-Stock Products for {own_brand}:")
                st.dataframe(out_of_stock_df)
            else:
                st.write(f"No out-of-stock products found for {own_brand}.")

# Tab 2: Competitor Brands
with tab2:
    st.subheader("Competitor Brands (up to 5)")
    competitor_inputs = []
    for i in range(5):
        comp_input = st.text_input(f"Competitor Brand {i+1}", key=f"comp_{i}")
        if comp_input:
            suggestions = [b for b in brand_list if comp_input.lower() in b.lower()]
            selected = st.selectbox(f"Select Competitor {i+1}", suggestions, key=f"comp_select_{i}")
            competitor_inputs.append(selected)
        else:
            competitor_inputs.append(None)

    if st.button("Submit Competitors", key="comp_submit"):
        selected_brands = [b for b in competitor_inputs if b]  # Filter out None values
        if selected_brands:
            with st.spinner("Scraping competitor data..."):
                for brand in selected_brands:
                    df = scrape_brand_data(brand)
                    append_to_sheet2(df)
                st.success(f"Scraped and saved data for {', '.join(selected_brands)}")
            
            for brand in selected_brands:
                out_of_stock_df = get_out_of_stock_products(brand)
                if not out_of_stock_df.empty:
                    st.write(f"Out-of-Stock Products for {brand}:")
                    st.dataframe(out_of_stock_df)
                else:
                    st.write(f"No out-of-stock products found for {brand}.")
        else:
            st.warning("Please select at least one competitor brand.")
