from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from bs4 import BeautifulSoup
import pandas as pd
import time
import datetime
from webdriver_manager.chrome import ChromeDriverManager
import gspread
from google.oauth2.service_account import Credentials
import os

# Function to scroll and load all content
def scroll_and_load(driver):
    last_height = driver.execute_script("return document.body.scrollHeight")
    while True:
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(3)
        new_height = driver.execute_script("return document.body.scrollHeight")
        if new_height == last_height:
            break
        last_height = new_height

# Main scraping function
def scrape_brand_data(brand_name, spreadsheet_url, creds_json):
    # Google Sheets Authentication using service account JSON
    SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
    try:
        creds = Credentials.from_service_account_info(creds_json, scopes=SCOPES)
        gc = gspread.authorize(creds)
        spreadsheet = gc.open_by_url(spreadsheet_url)
        try:
            worksheet = spreadsheet.worksheet("Sheet2")
        except gspread.exceptions.WorksheetNotFound:
            worksheet = spreadsheet.add_worksheet(title="Sheet2", rows=100, cols=20)
    except Exception as e:
        print(f"Error with Google Sheets: {e}")
        return None

    # Setup Chrome options for headless cloud environment
    options = Options()
    options.add_argument("--headless")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/110.0.0.0 Safari/537.36")

    try:
        driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
        base_url = f"https://www.bigbasket.com/pb/{brand_name}/"
        driver.get(base_url)
        scroll_and_load(driver)
        soup = BeautifulSoup(driver.page_source, "html.parser")
    except Exception as e:
        print(f"Error scraping {brand_name}: {e}")
        driver.quit()
        return None

    # Extract product data
    product_containers = soup.find_all('div', class_='SKUDeck___StyledDiv-sc-1e5d9gk-0 eA-dmzP')
    all_data = []

    for container in product_containers:
        product_name = container.find('h3', class_='block m-0 line-clamp-2 font-regular text-base leading-sm text-darkOnyx-800 pt-0.5 h-full').text.strip() if container.find('h3') else "N/A"
        price = container.find('span', class_='Label-sc-15v1nk5-0 Pricing___StyledLabel-sc-pldi2d-1 gJxZPQ AypOi').text.strip() if container.find('span', class_='Label-sc-15v1nk5-0 Pricing___StyledLabel-sc-pldi2d-1 gJxZPQ AypOi') else "N/A"
        quantity = container.find('div', class_='py-1.5 xl:py-1').text.strip() if container.find('div', class_='py-1.5 xl:py-1') else "N/A"
        stock_availability = container.find('span', class_='Label-sc-15v1nk5-0 Tags___StyledLabel2-sc-aeruf4-1 gJxZPQ gPgOvC').text.strip() if container.find('span', class_='Label-sc-15v1nk5-0 Tags___StyledLabel2-sc-aeruf4-1 gJxZPQ gPgOvC') else "In Stock"
        product_url = "https://www.bigbasket.com" + container.find('a', href=True)['href'] if container.find('a', href=True) else "N/A"
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

    df = pd.DataFrame(all_data)

    # Write to Google Sheets
    try:
        headers = df.columns.tolist()
        worksheet.append_row(headers)  # Append headers only once if needed
        worksheet.append_rows(df.values.tolist())
        print(f"✅ Written {len(df)} products for {brand_name} to Google Sheets!")
    except Exception as e:
        print(f"Error writing to Google Sheet: {e}")

    driver.quit()
    return df

if __name__ == "__main__":
