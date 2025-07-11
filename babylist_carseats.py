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

class BabylistCarSeatScraper:
    def __init__(self, chrome_path):
        self.chrome_path = chrome_path
        self.driver = None
        self.setup_driver()
        
    def setup_driver(self):
        """Initialize Chrome driver with options"""
        options = Options()
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_argument("--disable-extensions")
        options.add_argument("--disable-gpu")
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option('useAutomationExtension', False)
        
        service = Service(self.chrome_path)
        self.driver = webdriver.Chrome(service=service, options=options)
        self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
    
    def scroll_and_load_all(self, max_scrolls=25):
        """Scroll to load all products"""
        print("Loading all products...")
        last_height = self.driver.execute_script("return document.body.scrollHeight")
        
        for i in range(max_scrolls):
            self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(3)
            
            new_height = self.driver.execute_script("return document.body.scrollHeight")
            if new_height == last_height:
                print(f"No more content to load after {i+1} scrolls")
                break
            last_height = new_height
            print(f"Scroll {i+1}/{max_scrolls}")
    
    def extract_product_list(self):
        """Extract product URLs from listing page"""
        soup = BeautifulSoup(self.driver.page_source, 'html.parser')
        
        # More specific selectors for actual product links, avoiding navigation/category links
        selectors = [
            "[data-testid*='product'] a",
            ".product-card a",
            ".product-grid a",
            "[class*='ProductCard'] a",
            "[class*='product-item'] a"
        ]
        
        product_links = set()
        
        # First try specific product selectors
        for selector in selectors:
            links = soup.select(selector)
            for link in links:
                href = link.get('href')
                if href and '/gp/' in href:  # Only /gp/ links are actual products
                    full_url = urljoin("https://www.babylist.com", href)
                    product_links.add(full_url)
        
        # If we don't find many products with specific selectors, try broader approach
        if len(product_links) < 10:
            print("Using fallback method to find product links...")
            all_links = soup.select("a[href*='/gp/']")
            for link in all_links:
                href = link.get('href')
                if href and '/gp/' in href:
                    # Filter out non-car seat products by checking if link contains car seat-related terms
                    link_text = link.get_text().lower()
                    parent_text = ""
                    if link.parent:
                        parent_text = link.parent.get_text().lower()
                    
                    combined_text = link_text + " " + parent_text
                    
                    # Only include if it seems to be a car seat product
                    if any(term in combined_text for term in ['car seat', 'infant', 'seat', 'safety', 'base']):
                        full_url = urljoin("https://www.babylist.com", href)
                        # Exclude obvious non-car seat categories
                        if not any(exclude in href.lower() for exclude in [
                            'stroller', 'bottle', 'cleaning', 'nursing', 'swaddle', 'bassinet', 
                            'changing', 'bedding', 'blanket', 'toy', 'clothing', 'diaper'
                        ]):
                            product_links.add(full_url)
        
        # Final filter: only keep URLs that actually look like car seat products
        filtered_links = []
        for url in product_links:
            # Skip category pages and non-product pages
            if '/store/' in url and not '/gp/' in url:
                continue
            # Skip URLs with obvious non-car seat terms
            if any(term in url.lower() for term in [
                'stroller', 'bottle', 'cleaning', 'nursing', 'swaddle', 'bassinet',
                'changing', 'bedding', 'blanket', 'toy', 'clothing', 'diaper'
            ]):
                continue
            filtered_links.append(url)
        
        print(f"Found {len(filtered_links)} unique product URLs after filtering")
        return filtered_links
    
    def extract_description(self, soup):
        """Extract product description"""
        selectors = [
            '[data-testid*="description"]',
            '.product-description',
            '[class*="ProductDescription"]',
            'main p'
        ]
        
        for selector in selectors:
            elem = soup.select_one(selector)
            if elem:
                text = elem.get_text().strip()
                if len(text) > 50:
                    return re.sub(r'\s+', ' ', text)
        
        # Try JSON-LD
        try:
            for script in soup.select('script[type="application/ld+json"]'):
                if script.string:
                    data = json.loads(script.string)
                    desc = self._get_json_field(data, ['description', 'productDescription'])
                    if desc and len(desc) > 50:
                        return desc
        except:
            pass
        
        return "N/A"
    
    def _get_json_field(self, obj, fields):
        """Recursively search for fields in JSON object"""
        if isinstance(obj, dict):
            for field in fields:
                if field in obj and isinstance(obj[field], str):
                    return obj[field].strip()
            for value in obj.values():
                result = self._get_json_field(value, fields)
                if result:
                    return result
        elif isinstance(obj, list):
            for item in obj:
                result = self._get_json_field(item, fields)
                if result:
                    return result
        return None
    
    def extract_colors(self, soup, product_name):
        """Enhanced color extraction with better detection"""
        colors = set()
        
        # 1. Color variant buttons/options
        color_selectors = [
            '[data-testid*="color"]',
            '[data-testid*="variant"]',
            '.color-option',
            '.variant-option',
            '[class*="ColorOption"]',
            '[class*="VariantOption"]',
            'button[data-color]',
            '[role="radio"]'
        ]
        
        for selector in color_selectors:
            for elem in soup.select(selector):
                # Check attributes
                for attr in ['data-color', 'data-value', 'title', 'aria-label', 'alt']:
                    val = elem.get(attr, '').strip()
                    if val and self._is_color(val):
                        colors.add(val)
                
                # Check text content
                text = elem.get_text().strip()
                if text and self._is_color(text):
                    colors.add(text)
        
        # 2. Dropdown/select options
        for select in soup.select('select'):
            context = (select.get('name', '') + ' ' + select.get('aria-label', '')).lower()
            if any(word in context for word in ['color', 'variant', 'style']):
                for option in select.select('option'):
                    text = option.get_text().strip()
                    value = option.get('value', '').strip()
                    if text and self._is_color(text):
                        colors.add(text)
                    if value and self._is_color(value):
                        colors.add(value)
        
        # 3. Extract from product name (common pattern: "Product Name - Color")
        if product_name and ' - ' in product_name:
            potential_color = product_name.split(' - ')[-1].strip()
            if self._is_color(potential_color):
                colors.add(potential_color)
        
        # 4. Image alt text with color info
        for img in soup.select('img[alt]'):
            alt_text = img.get('alt', '')
            # Look for color patterns in alt text
            color_match = re.search(r'(?:in|frame|seat)\s+([A-Za-z\s/&-]+?)(?:\s|$|,)', alt_text, re.IGNORECASE)
            if color_match and self._is_color(color_match.group(1).strip()):
                colors.add(color_match.group(1).strip())
        
        # 5. Check for color variations in same product family
        # Look for links to other color variants
        for link in soup.select('a[href]'):
            href = link.get('href', '')
            if '/store/' in href or '/gp/' in href:
                link_text = link.get_text().strip()
                # If it's a similar product name but different color
                if product_name and len(link_text) > 10:
                    # Extract potential color from link text
                    if any(color_word in link_text.lower() for color_word in ['black', 'white', 'gray', 'blue', 'red', 'green', 'brown']):
                        color_match = re.search(r' - ([A-Za-z\s/&-]+)$', link_text)
                        if color_match and self._is_color(color_match.group(1).strip()):
                            colors.add(color_match.group(1).strip())
        
        return list(colors) if colors else ["N/A"]
    
    def _is_color(self, text):
        """Check if text represents a color"""
        if not text or len(text) > 50 or len(text) < 3:
            return False
        
        text_lower = text.lower().strip()
        
        # Skip non-colors
        skip_words = ['select', 'choose', 'add', 'cart', 'buy', 'quantity', 'shipping', 'size']
        if any(skip in text_lower for skip in skip_words):
            return False
        
        # Color indicators
        color_words = [
            'black', 'white', 'gray', 'grey', 'blue', 'red', 'green', 'brown', 'pink', 'purple', 'yellow',
            'navy', 'teal', 'sage', 'olive', 'burgundy', 'plum', 'coral', 'cream', 'ivory', 'charcoal',
            'slate', 'midnight', 'forest', 'ocean', 'rose', 'gold', 'silver', 'bronze', 'copper',
            'beige', 'taupe', 'almond', 'frame', 'seat', 'canopy'
        ]
        
        # Check if contains color words
        if any(color in text_lower for color in color_words):
            return True
        
        # Check format like "Color/Color"
        if '/' in text and len(text.split('/')) == 2:
            return all(len(part.strip()) > 2 for part in text.split('/'))
        
        # Check if it's mostly letters (potential color name)
        if re.match(r'^[A-Za-z\s/&-]+$', text) and not text.isdigit():
            return True
        
        return False
    
    def simplify_color(self, color_name):
        """Map color to simplified category"""
        if not color_name or color_name == "N/A":
            return "Other"
        
        color_lower = color_name.lower()
        
        color_map = {
            'Black': ['black', 'midnight', 'onyx', 'charcoal'],
            'White': ['white', 'ivory', 'cream', 'pearl'],
            'Gray': ['gray', 'grey', 'silver', 'slate', 'stone'],
            'Blue': ['blue', 'navy', 'teal', 'aqua', 'ocean'],
            'Red': ['red', 'burgundy', 'wine', 'crimson'],
            'Green': ['green', 'olive', 'forest', 'sage'],
            'Brown': ['brown', 'tan', 'beige', 'khaki', 'taupe', 'bronze'],
            'Pink': ['pink', 'rose', 'blush', 'coral'],
            'Purple': ['purple', 'lavender', 'plum'],
            'Yellow': ['yellow', 'gold']
        }
        
        for category, variations in color_map.items():
            if any(var in color_lower for var in variations):
                return category
        
        return "Other"
    
    def extract_dimensions(self, soup):
        """Extract dimensions from product details section - optimized for car seats"""
        # Look for "Details" section and various dimension patterns
        page_text = soup.get_text()
        
        # Car seat specific dimension patterns
        dimension_patterns = [
            # Pattern: L x W x H with or without units
            r'dimensions?[:\s]*(\d+(?:\.\d+)?)[″"\']*\s*[lL]?\s*[xX×]\s*(\d+(?:\.\d+)?)[″"\']*\s*[wW]?\s*[xX×]\s*(\d+(?:\.\d+)?)[″"\']*\s*[hH]?',
            # Pattern: 3 numbers separated by x without L/W/H labels
            r'dimensions?[:\s]*(\d+(?:\.\d+)?)[″"\']*\s*[xX×]\s*(\d+(?:\.\d+)?)[″"\']*\s*[xX×]\s*(\d+(?:\.\d+)?)[″"\']*',
            # Pattern: with inches explicitly mentioned
            r'dimensions?[:\s]*(\d+(?:\.\d+)?)\s*(?:inches?|in|″|")\s*[xX×]\s*(\d+(?:\.\d+)?)\s*(?:inches?|in|″|")\s*[xX×]\s*(\d+(?:\.\d+)?)\s*(?:inches?|in|″|")?',
            # Pattern: with commas as separators
            r'dimensions?[:\s]*(\d+(?:\.\d+)?)[″"\']*\s*[,]\s*(\d+(?:\.\d+)?)[″"\']*\s*[,]\s*(\d+(?:\.\d+)?)[″"\']*',
            # Pattern: Overall dimensions
            r'overall\s+dimensions?[:\s]*(\d+(?:\.\d+)?)[″"\']*\s*[xX×]\s*(\d+(?:\.\d+)?)[″"\']*\s*[xX×]\s*(\d+(?:\.\d+)?)[″"\']*',
            # Pattern: Seat dimensions
            r'seat\s+dimensions?[:\s]*(\d+(?:\.\d+)?)[″"\']*\s*[xX×]\s*(\d+(?:\.\d+)?)[″"\']*\s*[xX×]\s*(\d+(?:\.\d+)?)[″"\']*',
            # Pattern: Size specifications
            r'size[:\s]*(\d+(?:\.\d+)?)[″"\']*\s*[xX×]\s*(\d+(?:\.\d+)?)[″"\']*\s*[xX×]\s*(\d+(?:\.\d+)?)[″"\']*'
        ]
        
        for pattern in dimension_patterns:
            match = re.search(pattern, page_text, re.IGNORECASE)
            if match:
                return f'{match.group(1)}" x {match.group(2)}" x {match.group(3)}"'
        
        # Look in structured data sections
        details_sections = soup.select('h3, h4, h2, strong, b, dt, th')
        
        for section in details_sections:
            section_text = section.get_text().lower()
            if any(keyword in section_text for keyword in ['detail', 'spec', 'dimension', 'size']):
                # Found relevant section, look for dimensions in following content
                parent = section.parent or section
                
                # Check next siblings or parent content
                content_areas = [parent]
                if section.find_next_sibling():
                    content_areas.append(section.find_next_sibling())
                
                for content in content_areas:
                    if content:
                        full_text = content.get_text()
                        
                        for pattern in dimension_patterns:
                            match = re.search(pattern, full_text, re.IGNORECASE)
                            if match:
                                return f'{match.group(1)}" x {match.group(2)}" x {match.group(3)}"'
        
        # Check table data for dimensions
        tables = soup.select('table')
        for table in tables:
            table_text = table.get_text().lower()
            if any(keyword in table_text for keyword in ['dimension', 'size', 'measurement']):
                for pattern in dimension_patterns:
                    match = re.search(pattern, table_text, re.IGNORECASE)
                    if match:
                        return f'{match.group(1)}" x {match.group(2)}" x {match.group(3)}"'
        
        # Check list items and definition lists
        lists = soup.select('ul, ol, dl')
        for list_elem in lists:
            list_text = list_elem.get_text().lower()
            if any(keyword in list_text for keyword in ['dimension', 'size', 'measurement']):
                for pattern in dimension_patterns:
                    match = re.search(pattern, list_text, re.IGNORECASE)
                    if match:
                        return f'{match.group(1)}" x {match.group(2)}" x {match.group(3)}"'
        
        return "N/A"
    
    def extract_product_details(self, url):
        """Extract detailed info from product page"""
        try:
            print(f"Scraping: {url}")
            self.driver.get(url)
            WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.TAG_NAME, "body"))
            )
            time.sleep(3)
            
            soup = BeautifulSoup(self.driver.page_source, 'html.parser')
            
            # Basic product info
            product_data = {
                "name": "N/A",
                "brand": "N/A",
                "description": "N/A",
                "category": "Infant Car Seat",
                "price": "N/A",
                "retailer": "Babylist",
                "retailer_url": url,
                "color_options": [],
                "simplified_colors": [],
                "dimensions": "N/A",
                "weight": "N/A",
                "rating": "N/A",
                "image_url": "N/A"
            }
            
            # Product name
            title_tag = soup.select_one('title')
            if title_tag:
                title = re.sub(r'\s*\|\s*Babylist.*$', '', title_tag.get_text().strip())
                product_data["name"] = title
            
            if product_data["name"] == "N/A":
                h1_tag = soup.select_one('h1')
                if h1_tag:
                    product_data["name"] = h1_tag.get_text().strip()
            
            # Brand (from name or dedicated element) - car seat brands
            brands = ['Chicco', 'Graco', 'Britax', 'Nuna', 'Maxi-Cosi', 'Cybex', 'UPPAbaby', 
                     'Evenflo', 'Safety 1st', 'Cosco', 'Peg Perego', 'Clek', 'Diono']
            
            brand_elem = soup.select_one('[data-testid*="brand"], .brand, [class*="brand"]')
            if brand_elem:
                product_data["brand"] = brand_elem.get_text().strip()
            elif product_data["name"] != "N/A":
                for brand in brands:
                    if brand.lower() in product_data["name"].lower():
                        product_data["brand"] = brand
                        break
            
            # Description
            product_data["description"] = self.extract_description(soup)
            
            # Colors
            colors = self.extract_colors(soup, product_data["name"])
            product_data["color_options"] = colors
            
            if colors != ["N/A"]:
                simplified = list(set([self.simplify_color(color) for color in colors]))
                product_data["simplified_colors"] = simplified
            else:
                product_data["simplified_colors"] = ["N/A"]
            
            # Dimensions
            product_data["dimensions"] = self.extract_dimensions(soup)
            
            # Weight - Enhanced patterns for car seats
            page_text = soup.get_text().lower()
            weight_patterns = [
                r'weight[:\s]*(\d+(?:\.\d+)?)\s*lbs?',
                r'weighs[:\s]*(\d+(?:\.\d+)?)\s*lbs?',
                r'(\d+(?:\.\d+)?)\s*lbs?\s*weight',
                r'(\d+(?:\.\d+)?)\s*pounds?',
                r'seat\s+weight[:\s]*(\d+(?:\.\d+)?)\s*lbs?',
                r'car\s+seat\s+weight[:\s]*(\d+(?:\.\d+)?)\s*lbs?'
            ]
            
            for pattern in weight_patterns:
                weight_match = re.search(pattern, page_text)
                if weight_match:
                    product_data["weight"] = f"{weight_match.group(1)} lbs"
                    break
            
            # Price
            price_elem = soup.select_one('[data-testid*="price"], .price, [class*="price"]')
            if price_elem:
                price_match = re.search(r'\$(\d+(?:,\d{3})*(?:\.\d{2})?)', price_elem.get_text())
                if price_match:
                    product_data["price"] = f"${price_match.group(1)}"
            
            # Image - Enhanced with more selectors
            img_selectors = [
                'img[data-testid*="product"]',
                '.product-image img',
                'img[alt*="car seat"]',
                'img[alt*="Car Seat"]',
                'img[alt*="seat"]',
                'main img',
                '[data-testid*="image"] img',
                '.product-hero img',
                '.product-gallery img',
                'img[src*="product"]',
                'img[class*="product"]'
            ]
            
            product_data["image_url"] = "N/A"
            for selector in img_selectors:
                img = soup.select_one(selector)
                if img and img.get('src'):
                    src = img['src']
                    # Make sure it's a valid image URL
                    if src.startswith('http') or src.startswith('//'):
                        if src.startswith('//'):
                            src = 'https:' + src
                        product_data["image_url"] = src
                        break
            
            # If still no image found, try getting the first meaningful image
            if product_data["image_url"] == "N/A":
                all_imgs = soup.select('img[src]')
                for img in all_imgs:
                    src = img.get('src', '')
                    alt = img.get('alt', '').lower()
                    # Skip icons, logos, and other non-product images
                    if (src and 
                        not any(skip in src.lower() for skip in ['icon', 'logo', 'sprite', 'button']) and
                        not any(skip in alt for skip in ['icon', 'logo', 'button', 'arrow']) and
                        (src.startswith('http') or src.startswith('//'))):
                        
                        if src.startswith('//'):
                            src = 'https:' + src
                        product_data["image_url"] = src
                        break
            
            # Rating
            rating_elem = soup.select_one('[data-testid*="rating"], [class*="rating"]')
            if rating_elem:
                rating_match = re.search(r'(\d+(?:\.\d+)?)', rating_elem.get_text())
                if rating_match:
                    product_data["rating"] = rating_match.group(1)
            
            return product_data
            
        except Exception as e:
            print(f"Error scraping {url}: {e}")
            return None
    
    def scrape_all_infant_car_seats(self):
        """Main scraping method for infant car seats"""
        try:
            url = "https://www.babylist.com/store/infant-car-seats"
            print(f"Loading: {url}")
            self.driver.get(url)
            time.sleep(3)
            
            self.scroll_and_load_all()
            product_urls = self.extract_product_list()
            
            if not product_urls:
                print("No products found!")
                return []
            
            print(f"Found {len(product_urls)} infant car seat URLs")
            
            products = []
            for i, url in enumerate(product_urls, 1):
                print(f"\nProduct {i}/{len(product_urls)}")
                product_data = self.extract_product_details(url)
                if product_data:
                    products.append(product_data)
                    print(f"Colors found: {product_data['color_options']}")
                    print(f"Dimensions: {product_data['dimensions']}")
                    print(f"Weight: {product_data['weight']}")
                
                time.sleep(2)  # Be respectful
            
            return products
            
        except Exception as e:
            print(f"Scraping error: {e}")
            return []
    
    def save_to_csv(self, products, filename="babylist_infant_car_seats.csv"):
        """Save to CSV"""
        if not products:
            print("No products to save!")
            return
        
        df = pd.DataFrame(products)
        
        # Handle list columns
        for col in ['color_options', 'simplified_colors']:
            if col in df.columns:
                df[col] = df[col].apply(lambda x: ', '.join(x) if isinstance(x, list) else x)
        
        df.to_csv(filename, index=False)
        print(f"\nSaved {len(products)} products to {filename}")
    
    def close(self):
        """Close driver"""
        if self.driver:
            self.driver.quit()

# Usage
if __name__ == "__main__":
    chrome_path = "/Users/makaylacheng/Downloads/chromedriver-mac-arm64/chromedriver"
    
    scraper = BabylistCarSeatScraper(chrome_path)
    try:
        products = scraper.scrape_all_infant_car_seats()
        scraper.save_to_csv(products)
        print(f"\nComplete! Found {len(products)} infant car seats.")
    finally:
        scraper.close()