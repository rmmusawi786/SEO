import os
import json
import pandas as pd
from datetime import datetime, timedelta
from openai import OpenAI
from utils.database import get_products, get_price_history, get_settings

# Initialize OpenAI client
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
client = OpenAI(api_key=OPENAI_API_KEY)

def prepare_price_data(product_id, days=None):
    """
    Prepare price data for a product for AI analysis
    
    Args:
        product_id (int): Product ID
        days (int, optional): Number of days of history to include
    
    Returns:
        dict: Structured price data
    """
    # Get product information
    products_df = get_products()
    product_info = products_df[products_df['id'] == product_id]
    
    if product_info.empty:
        return None
    
    product_name = product_info.iloc[0]['name']
    
    # Get price history
    price_history = get_price_history(product_id, days)
    
    if price_history.empty:
        return {
            "product_id": product_id,
            "product_name": product_name,
            "error": "No price history available"
        }
    
    # Prepare the data structure
    data = {
        "product_id": product_id,
        "product_name": product_name,
        "date_range": {
            "start": price_history['timestamp'].min().strftime('%Y-%m-%d'),
            "end": price_history['timestamp'].max().strftime('%Y-%m-%d')
        },
        "our_prices": [],
        "competitor_prices": {}
    }
    
    # Process our prices
    for idx, row in price_history.iterrows():
        data["our_prices"].append({
            "date": row['timestamp'].strftime('%Y-%m-%d %H:%M'),
            "price": row['our_price']
        })
        
        # Process competitor prices
        competitor_prices = row['competitor_prices']
        for competitor, price in competitor_prices.items():
            if competitor not in data["competitor_prices"]:
                data["competitor_prices"][competitor] = []
            
            data["competitor_prices"][competitor].append({
                "date": row['timestamp'].strftime('%Y-%m-%d %H:%M'),
                "price": price
            })
    
    # Calculate statistics
    our_prices = [p["price"] for p in data["our_prices"]]
    data["our_price_stats"] = {
        "min": min(our_prices) if our_prices else 0,
        "max": max(our_prices) if our_prices else 0,
        "avg": sum(our_prices) / len(our_prices) if our_prices else 0,
        "current": our_prices[-1] if our_prices else None
    }
    
    # Create a separate stats dictionary to avoid modifying during iteration
    competitor_stats = {}
    for competitor, prices in list(data["competitor_prices"].items()):
        price_values = [p["price"] for p in prices]
        if price_values:
            competitor_stats[competitor] = {
                "min": min(price_values),
                "max": max(price_values),
                "avg": sum(price_values) / len(price_values),
                "current": price_values[-1] if price_values else None
            }
    
    # Add the stats to the data separately
    data["competitor_stats"] = competitor_stats
    
    return data

def analyze_price_data(data, product_id=None):
    """
    Analyze price data using OpenAI's GPT-4o model
    
    Args:
        data (dict): Structured price data
        product_id (int, optional): Product ID to get product-specific thresholds
    
    Returns:
        dict: Analysis results
    """
    if "error" in data:
        return {
            "product_id": data["product_id"],
            "product_name": data["product_name"],
            "error": data["error"]
        }
    
    if not OPENAI_API_KEY:
        return {
            "product_id": data["product_id"],
            "product_name": data["product_name"],
            "error": "OpenAI API key is not set"
        }
    
    # Get price thresholds from settings and product
    settings = get_settings()
    use_global_thresholds = settings.get("use_global_price_thresholds", True)
    global_min_threshold = settings.get("global_min_price_threshold", 5)
    global_max_threshold = settings.get("global_max_price_threshold", 15)
    
    min_threshold = global_min_threshold
    max_threshold = global_max_threshold
    
    # If product_id is provided and global thresholds should not be used, get product-specific thresholds
    if product_id and not use_global_thresholds:
        products_df = get_products()
        product_info = products_df[products_df['id'] == product_id]
        
        if not product_info.empty:
            has_min = ('min_price_threshold' in product_info.columns and 
                      product_info.iloc[0]['min_price_threshold'] is not None and 
                      not pd.isna(product_info.iloc[0]['min_price_threshold']))
            
            has_max = ('max_price_threshold' in product_info.columns and 
                      product_info.iloc[0]['max_price_threshold'] is not None and 
                      not pd.isna(product_info.iloc[0]['max_price_threshold']))
            
            if has_min:
                min_threshold = float(product_info.iloc[0]['min_price_threshold'])
            
            if has_max:
                max_threshold = float(product_info.iloc[0]['max_price_threshold'])
    
    current_price = data['our_price_stats']['current']
    min_allowed_price = current_price * (1 - (min_threshold / 100))
    max_allowed_price = current_price * (1 + (max_threshold / 100))
    
    try:
        # Create the prompt
        prompt = f"""
        You are an expert in e-commerce pricing and competitive analysis. Analyze the following pricing data for {data['product_name']} 
        and provide detailed insights and actionable recommendations.
        
        Data period: {data['date_range']['start']} to {data['date_range']['end']}
        
        Our pricing information:
        - Current price: {data['our_price_stats']['current']}
        - Average price: {data['our_price_stats']['avg']}
        - Min price: {data['our_price_stats']['min']}
        - Max price: {data['our_price_stats']['max']}
        
        Competitor pricing information:
        """
        
        for competitor, stats in data["competitor_stats"].items():
            prompt += f"""
        {competitor}:
        - Current price: {stats['current']}
        - Average price: {stats['avg']}
        - Min price: {stats['min']}
        - Max price: {stats['max']}
                    """
        
        prompt += f"""
        IMPORTANT PRICE CONSTRAINTS:
        Your price suggestions must stay within the following threshold:
        - Minimum allowed price: {min_allowed_price} ({min_threshold}% below current price)
        - Maximum allowed price: {max_allowed_price} ({max_threshold}% above current price)
        - Current price: {current_price}
        
        Based on this data, please provide:
        1. Analysis of our current pricing position compared to competitors
        2. Price trend analysis for us and competitors
        3. Specific pricing recommendations to be more competitive
        4. Suggested optimal price and explanation (MUST be between {min_allowed_price} and {max_allowed_price})
        
        Format your response as a JSON object with the following structure:
        {
            "market_position": "Analysis of our position in the market",
            "price_trends": "Analysis of price trends",
            "competitive_analysis": "Analysis of competitor pricing strategies",
            "recommendations": "Actionable pricing recommendations",
            "suggested_price": float,
            "rationale": "Brief explanation for the suggested price (100 words or less)"
        }
        """
        
        # Call the OpenAI API
        # the newest OpenAI model is "gpt-4o" which was released May 13, 2024
        # do not change this unless explicitly requested by the user
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
            temperature=0.5,
            max_tokens=1000
        )
        
        # Parse the response
        analysis = json.loads(response.choices[0].message.content)
        
        # Add product information to the result
        analysis["product_id"] = data["product_id"]
        analysis["product_name"] = data["product_name"]
        analysis["date_range"] = data["date_range"]
        
        # Add price threshold information
        analysis["price_constraints"] = {
            "current_price": current_price,
            "min_allowed_price": min_allowed_price,
            "max_allowed_price": max_allowed_price,
            "min_threshold_percent": min_threshold,
            "max_threshold_percent": max_threshold
        }
        
        return analysis
    
    except Exception as e:
        return {
            "product_id": data["product_id"],
            "product_name": data["product_name"],
            "error": str(e)
        }

def get_price_analysis(product_id, days=None):
    """
    Get AI price analysis for a product
    
    Args:
        product_id (int): Product ID
        days (int, optional): Number of days of history to include
    
    Returns:
        dict: Analysis results
    """
    # If days is not specified, get from settings
    if days is None:
        settings = get_settings()
        days = settings["analysis_period"]
    
    # Prepare data
    data = prepare_price_data(product_id, days)
    
    if not data:
        return {
            "product_id": product_id,
            "error": "Product not found"
        }
    
    # Analyze data with product-specific thresholds
    analysis = analyze_price_data(data, product_id)
    
    return analysis

def get_bulk_analysis(days=None):
    """
    Get AI price analysis for all products
    
    Args:
        days (int, optional): Number of days of history to include
    
    Returns:
        list: List of analysis results for each product
    """
    # Get all products
    products_df = get_products()
    
    results = []
    
    for _, product in products_df.iterrows():
        product_id = product['id']
        
        # Get analysis for the product
        analysis = get_price_analysis(product_id, days)
        results.append(analysis)
    
    return results
