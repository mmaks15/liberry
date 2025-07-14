
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from bs4 import BeautifulSoup
import pandas as pd
import time

# === Setup ===
chrome_path = "/Users/makaylacheng/chromedriver"  # Update if needed
options = Options()
options.add_argument("--headless")
service = Service(chrome_path)
driver = webdriver.Chrome(service=service, options=options)

# === Step 1: Visit main product listing page ===
url = "https://www.babylist.com/store/single-strollers"
driver.get(url)
time.sleep(5)  # Wait for page to load

soup = BeautifulSoup(driver.page_source, "html.parser")
product_links = []
for a in soup.select("a[href*='/gp/']"):
    link = a["href"]
    if "/gp/" in link and link.startswith("/gp/"):
        full_link = "https://www.babylist.com" + link
        if full_link not in product_links:
            product_links.append(full_link)

print(f"Found {len(product_links)} product links.")

# === Step 2: Scrape each product detail page ===
products = []

for link in product_links:
    try:
        driver.get(link)
        WebDriverWait(driver, 5).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "h1"))
        )
        time.sleep(2)
        detail_soup = BeautifulSoup(driver.page_source, "html.parser")

        name = detail_soup.select_one("h1").text.strip()
        brand = name.split()[0] if name else "N/A"
        price_tag = detail_soup.select_one("[data-testid='price']")
        price = price_tag.text.strip() if price_tag else "N/A"

        # Image URL
        img_tag = detail_soup.select_one("img[src*='babylist.com']")
        image_url = img_tag["src"] if img_tag else "N/A"

        # Colors
        color_tags = detail_soup.select("div[data-testid='color-name']")
        colors = [c.text.strip() for c in color_tags] if color_tags else ["N/A"]

        # Dimensions
        dims_tag = detail_soup.find(string=lambda text: text and "Dimensions" in text)
        dimensions = dims_tag.find_next().text.strip() if dims_tag else "N/A"

        # Features as tags
        features = []
        bullet_tags = detail_soup.select("ul li")
        for li in bullet_tags:
            text = li.get_text(strip=True)
            if any(keyword in text.lower() for keyword in ["lightweight", "fold", "urban", "terrain", "bassinet", "recline", "compact", "modular", "seat", "comfort", "suspension"]):
                features.append(text.lower())

        # Star rating
        star_tag = detail_soup.select_one("div[data-testid='star-rating']")
        star_rating = star_tag.text.strip() if star_tag else "N/A"

        # Placeholder for individual star breakdown (not always available)
        review_counts = {"1_star": "N/A", "2_star": "N/A", "3_star": "N/A", "4_star": "N/A", "5_star": "N/A"}

        products.append({
            "name": name,
            "brand": brand,
            "price": price,
            "product_url": link,
            "image_url": image_url,
            "dimensions": dimensions,
            "colors": ", ".join(colors),
            "tags": ", ".join(features),
            "star_rating": star_rating,
            **review_counts
        })

    except Exception as e:
        print(f"Error scraping {link}: {e}")

driver.quit()

# === Step 3: Save results ===
df = pd.DataFrame(products)
df.to_csv("babylist_strollers.csv", index=False)
print("Saved to babylist_strollers.csv")
