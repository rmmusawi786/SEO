import requests
from bs4 import BeautifulSoup
import re
import json
import time
import random
from urllib.parse import urlparse
import streamlit as st
import pandas as pd
from utils.database import get_products, add_price_data, update_last_scrape, get_settings

def extract_price(text):
    """Extract a price from text by finding numbers with optional decimal points
    
    Handles various price formats including:
    - US/UK format (1,234.56)
    - European format (1.234,56)
    - Formats with currency symbols (€, $, etc.)
    - Formats with spaces as thousand separators (1 234,56)
    """
    if not text:
        return None
    
    # Clean up the text - remove currency symbols and extra spaces
    text = text.strip()
    text = re.sub(r'[€$£¥]', '', text)
    
    # Try to identify the format and extract the price
    
    # Case 1: European format with comma as decimal (1.234,56 or 1.845,90 €)
    euro_match = re.search(r'(\d{1,3}(?:\.\d{3})*),(\d{1,2})', text)
    if euro_match:
        try:
            whole_part = euro_match.group(1).replace('.', '')
            decimal_part = euro_match.group(2)
            price = float(f"{whole_part}.{decimal_part}")
            return price
        except (ValueError, AttributeError):
            pass
            
    # Additional European format (1845,90 €)
    euro_alt_match = re.search(r'(\d+),(\d{1,2})', text)
    if euro_alt_match:
        try:
            whole_part = euro_alt_match.group(1)
            decimal_part = euro_alt_match.group(2)
            price = float(f"{whole_part}.{decimal_part}")
            return price
        except (ValueError, AttributeError):
            pass
    
    # Case 2: US/UK format with dot as decimal (1,234.56)
    us_match = re.search(r'(\d{1,3}(?:,\d{3})*).(\d{1,2})', text)
    if us_match:
        try:
            whole_part = us_match.group(1).replace(',', '')
            decimal_part = us_match.group(2)
            price = float(f"{whole_part}.{decimal_part}")
            return price
        except (ValueError, AttributeError):
            pass
    
    # Case 3: Format with spaces as thousand separators (1 234,56)
    space_match = re.search(r'(\d{1,3}(?: \d{3})*)[,.](\d{1,2})', text)
    if space_match:
        try:
            whole_part = space_match.group(1).replace(' ', '')
            decimal_part = space_match.group(2)
            price = float(f"{whole_part}.{decimal_part}")
            return price
        except (ValueError, AttributeError):
            pass
    
    # Case 4: Simple number (1234 or 1234.56 or 1234,56)
    simple_match = re.search(r'(\d+)(?:[.,](\d{1,2}))?', text)
    if simple_match:
        try:
            whole_part = simple_match.group(1)
            decimal_part = simple_match.group(2) if simple_match.group(2) else "00"
            price = float(f"{whole_part}.{decimal_part}")
            return price
        except (ValueError, AttributeError):
            pass
    
    # If none of the above worked, try a more generic approach
    try:
        # Replace all commas with dots
        text = text.replace(',', '.')
        
        # Find any number with a decimal point
        price_matches = re.findall(r'\d+\.\d+|\d+', text)
        
        if price_matches:
            return float(price_matches[0])
    except ValueError:
        pass
    
    # If all else failed, return None
    return None

def parse_selector(selector):
    """
    Parse a selector to determine its type (id, class, tag, or CSS)
    
    Args:
        selector (str): The selector string
        
    Returns:
        tuple: (type, value) where type is 'id', 'class', 'tag', or 'css'
    """
    if not selector:
        return None, None
    
    # Check if it's an ID selector (starts with #)
    if selector.startswith('#'):
        return 'id', selector[1:]
    
    # Check if it's a class selector (starts with .)
    if selector.startswith('.'):
        return 'class', selector[1:]
    
    # Check if it might be an HTML element without any selectors
    if re.match(r'^[a-zA-Z][a-zA-Z0-9]*$', selector):
        return 'tag', selector
    
    # Otherwise treat as a normal CSS selector
    return 'css', selector

def find_element(soup, selector):
    """
    Find an element using various selector types including raw HTML
    
    Args:
        soup (BeautifulSoup): The BeautifulSoup object
        selector (str): The selector string or HTML fragment
        
    Returns:
        element: The found BeautifulSoup element or None
    """
    if not selector:
        return None
    
    # First, check if this is an HTML fragment
    if '<' in selector and '>' in selector:
        try:
            # For HTML fragments, search for a similar structure in the page
            html_fragment = selector.strip()
            
            # Create a more forgiving pattern by extracting key attributes and classes
            # Extract classes
            classes = re.findall(r'class=["\']([^"\']+)["\']', html_fragment)
            # Extract attributes like itemprop
            itemprops = re.findall(r'itemprop=["\']([^"\']+)["\']', html_fragment)
            # Extract IDs
            ids = re.findall(r'id=["\']([^"\']+)["\']', html_fragment)
            # Extract itemtype if present
            itemtypes = re.findall(r'itemtype=["\']([^"\']+)["\']', html_fragment)
            
            # Try finding by class combinations first
            if classes:
                # Try each class one by one
                for class_name in classes[0].split():
                    element = soup.find(class_=class_name)
                    if element:
                        return element
            
            # Try by ID
            if ids:
                element = soup.find(id=ids[0])
                if element:
                    return element
            
            # Try by itemprop
            if itemprops:
                element = soup.find(attrs={"itemprop": itemprops[0]})
                if element:
                    return element
            
            # Try by itemtype
            if itemtypes:
                element = soup.find(attrs={"itemtype": itemtypes[0]})
                if element:
                    return element
            
            # Try to find the nested tag structure
            # First, extract the primary tag name
            primary_tag_match = re.match(r'<([a-zA-Z][a-zA-Z0-9]*)[^>]*>', html_fragment)
            if primary_tag_match:
                primary_tag = primary_tag_match.group(1)
                
                # If we have a div.class structure, try to find that combination
                if primary_tag == 'div' and classes:
                    elements = soup.find_all('div', class_=classes[0])
                    for element in elements:
                        # If this div contains an h1 tag (common for product titles), return it
                        if element.find('h1'):
                            return element
                
                # For a typical product name container with H1
                if primary_tag == 'div':
                    # Look for H1 inside the div that might be a product title
                    h1_elements = soup.find_all('h1')
                    for h1 in h1_elements:
                        # Check if it has itemprop="name" (schema.org markup for product name)
                        if h1.get('itemprop') == 'name':
                            return h1
                        # Check if the h1 contains descriptive text
                        if len(h1.get_text().strip()) > 10:  # Likely a product name if sufficiently long
                            return h1
                
                # If looking for an h1 directly
                if primary_tag == 'h1':
                    h1_elements = soup.find_all('h1')
                    
                    # First, look for h1 with matching attributes
                    for h1 in h1_elements:
                        if any(attr in str(h1) for attr in ['itemprop="name"', 'class="title"', 'class="product-title"']):
                            return h1
                    
                    # If no specialized h1s found, just return the first h1 with substantial content
                    for h1 in h1_elements:
                        if len(h1.get_text().strip()) > 5:  # A real title should have some text
                            return h1
                
                # As a fallback, get the innermost tag name from the fragment
                tag_name = re.search(r'<([a-zA-Z][a-zA-Z0-9]*)[^>]*>[^<]*</\1>', html_fragment)
                if tag_name:
                    # Look for a tag with similar text content if there's text in the fragment
                    text_content = re.search(r'>([^<]+)<', html_fragment)
                    if text_content and text_content.group(1).strip():
                        # Search for elements with similar text
                        text_pattern = text_content.group(1).strip()
                        for element in soup.find_all(tag_name.group(1)):
                            if element.get_text().strip() and text_pattern in element.get_text().strip():
                                return element
            
            # If we're looking for a price element
            if 'price' in html_fragment.lower():
                # Look for elements with price-like text (numbers with currency symbols)
                price_elements = soup.find_all(string=re.compile(r'[\d.,]+\s*[€$£¥]|[€$£¥]\s*[\d.,]+'))
                if price_elements:
                    for price_text in price_elements:
                        # Return the parent element of the found text
                        return price_text.parent
            
            return None
        except Exception as e:
            # If parsing the HTML fragment fails, fall back to other methods
            pass
    
    # If not an HTML fragment or HTML parsing failed, proceed with regular selector handling
    selector_type, selector_value = parse_selector(selector)
    
    if selector_type == 'id':
        return soup.find(id=selector_value)
    
    elif selector_type == 'class':
        # Expand class search to look for any element with this class
        if selector_value:  # Check if selector_value is not None
            try:
                pattern = re.compile(rf'\b{re.escape(selector_value)}\b')
                elements = soup.find_all(class_=pattern)
                if elements:
                    return elements[0]  # Return the first match
            except (TypeError, re.error):
                pass
        return soup.find(class_=selector_value)
    
    elif selector_type == 'tag':
        # For tag selectors, try to be smarter about product names
        if selector_value and selector_value.lower() in ['h1', 'h2', 'h3']:
            # For headings, look for one with product name indicators
            elements = soup.find_all(selector_value)
            for element in elements:
                if element.get('itemprop') == 'name':
                    return element
                if 'title' in str(element.get('class', '')).lower() or 'product' in str(element.get('class', '')).lower():
                    return element
            # If no special heading found, return the first one
            if elements:
                return elements[0]
        return soup.find(selector_value)
    
    else:  # CSS selector
        try:
            return soup.select_one(selector)
        except Exception:
            # If the CSS selector fails, try a more forgiving approach
            try:
                # Try direct ID
                if '#' in selector:
                    id_part = selector.split('#')[1].split(' ')[0].split('.')[0]
                    return soup.find(id=id_part)
                # Try direct class
                elif '.' in selector:
                    class_part = selector.split('.')[1].split(' ')[0].split('#')[0]
                    return soup.find(class_=class_part)
            except Exception:
                pass
    
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
    # Get settings
    settings = get_settings()
    
    # Use settings for user agent and timeout
    user_agent = settings.get('user_agent', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36')
    timeout = settings.get('request_timeout', 30)
    
    headers = {
        'User-Agent': user_agent,
        'Accept-Language': 'en-US,en;q=0.9',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Referer': f'https://{urlparse(url).netloc}/'
    }
    
    if additional_headers:
        headers.update(additional_headers)
    
    try:
        response = requests.get(url, headers=headers, timeout=timeout)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        result = {'url': url}
        
        # Extract product name if selector provided
        if name_selector:
            name_element = find_element(soup, name_selector)
            if name_element:
                result['name'] = name_element.get_text().strip()
        
        # Extract price
        price_element = find_element(soup, price_selector)
        if price_element:
            price_text = price_element.get_text().strip()
            price = extract_price(price_text)
            result['price'] = price
        else:
            result['error'] = f"Price element not found with selector: {price_selector}"
        
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
        
        # Track issues with our product data
        our_product_issues = None
        if 'error' in our_result:
            our_product_issues = our_result['error']
        elif not our_price:
            our_product_issues = "Failed to extract price"
        
        # Scrape competitor prices
        competitor_prices = {}
        competitor_issues = {}  # Track issues with competitor data
        
        if product['competitor_urls'] and not pd.isna(product['competitor_urls']):
            competitor_urls = product['competitor_urls'].split(',')
            competitor_selectors = json.loads(product['competitor_selectors']) if not pd.isna(product['competitor_selectors']) else {}
            
            for i, comp_url in enumerate(competitor_urls):
                # Add a small delay to avoid being blocked
                time.sleep(random.uniform(1, 3))
                
                price_selector = competitor_selectors.get(f"price_{i}", None)
                name_selector = competitor_selectors.get(f"name_{i}", None)
                
                # Get competitor display name if available
                display_name = competitor_selectors.get(f"display_name_{i}", f"Competitor {i+1}")
                
                if price_selector:
                    comp_result = scrape_product(comp_url, price_selector, name_selector)
                    
                    # Use display name if available, otherwise use scraped name or default
                    competitor_name = display_name
                    if not competitor_name or competitor_name == f"Competitor {i+1}":
                        competitor_name = comp_result.get('name', display_name)
                    
                    if 'price' in comp_result and comp_result['price'] is not None:
                        competitor_prices[competitor_name] = comp_result['price']
                    else:
                        # Track issues with this competitor
                        if 'error' in comp_result:
                            issue = comp_result['error']
                        else:
                            issue = "Failed to extract price"
                        
                        competitor_issues[competitor_name] = {
                            'url': comp_url,
                            'issue': issue
                        }
                else:
                    competitor_issues[display_name] = {
                        'url': comp_url,
                        'issue': "No price selector configured"
                    }
        
        # Add price data to database if we have our price
        product_result = {
            'product_id': product_id,
            'product_name': product_name,
            'competitor_issues': competitor_issues
        }
        
        if our_price:
            add_price_data(product_id, our_price, competitor_prices)
            product_result['our_price'] = our_price
            product_result['competitor_prices'] = competitor_prices
        else:
            product_result['our_product_issues'] = our_product_issues
        
        results.append(product_result)
    
    # Update last scrape time
    update_last_scrape()
    
    return results

def test_scrape(url, price_selector, name_selector=None):
    """Test scraping a URL with given selectors"""
    result = scrape_product(url, price_selector, name_selector)
    return result
