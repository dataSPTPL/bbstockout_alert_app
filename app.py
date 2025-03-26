import streamlit as st
import pandas as pd
from scraper import scrape_brand_data
import smtplib
from email.mime.text import MIMEText
import gspread
from google.oauth2.service_account import Credentials

# Email notification function
def send_email(brand, product_name, sender_email, sender_password, recipient_email):
    subject = f"Stockout Alert: {brand} - {product_name}"
    body = f"The product '{product_name}' from {brand} is out of stock as of {pd.Timestamp.now()}."
    msg = MIMEText(body)
    msg['Subject'] = subject
    msg['From'] = sender_email
    msg['To'] = recipient_email

    try:
        with smtplib.SMTP('smtp.gmail.com', 587) as server:
            server.starttls()
            server.login(sender_email, sender_password)
            server.send_message(msg)
        st.success(f"Email sent to {recipient_email} for {product_name}!")
    except Exception as e:
        st.error(f"Failed to send email: {e}")

# Fetch brand list from Google Sheet
def get_brand_list(spreadsheet_url, creds_json):
    SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
    try:
        creds = Credentials.from_service_account_info(creds_json, scopes=SCOPES)
        gc = gspread.authorize(creds)
        spreadsheet = gc.open_by_url(spreadsheet_url)
        worksheet = spreadsheet.worksheet("Sheet1")  # Assuming brands are in Sheet1
        data = worksheet.get_all_values()
        headers = data[0]
        rows = data[1:]
        brands = [row[0] for row in rows if row]  # Extract "Brand" column
        return brands
    except Exception as e:
        st.error(f"Error fetching brand list: {e}")
        return []

# Streamlit app
st.title("Stockout Alert Dashboard")

# Load secrets
spreadsheet_url = st.secrets["google"]["spreadsheet_url"]
creds_json = {
    "type": st.secrets["google"]["type"],
    "project_id": st.secrets["google"]["project_id"],
    "private_key_id": st.secrets["google"]["private_key_id"],
    "private_key": st.secrets["google"]["private_key"],
    "client_email": st.secrets["google"]["client_email"],
    "client_id": st.secrets["google"]["client_id"],
    "auth_uri": st.secrets["google"]["auth_uri"],
    "token_uri": st.secrets["google"]["token_uri"],
    "auth_provider_x509_cert_url": st.secrets["google"]["auth_provider_x509_cert_url"],
    "client_x509_cert_url": st.secrets["google"]["client_x509_cert_url"]
}
sender_email = st.secrets["email"]["sender_email"]
sender_password = st.secrets["email"]["sender_password"]

# Get recipient email from user
recipient_email = st.text_input("Enter your email to receive stockout alerts:", key="recipient_email")
if not recipient_email:
    st.warning("Please enter an email address to proceed.")
    st.stop()

# Fetch brand list
brand_list = get_brand_list(spreadsheet_url, creds_json)

# Tabs for My Brand and Competitors
tab1, tab2 = st.tabs(["My Brand", "Competitors"])

# Session state to store data
if 'my_brand_data' not in st.session_state:
    st.session_state.my_brand_data = None
if 'competitor_data' not in st.session_state:
    st.session_state.competitor_data = []

# Tab 1: My Brand
with tab1:
    st.header("My Brand")
    my_brand = st.selectbox("Select or type your brand name:", options=[""] + brand_list, key="my_brand_input")
    if st.button("Submit My Brand"):
        if my_brand:
            with st.spinner(f"Scraping data for {my_brand}..."):
                df = scrape_brand_data(my_brand, spreadsheet_url, creds_json)
                if df is not None:
                    st.session_state.my_brand_data = df
                    st.success(f"Data scraped for {my_brand}!")
                    st.dataframe(df)

                    # Check for out-of-stock products
                    out_of_stock = df[df['Stock Availability'] != "In Stock"]
                    if not out_of_stock.empty:
                        for _, row in out_of_stock.iterrows():
                            send_email(my_brand, row['Product Name'], sender_email, sender_password, recipient_email)

# Tab 2: Competitors
with tab2:
    st.header("Competitor Brands")
    num_competitors = 5
    competitor_brands = []
    for i in range(num_competitors):
        brand = st.selectbox(f"Select or type competitor brand {i+1}:", options=[""] + brand_list, key=f"comp_{i}")
        if brand:
            competitor_brands.append(brand)

    if st.button("Submit Competitor Brands"):
        if competitor_brands:
            with st.spinner("Scraping data for competitors..."):
                competitor_data = []
                for brand in competitor_brands:
                    df = scrape_brand_data(brand, spreadsheet_url, creds_json)
                    if df is not None:
                        competitor_data.append(df)
                        # Check for out-of-stock products
                        out_of_stock = df[df['Stock Availability'] != "In Stock"]
                        if not out_of_stock.empty:
                            for _, row in out_of_stock.iterrows():
                                send_email(brand, row['Product Name'], sender_email, sender_password, recipient_email)
                st.session_state.competitor_data = competitor_data
                st.success("Data scraped for competitors!")
                for i, df in enumerate(competitor_data):
                    st.subheader(f"{competitor_brands[i]}")
                    st.dataframe(df)

# Display combined analysis
if st.session_state.my_brand_data is not None and st.session_state.competitor_data:
    st.header("Combined Analysis")
    all_data = pd.concat([st.session_state.my_brand_data] + st.session_state.competitor_data)
    st.dataframe(all_data)
