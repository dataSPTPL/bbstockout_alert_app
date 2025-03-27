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
        soup = BeautifulSoup(response.text, "html.parser")
        parent_container = soup.find('div', class_="grid grid-flow-col gap-x-6 relative mt-5 pb-5 border-t border-dashed border-silverSurfer-400")

        product_containers = parent_container.find_all('div', class_='SKUDeck___StyledDiv-sc-1e5d9gk-0 eA-dmzP')
        all_data = []

        if not product_containers:
            st.warning(f"No product containers found for {brand_name}. The page might require JavaScript rendering.")
            return pd.DataFrame()

        for container in product_containers:
            # Product Name
            product_name = container.find('h3', class_='block m-0 line-clamp-2 font-regular text-base leading-sm text-darkOnyx-800 pt-0.5 h-full')
            product_name = product_name.text.strip() if product_name else "N/A"
            
            # Price
            price = container.find('span', class_='Label-sc-15v1nk5-0 Pricing___StyledLabel-sc-pldi2d-1 gJxZPQ AypOi')
            price = price.text.strip() if price else "N/A"
            
            # Quantity
            quantity = container.find('div', class_='py-1.5 xl:py-1')
            quantity = quantity.text.strip() if quantity else "N/A"
            
            availability = container.find('span',class_='Label-sc-15v1nk5-0 Tags___StyledLabel2-sc-aeruf4-1 gJxZPQ gPgOvC')
            stock_availability=availability.text.strip() if availability else "In Stock"
        
            
            # Product URL
            product_link = container.find('a', href=True)
            product_url = "https://www.bigbasket.com" + product_link['href'] if product_link else "N/A"
            
            # Timestamp
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
    values = [df.columns.tolist()] + df.values.tolist()  # Include headers
    result = service.spreadsheets().values().append(
        spreadsheetId=SPREADSHEET_ID,
        range='Sheet2',
        valueInputOption='RAW',
        body={'values': values}
    ).execute()
    return result

def get_out_of_stock_products(brand_name):
    result = service.spreadsheets().values().get(spreadsheetId=SPREADSHEET_ID, range='Sheet2').execute()
    values = result.get('values', [])
    if not values or len(values) < 2:
        return pd.DataFrame()
    df = pd.DataFrame(values[1:], columns=values[0])
    return df[(df['Brand'] == brand_name) & (df['Stock Availability'] == 'Currently unavailable')]

# --- Streamlit UI ---
st.set_page_config(page_title="BigBasket Stock Dashboard", layout="wide")

# Custom CSS
st.markdown("""
    <style>
    .navbar {
        background-color: #333;
        padding: 10px;
        color: white;
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-bottom: 20px;
    }
    .navbar a {
        color: white;
        text-decoration: none;
        margin: 0 15px;
    }
    .navbar a:hover {
        color: #ddd;
    }
    .stButton>button {
        background-color: #4CAF50;
        color: white;
        border-radius: 4px;
        padding: 8px 16px;
        border: none;
    }
    .stButton>button:hover {
        background-color: #45a049;
    }
    .out-of-stock {
        color: red;
        font-weight: bold;
    }
    /* Ensure selectbox shows selected value clearly */
    .stSelectbox div[data-baseweb="select"] > div {
        border-radius: 4px;
        padding: 8px;
        font-size: 16px;
        color: #000 !important;  /* Ensure text is visible */
    }
    </style>
""", unsafe_allow_html=True)

# Navbar
st.markdown("""
    <div class="navbar">
        <div>BigBasket Stock Dashboard</div>
        <div>
            <a href="#">Home</a>
            <a href="#">About</a>
            <a href="#">Contact</a>
        </div>
    </div>
""", unsafe_allow_html=True)

# Main Header
st.markdown("<h1 style='text-align: center;'>BigBasket Stock Tracker</h1>", unsafe_allow_html=True)

# Fetch brands
brands_df = fetch_brands_from_sheet1()
brand_list = brands_df['Brand Name'].tolist()

# Single Autocomplete Search Bar with Session State
st.subheader("Brand Search")

# Use session state to persist the selected brand
if 'selected_brand' not in st.session_state:
    st.session_state.selected_brand = None

# Update session state when a brand is selected
def update_selected_brand():
    st.session_state.selected_brand = st.session_state.brand_search

selected_brand = st.selectbox(
    "Search for a brand (type to filter)", 
    options=brand_list,
    index=brand_list.index(st.session_state.selected_brand) if st.session_state.selected_brand in brand_list else None,
    placeholder="Start typing brand name...",
    key="brand_search",
    on_change=update_selected_brand
)

# Tabs
tab1, tab2 = st.tabs(["Brand Analysis", "Competitor Comparison"])

# Brand Analysis Tab
with tab1:
    if selected_brand:
        st.subheader(f"Analyzing: {selected_brand}")
        
        if st.button("Analyze Brand", key="analyze"):
            brand_url = brands_df[brands_df['Brand Name'] == selected_brand]['Brand URL'].iloc[0]
            with st.spinner(f"Scraping data for {selected_brand}..."):
                df = scrape_brand_data(selected_brand, brand_url)
                if not df.empty:
                    append_to_sheet2(df)
                    st.success(f"Scraped and saved data for {selected_brand}")
                    
                    # Show only out-of-stock items
                    out_of_stock_df = df[df['Stock Availability'] == 'Currently unavailable']
                    if not out_of_stock_df.empty:
                        st.subheader("Out of Stock Products")
                        st.markdown(f"<p class='out-of-stock'>{len(out_of_stock_df)} products out of stock</p>", unsafe_allow_html=True)
                        st.dataframe(out_of_stock_df)
                    else:
                        st.success("No products are out of stock!")
                    
                    # Show raw scraped data
                    st.subheader("Raw Scraped Data")
                    st.write(f"Total products scraped: {len(df)}")
                    st.dataframe(df)
                else:
                    st.warning(f"No products found for {selected_brand}")
        else:
            st.info("Click the 'Analyze Brand' button to start scraping")
    else:
        st.warning("Please select a brand to analyze")

# Competitor Comparison Tab
with tab2:
    st.subheader("Compare with Competitors")
    
    if selected_brand:
        st.write(f"Main brand: {selected_brand}")
    
    num_competitors = st.number_input("Number of competitors to compare", min_value=1, max_value=5, value=1)
    
    competitor_brands = []
    for i in range(num_competitors):
        # Use session state for competitor brands as well
        if f'comp_search_{i}' not in st.session_state:
            st.session_state[f'comp_search_{i}'] = None

        def update_competitor(i=i):
            st.session_state[f'comp_search_{i}'] = st.session_state[f'comp_search_{i}_select']

        competitor = st.selectbox(
            f"Search Competitor Brand {i+1}", 
            options=brand_list,
            index=brand_list.index(st.session_state[f'comp_search_{i}']) if st.session_state[f'comp_search_{i}'] in brand_list else None,
            placeholder=f"Type competitor brand name {i+1}...",
            key=f"comp_search_{i}_select",
            on_change=update_competitor
        )
        if competitor:
            competitor_brands.append(competitor)

    if st.button("Analyze Competitors", key="comp_analyze") and competitor_brands:
        all_data = []
        with st.spinner("Scraping competitor data..."):
            for brand in competitor_brands:
                brand_url = brands_df[brands_df['Brand Name'] == brand]['Brand URL'].iloc[0]
                df = scrape_brand_data(brand, brand_url)
                if not df.empty:
                    all_data.append(df)
            
            if all_data:
                combined_df = pd.concat(all_data)
                append_to_sheet2(combined_df)
                st.success(f"Scraped and saved data for {', '.join(competitor_brands)}")
                
                # Show out-of-stock items for competitors
                for brand in competitor_brands:
                    out_of_stock_df = combined_df[combined_df['Brand'] == brand]
                    out_of_stock_df = out_of_stock_df[out_of_stock_df['Stock Availability'] == 'Currently unavailable']
                    if not out_of_stock_df.empty:
                        st.subheader(f"Out of Stock Products for {brand}")
                        st.markdown(f"<p class='out-of-stock'>{len(out_of_stock_df)} products out of stock</p>", unsafe_allow_html=True)
                        st.dataframe(out_of_stock_df)
                    else:
                        st.success(f"No products are out of stock for {brand}!")
                
                # Show raw scraped data for all competitors
                st.subheader("Raw Scraped Data for Competitors")
                st.write(f"Total products scraped: {len(combined_df)}")
                st.dataframe(combined_df)
            else:
                st.warning("No data scraped for competitors")
    elif not competitor_brands:
        st.warning("Please select at least one competitor brand.")