import os
import json
import pandas as pd
import numpy as np
import re
import datetime
import openai
from openai import OpenAI
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from sklearn.linear_model import LinearRegression
from scipy import stats

from database import get_products, get_price_history, get_settings, get_product

# Set up OpenAI API key
OPENAI_API_KEY = os.environ.get('OPENAI_API_KEY')
openai_client = None
if OPENAI_API_KEY:
    try:
        openai_client = OpenAI(api_key=OPENAI_API_KEY)
    except Exception as e:
        print(f"Error initializing OpenAI client: {e}")

# AI Analysis functions
def prepare_price_data(product_id, days=None):
    """
    Prepare price data for a product for AI analysis
    
    Args:
        product_id (int): Product ID
        days (int, optional): Number of days of history to include
    
    Returns:
        dict: Structured price data
    """
    # Get product info
    product = get_product(product_id)
    if not product:
        return None
    
    # Get price history
    price_history = get_price_history(product_id, days)
    if price_history.empty:
        return None
    
    # Calculate date range
    start_date = price_history['timestamp'].min()
    end_date = price_history['timestamp'].max()
    
    if pd.isna(start_date) or pd.isna(end_date):
        return None
    
    # Format dates
    start_date_str = pd.to_datetime(start_date).strftime('%Y-%m-%d')
    end_date_str = pd.to_datetime(end_date).strftime('%Y-%m-%d')
    
    # Get our price stats
    our_prices = price_history['our_price'].dropna()
    if our_prices.empty:
        return None
    
    our_stats = {
        "min": float(our_prices.min()),
        "max": float(our_prices.max()),
        "avg": float(our_prices.mean()),
        "current": float(our_prices.iloc[-1]),
        "change": float(our_prices.iloc[-1] - our_prices.iloc[0]) if len(our_prices) > 1 else 0,
        "change_percentage": float((our_prices.iloc[-1] - our_prices.iloc[0]) / our_prices.iloc[0] * 100) if len(our_prices) > 1 and our_prices.iloc[0] > 0 else 0
    }
    
    # Get competitor stats
    competitor_stats = {}
    
    # Check if we have competitor prices
    if 'competitor_prices' in price_history.columns:
        competitors = set()
        
        # Get all competitor names
        for idx, row in price_history.iterrows():
            if isinstance(row['competitor_prices'], dict):
                competitors.update(row['competitor_prices'].keys())
        
        # Calculate stats for each competitor
        for competitor in competitors:
            competitor_prices = []
            
            for idx, row in price_history.iterrows():
                if isinstance(row['competitor_prices'], dict) and competitor in row['competitor_prices']:
                    price = row['competitor_prices'][competitor]
                    if price and isinstance(price, (int, float)):
                        competitor_prices.append(price)
            
            if competitor_prices:
                competitor_stats[competitor] = {
                    "min": min(competitor_prices),
                    "max": max(competitor_prices),
                    "avg": sum(competitor_prices) / len(competitor_prices),
                    "current": competitor_prices[-1],
                    "change": competitor_prices[-1] - competitor_prices[0] if len(competitor_prices) > 1 else 0,
                    "change_percentage": (competitor_prices[-1] - competitor_prices[0]) / competitor_prices[0] * 100 if len(competitor_prices) > 1 and competitor_prices[0] > 0 else 0
                }
    
    # Calculate average competitor price
    avg_competitor_price = 0
    if competitor_stats:
        avg_competitor_price = sum(stat['current'] for stat in competitor_stats.values()) / len(competitor_stats)
    
    # Create structured data for analysis
    data = {
        "product_id": product_id,
        "product_name": product['name'],
        "date_range": {
            "start": start_date_str,
            "end": end_date_str,
            "days": (pd.to_datetime(end_date) - pd.to_datetime(start_date)).days + 1
        },
        "our_price_stats": our_stats,
        "competitor_stats": competitor_stats,
        "average_competitor_price": avg_competitor_price,
        "price_difference": our_stats['current'] - avg_competitor_price if competitor_stats else 0,
        "price_difference_percentage": (our_stats['current'] - avg_competitor_price) / avg_competitor_price * 100 if competitor_stats and avg_competitor_price > 0 else 0
    }
    
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
    if not data:
        return {
            "product_id": product_id,
            "error": "No data available for analysis"
        }
    
    # Get our price stats
    our_price = data["our_price_stats"]["current"]
    avg_competitor_price = data["average_competitor_price"]
    
    # Determine price position
    if avg_competitor_price > 0:
        price_diff_pct = (our_price - avg_competitor_price) / avg_competitor_price * 100
        if price_diff_pct > 3:
            price_position = "above market"
        elif price_diff_pct < -3:
            price_position = "below market"
        else:
            price_position = "at market"
    else:
        price_position = "unknown"
    
    # Generate simple recommendation
    if price_position == "above market":
        recommendation = "Consider reducing price to be more competitive."
    elif price_position == "below market":
        recommendation = "There may be an opportunity to increase price."
    else:
        recommendation = "Price is well-positioned in the market."
    
    # Return analysis results
    return {
        "product_id": data["product_id"],
        "product_name": data["product_name"],
        "current_price": our_price,
        "average_competitor_price": avg_competitor_price,
        "price_difference": our_price - avg_competitor_price,
        "price_difference_percentage": (our_price - avg_competitor_price) / avg_competitor_price * 100 if avg_competitor_price > 0 else 0,
        "price_change_percentage": data["our_price_stats"]["change_percentage"],
        "price_position": price_position,
        "recommendation": recommendation
    }

def analyze_price_data(data, product_id=None):
    """
    Analyze price data using OpenAI's GPT-4o model
    
    Args:
        data (dict): Structured price data
        product_id (int, optional): Product ID for thresholds
    
    Returns:
        dict: Analysis results
    """
    if not data:
        return {
            "product_id": product_id,
            "error": "No data available for analysis"
        }
    
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

        # Call the OpenAI API
        # The newest OpenAI model is "gpt-4o" which was released May 13, 2024
        response = openai_client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": "You are a pricing analyst AI. Provide analysis and recommendations in JSON format."},
                {"role": "user", "content": formatted_prompt}
            ],
            response_format={"type": "json_object"},
            temperature=0.2,
        )

        # Parse the response
        result_json = json.loads(response.choices[0].message.content)

        # Format results for our use
        results = {
            "product_id": data["product_id"],
            "product_name": data["product_name"],
            "current_price": data["our_price_stats"]["current"],
            "average_competitor_price": data["average_competitor_price"],
            "lowest_competitor_price": min([stats.get("current", float('inf')) for stats in data["competitor_stats"].values()]) if data["competitor_stats"] else None,
            "highest_competitor_price": max([stats.get("current", 0) for stats in data["competitor_stats"].values()]) if data["competitor_stats"] else None,
            "price_change_percentage": data["our_price_stats"]["change_percentage"],
            "suggested_price": result_json.get("suggested_price"),
            "price_difference": data["price_difference"],
            "price_difference_percentage": data["price_difference_percentage"]
        }

        # Determine price position
        if data["average_competitor_price"] > 0:
            price_diff_pct = data["price_difference_percentage"]
            if price_diff_pct > 3:
                results["price_position"] = "above market"
            elif price_diff_pct < -3:
                results["price_position"] = "below market"
            else:
                results["price_position"] = "at market"
        else:
            results["price_position"] = "unknown"

        # Add the analysis parts
        results["market_analysis"] = result_json.get("market_position", "")
        results["trend_analysis"] = result_json.get("price_trends", "")
        results["competitor_analysis"] = result_json.get("competitive_analysis", "")
        results["recommendation"] = result_json.get("recommendations", "")
        results["reasoning"] = result_json.get("rationale", "")

        # Create concise versions for display
        results["short_recommendation"] = results["recommendation"].split('.')[0] + '.' if results["recommendation"] else ""

        # Add any useful tips
        tips = []
        if results.get("price_position") == "above market" and data["price_difference_percentage"] > 10:
            tips.append("Your price is significantly higher than competitors. Consider a tiered approach to gradual price reductions.")
        elif results.get("price_position") == "below market" and data["price_difference_percentage"] < -10:
            tips.append("Your price is significantly lower than competitors. You may be leaving money on the table.")

        if tips:
            results["tips"] = " ".join(tips)

        return results

    except Exception as e:
        print(f"Error analyzing price data: {str(e)}")
        # Fallback to simple analysis
        simple_results = simple_price_analysis(data, product_id)
        simple_results["error"] = f"AI analysis error: {str(e)}"
        return simple_results

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

# Visualization functions
def create_price_history_chart(price_history_df, product_name, view_mode="line"):
    """
    Create an enhanced price history visualization
    
    Args:
        price_history_df (DataFrame): Price history data
        product_name (str): Name of the product
        view_mode (str): Visualization type ('line', 'area', 'bar', 'candlestick')
        
    Returns:
        plotly.graph_objects.Figure: Plotly figure object
    """
    if price_history_df.empty:
        fig = go.Figure()
        fig.add_annotation(
            text="No price history data available",
            xref="paper", yref="paper",
            x=0.5, y=0.5,
            showarrow=False,
            font=dict(size=16)
        )
        return fig
    
    # Convert timestamp to datetime
    price_history_df['timestamp'] = pd.to_datetime(price_history_df['timestamp'])
    
    # Create a DataFrame for our prices
    our_prices_df = price_history_df[['timestamp', 'our_price']].copy()
    our_prices_df.columns = ['Date', 'Price']
    our_prices_df['Source'] = 'Our Price'
    
    # Create a list to hold all competitor DataFrames
    all_prices = [our_prices_df]
    
    # Extract competitor prices
    competitor_dfs = []
    
    for idx, row in price_history_df.iterrows():
        if 'competitor_prices' in row and isinstance(row['competitor_prices'], dict):
            for competitor, price in row['competitor_prices'].items():
                if isinstance(price, (int, float)):
                    competitor_dfs.append({
                        'Date': row['timestamp'],
                        'Price': price,
                        'Source': competitor
                    })
    
    # Create a DataFrame for all competitor prices
    if competitor_dfs:
        competitor_prices_df = pd.DataFrame(competitor_dfs)
        all_prices.append(competitor_prices_df)
    
    # Combine all prices into a single DataFrame
    combined_df = pd.concat(all_prices, ignore_index=True)
    
    # Handle different view modes
    if view_mode == "line":
        # Line chart
        fig = px.line(
            combined_df, 
            x='Date', 
            y='Price', 
            color='Source',
            title=f'Price History for {product_name}',
            labels={'Price': 'Price (€)', 'Date': 'Date', 'Source': 'Source'},
            template='plotly_white'
        )
        
        # Improve layout
        fig.update_layout(
            legend=dict(
                orientation="h",
                yanchor="bottom",
                y=1.02,
                xanchor="right",
                x=1
            ),
            margin=dict(l=40, r=40, t=60, b=40),
            hovermode="x unified"
        )
        
        # Add range slider
        fig.update_xaxes(
            rangeslider_visible=True,
            rangeselector=dict(
                buttons=list([
                    dict(count=1, label="1d", step="day", stepmode="backward"),
                    dict(count=7, label="1w", step="day", stepmode="backward"),
                    dict(count=1, label="1m", step="month", stepmode="backward"),
                    dict(step="all")
                ])
            )
        )
    
    elif view_mode == "area":
        # Area chart
        fig = px.area(
            combined_df, 
            x='Date', 
            y='Price', 
            color='Source',
            title=f'Price History for {product_name}',
            labels={'Price': 'Price (€)', 'Date': 'Date', 'Source': 'Source'},
            template='plotly_white'
        )
        
        # Improve layout
        fig.update_layout(
            legend=dict(
                orientation="h",
                yanchor="bottom",
                y=1.02,
                xanchor="right",
                x=1
            ),
            margin=dict(l=40, r=40, t=60, b=40),
            hovermode="x unified"
        )
    
    elif view_mode == "bar":
        # Bar chart
        fig = px.bar(
            combined_df, 
            x='Date', 
            y='Price', 
            color='Source',
            title=f'Price History for {product_name}',
            labels={'Price': 'Price (€)', 'Date': 'Date', 'Source': 'Source'},
            template='plotly_white',
            barmode='group'
        )
        
        # Improve layout
        fig.update_layout(
            legend=dict(
                orientation="h",
                yanchor="bottom",
                y=1.02,
                xanchor="right",
                x=1
            ),
            margin=dict(l=40, r=40, t=60, b=40),
            hovermode="x unified"
        )
    
    elif view_mode == "candlestick":
        # For candlestick, we need OHLC (Open, High, Low, Close) data
        # We can create this from our price data by resampling
        
        # Group by date for our price only
        ohlc_df = our_prices_df.copy()
        ohlc_df['Date'] = ohlc_df['Date'].dt.date
        
        # Resample to get OHLC
        ohlc = ohlc_df.groupby('Date')['Price'].agg(['first', 'max', 'min', 'last'])
        ohlc.columns = ['Open', 'High', 'Low', 'Close']
        ohlc = ohlc.reset_index()
        ohlc['Date'] = pd.to_datetime(ohlc['Date'])
        
        # Create candlestick chart
        fig = go.Figure(data=[go.Candlestick(
            x=ohlc['Date'],
            open=ohlc['Open'],
            high=ohlc['High'],
            low=ohlc['Low'],
            close=ohlc['Close'],
            name='Our Price'
        )])
        
        # Add competitor prices as scatter points
        for competitor in combined_df['Source'].unique():
            if competitor != 'Our Price':
                comp_df = combined_df[combined_df['Source'] == competitor]
                fig.add_trace(go.Scatter(
                    x=comp_df['Date'],
                    y=comp_df['Price'],
                    mode='markers',
                    name=competitor
                ))
        
        # Update layout
        fig.update_layout(
            title=f'Price History for {product_name}',
            yaxis_title='Price (€)',
            xaxis_title='Date',
            template='plotly_white',
            legend=dict(
                orientation="h",
                yanchor="bottom",
                y=1.02,
                xanchor="right",
                x=1
            ),
            margin=dict(l=40, r=40, t=60, b=40),
            hovermode="x unified"
        )
    
    else:
        # Default to line chart if view_mode is not recognized
        fig = px.line(
            combined_df, 
            x='Date', 
            y='Price', 
            color='Source',
            title=f'Price History for {product_name}',
            labels={'Price': 'Price (€)', 'Date': 'Date', 'Source': 'Source'},
            template='plotly_white'
        )
        
        # Improve layout
        fig.update_layout(
            legend=dict(
                orientation="h",
                yanchor="bottom",
                y=1.02,
                xanchor="right",
                x=1
            ),
            margin=dict(l=40, r=40, t=60, b=40),
            hovermode="x unified"
        )
    
    return fig

def create_price_statistics_table(price_history_df):
    """
    Create enhanced price statistics
    
    Args:
        price_history_df (DataFrame): Price history data
        
    Returns:
        DataFrame: Statistics dataframe
    """
    if price_history_df.empty:
        return pd.DataFrame()
    
    # Calculate our price statistics
    our_stats = {
        'Seller': 'Our Price',
        'Latest': price_history_df['our_price'].iloc[-1],
        'Average': price_history_df['our_price'].mean(),
        'Min': price_history_df['our_price'].min(),
        'Max': price_history_df['our_price'].max(),
        'Change': price_history_df['our_price'].iloc[-1] - price_history_df['our_price'].iloc[0],
        'Change %': (price_history_df['our_price'].iloc[-1] - price_history_df['our_price'].iloc[0]) / price_history_df['our_price'].iloc[0] * 100 
                   if price_history_df['our_price'].iloc[0] > 0 else 0
    }
    
    stats_rows = [our_stats]
    
    # Extract competitor statistics
    competitors = set()
    for idx, row in price_history_df.iterrows():
        if isinstance(row['competitor_prices'], dict):
            competitors.update(row['competitor_prices'].keys())
    
    for competitor in competitors:
        comp_prices = []
        for idx, row in price_history_df.iterrows():
            if isinstance(row['competitor_prices'], dict) and competitor in row['competitor_prices']:
                price = row['competitor_prices'][competitor]
                if isinstance(price, (int, float)):
                    comp_prices.append(price)
        
        if comp_prices:
            comp_stats = {
                'Seller': competitor,
                'Latest': comp_prices[-1],
                'Average': sum(comp_prices) / len(comp_prices),
                'Min': min(comp_prices),
                'Max': max(comp_prices),
                'Change': comp_prices[-1] - comp_prices[0] if len(comp_prices) > 1 else 0,
                'Change %': (comp_prices[-1] - comp_prices[0]) / comp_prices[0] * 100 
                           if len(comp_prices) > 1 and comp_prices[0] > 0 else 0
            }
            stats_rows.append(comp_stats)
    
    # Create DataFrame
    stats_df = pd.DataFrame(stats_rows)
    
    # Format the columns
    for col in ['Latest', 'Average', 'Min', 'Max', 'Change']:
        stats_df[col] = stats_df[col].round(2)
    
    stats_df['Change %'] = stats_df['Change %'].round(2)
    
    return stats_df

def create_price_comparison_gauge_chart(price_history_df, product_name):
    """
    Create a gauge chart comparing our price vs competition
    
    Args:
        price_history_df (DataFrame): Price history data
        product_name (str): Name of the product
        
    Returns:
        plotly.graph_objects.Figure: Plotly figure object
    """
    if price_history_df.empty:
        fig = go.Figure()
        fig.add_annotation(
            text="No price history data available",
            xref="paper", yref="paper",
            x=0.5, y=0.5,
            showarrow=False,
            font=dict(size=16)
        )
        return fig
    
    # Get the latest data
    latest_data = price_history_df.iloc[-1]
    our_price = latest_data['our_price']
    
    # Extract competitor prices
    competitor_prices = []
    if isinstance(latest_data['competitor_prices'], dict):
        for competitor, price in latest_data['competitor_prices'].items():
            if isinstance(price, (int, float)):
                competitor_prices.append(price)
    
    if not competitor_prices:
        fig = go.Figure()
        fig.add_annotation(
            text="No competitor price data available",
            xref="paper", yref="paper",
            x=0.5, y=0.5,
            showarrow=False,
            font=dict(size=16)
        )
        return fig
    
    # Calculate average competitor price
    avg_competitor_price = sum(competitor_prices) / len(competitor_prices)
    
    # Calculate price difference as percentage
    price_diff_pct = (our_price - avg_competitor_price) / avg_competitor_price * 100
    
    # Create gauge chart
    fig = go.Figure(go.Indicator(
        mode="gauge+number+delta",
        value=price_diff_pct,
        domain={'x': [0, 1], 'y': [0, 1]},
        title={'text': f"Price Position for {product_name}", 'font': {'size': 24}},
        delta={'reference': 0, 'increasing': {'color': "red"}, 'decreasing': {'color': "green"}},
        gauge={
            'axis': {'range': [-20, 20], 'tickwidth': 1, 'tickcolor': "darkblue"},
            'bar': {'color': "darkblue"},
            'bgcolor': "white",
            'borderwidth': 2,
            'bordercolor': "gray",
            'steps': [
                {'range': [-20, -10], 'color': 'green'},
                {'range': [-10, -3], 'color': 'lightgreen'},
                {'range': [-3, 3], 'color': 'yellow'},
                {'range': [3, 10], 'color': 'orange'},
                {'range': [10, 20], 'color': 'red'},
            ],
            'threshold': {
                'line': {'color': "red", 'width': 4},
                'thickness': 0.75,
                'value': 0
            }
        }
    ))
    
    # Add annotations
    fig.add_annotation(
        text=f"Our Price: €{our_price:.2f}",
        x=0.5, y=0.7,
        xref="paper", yref="paper",
        showarrow=False,
        font=dict(size=16)
    )
    
    fig.add_annotation(
        text=f"Avg Competitor Price: €{avg_competitor_price:.2f}",
        x=0.5, y=0.6,
        xref="paper", yref="paper",
        showarrow=False,
        font=dict(size=16)
    )
    
    fig.add_annotation(
        text=f"Difference: {price_diff_pct:.2f}%",
        x=0.5, y=0.5,
        xref="paper", yref="paper",
        showarrow=False,
        font=dict(size=16, color="blue")
    )
    
    # Add explanation of the gauge
    fig.add_annotation(
        text="[-20% to -10%: Much Lower] [-10% to -3%: Lower] [-3% to 3%: At Market]<br>[3% to 10%: Higher] [10% to 20%: Much Higher]",
        x=0.5, y=0.35,
        xref="paper", yref="paper",
        showarrow=False,
        font=dict(size=12),
        align="center"
    )
    
    # Add interpretation
    if price_diff_pct < -10:
        position_text = "Your price is much lower than competitors. Consider a price increase."
    elif price_diff_pct < -3:
        position_text = "Your price is lower than competitors. You may have room to increase."
    elif price_diff_pct < 3:
        position_text = "Your price is at market level. Maintain current positioning."
    elif price_diff_pct < 10:
        position_text = "Your price is higher than competitors. Monitor for impact on sales."
    else:
        position_text = "Your price is much higher than competitors. Consider a price adjustment."
    
    fig.add_annotation(
        text=position_text,
        x=0.5, y=0.2,
        xref="paper", yref="paper",
        showarrow=False,
        font=dict(size=14, color="darkblue"),
        bgcolor="rgba(255, 255, 255, 0.8)",
        bordercolor="blue",
        borderwidth=1,
        borderpad=4,
        align="center"
    )
    
    # Update layout
    fig.update_layout(
        margin=dict(l=20, r=20, t=100, b=20),
    )
    
    return fig

def create_price_trend_forecast(price_history_df, product_name, days_to_forecast=7):
    """
    Create a price trend forecast visualization
    
    Args:
        price_history_df (DataFrame): Price history data
        product_name (str): Name of the product
        days_to_forecast (int): Number of days to forecast
        
    Returns:
        plotly.graph_objects.Figure: Plotly figure object
    """
    if price_history_df.empty or len(price_history_df) < 5:  # Need at least 5 data points for a forecast
        fig = go.Figure()
        fig.add_annotation(
            text="Insufficient price history data for forecast",
            xref="paper", yref="paper",
            x=0.5, y=0.5,
            showarrow=False,
            font=dict(size=16)
        )
        return fig
    
    # Convert timestamp to datetime
    price_history_df['timestamp'] = pd.to_datetime(price_history_df['timestamp'])
    
    # Create a DataFrame for our prices
    our_prices_df = price_history_df[['timestamp', 'our_price']].copy()
    our_prices_df.columns = ['Date', 'Price']
    
    # Prepare data for forecasting
    our_prices_df['Day'] = (our_prices_df['Date'] - our_prices_df['Date'].min()).dt.days
    
    # Create a simple linear regression model for our prices
    X = our_prices_df['Day'].values.reshape(-1, 1)
    y = our_prices_df['Price'].values
    
    model = LinearRegression()
    model.fit(X, y)
    
    # Create forecast dates
    last_date = our_prices_df['Date'].max()
    forecast_dates = pd.date_range(start=last_date + pd.Timedelta(days=1), periods=days_to_forecast)
    
    # Prepare forecast DataFrame
    forecast_df = pd.DataFrame({'Date': forecast_dates})
    forecast_df['Day'] = (forecast_df['Date'] - our_prices_df['Date'].min()).dt.days
    forecast_df['Price'] = model.predict(forecast_df['Day'].values.reshape(-1, 1))
    
    # Create plot
    fig = go.Figure()
    
    # Add historical prices
    fig.add_trace(go.Scatter(
        x=our_prices_df['Date'],
        y=our_prices_df['Price'],
        mode='lines+markers',
        name='Historical Prices',
        line=dict(color='blue')
    ))
    
    # Add forecast
    fig.add_trace(go.Scatter(
        x=forecast_df['Date'],
        y=forecast_df['Price'],
        mode='lines+markers',
        name='Forecast',
        line=dict(color='red', dash='dash')
    ))
    
    # Add forecast confidence interval (simple approach)
    y_pred = model.predict(X)
    mse = np.mean((y - y_pred) ** 2)
    rmse = np.sqrt(mse)
    
    forecast_upper = forecast_df['Price'] + 1.96 * rmse
    forecast_lower = forecast_df['Price'] - 1.96 * rmse
    
    fig.add_trace(go.Scatter(
        x=forecast_df['Date'],
        y=forecast_upper,
        mode='lines',
        line=dict(width=0),
        showlegend=False
    ))
    
    fig.add_trace(go.Scatter(
        x=forecast_df['Date'],
        y=forecast_lower,
        mode='lines',
        line=dict(width=0),
        fill='tonexty',
        fillcolor='rgba(255, 0, 0, 0.2)',
        name='95% Confidence'
    ))
    
    # Add a vertical line to separate historical data from forecast
    fig.add_shape(
        type='line',
        x0=last_date,
        y0=min(our_prices_df['Price'].min(), forecast_lower.min()) * 0.95,
        x1=last_date,
        y1=max(our_prices_df['Price'].max(), forecast_upper.max()) * 1.05,
        line=dict(
            color='gray',
            width=2,
            dash='dash'
        )
    )
    
    # Add annotation for the forecast start
    fig.add_annotation(
        x=last_date,
        y=max(our_prices_df['Price'].max(), forecast_upper.max()) * 1.05,
        text="Forecast Start",
        showarrow=True,
        arrowhead=1,
        axref='x',
        ayref='y',
        ax=last_date,
        ay=max(our_prices_df['Price'].max(), forecast_upper.max()) * 1.02
    )
    
    # Update layout
    fig.update_layout(
        title=f'Price Trend Forecast for {product_name}',
        xaxis_title='Date',
        yaxis_title='Price (€)',
        template='plotly_white',
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1
        ),
        margin=dict(l=40, r=40, t=60, b=40),
        hovermode="x unified"
    )
    
    return fig

def create_competitor_price_matrix(price_history_df, product_name):
    """
    Create a heat map visualization of competitor prices
    
    Args:
        price_history_df (DataFrame): Price history data
        product_name (str): Name of the product
        
    Returns:
        plotly.graph_objects.Figure: Plotly figure object
    """
    if price_history_df.empty:
        fig = go.Figure()
        fig.add_annotation(
            text="No price history data available",
            xref="paper", yref="paper",
            x=0.5, y=0.5,
            showarrow=False,
            font=dict(size=16)
        )
        return fig
    
    # Convert timestamp to datetime
    price_history_df['timestamp'] = pd.to_datetime(price_history_df['timestamp'])
    
    # Get all competitors
    competitors = set()
    for idx, row in price_history_df.iterrows():
        if isinstance(row['competitor_prices'], dict):
            competitors.update(row['competitor_prices'].keys())
    
    if not competitors:
        fig = go.Figure()
        fig.add_annotation(
            text="No competitor price data available",
            xref="paper", yref="paper",
            x=0.5, y=0.5,
            showarrow=False,
            font=dict(size=16)
        )
        return fig
    
    # Create a DataFrame for the heatmap
    heatmap_data = []
    
    for idx, row in price_history_df.iterrows():
        date = row['timestamp']
        our_price = row['our_price']
        
        entry = {
            'Date': date,
            'Our Price': our_price
        }
        
        if isinstance(row['competitor_prices'], dict):
            for competitor in competitors:
                if competitor in row['competitor_prices']:
                    price = row['competitor_prices'][competitor]
                    if isinstance(price, (int, float)):
                        entry[competitor] = price
        
        heatmap_data.append(entry)
    
    heatmap_df = pd.DataFrame(heatmap_data)
    
    # Convert to percent difference from our price
    for competitor in competitors:
        if competitor in heatmap_df.columns:
            heatmap_df[f"{competitor} (%)"] = (heatmap_df[competitor] - heatmap_df['Our Price']) / heatmap_df['Our Price'] * 100
    
    # Create the heatmap
    z_data = []
    y_labels = []
    
    for competitor in competitors:
        percent_col = f"{competitor} (%)"
        if percent_col in heatmap_df.columns:
            z_data.append(heatmap_df[percent_col].values)
            y_labels.append(competitor)
    
    if not z_data:
        fig = go.Figure()
        fig.add_annotation(
            text="Could not calculate price differences",
            xref="paper", yref="paper",
            x=0.5, y=0.5,
            showarrow=False,
            font=dict(size=16)
        )
        return fig
    
    # Create heatmap
    fig = go.Figure(data=go.Heatmap(
        z=z_data,
        x=heatmap_df['Date'],
        y=y_labels,
        colorscale=[
            [0, 'green'],      # -100% (they are cheaper)
            [0.4, 'lightgreen'],
            [0.5, 'white'],    # 0%
            [0.6, 'salmon'],
            [1, 'red']         # +100% (they are more expensive)
        ],
        colorbar=dict(
            title='% Difference<br>from Our Price',
            titleside='top',
            tickmode='array',
            tickvals=[-50, -25, 0, 25, 50],
            ticktext=['-50% (cheaper)', '-25%', '0%', '+25%', '+50% (more expensive)'],
            ticks='outside'
        ),
        zmid=0,  # Center the color scale on zero
        zmin=-50,
        zmax=50
    ))
    
    # Update layout
    fig.update_layout(
        title=f'Competitor Price Differences for {product_name}',
        xaxis_title='Date',
        yaxis_title='Competitor',
        template='plotly_white',
        margin=dict(l=40, r=40, t=60, b=40),
        yaxis=dict(
            tickmode='array',
            tickvals=list(range(len(y_labels))),
            ticktext=y_labels
        )
    )
    
    return fig

def create_price_difference_chart(price_history_df, product_name):
    """
    Create a chart showing price differences between our store and competitors
    
    Args:
        price_history_df (DataFrame): Price history data
        product_name (str): Name of the product
        
    Returns:
        plotly.graph_objects.Figure: Plotly figure object
    """
    if price_history_df.empty:
        fig = go.Figure()
        fig.add_annotation(
            text="No price history data available",
            xref="paper", yref="paper",
            x=0.5, y=0.5,
            showarrow=False,
            font=dict(size=16)
        )
        return fig
    
    # Convert timestamp to datetime
    price_history_df['timestamp'] = pd.to_datetime(price_history_df['timestamp'])
    
    # Get all competitors
    competitors = set()
    for idx, row in price_history_df.iterrows():
        if isinstance(row['competitor_prices'], dict):
            competitors.update(row['competitor_prices'].keys())
    
    if not competitors:
        fig = go.Figure()
        fig.add_annotation(
            text="No competitor price data available",
            xref="paper", yref="paper",
            x=0.5, y=0.5,
            showarrow=False,
            font=dict(size=16)
        )
        return fig
    
    # Create a DataFrame for the differences
    diff_data = []
    
    for idx, row in price_history_df.iterrows():
        date = row['timestamp']
        our_price = row['our_price']
        
        if isinstance(row['competitor_prices'], dict):
            for competitor in competitors:
                if competitor in row['competitor_prices']:
                    price = row['competitor_prices'][competitor]
                    if isinstance(price, (int, float)):
                        diff_pct = (our_price - price) / price * 100
                        diff_data.append({
                            'Date': date,
                            'Competitor': competitor,
                            'Difference (%)': diff_pct
                        })
    
    if not diff_data:
        fig = go.Figure()
        fig.add_annotation(
            text="Could not calculate price differences",
            xref="paper", yref="paper",
            x=0.5, y=0.5,
            showarrow=False,
            font=dict(size=16)
        )
        return fig
    
    diff_df = pd.DataFrame(diff_data)
    
    # Create the chart
    fig = px.line(
        diff_df, 
        x='Date', 
        y='Difference (%)', 
        color='Competitor',
        title=f'Price Difference from Competitors for {product_name}',
        labels={'Difference (%)': 'Our Price Difference (%)', 'Date': 'Date', 'Competitor': 'Competitor'},
        template='plotly_white'
    )
    
    # Add a zero line
    fig.add_shape(
        type='line',
        x0=diff_df['Date'].min(),
        y0=0,
        x1=diff_df['Date'].max(),
        y1=0,
        line=dict(
            color='black',
            width=1,
            dash='dash'
        )
    )
    
    # Add zones
    fig.add_shape(
        type='rect',
        x0=diff_df['Date'].min(),
        y0=5,
        x1=diff_df['Date'].max(),
        y1=100,
        fillcolor='rgba(255, 0, 0, 0.1)',
        line=dict(width=0),
        layer='below'
    )
    
    fig.add_shape(
        type='rect',
        x0=diff_df['Date'].min(),
        y0=-5,
        x1=diff_df['Date'].max(),
        y1=5,
        fillcolor='rgba(255, 255, 0, 0.1)',
        line=dict(width=0),
        layer='below'
    )
    
    fig.add_shape(
        type='rect',
        x0=diff_df['Date'].min(),
        y0=-100,
        x1=diff_df['Date'].max(),
        y1=-5,
        fillcolor='rgba(0, 255, 0, 0.1)',
        line=dict(width=0),
        layer='below'
    )
    
    # Add annotations for the zones
    fig.add_annotation(
        x=diff_df['Date'].max(),
        y=10,
        text="Above Market",
        showarrow=False,
        xanchor='right',
        font=dict(color='darkred')
    )
    
    fig.add_annotation(
        x=diff_df['Date'].max(),
        y=0,
        text="At Market",
        showarrow=False,
        xanchor='right',
        font=dict(color='darkgoldenrod')
    )
    
    fig.add_annotation(
        x=diff_df['Date'].max(),
        y=-10,
        text="Below Market",
        showarrow=False,
        xanchor='right',
        font=dict(color='darkgreen')
    )
    
    # Update layout
    fig.update_layout(
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1
        ),
        margin=dict(l=40, r=40, t=60, b=40),
        hovermode="x unified"
    )
    
    return fig