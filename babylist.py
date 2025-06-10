from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from bs4 import BeautifulSoup
import pandas as pd
import time
import re

# Setup
chrome_path = "/Users/makaylacheng/Downloads/chromedriver-mac-arm64/chromedriver"
options = Options()
options.add_argument("--no-sandbox")
options.add_argument("--disable-dev-shm-usage")
service = Service(chrome_path)
driver = webdriver.Chrome(service=service, options=options)

# Visit the page
url = "https://www.babylist.com/store/single-strollers"
driver.get(url)
time.sleep(3)

# Scroll to load all products
def scroll_and_collect(driver, pause_time=2, max_scrolls=15):
    last_height = driver.execute_script("return document.body.scrollHeight")
    for _ in range(max_scrolls):
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(pause_time)
        new_height = driver.execute_script("return document.body.scrollHeight")
        if new_height == last_height:
            break
        last_height = new_height

scroll_and_collect(driver)

# Parse page
soup = BeautifulSoup(driver.page_source, 'html.parser')

# Extract product tiles
product_cards = soup.select("div[class^='product-grid__ProductGrid__grid-item']")
print(f" Found {len(product_cards)} product cards.")

products = []
for card in product_cards:
    try:
        link_tag = card.select_one("a")
        product_url = "https://www.babylist.com" + link_tag["href"] if link_tag else "N/A"

        name_tag = card.select_one("img")
        name = name_tag.get("alt", "").strip() if name_tag else "N/A"

        img_url = name_tag.get("src") if name_tag else "N/A"
        price = "N/A"  # Babylist doesn't show price in tiles directly

        products.append({
            "name": name,
            "Brand": "Various",
            "description": "N/A",
            "category": "stroller",
            "price": price,
            "retailer": "Babylist",
            "retailer_url": product_url,
            "tags": [],
            "image_url": img_url,
            "SKU": "N/A",
            "Color Options": [],
            "simplified_color": []
        })

    except Exception as e:
        print(" Error with product card:", e)

# get description + color from each detail page
for product in products:
    try:
        driver.get(product["retailer_url"])
        WebDriverWait(driver, 5).until(EC.presence_of_element_located((By.TAG_NAME, "title")))
        detail_soup = BeautifulSoup(driver.page_source, 'html.parser')

        # Description from meta tag
        desc_meta = detail_soup.select_one('meta[name="description"]')
        description = desc_meta["content"] if desc_meta else ""
        product["description"] = description

        # Color from title
        title_tag = detail_soup.select_one("title")
        title_text = title_tag.get_text() if title_tag else ""
        match = re.search(r"- (.*?) \|", title_text)
        color = match.group(1).strip() if match else "N/A"
        product["Color Options"] = [color]

    except Exception as e:
        print(f" Failed to load details for {product['name']}: {e}")

driver.quit()

# Save to CSV
df = pd.DataFrame(products)
df.to_csv("babylist_single_strollers_full.csv", index=False)
print("Saved all strollers to babylist_single_strollers_full.csv")
