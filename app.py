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

# Load service account credentials from Streamlit secrets
creds_dict = json.loads(st.secrets["google_sheets"]["SERVICE_ACCOUNT_JSON"])
creds = service_account.Credentials.from_service_account_info(creds_dict, scopes=SCOPES)
service = build('sheets', 'v4', credentials=creds)

# Function to fetch brands and URLs from Sheet1
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

# Function to scrape brand data using requests
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

# Function to append data to Sheet2
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
    
    if 'Brand' not in df.columns or 'Stock Availability' not in df.columns:
        return pd.DataFrame()
    
    out_of_stock = df[(df['Brand'] == brand_name) & (df['Stock Availability'] != 'In Stock')]
    return out_of_stock

# --- Streamlit UI ---
st.title("BigBasket Stock Dashboard")

# Fetch brand list and URLs from Sheet1
brands_df = fetch_brands_from_sheet1()
brand_list = brands_df['Brand Name'].tolist()

# Single container for all functionality
with st.container():
    # Your Brand Section
    st.subheader("Your Brand")
    own_brand = st.text_input("Type your brand name", key="own_brand", help="Start typing to see suggestions")
    
    # Display suggestions as a selectbox below the input
    if own_brand:
        suggestions = [b for b in brand_list if own_brand.lower() in b.lower()]
    else:
        suggestions = brand_list
    
    if suggestions:  # Only show selectbox if there are suggestions
        selected_own_brand = st.selectbox("Suggestions (select or keep typing)", suggestions, key="own_suggestion")
    else:
        selected_own_brand = own_brand  # Use typed value if no suggestions
    
    if st.button("Submit Your Brand", key="own_submit"):
        # Use the selected suggestion if available, otherwise the typed value
        final_own_brand = selected_own_brand if selected_own_brand in brand_list else own_brand
        brand_url = brands_df[brands_df['Brand Name'] == final_own_brand]['Brand URL'].iloc[0] if final_own_brand in brand_list else f"https://www.bigbasket.com/pb/{final_own_brand.lower()}/"
        with st.spinner(f"Scraping data for {final_own_brand}..."):
            df = scrape_brand_data(final_own_brand, brand_url)
            if not df.empty:
                append_to_sheet2(df)
                st.success(f"Scraped and saved data for {final_own_brand}")
            else:
                st.warning(f"No data scraped for {final_own_brand}")
        
        out_of_stock_df = get_out_of_stock_products(final_own_brand)
        if not out_of_stock_df.empty:
            st.write(f"Out-of-Stock Products for {final_own_brand}:")
            st.dataframe(out_of_stock_df)
        else:
            st.write(f"No out-of-stock products found for {final_own_brand}.")

    st.markdown("---")

    # Competitor Brands Section
    st.subheader("Competitor Brands (up to 5)")
    competitor_brands = []
    for i in range(5):
        comp_brand = st.text_input(f"Competitor Brand {i+1}", key=f"comp_{i}", help="Start typing to see suggestions")
        
        if comp_brand:
            suggestions = [b for b in brand_list if comp_brand.lower() in b.lower()]
        else:
            suggestions = brand_list
        
        if suggestions:
            selected_comp_brand = st.selectbox(f"Suggestions for Competitor {i+1}", suggestions, key=f"comp_suggestion_{i}")
        else:
            selected_comp_brand = comp_brand
        
        competitor_brands.append(selected_comp_brand if selected_comp_brand in brand_list else comp_brand)

    if st.button("Submit Competitor Brands", key="comp_submit"):
        selected_brands = [b for b in competitor_brands if b]  # Filter out empty inputs
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
                    st.dataframe(out_of_stock_df)
                else:
                    st.write(f"No out-of-stock products found for {brand}.")
        else:
            st.warning("Please enter at least one competitor brand.")