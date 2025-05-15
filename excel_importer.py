import pandas as pd
import io
import streamlit as st
from utils.database import add_product

def process_excel_file(file_data):
    """
    Process an Excel file containing product data
    
    Expected columns:
    - product_name: Name of the product
    - our_url: URL of our product
    - our_name_selector: CSS selector for product name
    - our_price_selector: CSS selector for product price
    - competitor1_url, competitor1_name_selector, competitor1_price_selector
    - competitor2_url, competitor2_name_selector, competitor2_price_selector
    - etc. (up to 5 competitors)
    - min_price_threshold (optional): Minimum price threshold in EUR
    - max_price_threshold (optional): Maximum price threshold in EUR
    
    Args:
        file_data: Uploaded file data
        
    Returns:
        dict: Results of the import process
    """
    try:
        # Read Excel file into a pandas DataFrame
        df = pd.read_excel(file_data, engine='openpyxl')
        
        # Validate the DataFrame to ensure required columns are present
        required_columns = ['product_name', 'our_url', 'our_price_selector']
        for col in required_columns:
            if col not in df.columns:
                return {
                    'success': False,
                    'error': f"Missing required column: {col}",
                    'products_added': 0
                }
        
        # Process each row in the DataFrame
        products_added = 0
        failed_products = []
        
        for idx, row in df.iterrows():
            try:
                # Extract product information
                product_name = row['product_name']
                our_url = row['our_url']
                our_name_selector = row.get('our_name_selector', '')  # Optional
                our_price_selector = row['our_price_selector']
                
                # Extract price thresholds if they exist
                min_threshold = None
                max_threshold = None
                if 'min_price_threshold' in row and pd.notna(row['min_price_threshold']):
                    min_threshold = float(row['min_price_threshold'])
                if 'max_price_threshold' in row and pd.notna(row['max_price_threshold']):
                    max_threshold = float(row['max_price_threshold'])
                
                # Extract competitor information
                competitor_urls = []
                competitor_selectors = {}
                
                for i in range(1, 6):  # Up to 5 competitors
                    comp_url_col = f'competitor{i}_url'
                    comp_name_col = f'competitor{i}_name_selector'
                    comp_price_col = f'competitor{i}_price_selector'
                    comp_display_name_col = f'competitor{i}_display_name'
                    
                    if (comp_url_col in row and pd.notna(row[comp_url_col]) and 
                        comp_price_col in row and pd.notna(row[comp_price_col])):
                        competitor_urls.append(row[comp_url_col])
                        
                        # Set display name
                        display_name = f"Competitor {i}"
                        if comp_display_name_col in row and pd.notna(row[comp_display_name_col]):
                            display_name = row[comp_display_name_col]
                        
                        competitor_selectors[f'display_name_{i-1}'] = display_name
                        competitor_selectors[f'name_{i-1}'] = row.get(comp_name_col, '') if comp_name_col in row else ''
                        competitor_selectors[f'price_{i-1}'] = row[comp_price_col]
                
                # Add the product to the database
                product_id = add_product(
                    product_name,
                    our_url,
                    our_name_selector,
                    our_price_selector,
                    competitor_urls,
                    competitor_selectors,
                    min_price_threshold=min_threshold,
                    max_price_threshold=max_threshold
                )
                
                if product_id:
                    products_added += 1
                else:
                    failed_products.append(product_name)
            
            except Exception as e:
                # If a row fails, continue with the next one
                failed_products.append(f"Row {idx+2}: {str(e)}")
        
        # Return the results
        return {
            'success': True,
            'products_added': products_added,
            'failed_products': failed_products
        }
    
    except Exception as e:
        return {
            'success': False,
            'error': f"Error processing Excel file: {str(e)}",
            'products_added': 0
        }

def generate_template_excel():
    """
    Generate a template Excel file for importing products
    
    Returns:
        bytes: Excel file as bytes
    """
    # Create a sample DataFrame
    data = {
        'product_name': ['Sample Product 1', 'Sample Product 2'],
        'our_url': ['https://example.com/product1', 'https://example.com/product2'],
        'our_name_selector': ['.product-title', '#product-name'],
        'our_price_selector': ['.product-price', '#price'],
        'min_price_threshold': [-5, -10],
        'max_price_threshold': [5, 10],
        'competitor1_url': ['https://competitor1.com/product1', 'https://competitor1.com/product2'],
        'competitor1_display_name': ['Amazon', 'Amazon'],
        'competitor1_name_selector': ['.product-title', '.product-title'],
        'competitor1_price_selector': ['.price', '.price'],
        'competitor2_url': ['https://competitor2.com/product1', ''],
        'competitor2_display_name': ['eBay', ''],
        'competitor2_name_selector': ['.title', ''],
        'competitor2_price_selector': ['.price-current', '']
    }
    
    df = pd.DataFrame(data)
    
    # Create a bytes buffer and write DataFrame to Excel
    buffer = io.BytesIO()
    df.to_excel(buffer, index=False, sheet_name='Products', engine='openpyxl')
    
    # Reset buffer position to the beginning
    buffer.seek(0)
    
    # Return the bytes
    return buffer.getvalue()