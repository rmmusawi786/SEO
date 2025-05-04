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
        "min": min(our_prices),
        "max": max(our_prices),
        "avg": sum(our_prices) / len(our_prices),
        "current": our_prices[-1] if our_prices else None
    }
    
    for competitor, prices in data["competitor_prices"].items():
        price_values = [p["price"] for p in prices]
        if price_values:
            data["competitor_prices"][competitor + "_stats"] = {
                "min": min(price_values),
                "max": max(price_values),
                "avg": sum(price_values) / len(price_values),
                "current": price_values[-1] if price_values else None
            }
    
    return data

def analyze_price_data(data):
    """
    Analyze price data using OpenAI's GPT-4o model
    
    Args:
        data (dict): Structured price data
    
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
        
        for competitor, prices in data["competitor_prices"].items():
            if not competitor.endswith("_stats"):
                stats_key = competitor + "_stats"
                if stats_key in data["competitor_prices"]:
                    stats = data["competitor_prices"][stats_key]
                    prompt += f"""
        {competitor}:
        - Current price: {stats['current']}
        - Average price: {stats['avg']}
        - Min price: {stats['min']}
        - Max price: {stats['max']}
                    """
        
        prompt += """
        Based on this data, please provide:
        1. Analysis of our current pricing position compared to competitors
        2. Price trend analysis for us and competitors
        3. Specific pricing recommendations to be more competitive
        4. Suggested optimal price and explanation
        
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
    
    # Analyze data
    analysis = analyze_price_data(data)
    
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
