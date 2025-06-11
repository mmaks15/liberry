import requests
from bs4 import BeautifulSoup
import pandas as pd
import time
import re
import json
from urllib.parse import urljoin, urlparse
import random

class BabylistRequestsScraper:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1'
        })
        
        # Color mapping to 10 simplified categories
        self.color_mapping = {
            'black': 'Black',
            'white': 'White', 
            'gray': 'Gray', 'grey': 'Gray', 'charcoal': 'Gray', 'slate': 'Gray',
            'blue': 'Blue', 'navy': 'Blue', 'teal': 'Blue', 'aqua': 'Blue',
            'red': 'Red', 'burgundy': 'Red', 'wine': 'Red', 'crimson': 'Red',
            'green': 'Green', 'olive': 'Green', 'forest': 'Green', 'sage': 'Green',
            'brown': 'Brown', 'tan': 'Brown', 'beige': 'Brown', 'khaki': 'Brown',
            'coffee': 'Brown', 'espresso': 'Brown', 'chocolate': 'Brown',
            'pink': 'Pink', 'rose': 'Pink', 'blush': 'Pink', 'coral': 'Pink',
            'purple': 'Purple', 'lavender': 'Purple', 'plum': 'Purple',
            'yellow': 'Yellow', 'gold': 'Yellow', 'cream': 'Yellow'
        }
    
    def get_page(self, url, retries=3):
        """Get page content with retries"""
        for attempt in range(retries):
            try:
                response = self.session.get(url, timeout=15)
                response.raise_for_status()
                return response
            except Exception as e:
                print(f"Attempt {attempt + 1} failed for {url}: {e}")
                if attempt < retries - 1:
                    time.sleep(random.uniform(2, 4))
                else:
                    return None
    
    def simplify_color(self, color_name):
        """Map color name to simplified category"""
        if not color_name or color_name == "N/A":
            return "Other"
            
        color_lower = color_name.lower()
        for key, simplified in self.color_mapping.items():
            if key in color_lower:
                return simplified
        return "Other"
    
    def extract_price(self, soup, page_text):
        """Enhanced price extraction"""
        price_selectors = [
            '.price',
            '[data-testid*="price"]',
            '.product-price',
            '.current-price',
            '[class*="price"]',
            '.cost',
            '.amount'
        ]
        
        # Try CSS selectors first
        for selector in price_selectors:
            price_elem = soup.select_one(selector)
            if price_elem:
                price_text = price_elem.get_text().strip()
                price_match = re.search(r'\$(\d+(?:,\d{3})*(?:\.\d{2})?)', price_text)
                if price_match:
                    return f"${price_match.group(1)}"
        
        # Try regex patterns on full text
        price_patterns = [
            r'\$(\d+(?:,\d{3})*(?:\.\d{2})?)',
            r'price[:\s]*\$?(\d+(?:,\d{3})*(?:\.\d{2})?)',
            r'costs?\s*\$?(\d+(?:,\d{3})*(?:\.\d{2})?)',
            r'(\d+(?:,\d{3})*(?:\.\d{2})?)\s*dollars?'
        ]
        
        for pattern in price_patterns:
            match = re.search(pattern, page_text, re.IGNORECASE)
            if match:
                price_val = match.group(1)
                return f"${price_val}"
        
        return "N/A"
    
    def extract_sku(self, soup, page_text):
        """Enhanced SKU extraction"""
        sku_selectors = [
            '[data-testid*="sku"]',
            '.sku',
            '.product-sku',
            '.item-number',
            '[class*="sku"]'
        ]
        
        # Try CSS selectors
        for selector in sku_selectors:
            sku_elem = soup.select_one(selector)
            if sku_elem:
                sku_text = sku_elem.get_text().strip()
                if sku_text and len(sku_text) < 50:
                    return sku_text
        
        # Try regex patterns
        sku_patterns = [
            r'sku[:\s]*([a-zA-Z0-9\-_]+)',
            r'item\s*#?[:\s]*([a-zA-Z0-9\-_]+)',
            r'product\s*#?[:\s]*([a-zA-Z0-9\-_]+)',
            r'model[:\s]*([a-zA-Z0-9\-_]+)'
        ]
        
        for pattern in sku_patterns:
            match = re.search(pattern, page_text, re.IGNORECASE)
            if match:
                sku = match.group(1).strip()
                if 5 <= len(sku) <= 20:  # Reasonable SKU length
                    return sku
        
        return "N/A"
    
    def extract_dimensions(self, soup, page_text):
        """Enhanced dimensions extraction"""
        # Look for dimensions in structured data or specific elements
        dim_selectors = [
            '[data-testid*="dimension"]',
            '.dimensions',
            '.specs',
            '.specifications'
        ]
        
        for selector in dim_selectors:
            dim_elem = soup.select_one(selector)
            if dim_elem:
                dim_text = dim_elem.get_text().lower()
                dim_match = re.search(r'(\d+(?:\.\d+)?)\s*["\']?\s*[xX×]\s*(\d+(?:\.\d+)?)\s*["\']?\s*[xX×]\s*(\d+(?:\.\d+)?)\s*["\']?', dim_text)
                if dim_match:
                    return f'{dim_match.group(1)}" x {dim_match.group(2)}" x {dim_match.group(3)}"'
        
        # Enhanced regex patterns for dimensions
        dim_patterns = [
            r'dimensions?[:\s]*(\d+(?:\.\d+)?)\s*["\']?\s*[xX×]\s*(\d+(?:\.\d+)?)\s*["\']?\s*[xX×]\s*(\d+(?:\.\d+)?)\s*["\']?',
            r'(\d+(?:\.\d+)?)\s*["\']?\s*[lL]\s*[xX×]\s*(\d+(?:\.\d+)?)\s*["\']?\s*[wW]\s*[xX×]\s*(\d+(?:\.\d+)?)\s*["\']?\s*[hH]',
            r'folded[:\s]*(\d+(?:\.\d+)?)\s*["\']?\s*[xX×]\s*(\d+(?:\.\d+)?)\s*["\']?\s*[xX×]\s*(\d+(?:\.\d+)?)\s*["\']?',
            r'open[:\s]*(\d+(?:\.\d+)?)\s*["\']?\s*[xX×]\s*(\d+(?:\.\d+)?)\s*["\']?\s*[xX×]\s*(\d+(?:\.\d+)?)\s*["\']?',
            r'size[:\s]*(\d+(?:\.\d+)?)\s*["\']?\s*[xX×]\s*(\d+(?:\.\d+)?)\s*["\']?\s*[xX×]\s*(\d+(?:\.\d+)?)\s*["\']?'
        ]
        
        for pattern in dim_patterns:
            match = re.search(pattern, page_text)
            if match:
                dims = f'{match.group(1)}" x {match.group(2)}" x {match.group(3)}"'
                return dims
        
        return "N/A"
    
    def extract_rating(self, soup, page_text):
        """Enhanced rating extraction"""
        rating_selectors = [
            '[data-testid*="rating"]',
            '.rating',
            '.stars',
            '.review-score',
            '[class*="rating"]',
            '[class*="stars"]'
        ]
        
        # Try CSS selectors
        for selector in rating_selectors:
            rating_elem = soup.select_one(selector)
            if rating_elem:
                rating_text = rating_elem.get_text()
                rating_match = re.search(r'(\d+(?:\.\d+)?)', rating_text)
                if rating_match:
                    rating_val = float(rating_match.group(1))
                    if 0 <= rating_val <= 5:
                        return str(rating_val)
        
        # Enhanced regex patterns for ratings
        rating_patterns = [
            r'(\d+(?:\.\d+)?)\s*(?:out of|/)\s*5\s*stars?',
            r'rating[:\s]*(\d+(?:\.\d+)?)',
            r'(\d+(?:\.\d+)?)\s*stars?',
            r'score[:\s]*(\d+(?:\.\d+)?)',
            r'rated\s*(\d+(?:\.\d+)?)'
        ]
        
        for pattern in rating_patterns:
            match = re.search(pattern, page_text, re.IGNORECASE)
            if match:
                rating_val = float(match.group(1))
                if 0 <= rating_val <= 5:
                    return str(rating_val)
        
        return "N/A"
    
    def extract_colors(self, soup, page_text, product_name):
        """Enhanced color extraction"""
        colors_found = set()
        
        # Look for color selection elements
        color_selectors = [
            '[data-testid*="color"]',
            '.color-option',
            '.color-selector',
            '[class*="color"]',
            '.variant-option'
        ]
        
        for selector in color_selectors:
            color_elems = soup.select(selector)
            for elem in color_elems:
                color_text = elem.get_text().strip()
                if color_text and len(color_text) < 30:
                    colors_found.add(color_text)
        
        # Try to find colors in the title
        if product_name != "N/A":
            color_patterns = [
                r'in (\w+(?:\s+\w+)?)',
                r'- (\w+(?:\s+\w+)?)\s*(?:\||$)',
                r'\((\w+(?:\s+\w+)?)\)',
                r', (\w+(?:\s+\w+)?)$'
            ]
            
            for pattern in color_patterns:
                matches = re.findall(pattern, product_name, re.IGNORECASE)
                for match in matches:
                    if not any(word in match.lower() for word in ['stroller', 'car', 'seat', 'system', 'baby', 'jogger']):
                        colors_found.add(match.strip().title())
        
        # Look for color mentions in page text with context
        color_keywords = ['black', 'white', 'gray', 'grey', 'blue', 'red', 'green', 'brown', 
                         'pink', 'purple', 'yellow', 'navy', 'charcoal', 'beige', 'tan',
                         'silver', 'gold', 'cream', 'ivory', 'teal', 'burgundy', 'olive']
        
        for color in color_keywords:
            color_patterns = [
                rf'available in {color}',
                rf'{color} color',
                rf'{color} option',
                rf'comes in {color}',
                rf'choose {color}'
            ]
            
            for pattern in color_patterns:
                if re.search(pattern, page_text, re.IGNORECASE):
                    colors_found.add(color.title())
        
        return list(colors_found) if colors_found else ["N/A"]
    
    def extract_product_links(self):
        """Extract product URLs from the main listing page"""
        url = "https://www.babylist.com/store/single-strollers"
        print(f"Fetching main page: {url}")
        
        response = self.get_page(url)
        if not response:
            print("Failed to fetch main page")
            return []
        
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Enhanced selectors for product links
        selectors = [
            "div[class*='product-grid'] a",
            "a[href*='/gp/']",
            "a[href*='/store/']",
            "[data-testid*='product'] a",
            "div[class*='product'] a",
            ".product-tile a",
            ".product-card a",
            "article a",
            "[class*='item'] a"
        ]
        
        product_links = set()
        
        for selector in selectors:
            links = soup.select(selector)
            print(f"Selector '{selector}' found {len(links)} links")
            
            for link in links:
                href = link.get('href')
                if href and ('/store/' in href or '/gp/' in href):
                    full_url = urljoin("https://www.babylist.com", href)
                    product_links.add(full_url)
            
            if product_links:
                break
        
        # Fallback: try to find any product-related links
        if not product_links:
            print("No product links found with specific selectors, trying general approach...")
            all_links = soup.find_all('a', href=True)
            for link in all_links:
                href = link['href']
                if ('/store/' in href or '/gp/' in href) and any(word in href.lower() for word in ['stroller', 'product', 'item']):
                    full_url = urljoin("https://www.babylist.com", href)
                    product_links.add(full_url)
        
        product_list = list(product_links)
        print(f"Found {len(product_list)} unique product URLs")
        
        # Debug: show first few URLs
        if product_list:
            print("Sample URLs:")
            for i, url in enumerate(product_list[:5]):
                print(f"  {i+1}: {url}")
        
        return product_list
    
    def extract_product_details(self, url):
        """Extract detailed info from individual product page"""
        print(f"Scraping: {url}")
        
        response = self.get_page(url)
        if not response:
            print(f"Failed to fetch {url}")
            return None
        
        soup = BeautifulSoup(response.content, 'html.parser')
        page_text = soup.get_text().lower()
        
        # Initialize product data
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
        
        # Product name extraction
        name_selectors = [
            'h1[data-testid*="title"]',
            'h1[class*="title"]',
            'h1[class*="name"]',
            '.product-title',
            '.product-name',
            'h1'
        ]
        
        for selector in name_selectors:
            name_elem = soup.select_one(selector)
            if name_elem:
                product_data["name"] = name_elem.get_text().strip()
                break
        
        # Fallback to title tag
        if product_data["name"] == "N/A":
            title_tag = soup.select_one('title')
            if title_tag:
                title_text = title_tag.get_text().strip()
                product_data["name"] = re.sub(r'\s*\|\s*Babylist.*$', '', title_text)
        
        # Brand extraction
        if product_data["name"] != "N/A":
            brands = ['UPPAbaby', 'Bugaboo', 'Baby Jogger', 'BOB', 'Chicco', 'Graco', 
                     'Britax', 'Nuna', 'Maxi-Cosi', 'Cybex', 'Stokke', 'Doona', 'Evenflo',
                     'Summer Infant', 'Joovy', 'Phil & Teds', 'Mountain Buggy', 'Thule']
            for brand in brands:
                if brand.lower() in product_data["name"].lower():
                    product_data["brand"] = brand
                    break
        
        # Description extraction
        desc_selectors = [
            '[data-testid*="description"]',
            '.product-description',
            '.description',
            'meta[name="description"]',
            'meta[property="og:description"]'
        ]
        
        for selector in desc_selectors:
            desc_elem = soup.select_one(selector)
            if desc_elem:
                if desc_elem.name == 'meta':
                    product_data["description"] = desc_elem.get('content', '').strip()
                else:
                    product_data["description"] = desc_elem.get_text().strip()
                if product_data["description"]:
                    break
        
        # Image URL extraction
        img_selectors = [
            'meta[property="og:image"]',
            '[data-testid*="image"] img',
            '.product-image img',
            '.main-image img',
            'img[alt*="stroller"]',
            'img[src*="product"]'
        ]
        
        for selector in img_selectors:
            img = soup.select_one(selector)
            if img:
                src = img.get('content') if img.name == 'meta' else img.get('src')
                if src and src.startswith(('http', '//')):
                    product_data["image_url"] = src
                    break
        
        # Extract all the missing fields using enhanced methods
        product_data["price"] = self.extract_price(soup, page_text)
        product_data["sku"] = self.extract_sku(soup, page_text)
        product_data["dimensions"] = self.extract_dimensions(soup, page_text)
        product_data["rating"] = self.extract_rating(soup, page_text)
        
        # Weight extraction (keeping existing logic but enhanced)
        weight_patterns = [
            r'weight[:\s]*(\d+(?:\.\d+)?)\s*(?:lbs?|pounds?)',
            r'(\d+(?:\.\d+)?)\s*(?:lbs?|pounds?)\s*(?:weight|when folded)',
            r'weighs?\s*(\d+(?:\.\d+)?)\s*(?:lbs?|pounds?)',
            r'(\d+(?:\.\d+)?)\s*lb\s*weight'
        ]
        
        for pattern in weight_patterns:
            match = re.search(pattern, page_text)
            if match:
                product_data["weight"] = f"{match.group(1)} lbs"
                break
        
        # Color extraction
        color_options = self.extract_colors(soup, page_text, product_data["name"])
        product_data["color_options"] = color_options
        product_data["simplified_colors"] = [self.simplify_color(color) for color in color_options]
        
        # Tags extraction (enhanced)
        feature_keywords = ['lightweight', 'compact', 'foldable', 'travel', 'jogging', 'all-terrain', 
                           'reversible', 'adjustable', 'safety', 'storage', 'canopy', 'wheels',
                           'one-hand', 'quick-fold', 'car-seat', 'compatible', 'umbrella']
        
        tags = []
        for keyword in feature_keywords:
            if keyword.replace('-', ' ') in page_text or keyword.replace('-', '') in page_text:
                tags.append(keyword.replace('-', ' ').title())
        
        product_data["tags"] = tags
        
        print(f"  ✓ Name: {product_data['name'][:50]}...")
        print(f"  ✓ Price: {product_data['price']}")
        print(f"  ✓ SKU: {product_data['sku']}")
        print(f"  ✓ Colors: {', '.join(product_data['color_options'][:3])}")
        print(f"  ✓ Dimensions: {product_data['dimensions']}")
        print(f"  ✓ Rating: {product_data['rating']}")
        
        return product_data
    
    def scrape_all_strollers(self):
        """Main scraping method"""
        # Get product URLs
        product_urls = self.extract_product_links()
        
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
            
            # Be respectful - add delay
            time.sleep(random.uniform(2, 3))
        
        return products
    
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
        
        # Print summary of data completeness
        print("\nData completeness summary:")
        for col in ['price', 'sku', 'color_options', 'dimensions', 'rating']:
            if col in df.columns:
                non_na_count = len(df[df[col] != 'N/A'])
                total_count = len(df)
                percentage = (non_na_count / total_count * 100) if total_count > 0 else 0
                print(f"  {col}: {non_na_count}/{total_count} ({percentage:.1f}%)")

# Usage
if __name__ == "__main__":
    scraper = BabylistRequestsScraper()
    products = scraper.scrape_all_strollers()
    scraper.save_to_csv(products)
    
    print(f"\nScraping complete! Found {len(products)} products.")
    
    # Show sample of extracted data
    if products:
        print("\nSample product data:")
        sample = products[0]
        for key, value in sample.items():
            print(f"  {key}: {value}")