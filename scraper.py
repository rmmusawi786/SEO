import requests
import re
import json
import time
import threading
import datetime
import concurrent.futures
import pandas as pd
from bs4 import BeautifulSoup
import schedule
import traceback

from database import get_products, add_price_data, get_settings, update_last_scrape

# Global variables for the scheduler
scheduler_thread = None
scheduler_running = False
scheduler_last_run = None

class ScrapeError(Exception):
    """Custom exception for scraping errors"""
    pass

def extract_price(text):
    """Extract a price from text by finding numbers with optional decimal points
    
    Handles various price formats including:
    - US/UK format (1,234.56)
    - European format (1.234,56 or 1.845,90 €)
    - Formats with currency symbols (€, $, £, ¥, etc.)
    - Formats with spaces as thousand separators (1 234,56)
    - Various other number formats
    """
    if not text:
        return None
    
    # Strip whitespace and non-breaking spaces
    text = text.strip().replace('\xa0', ' ')
    
    # Try to find a price pattern in the text
    # This regex covers most price formats including those with currency symbols
    # It matches:
    # - Optional currency symbol at the start or end
    # - Numbers with thousand separators (comma, dot, or space)
    # - Decimal part with comma or dot
    
    # 1. European format with comma as decimal (e.g. 1.234,56€ or 1 234,56€)
    pattern1 = r'[€$£¥]?\s*([0-9]+(?:[.,\s][0-9]+)*(?:,[0-9]+))\s*[€$£¥]?'
    # 2. US/UK format with dot as decimal (e.g. $1,234.56 or £ 1,234.56)
    pattern2 = r'[€$£¥]?\s*([0-9]+(?:[.,\s][0-9]+)*(?:\.[0-9]+))\s*[€$£¥]?'
    # 3. Simple integer format (e.g. 1234€ or $1234)
    pattern3 = r'[€$£¥]?\s*([0-9]+)\s*[€$£¥]?'
    
    # Try to find matches for each pattern
    for pattern in [pattern1, pattern2, pattern3]:
        match = re.search(pattern, text)
        if match:
            # Extract the price part
            price_str = match.group(1)
            
            # Determine the decimal separator based on the format
            if ',' in price_str and '.' in price_str:
                # Format like 1.234,56 - European with dot as thousands and comma as decimal
                if price_str.rfind(',') > price_str.rfind('.'):
                    # Replace all dots (thousand separators) and then comma with dot
                    price_str = price_str.replace('.', '').replace(',', '.')
                else:
                    # US format with thousand separators
                    price_str = price_str.replace(',', '')
            elif ',' in price_str:
                # Check if comma is a decimal separator (usually followed by 2 digits at the end)
                if re.search(r',[0-9]{1,2}$', price_str):
                    # It's a decimal comma (e.g. 1234,56)
                    price_str = price_str.replace(',', '.')
                else:
                    # It's a thousands separator (e.g. 1,234)
                    price_str = price_str.replace(',', '')
            
            # Replace spaces used as thousand separators
            price_str = price_str.replace(' ', '')
            
            try:
                # Parse the cleaned price string to float
                return float(price_str)
            except ValueError:
                continue
    
    # If no match found or conversion failed, return None
    return None

def parse_selector(selector):
    """
    Parse a selector to determine its type (id, class, tag, or CSS)
    
    Args:
        selector (str): The selector string
        
    Returns:
        tuple: (type, value) where type is 'id', 'class', 'tag', or 'css'
    """
    if not selector or not isinstance(selector, str):
        return None, None
    
    selector = selector.strip()
    
    # Check if it's an ID selector
    if selector.startswith('#'):
        return 'id', selector[1:]
    # Check if it's a class selector
    elif selector.startswith('.'):
        return 'class', selector[1:]
    # Check if it might be HTML tag
    elif selector.lower() in ['div', 'span', 'p', 'h1', 'h2', 'h3', 'h4', 'h5', 'strong', 'em', 'a', 'button', 'li', 'ul', 'ol', 'table', 'tr', 'td']:
        return 'tag', selector
    # Assume it's a complex CSS selector
    else:
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
    if not selector or not soup:
        return None
    
    # Clean the selector
    if isinstance(selector, str):
        selector = selector.strip()
    else:
        return None
    
    # Parse the selector to determine its type
    selector_type, selector_value = parse_selector(selector)
    
    try:
        # Find based on selector type
        if selector_type == 'id':
            element = soup.find(id=selector_value)
        elif selector_type == 'class':
            element = soup.find(class_=selector_value)
        elif selector_type == 'tag':
            element = soup.find(selector_value)
        elif selector_type == 'css':
            # For complex CSS selectors, try to parse it
            if ' ' in selector:  # Nested selector like ".price h1"
                parts = selector.split(' ')
                current = soup
                for part in parts:
                    part_type, part_value = parse_selector(part)
                    
                    if part_type == 'id':
                        current = current.find(id=part_value)
                    elif part_type == 'class':
                        current = current.find(class_=part_value)
                    elif part_type == 'tag':
                        current = current.find(part_value)
                    else:
                        # If it's still a complex part, try using find method
                        try:
                            current = current.select_one(part)
                        except:
                            current = None
                    
                    if not current:
                        break
                
                element = current
            else:
                # Try using select_one for single CSS selectors
                try:
                    element = soup.select_one(selector)
                except:
                    element = None
        else:
            # Try as raw HTML fragment (might be from browser inspector)
            if '<' in selector and '>' in selector:
                # Create a temporary soup to parse it
                temp_soup = BeautifulSoup(selector, 'html.parser')
                first_tag = temp_soup.find()
                if first_tag:
                    # Extract key attributes to find similar element
                    attrs = first_tag.attrs
                    tag_name = first_tag.name
                    
                    # Try to find by tag and attributes
                    element = soup.find(tag_name, attrs=attrs)
                else:
                    element = None
            else:
                # Try direct text search
                element = soup.find(text=lambda text: text and selector in text)
                if element:
                    # Get parent element for better context
                    element = element.parent
    except Exception as e:
        print(f"Error finding element with selector '{selector}': {e}")
        element = None
    
    # If element not found, try fallback approaches
    if not element:
        try:
            # Try using CSS selector directly
            element = soup.select_one(selector)
        except:
            try:
                # Try containing text for certain tags
                for tag in ['span', 'div', 'p', 'h1', 'h2', 'h3', 'h4', 'h5']:
                    element = soup.find(tag, string=lambda s: s and selector.lower() in s.lower())
                    if element:
                        break
            except:
                element = None
    
    return element

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
    if not url or not price_selector:
        return {"error": "URL and price selector are required"}
    
    # Default headers to mimic a browser
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
        "Accept-Encoding": "gzip, deflate",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
        "Cache-Control": "max-age=0"
    }
    
    # Add any additional headers
    if additional_headers and isinstance(additional_headers, dict):
        headers.update(additional_headers)
    
    try:
        # Send request
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()  # Raise an exception for HTTP errors
        
        # Parse HTML
        soup = BeautifulSoup(response.text, 'html.parser')
        
        result = {}
        
        # Find price element
        price_element = find_element(soup, price_selector)
        
        if price_element:
            # Extract text
            price_text = price_element.get_text()
            
            # Extract price
            price = extract_price(price_text)
            
            result['price'] = price
            result['price_text'] = price_text
        else:
            result['error'] = f"Price element not found with selector: {price_selector}"
        
        # Find name element if selector provided
        if name_selector:
            name_element = find_element(soup, name_selector)
            
            if name_element:
                # Extract text
                name_text = name_element.get_text().strip()
                result['name'] = name_text
            else:
                result['name_error'] = f"Name element not found with selector: {name_selector}"
        
        return result
    except requests.exceptions.RequestException as e:
        return {"error": f"Request error: {str(e)}"}
    except Exception as e:
        return {"error": f"Scraping error: {str(e)}"}

def scrape_all_products():
    """Scrape all products in the database and update their price information"""
    products_df = get_products()
    
    if products_df.empty:
        print("No products found to scrape")
        return {"scraped": 0, "errors": 0}
    
    results = {
        "scraped": 0,
        "errors": 0,
        "product_results": []
    }
    
    for _, product in products_df.iterrows():
        product_id = product['id']
        product_name = product['name']
        our_url = product['our_url']
        our_price_selector = product['our_price_selector']
        our_name_selector = product['our_name_selector']
        competitor_urls = product['competitor_urls'] if pd.notna(product['competitor_urls']) else None
        competitor_selectors = product['competitor_selectors'] if pd.notna(product['competitor_selectors']) else None
        
        product_result = {
            "id": product_id,
            "name": product_name,
            "success": False
        }
        
        try:
            # Scrape our price
            our_result = scrape_product(our_url, our_price_selector, our_name_selector)
            
            if 'error' in our_result:
                product_result["our_error"] = our_result['error']
                results["errors"] += 1
                continue
            
            our_price = our_result.get('price')
            
            if our_price is None:
                product_result["our_error"] = "Failed to extract price"
                results["errors"] += 1
                continue
            
            # Scrape competitor prices
            competitor_prices = {}
            
            if competitor_urls and competitor_selectors:
                # Identify the URL format - either dict, list, or string
                if isinstance(competitor_urls, str):
                    # Handle comma-separated string format
                    competitor_urls = [url.strip() for url in competitor_urls.split(',') if url.strip()]
                
                if isinstance(competitor_urls, list):
                    # List format - urls at idx 0, 1, 2, etc.
                    for idx, comp_url in enumerate(competitor_urls):
                        # Skip empty URLs
                        if not comp_url:
                            continue
                        
                        comp_name = f"Competitor {idx+1}"
                        comp_price_selector = None
                        
                        # Try to get selectors from different formats
                        if isinstance(competitor_selectors, dict):
                            # Dictionary format - keyed by index or name  
                            # Try as string index
                            str_idx = str(idx)
                            if str_idx in competitor_selectors:
                                selectors = competitor_selectors[str_idx]
                                if isinstance(selectors, list) and len(selectors) >= 2:
                                    comp_price_selector = selectors[1]  # Price selector is second
                                elif isinstance(selectors, dict):
                                    comp_price_selector = selectors.get('price')
                        elif isinstance(competitor_selectors, list) and idx < len(competitor_selectors):
                            # List of lists format
                            idx_selectors = competitor_selectors[idx]
                            if isinstance(idx_selectors, list) and len(idx_selectors) >= 2:
                                comp_price_selector = idx_selectors[1]  # Price selector is second
                            elif isinstance(idx_selectors, dict):
                                comp_price_selector = idx_selectors.get('price')
                        
                        # Skip if no valid selector found
                        if not comp_price_selector:
                            continue
                        
                        try:
                            # Scrape competitor price
                            comp_result = scrape_product(comp_url, comp_price_selector)
                            
                            if 'price' in comp_result and comp_result['price'] is not None:
                                competitor_prices[comp_name] = comp_result['price']
                        except Exception as e:
                            print(f"Error scraping competitor {comp_name}: {e}")
                
                elif isinstance(competitor_urls, dict):
                    # Dictionary format - keyed by name
                    for comp_name, comp_url in competitor_urls.items():
                        # Skip empty URLs
                        if not comp_url:
                            continue
                        
                        comp_price_selector = None
                        
                        # Try to get the price selector from the competitor_selectors
                        if isinstance(competitor_selectors, dict):
                            if comp_name in competitor_selectors:
                                selectors = competitor_selectors[comp_name]
                                if isinstance(selectors, list) and len(selectors) >= 2:
                                    comp_price_selector = selectors[1]  # Price selector is second
                                elif isinstance(selectors, dict):
                                    comp_price_selector = selectors.get('price')
                        
                        # Skip if no valid selector found
                        if not comp_price_selector:
                            continue
                        
                        try:
                            # Scrape competitor price
                            comp_result = scrape_product(comp_url, comp_price_selector)
                            
                            if 'price' in comp_result and comp_result['price'] is not None:
                                competitor_prices[comp_name] = comp_result['price']
                        except Exception as e:
                            print(f"Error scraping competitor {comp_name}: {e}")
            
            # Add price data to database
            add_price_data(product_id, our_price, competitor_prices)
            
            product_result["success"] = True
            product_result["our_price"] = our_price
            product_result["competitor_prices"] = competitor_prices
            
            results["scraped"] += 1
        except Exception as e:
            product_result["error"] = str(e)
            results["errors"] += 1
        
        results["product_results"].append(product_result)
    
    # Update last scrape time
    update_last_scrape()
    
    return results

def test_scrape(url, price_selector, name_selector=None):
    """Test scraping a URL with given selectors"""
    return scrape_product(url, price_selector, name_selector)

# Scheduler functions

def _run_scraper():
    """Run the scraper and update last run time"""
    global scheduler_last_run
    try:
        print(f"Running scheduled scraper at {datetime.datetime.now()}")
        results = scrape_all_products()
        print(f"Scraper completed: {results['scraped']} products scraped, {results['errors']} errors")
        scheduler_last_run = datetime.datetime.now()
    except Exception as e:
        print(f"Error in scheduled scraper: {e}")
        traceback.print_exc()

def _scheduler_loop():
    """Main scheduler loop that runs in a background thread"""
    global scheduler_running
    
    while scheduler_running:
        # Run pending tasks (if any)
        schedule.run_pending()
        
        # Sleep for a short time to avoid high CPU usage
        time.sleep(1)

def start_scheduler():
    """Start the scheduler with the configured interval"""
    global scheduler_thread, scheduler_running
    
    if scheduler_thread and scheduler_thread.is_alive():
        print("Scheduler already running")
        return False
    
    # Get scraping interval from settings
    settings = get_settings()
    interval_minutes = int(settings.get("scraping_interval", 720))  # Default to 12 hours
    
    # Clear existing jobs
    schedule.clear()
    
    # Add the job with the specified interval
    schedule.every(interval_minutes).minutes.do(_run_scraper)
    
    # Start the scheduler thread
    scheduler_running = True
    scheduler_thread = threading.Thread(target=_scheduler_loop, daemon=True)
    scheduler_thread.start()
    
    print(f"Scheduler started with interval of {interval_minutes} minutes")
    return True

def stop_scheduler():
    """Stop the scheduler"""
    global scheduler_running, scheduler_thread
    
    if not scheduler_thread or not scheduler_thread.is_alive():
        print("Scheduler not running")
        return False
    
    scheduler_running = False
    scheduler_thread.join(timeout=2)  # Wait for thread to end
    
    print("Scheduler stopped")
    return True

def get_scheduler_status():
    """Get the current status of the scheduler"""
    global scheduler_thread, scheduler_running, scheduler_last_run
    
    # Check if thread is alive
    running = scheduler_thread is not None and scheduler_thread.is_alive()
    
    # Get settings for interval
    settings = get_settings()
    interval_minutes = int(settings.get("scraping_interval", 720))
    
    # Get last run time
    last_scrape = settings.get("last_scrape", "")
    
    if last_scrape and not scheduler_last_run:
        try:
            scheduler_last_run = datetime.datetime.strptime(last_scrape, '%Y-%m-%d %H:%M:%S')
        except:
            pass
    
    # Calculate next run time if running
    next_run = None
    if running:
        next_job = schedule.next_run()
        if next_job:
            next_run = next_job.strftime('%Y-%m-%d %H:%M:%S')
    
    return {
        "running": running,
        "interval_minutes": interval_minutes,
        "last_run": scheduler_last_run.strftime('%Y-%m-%d %H:%M:%S') if scheduler_last_run else None,
        "next_run": next_run
    }

def run_scraper_now():
    """Run the scraper immediately"""
    try:
        results = scrape_all_products()
        print(f"Manual scraper completed: {results['scraped']} products scraped, {results['errors']} errors")
        return results
    except Exception as e:
        print(f"Error in manual scraper: {e}")
        traceback.print_exc()
        return {"error": str(e)}