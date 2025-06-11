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
import json
from urllib.parse import urljoin

class BabylistStrollerScraper:
    def __init__(self, chrome_path):
        self.chrome_path = chrome_path
        self.driver = None
        self.setup_driver()
        
        # Color mapping to 10 simplified categories
        self.color_mapping = {
            'black': 'Black',
            'white': 'White', 
            'gray': 'Gray', 'grey': 'Gray', 'charcoal': 'Gray', 'slate': 'Gray',
            'blue': 'Blue', 'navy': 'Blue', 'teal': 'Blue', 'aqua': 'Blue',
            'red': 'Red', 'burgundy': 'Red', 'wine': 'Red', 'crimson': 'Red',
            'green': 'Green', 'olive': 'Green', 'forest': 'Green', 'sage': 'Green',
            'brown': 'Brown', 'tan': 'Brown', 'beige': 'Brown', 'khaki': 'Brown',
            'pink': 'Pink', 'rose': 'Pink', 'blush': 'Pink', 'coral': 'Pink',
            'purple': 'Purple', 'lavender': 'Purple', 'plum': 'Purple',
            'yellow': 'Yellow', 'gold': 'Yellow', 'cream': 'Yellow'
        }
    
    def setup_driver(self):
        """Initialize Chrome driver with options"""
        options = Options()
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_argument("--disable-extensions")
        options.add_argument("--disable-gpu")
        options.add_argument("--remote-debugging-port=9222")
        options.add_argument("--disable-web-security")
        options.add_argument("--allow-running-insecure-content")
        options.add_argument("--user-data-dir=/tmp/chrome_dev_test")
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option('useAutomationExtension', False)
        
        service = Service(self.chrome_path)
        self.driver = webdriver.Chrome(service=service, options=options)
        self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
    
    def scroll_and_load_all(self, max_scrolls=20):
        """Scroll to load all products with better detection"""
        print("Loading all products...")
        last_height = self.driver.execute_script("return document.body.scrollHeight")
        
        for i in range(max_scrolls):
            # Scroll down
            self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(3)
            
            # Check if new content loaded
            new_height = self.driver.execute_script("return document.body.scrollHeight")
            if new_height == last_height:
                print(f"No more content to load after {i+1} scrolls")
                break
            last_height = new_height
            print(f"Scroll {i+1}/{max_scrolls} - Page height: {new_height}")
    
    def extract_product_list(self):
        """Extract basic product info from listing page"""
        soup = BeautifulSoup(self.driver.page_source, 'html.parser')
        
        # Try multiple selectors for product cards
        selectors = [
            "div[class*='product-grid'] a",
            "div[class*='ProductGrid'] a", 
            "a[href*='/store/']",
            "[data-testid*='product'] a"
        ]
        
        product_links = []
        for selector in selectors:
            links = soup.select(selector)
            if links:
                print(f"Found {len(links)} products using selector: {selector}")
                
                # Debug: print first few URLs to see the pattern
                print("Sample URLs found:")
                for i, link in enumerate(links[:5]):
                    href = link.get('href')
                    if href:
                        full_url = urljoin("https://www.babylist.com", href)
                        print(f"  {i+1}: {full_url}")
                
                for link in links:
                    href = link.get('href')
                    if href and ('/store/' in href or '/gp/' in href):
                        # Accept both /store/ and /gp/ URLs since we're on the stroller page already
                        full_url = urljoin("https://www.babylist.com", href)
                        if full_url not in product_links:
                            product_links.append(full_url)
                break
        
        print(f"Total unique product URLs found: {len(product_links)}")
        
        # Debug: print first few final URLs
        if product_links:
            print("Final product URLs (first 5):")
            for i, url in enumerate(product_links[:5]):
                print(f"  {i+1}: {url}")
        
        return product_links
    
    def simplify_color(self, color_name):
        """Map color name to simplified category"""
        if not color_name or color_name == "N/A":
            return "Other"
            
        color_lower = color_name.lower()
        for key, simplified in self.color_mapping.items():
            if key in color_lower:
                return simplified
        return "Other"
    
    def extract_product_details(self, url):
        """Extract detailed info from individual product page"""
        try:
            print(f"Scraping: {url}")
            self.driver.get(url)
            WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.TAG_NAME, "body"))
            )
            time.sleep(2)
            
            soup = BeautifulSoup(self.driver.page_source, 'html.parser')
            
            # Extract basic info
            product_data = {
                "name": "N/A",
                "brand": "N/A", 
                "description": "N/A",
                "category": "Single Stroller",
                "price": "N/A",
                "retailer": "Babylist",
                "retailer_url": url,
                "tags": [],
                "image_url": "N/A",
                "sku": "N/A",
                "color_options": [],
                "simplified_colors": [],
                "weight": "N/A",
                "dimensions": "N/A",
                "rating": "N/A"
            }
            
            # Product name from title or h1
            title_tag = soup.select_one('title')
            if title_tag:
                title_text = title_tag.get_text().strip()
                # Remove "| Babylist" from title
                product_data["name"] = re.sub(r'\s*\|\s*Babylist.*$', '', title_text)
            
            h1_tag = soup.select_one('h1')
            if h1_tag and product_data["name"] == "N/A":
                product_data["name"] = h1_tag.get_text().strip()
            
            # Brand extraction
            brand_selectors = [
                '[data-testid*="brand"]',
                '.brand',
                '[class*="brand"]'
            ]
            for selector in brand_selectors:
                brand_elem = soup.select_one(selector)
                if brand_elem:
                    product_data["brand"] = brand_elem.get_text().strip()
                    break
            
            # If brand not found, try to extract from product name
            if product_data["brand"] == "N/A" and product_data["name"] != "N/A":
                # Common stroller brands
                brands = ['UPPAbaby', 'Bugaboo', 'Baby Jogger', 'BOB', 'Chicco', 'Graco', 
                         'Britax', 'Nuna', 'Maxi-Cosi', 'Cybex', 'Stokke', 'Doona']
                for brand in brands:
                    if brand.lower() in product_data["name"].lower():
                        product_data["brand"] = brand
                        break
            
            # Description - try multiple sources
            desc_sources = [
                'meta[name="description"]',
                'meta[property="og:description"]', 
                '[data-testid*="description"]',
                '.product-description',
                '[class*="description"]'
            ]
            
            for selector in desc_sources:
                desc_elem = soup.select_one(selector)
                if desc_elem:
                    if desc_elem.name == 'meta':
                        desc_text = desc_elem.get('content', '').strip()
                    else:
                        desc_text = desc_elem.get_text().strip()
                    
                    if desc_text and len(desc_text) > 20:
                        product_data["description"] = desc_text
                        break
            
            # SKU extraction
            sku_selectors = [
                '[data-testid*="sku"]',
                '[class*="sku"]', 
                'script[type="application/ld+json"]'
            ]
            
            for selector in sku_selectors:
                if 'script' in selector:
                    scripts = soup.select(selector)
                    for script in scripts:
                        try:
                            data = json.loads(script.string)
                            if isinstance(data, dict) and 'sku' in data:
                                product_data["sku"] = data['sku']
                                break
                            elif isinstance(data, list):
                                for item in data:
                                    if isinstance(item, dict) and 'sku' in item:
                                        product_data["sku"] = item['sku']
                                        break
                        except:
                            continue
                else:
                    sku_elem = soup.select_one(selector)
                    if sku_elem:
                        product_data["sku"] = sku_elem.get_text().strip()
                        break
            
            # Image URL
            img_selectors = [
                'img[data-testid*="product"]',
                '.product-image img',
                '[class*="product"] img',
                'img[alt*="stroller"]'
            ]
            
            for selector in img_selectors:
                img = soup.select_one(selector)
                if img and img.get('src'):
                    product_data["image_url"] = img['src']
                    break
            
            # Color options - look for color variants/swatches
            color_selectors = [
                '[data-testid*="color"]',
                '[class*="color"]',
                '[class*="swatch"]',
                '[data-testid*="variant"]'
            ]
            
            colors_found = set()
            for selector in color_selectors:
                color_elems = soup.select(selector)
                for elem in color_elems:
                    # Try different attributes
                    for attr in ['data-color', 'title', 'alt', 'aria-label']:
                        color_val = elem.get(attr)
                        if color_val:
                            colors_found.add(color_val.strip())
                    
                    # Try text content
                    text = elem.get_text().strip()
                    if text and len(text) < 30:  # Avoid long descriptions
                        colors_found.add(text)
            
            # If no colors found, try extracting from product name
            if not colors_found and product_data["name"] != "N/A":
                color_patterns = [
                    r'in (\w+)',
                    r'- (\w+(?:\s+\w+)?)\s*(?:\||$)',
                    r'\((\w+(?:\s+\w+)?)\)'
                ]
                
                for pattern in color_patterns:
                    matches = re.findall(pattern, product_data["name"], re.IGNORECASE)
                    for match in matches:
                        if not any(word in match.lower() for word in ['stroller', 'car', 'seat', 'system']):
                            colors_found.add(match.strip())
            
            product_data["color_options"] = list(colors_found) if colors_found else ["N/A"]
            product_data["simplified_colors"] = [self.simplify_color(color) for color in product_data["color_options"]]
            
            # Extract specifications (weight, dimensions, rating)
            spec_text = soup.get_text().lower()
            
            # Weight extraction
            weight_patterns = [
                r'weight[:\s]*(\d+(?:\.\d+)?)\s*(?:lbs?|pounds?)',
                r'(\d+(?:\.\d+)?)\s*(?:lbs?|pounds?)\s*weight',
                r'weighs?\s*(\d+(?:\.\d+)?)\s*(?:lbs?|pounds?)'
            ]
            
            for pattern in weight_patterns:
                match = re.search(pattern, spec_text)
                if match:
                    product_data["weight"] = f"{match.group(1)} lbs"
                    break
            
            # Dimensions extraction  
            dim_patterns = [
                r'dimensions?[:\s]*(\d+(?:\.\d+)?)\s*["\']?\s*[xX×]\s*(\d+(?:\.\d+)?)\s*["\']?\s*[xX×]\s*(\d+(?:\.\d+)?)\s*["\']?',
                r'(\d+(?:\.\d+)?)\s*["\']?\s*[lL]\s*[xX×]\s*(\d+(?:\.\d+)?)\s*["\']?\s*[wW]\s*[xX×]\s*(\d+(?:\.\d+)?)\s*["\']?\s*[hH]',
                r'folded[:\s]*(\d+(?:\.\d+)?)\s*["\']?\s*[xX×]\s*(\d+(?:\.\d+)?)\s*["\']?\s*[xX×]\s*(\d+(?:\.\d+)?)\s*["\']?'
            ]
            
            for pattern in dim_patterns:
                match = re.search(pattern, spec_text)
                if match:
                    dims = f'{match.group(1)}" x {match.group(2)}" x {match.group(3)}"'
                    product_data["dimensions"] = dims
                    break
            
            # Rating extraction
            rating_selectors = [
                '[data-testid*="rating"]',
                '[class*="rating"]',
                '[class*="stars"]'
            ]
            
            for selector in rating_selectors:
                rating_elem = soup.select_one(selector)
                if rating_elem:
                    rating_text = rating_elem.get_text()
                    rating_match = re.search(r'(\d+(?:\.\d+)?)\s*(?:out of|/)\s*5', rating_text)
                    if rating_match:
                        product_data["rating"] = rating_match.group(1)
                        break
                    
                    # Look for star elements
                    stars = rating_elem.select('[class*="star"]')
                    if stars:
                        filled_stars = len([s for s in stars if 'filled' in s.get('class', [])])
                        if filled_stars > 0:
                            product_data["rating"] = str(filled_stars)
                            break
            
            # Tags extraction
            tag_selectors = [
                '[data-testid*="tag"]',
                '[class*="tag"]',
                '[class*="feature"]',
                '[data-testid*="feature"]'
            ]
            
            tags = set()
            for selector in tag_selectors:
                tag_elems = soup.select(selector)
                for elem in tag_elems:
                    tag_text = elem.get_text().strip()
                    if tag_text and len(tag_text) < 50:
                        tags.add(tag_text)
            
            product_data["tags"] = list(tags)
            
            return product_data
            
        except Exception as e:
            print(f"Error scraping {url}: {e}")
            return None
    
    def scrape_all_strollers(self):
        """Main scraping method"""
        try:
            # Load the main page
            url = "https://www.babylist.com/store/single-strollers"
            print(f"Loading main page: {url}")
            self.driver.get(url)
            time.sleep(3)
            
            # Load all products
            self.scroll_and_load_all()
            
            # Get product URLs
            product_urls = self.extract_product_list()
            
            if not product_urls:
                print("No product URLs found!")
                return []
            
            # Scrape each product
            products = []
            for i, url in enumerate(product_urls, 1):
                print(f"\nScraping product {i}/{len(product_urls)}")
                product_data = self.extract_product_details(url)
                if product_data:
                    products.append(product_data)
                
                # Add delay to be respectful
                time.sleep(2)
            
            return products
            
        except Exception as e:
            print(f"Error in main scraping: {e}")
            return []
        
        finally:
            if self.driver:
                self.driver.quit()
    
    def save_to_csv(self, products, filename="babylist_single_strollers_complete.csv"):
        """Save products to CSV"""
        if not products:
            print("No products to save!")
            return
        
        df = pd.DataFrame(products)
        
        # Clean up list columns for CSV
        for col in ['color_options', 'simplified_colors', 'tags']:
            if col in df.columns:
                df[col] = df[col].apply(lambda x: ', '.join(x) if isinstance(x, list) else x)
        
        df.to_csv(filename, index=False)
        print(f"\nSaved {len(products)} products to {filename}")
        print(f"Columns: {list(df.columns)}")

# Usage
if __name__ == "__main__":
    chrome_path = "/Users/makaylacheng/Downloads/chromedriver-mac-arm64/chromedriver"
    
    scraper = BabylistStrollerScraper(chrome_path)
    products = scraper.scrape_all_strollers()
    scraper.save_to_csv(products)
    
    print(f"\nScraping complete! Found {len(products)} products.")