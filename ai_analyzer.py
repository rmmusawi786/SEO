import os
import json
import pandas as pd
from datetime import datetime, timedelta
from openai import OpenAI
from utils.database import get_products, get_price_history, get_settings

# Initialize OpenAI client
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")

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
        "our_price_history": price_history['our_price'].tolist(),
        "competitor_stats": {}
    }
    
    # Calculate statistics for our prices
    our_prices = price_history['our_price'].tolist()
    if our_prices:
        data["our_price_stats"] = {
            "min": min(our_prices),
            "max": max(our_prices),
            "avg": sum(our_prices) / len(our_prices),
            "current": our_prices[-1]
        }
    else:
        data["our_price_stats"] = {
            "min": 0,
            "max": 0,
            "avg": 0,
            "current": 0
        }
    
    # Process competitor prices
    for _, row in price_history.iterrows():
        competitor_prices = row.get('competitor_prices', {})
        if not isinstance(competitor_prices, dict):
            competitor_prices = {}
            
        for competitor, price in competitor_prices.items():
            if competitor not in data["competitor_stats"]:
                data["competitor_stats"][competitor] = {
                    "prices": [],
                    "min": None,
                    "max": None,
                    "avg": None,
                    "current": None
                }
            
            data["competitor_stats"][competitor]["prices"].append(price)
    
    # Calculate statistics for each competitor
    for competitor, stats in data["competitor_stats"].items():
        prices = stats["prices"]
        if prices:
            stats["min"] = min(prices)
            stats["max"] = max(prices)
            stats["avg"] = sum(prices) / len(prices)
            stats["current"] = prices[-1]
            # Remove the list of prices as we don't need it anymore
            del stats["prices"]
    
    return data

def simple_price_analysis(data, product_id=None):
    """
    A simplified analysis function that doesn't rely on OpenAI
    for testing the data processing part
    
    Args:
        data (dict): Structured price data
        product_id (int, optional): Product ID
    
    Returns:
        dict: Analysis results
    """
    if "error" in data:
        return data
    
    # Get settings for thresholds
    settings = get_settings()
    min_threshold = float(settings.get("global_min_price_threshold", -5))
    max_threshold = float(settings.get("global_max_price_threshold", 15))
    
    # Calculate price constraints
    current_price = data["our_price_stats"]["current"]
    min_allowed_price = current_price + min_threshold
    max_allowed_price = current_price + max_threshold
    
    # Calculate a simple suggested price (average between our price and competitor average)
    if data["competitor_stats"]:
        competitor_averages = [stats["avg"] for stats in data["competitor_stats"].values() 
                                if stats["avg"] is not None]
        if competitor_averages:
            avg_competitor_price = sum(competitor_averages) / len(competitor_averages)
            # Suggest a price between our current and the competitor average
            suggested_price = (current_price + avg_competitor_price) / 2
            
            # Ensure it's within constraints
            suggested_price = max(min_allowed_price, min(suggested_price, max_allowed_price))
        else:
            suggested_price = current_price
    else:
        suggested_price = current_price
    
    # Create simple analysis
    analysis = {
        "product_id": data["product_id"],
        "product_name": data["product_name"],
        "date_range": data["date_range"],
        "market_position": "Based on available data, this is a simple analysis without AI.",
        "price_trends": "This is a simplified analysis without trend detection.",
        "competitive_analysis": "Simple comparison with competitor pricing.",
        "recommendations": "This is a simplified recommendation based on averages.",
        "suggested_price": round(suggested_price, 2),
        "rationale": "Price suggestion based on averaging our price with competitor prices.",
        "price_constraints": {
            "current_price": current_price,
            "min_allowed_price": min_allowed_price,
            "max_allowed_price": max_allowed_price,
            "min_threshold_eur": min_threshold,
            "max_threshold_eur": max_threshold
        }
    }
    
    return analysis

def analyze_price_data(data, product_id=None):
    """
    Analyze price data using OpenAI's GPT-4o model
    
    Args:
        data (dict): Structured price data
        product_id (int, optional): Product ID for thresholds
    
    Returns:
        dict: Analysis results
    """
    # Handle errors or missing data
    if not data:
        return {"error": "No data available for analysis"}
    
    if "error" in data:
        return data
    
    # Check for API key
    if not OPENAI_API_KEY:
        return {
            "product_id": data["product_id"],
            "product_name": data["product_name"],
            "error": "OpenAI API key is not set"
        }
    
    # Get price thresholds
    settings = get_settings()
    try:
        min_threshold = float(settings.get("global_min_price_threshold", -5))
        max_threshold = float(settings.get("global_max_price_threshold", 15))
    except (ValueError, TypeError):
        min_threshold = -5.0
        max_threshold = 15.0
    
    # Calculate price constraints
    current_price = float(data["our_price_stats"]["current"])
    min_allowed_price = current_price + min_threshold
    max_allowed_price = current_price + max_threshold
    
    try:
        # Prepare a simple prompt with clear JSON structure expectation
        prompt = """
You are an expert in e-commerce pricing analysis. Based on the data below, provide a pricing analysis and recommendation.

PRODUCT DATA:
- Product: {product_name}
- Period: {start_date} to {end_date}
- Our current price: {our_current}
- Our price range: {our_min} to {our_max}
- Our average price: {our_avg}

COMPETITOR DATA:
{competitor_data}

CONSTRAINTS:
- Current price: {current_price}
- Minimum allowed price: {min_price} ({min_threshold}€ from current)
- Maximum allowed price: {max_price} ({max_threshold}€ from current)

ANALYSIS REQUIREMENTS:
1. Analyze our position compared to competitors
2. Identify price trends
3. Provide specific recommendations
4. Suggest an optimal price within the allowed range
5. Explain the rationale for the price recommendation

FORMAT YOUR RESPONSE AS VALID JSON WITH THESE FIELDS:
- market_position: analysis of our position in the market
- price_trends: analysis of price trends
- competitive_analysis: analysis of competitor pricing strategies
- recommendations: actionable pricing recommendations
- suggested_price: a number between {min_price} and {max_price}
- rationale: explanation for the suggested price
"""

        # Format the prompt with our data
        competitor_data_str = ""
        for competitor, stats in data["competitor_stats"].items():
            competitor_data_str += f"- {competitor}: current {stats.get('current', 'N/A')}, "
            competitor_data_str += f"avg {stats.get('avg', 'N/A')}, "
            competitor_data_str += f"range {stats.get('min', 'N/A')} to {stats.get('max', 'N/A')}\n"

        formatted_prompt = prompt.format(
            product_name=data["product_name"],
            start_date=data["date_range"]["start"],
            end_date=data["date_range"]["end"],
            our_current=data["our_price_stats"]["current"],
            our_min=data["our_price_stats"]["min"],
            our_max=data["our_price_stats"]["max"],
            our_avg=data["our_price_stats"]["avg"],
            competitor_data=competitor_data_str,
            current_price=current_price,
            min_price=min_allowed_price,
            max_price=max_allowed_price,
            min_threshold=min_threshold,
            max_threshold=max_threshold
        )

        # Create the OpenAI client with API key
        client = OpenAI(api_key=OPENAI_API_KEY)
        
        # Call the OpenAI API
        # the newest OpenAI model is "gpt-4o" which was released May 13, 2024
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": formatted_prompt}],
            response_format={"type": "json_object"},
            temperature=0.5,
            max_tokens=1000
        )
        
        # Parse the response
        result = json.loads(response.choices[0].message.content)
        
        # Add additional data
        result["product_id"] = data["product_id"]
        result["product_name"] = data["product_name"]
        result["date_range"] = data["date_range"]
        result["price_constraints"] = {
            "current_price": current_price,
            "min_allowed_price": min_allowed_price,
            "max_allowed_price": max_allowed_price,
            "min_threshold_eur": min_threshold,
            "max_threshold_eur": max_threshold
        }
        
        return result
    
    except Exception as e:
        # If anything goes wrong, return a fallback analysis
        return {
            "product_id": data["product_id"],
            "product_name": data["product_name"],
            "error": f"Error in AI analysis: {str(e)}"
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
        days = settings.get("analysis_period", 7)
    
    # Prepare data
    data = prepare_price_data(product_id, days)
    
    if not data:
        return {
            "product_id": product_id,
            "error": "Product not found"
        }
    
    # Analyze data
    try:
        analysis = analyze_price_data(data, product_id)
        return analysis
    except Exception as e:
        return {
            "product_id": product_id,
            "product_name": data.get("product_name", "Unknown"),
            "error": f"Analysis error: {str(e)}"
        }

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
