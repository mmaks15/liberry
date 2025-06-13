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
        """Map color to simplified category while preserving original name"""
        if not color_name or color_name == "N/A":
            return "Other"
        
        color_lower = color_name.lower()
        
        # Enhanced color mapping for complex names
        color_mappings = {
            'black': ['black', 'midnight', 'onyx', 'charcoal', 'slate'],
            'white': ['white', 'ivory', 'cream', 'pearl', 'snow'],
            'gray': ['gray', 'grey', 'silver', 'stone', 'ash', 'smoke'],
            'blue': ['blue', 'navy', 'teal', 'aqua', 'ocean', 'sky', 'denim'],
            'red': ['red', 'burgundy', 'wine', 'crimson', 'cherry', 'rust'],
            'green': ['green', 'olive', 'forest', 'sage', 'mint', 'emerald'],
            'brown': ['brown', 'tan', 'beige', 'khaki', 'taupe', 'almond', 'bronze', 'copper'],
            'pink': ['pink', 'rose', 'blush', 'coral', 'salmon', 'peach'],
            'purple': ['purple', 'lavender', 'plum', 'violet', 'lilac'],
            'yellow': ['yellow', 'gold', 'butter', 'lemon', 'honey']
        }
        
        # Check each category
        for category, variations in color_mappings.items():
            if any(variation in color_lower for variation in variations):
                return category.title()
        
        return "Other"

    def _is_babylist_color(self, text):
        """Enhanced color detection for Babylist's complex color names"""
        if not text or len(text) > 100:  # Increased length for complex names
            return False
        
        text_lower = text.lower().strip()
        
        # Skip obvious non-colors
        skip_phrases = [
            'select', 'choose', 'available', 'add to cart', 'buy now', 'quantity',
            'shipping', 'return', 'description', 'reviews', 'specifications',
            'compare', 'wishlist', 'registry', 'gift', 'share'
        ]
        
        if any(skip in text_lower for skip in skip_phrases):
            return False
        
        # Babylist-specific color indicators
        color_indicators = [
            # Frame/seat combinations
            'frame', 'seat', 'canopy', 'fabric', 'chassis',
            # Color words
            'beige', 'taupe', 'almond', 'seashell', 'charcoal', 'slate',
            'navy', 'sage', 'olive', 'burgundy', 'plum', 'coral',
            'cream', 'ivory', 'pearl', 'silver', 'bronze', 'copper',
            'midnight', 'forest', 'ocean', 'sky', 'rose', 'blush',
            # Basic colors
            'black', 'white', 'gray', 'grey', 'blue', 'red', 'green',
            'brown', 'pink', 'purple', 'yellow', 'gold'
        ]
        
        # Check if text contains color indicators
        if any(indicator in text_lower for indicator in color_indicators):
            return True
        
        # Check for "color/color" pattern (like "Beige/Taupe")
        if '/' in text and len(text.split('/')) == 2:
            parts = text.split('/')
            if all(len(part.strip()) > 2 for part in parts):
                return True
        
        # If it's a reasonable length and doesn't contain obvious non-color words
        if 3 <= len(text) <= 50 and not any(char.isdigit() for char in text):
            # Check if it looks like a color name (mostly letters and spaces)
            if re.match(r'^[A-Za-z\s/\-&]+$', text):
                return True
        
        return False
    
    def _extract_colors_from_json(self, obj):
        """Extract colors from JSON-LD structured data"""
        colors = set()
        
        if isinstance(obj, dict):
            # Look for color-related keys
            color_keys = ['color', 'colors', 'variant', 'variants', 'model', 'name', 'description']
            
            for key in color_keys:
                if key in obj:
                    val = obj[key]
                    if isinstance(val, str) and self._is_babylist_color(val):
                        colors.add(val)
                    elif isinstance(val, list):
                        for item in val:
                            if isinstance(item, str) and self._is_babylist_color(item):
                                colors.add(item)
                            elif isinstance(item, dict):
                                colors.update(self._extract_colors_from_json(item))
            
            # Recursively search all values
            for value in obj.values():
                if isinstance(value, (dict, list)):
                    colors.update(self._extract_colors_from_json(value))
        
        elif isinstance(obj, list):
            for item in obj:
                colors.update(self._extract_colors_from_json(item))
        
        return colors
    
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
            
            # Color extraction - Extract colors first
            colors_found = set()
            
            # Priority 1: Color variant selectors (most reliable)
            color_selectors = [
                '[data-testid*="color-option"]',
                '[data-testid*="variant-option"]', 
                '[data-testid*="color-swatch"]',
                '.color-option',
                '.color-swatch',
                '.variant-option',
                '[class*="ColorOption"]',
                '[class*="VariantOption"]',
                '[class*="color-picker"]'
            ]
            
            for selector in color_selectors:
                elements = soup.select(selector)
                for elem in elements:
                    # Check multiple attributes for color names
                    for attr in ['data-color', 'data-variant', 'title', 'alt', 'aria-label', 'data-value']:
                        color_val = elem.get(attr, '').strip()
                        if color_val and self._is_babylist_color(color_val):
                            colors_found.add(color_val)
                    
                    # Check text content
                    text = elem.get_text().strip()
                    if text and self._is_babylist_color(text):
                        colors_found.add(text)
            
            # Priority 2: Dropdown/select options
            selects = soup.select('select, [role="listbox"]')
            for select in selects:
                # Check if this is a color/variant selector
                context = (select.get('name', '') + ' ' + select.get('aria-label', '') + ' ' + select.get('id', '')).lower()
                if any(word in context for word in ['color', 'variant', 'style', 'option']):
                    options = select.select('option, [role="option"]')
                    for option in options:
                        option_text = option.get_text().strip()
                        option_value = option.get('value', '').strip()
                        
                        if option_text and self._is_babylist_color(option_text):
                            colors_found.add(option_text)
                        if option_value and self._is_babylist_color(option_value):
                            colors_found.add(option_value)
            
            # Priority 3: Radio buttons and checkboxes with labels
            inputs = soup.select('input[type="radio"], input[type="checkbox"]')
            for inp in inputs:
                # Check input attributes
                for attr in ['data-color', 'value', 'title', 'aria-label']:
                    val = inp.get(attr, '').strip()
                    if val and self._is_babylist_color(val):
                        colors_found.add(val)
                
                # Check associated labels
                label_for = inp.get('id')
                if label_for:
                    label = soup.select_one(f'label[for="{label_for}"]')
                    if label:
                        label_text = label.get_text().strip()
                        if self._is_babylist_color(label_text):
                            colors_found.add(label_text)
            
            # Priority 4: Extract from product title/name (handles "- Color Name" format)
            product_name = product_data["name"]
            if product_name and product_name != "N/A":
                # Look for " - [color]" pattern at end of product name
                dash_match = re.search(r'\s+-\s+([^-]+)$', product_name)
                if dash_match:
                    potential_color = dash_match.group(1).strip()
                    if self._is_babylist_color(potential_color):
                        colors_found.add(potential_color)
                
                # Look for "in [color]" patterns
                in_matches = re.findall(r'\bin\s+([^,\(\)]+?)(?:\s*[\(\),]|$)', product_name, re.IGNORECASE)
                for match in in_matches:
                    color = match.strip()
                    if self._is_babylist_color(color):
                        colors_found.add(color)
            
            # Priority 5: Image alt text (often contains color info)
            images = soup.select('img[alt*="/"], img[alt*="Frame"], img[alt*="Seat"]')
            for img in images:
                alt_text = img.get('alt', '').strip()
                if alt_text:
                    # Extract color patterns from alt text
                    color_patterns = [
                        r'([A-Za-z\s]+(?:Frame|Seat|Canopy))',
                        r'in\s+([A-Za-z\s/]+)',
                        r'-\s*([A-Za-z\s/]+?)(?:\s|$)'
                    ]
                    
                    for pattern in color_patterns:
                        matches = re.findall(pattern, alt_text, re.IGNORECASE)
                        for match in matches:
                            if self._is_babylist_color(match.strip()):
                                colors_found.add(match.strip())
            
            # Priority 6: JSON-LD structured data
            try:
                scripts = soup.select('script[type="application/ld+json"]')
                for script in scripts:
                    if script.string:
                        data = json.loads(script.string)
                        json_colors = self._extract_colors_from_json(data)
                        colors_found.update(json_colors)
            except:
                pass
            
            # Clean and validate colors
            cleaned_colors = []
            for color in colors_found:
                if color and len(color.strip()) >= 3:
                    cleaned_color = color.strip()
                    # Remove duplicates (case-insensitive)
                    if not any(cleaned_color.lower() == existing.lower() for existing in cleaned_colors):
                        cleaned_colors.append(cleaned_color)
            
            # Set color data in product_data
            product_data["color_options"] = cleaned_colors if cleaned_colors else ["N/A"]
            
            # Create simplified colors using the existing method
            if cleaned_colors and cleaned_colors != ["N/A"]:
                simplified = [self.simplify_color(color) for color in cleaned_colors]
                product_data["simplified_colors"] = list(set(simplified))  # Remove duplicates
            else:
                product_data["simplified_colors"] = ["N/A"]
            
            # Continue with other extractions...
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
            
            # Extract price
            price_selectors = [
                '[data-testid*="price"]',
                '.price',
                '[class*="price"]',
                '.product-price'
            ]
            
            for selector in price_selectors:
                price_elem = soup.select_one(selector)
                if price_elem:
                    price_text = price_elem.get_text()
                    price_match = re.search(r'\$(\d+(?:,\d{3})*(?:\.\d{2})?)', price_text)
                    if price_match:
                        product_data["price"] = f"${price_match.group(1)}"
                        break
            
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
    
    def close(self):
        """Close the web driver"""
        if self.driver:
            self.driver.quit()

# Usage
if __name__ == "__main__":
    chrome_path = "/Users/makaylacheng/Downloads/chromedriver-mac-arm64/chromedriver"
    
    scraper = BabylistStrollerScraper(chrome_path)
    try:
        products = scraper.scrape_all_strollers()
        scraper.save_to_csv(products)
        print(f"\nScraping complete! Found {len(products)} products.")
    finally:
        scraper.close()