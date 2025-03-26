import streamlit as st
import pandas as pd
from scraper import scrape_brand_data
import smtplib
from email.mime.text import MIMEText
import json

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
        st.success(f"Email sent for {product_name}!")
    except Exception as e:
        st.error(f"Failed to send email: {e}")

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
recipient_email = st.secrets["email"]["recipient_email"]

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
    my_brand = st.text_input("Enter your brand name:", key="my_brand_input")
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
        brand = st.text_input(f"Enter competitor brand {i+1}:", key=f"comp_{i}")
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
