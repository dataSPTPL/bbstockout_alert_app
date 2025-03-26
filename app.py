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
            # Product Name
            product_name = container.find('h3', class_='block m-0 line-clamp-2 font-regular text-base leading-sm text-darkOnyx-800 pt-0.5 h-full')
            product_name = product_name.text.strip() if product_name else "N/A"
            
            # Price
            price = container.find('span', class_='Label-sc-15v1nk5-0 Pricing___StyledLabel-sc-pldi2d-1 gJxZPQ AypOi')
            price = price.text.strip() if price else "N/A"
            
            # Quantity
            quantity = container.find('div', class_='py-1.5 xl:py-1')
            quantity = quantity.text.strip() if quantity else "N/A"
            
            # Stock Availability - Improved detection
            stock_status = "In Stock"  # Default assumption
            
            # Check for "Currently unavailable" in different possible elements
            unavailable_tags = container.find_all(['span', 'div'], class_=lambda x: x and any(
                cls in x for cls in ['gPgOvC', 'jzSAAq', 'Tags___StyledLabel2-sc-aeruf4-1', 'Tags___StyledLabel-sc-aeruf4-0']
            ))
            
            for tag in unavailable_tags:
                if "unavailable" in tag.text.strip().lower():
                    stock_status = "Out of Stock"
                    break
            
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
                'Stock Availability': stock_status,
                'Product URL': product_url
            })
        return pd.DataFrame(all_data)
    except requests.RequestException as e:
        st.error(f"Error scraping {brand_name}: {str(e)}")
        return pd.DataFrame()

def append_to_sheet2(df):
    if df.empty:
        return
    values = df.values.tolist()
    body = {
        'values': values
    }
    result = service.spreadsheets().values().append(
        spreadsheetId=SPREADSHEET_ID,
        range='Sheet2',
        valueInputOption='RAW',
        body=body
    ).execute()
    return result

def get_out_of_stock_products(brand_name):
    result = service.spreadsheets().values().get(
        spreadsheetId=SPREADSHEET_ID,
        range='Sheet2'
    ).execute()
    values = result.get('values', [])
    if not values or len(values) < 2:
        return pd.DataFrame()
    df = pd.DataFrame(values[1:], columns=values[0])
    return df[(df['Brand'] == brand_name) & (df['Stock Availability'] == 'Out of Stock')]

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

# Search and Select Brand
st.subheader("Brand Search")
search_term = st.text_input("Start typing brand name", key="brand_search", 
                          help="Type to see matching brand suggestions")

# Filter brands based on search term
filtered_brands = [b for b in brand_list if search_term.lower() in b.lower()] if search_term else []

# Display dropdown only if there are matches
if filtered_brands:
    selected_brand = st.selectbox("Select a brand from suggestions", filtered_brands, key="brand_select")
else:
    selected_brand = None
    st.info("No matching brands found. Try a different search term.")

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
                    st.success(f"Successfully scraped {len(df)} products for {selected_brand}")
                    
                    # Display results
                    st.dataframe(df)
                    
                    # Out of stock analysis
                    out_of_stock_df = df[df['Stock Availability'] == 'Out of Stock']
                    if not out_of_stock_df.empty:
                        st.subheader("Out of Stock Products")
                        st.markdown(f"<p class='out-of-stock'>{len(out_of_stock_df)} products out of stock</p>", 
                                    unsafe_allow_html=True)
                        st.dataframe(out_of_stock_df)
                    else:
                        st.success("All products are in stock!")
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
    
    num_competitors = st.number_input("Number of competitors to compare", 
                                     min_value=1, max_value=5, value=1)
    
    competitor_brands = []
    
    for i in range(num_competitors):
        comp_search = st.text_input(f"Search Competitor Brand {i+1}", 
                                  key=f"comp_search_{i}")
        filtered_comps = [b for b in brand_list if comp_search.lower() in b.lower()] if comp_search else []
        
        if filtered_comps:
            selected_comp = st.selectbox(f"Select Competitor {i+1}", 
                                       filtered_comps, 
                                       key=f"comp_select_{i}")
            competitor_brands.append(selected_comp)
        else:
            st.info(f"Type to search for competitor brand {i+1}")

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
                st.success(f"Scraped data for {len(competitor_brands)} competitors")
                
                # Display competitor analysis
                st.subheader("Competitor Stock Analysis")
                
                # Summary stats
                summary = []
                for brand in competitor_brands:
                    brand_df = combined_df[combined_df['Brand'] == brand]
                    total = len(brand_df)
                    out_of_stock = len(brand_df[brand_df['Stock Availability'] == 'Out of Stock'])
                    summary.append({
                        'Brand': brand,
                        'Total Products': total,
                        'Out of Stock': out_of_stock,
                        '% Out of Stock': f"{(out_of_stock/total)*100:.1f}%" if total > 0 else "N/A"
                    })
                
                st.dataframe(pd.DataFrame(summary))
                
                # Detailed view
                st.subheader("Detailed Competitor Products")
                st.dataframe(combined_df)
            else:
                st.warning("No data scraped for competitors")