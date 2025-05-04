import requests
from bs4 import BeautifulSoup
import re
import json
import time
import random
from urllib.parse import urlparse
import streamlit as st
from utils.database import get_products, add_price_data, update_last_scrape

def extract_price(text):
    """Extract a price from text by finding numbers with optional decimal points"""
    if not text:
        return None
    
    # Clean up the text
    text = text.strip().replace(',', '.')
    
    # Find all potential price patterns in the text
    price_matches = re.findall(r'\d+\.\d+|\d+\,\d+|\d+', text)
    
    if not price_matches:
        return None
    
    # Return the first match as a float
    try:
        price = float(price_matches[0].replace(',', '.'))
        return price
    except ValueError:
        return None

def scrape_product(url, price_selector, name_selector=None, additional_headers=None):
    """
    Scrape product information from a URL
    
    Args:
        url (str): The URL to scrape
        price_selector (str): CSS selector for the price element
        name_selector (str, optional): CSS selector for the product name
        additional_headers (dict, optional): Additional headers for the request
        
    Returns:
        dict: Product information including name and price
    """
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        'Accept-Language': 'en-US,en;q=0.9',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Referer': f'https://{urlparse(url).netloc}/'
    }
    
    if additional_headers:
        headers.update(additional_headers)
    
    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        result = {'url': url}
        
        # Extract product name if selector provided
        if name_selector:
            name_element = soup.select_one(name_selector)
            if name_element:
                result['name'] = name_element.get_text().strip()
        
        # Extract price
        price_element = soup.select_one(price_selector)
        if price_element:
            price_text = price_element.get_text().strip()
            price = extract_price(price_text)
            result['price'] = price
        
        return result
    
    except Exception as e:
        return {
            'url': url,
            'error': str(e)
        }

def scrape_all_products():
    """Scrape all products in the database and update their price information"""
    products_df = get_products()
    
    if products_df.empty:
        return "No products to scrape"
    
    results = []
    
    for _, product in products_df.iterrows():
        product_id = product['id']
        product_name = product['name']
        
        # Scrape our product price
        our_result = scrape_product(
            product['our_url'],
            product['our_price_selector'],
            product['our_name_selector']
        )
        
        our_price = our_result.get('price')
        
        # Scrape competitor prices
        competitor_prices = {}
        
        if product['competitor_urls'] and not pd.isna(product['competitor_urls']):
            competitor_urls = product['competitor_urls'].split(',')
            competitor_selectors = json.loads(product['competitor_selectors']) if not pd.isna(product['competitor_selectors']) else {}
            
            for i, comp_url in enumerate(competitor_urls):
                # Add a small delay to avoid being blocked
                time.sleep(random.uniform(1, 3))
                
                price_selector = competitor_selectors.get(f"price_{i}", None)
                name_selector = competitor_selectors.get(f"name_{i}", None)
                
                if price_selector:
                    comp_result = scrape_product(comp_url, price_selector, name_selector)
                    
                    if 'price' in comp_result:
                        competitor_name = comp_result.get('name', f"Competitor {i+1}")
                        competitor_prices[competitor_name] = comp_result['price']
        
        # Add price data to database
        if our_price:
            add_price_data(product_id, our_price, competitor_prices)
            
            results.append({
                'product_id': product_id,
                'product_name': product_name,
                'our_price': our_price,
                'competitor_prices': competitor_prices
            })
    
    # Update last scrape time
    update_last_scrape()
    
    return results

def test_scrape(url, price_selector, name_selector=None):
    """Test scraping a URL with given selectors"""
    result = scrape_product(url, price_selector, name_selector)
    return result
