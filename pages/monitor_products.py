import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import json
from datetime import datetime, timedelta
from utils.database import get_products, get_price_history
from utils.scheduler import run_scraper_now, get_scheduler_status
from utils.visualizations import (
    create_price_history_chart,
    create_price_statistics_table,
    create_price_comparison_gauge_chart,
    create_price_trend_forecast,
    create_competitor_price_matrix,
    create_price_difference_chart,
    create_price_radar_chart,
    create_price_parity_chart
)

def app():
    st.title("Price Monitor Dashboard")
    
    # Get all products
    products_df = get_products()
    
    if products_df.empty:
        st.info("No products have been added yet. Please add products in the 'Add Product' tab.")
        return
    
    # Dashboard header with metrics
    scheduler_status = get_scheduler_status()
    
    st.markdown("### Dashboard Overview")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.metric("Products Monitored", len(products_df))
    
    with col2:
        # Count unique competitors
        if 'competitor_urls' in products_df.columns:
            competitors = set()
            for urls in products_df['competitor_urls']:
                if urls and not pd.isna(urls):
                    competitors.update(urls.split(','))
            competitor_count = len(competitors)
        else:
            competitor_count = 0
        st.metric("Competitors Tracked", competitor_count)
    
    with col3:
        # Get scheduler status
        if scheduler_status["running"]:
            status_text = f"Running (every {scheduler_status['interval']})"
            next_run = scheduler_status.get("next_run")
            if next_run:
                time_remaining = next_run - datetime.now()
                minutes_remaining = int(time_remaining.total_seconds() / 60)
                if minutes_remaining > 0:
                    status_text += f" - Next in {minutes_remaining} min"
                else:
                    status_text += " - Next run soon"
        else:
            status_text = "Not Running"
        
        st.metric("Scraper Status", status_text)
    
    # Button to run scraper now
    col1, col2 = st.columns([1, 3])
    with col1:
        if st.button("Update Prices Now", type="primary"):
            with st.spinner("Scraping product prices..."):
                results = run_scraper_now()
                if isinstance(results, str) and "Error" in results:
                    st.error(results)
                elif isinstance(results, list) and results:
                    st.success(f"Successfully updated prices for {len(results)} products!")
                    st.rerun()
                else:
                    st.info("No products updated or no results returned.")
    
    # Product selection
    st.markdown("---")
    st.subheader("Product Price Monitoring")
    
    # Create product dropdown
    product_ids = products_df['id'].tolist()
    product_names = products_df['name'].tolist()
    product_options = [f"{id}: {name}" for id, name in zip(product_ids, product_names)]
    
    selected_product = st.selectbox("Select Product", product_options)
    
    if selected_product:
        # Extract product ID from selection
        selected_id = int(selected_product.split(":")[0])
        
        # Get product details
        product_row = products_df[products_df['id'] == selected_id].iloc[0]
        product_name = product_row['name']
        
        # Time period selection and visualization options
        col1, col2 = st.columns([3, 1])
        
        with col1:
            time_options = {
                "Last 24 Hours": 1,
                "Last 3 Days": 3,
                "Last 7 Days": 7,
                "Last 14 Days": 14,
                "Last 30 Days": 30,
                "All Time": None
            }
            
            selected_time = st.select_slider(
                "Select Time Period",
                options=list(time_options.keys()),
                value="Last 7 Days"
            )
            
            days = time_options[selected_time]
        
        with col2:
            chart_type = st.selectbox(
                "Chart Type",
                ["Line", "Area", "Bar", "Candlestick"],
                index=0
            )
            
            view_mode_map = {
                "Line": "line",
                "Area": "area",
                "Bar": "bar",
                "Candlestick": "candlestick"
            }
            
            view_mode = view_mode_map[chart_type]
        
        # Get price history
        price_history = get_price_history(selected_id, days)
        
        if price_history.empty:
            st.warning(f"No price history available for this product in the selected time period. Try updating prices or selecting a different time period.")
        else:
            # Create tabs for different analysis views
            price_tabs = st.tabs([
                "Price Overview", 
                "Competitive Analysis", 
                "Price Trends", 
                "Price Matrix",
                "Advanced Visualizations",
                "Data Table"
            ])
            
            # Tab 1: Price Overview
            with price_tabs[0]:
                st.subheader(f"Price History for {product_name}")
                
                # Enhanced price history chart
                fig = create_price_history_chart(price_history, product_name, view_mode)
                st.plotly_chart(fig, use_container_width=True)
                
                # Current price comparison
                st.subheader("Current Price Comparison")
                
                # Get latest prices
                latest_entry = price_history.iloc[-1]
                our_price = latest_entry['our_price']
                competitor_prices = latest_entry['competitor_prices']
                
                # Calculate price differences
                price_diffs = []
                for competitor, price in competitor_prices.items():
                    diff = our_price - price
                    diff_pct = (diff / price) * 100 if price else 0
                    price_diffs.append({
                        'competitor': competitor,
                        'price': price,
                        'diff': diff,
                        'diff_pct': diff_pct
                    })
                
                # Display price comparison
                cols = st.columns(len(price_diffs) + 1)
                
                with cols[0]:
                    st.metric("Our Price", f"€{our_price:.2f}")
                
                for i, diff in enumerate(price_diffs):
                    with cols[i+1]:
                        # Format delta values
                        if diff['diff'] > 0:
                            delta_text = f"+€{diff['diff']:.2f} ({diff['diff_pct']:.1f}%)"
                            delta_color = "inverse"  # Red for higher price (negative)
                        else:
                            delta_text = f"€{diff['diff']:.2f} ({diff['diff_pct']:.1f}%)"
                            delta_color = "normal"  # Green for lower price (positive)
                        
                        st.metric(
                            diff['competitor'],
                            f"€{diff['price']:.2f}",
                            delta=delta_text,
                            delta_color=delta_color
                        )
            
            # Tab 2: Competitive Analysis
            with price_tabs[1]:
                st.subheader("Competitive Analysis")
                
                # Pricing position gauge
                st.markdown("### Price Positioning")
                gauge_fig = create_price_comparison_gauge_chart(price_history, product_name)
                st.plotly_chart(gauge_fig, use_container_width=True)
                
                # Price difference analysis
                st.markdown("### Price Difference Analysis")
                diff_fig = create_price_difference_chart(price_history, product_name)
                st.plotly_chart(diff_fig, use_container_width=True)
            
            # Tab 3: Price Trends
            with price_tabs[2]:
                st.subheader("Price Trend Analysis")
                
                # Price trend forecast
                forecast_fig = create_price_trend_forecast(price_history, product_name)
                st.plotly_chart(forecast_fig, use_container_width=True)
                
                # Price statistics
                st.markdown("### Detailed Price Statistics")
                
                stats_df = create_price_statistics_table(price_history)
                
                if not stats_df.empty:
                    # Format the stats table for display
                    formatted_stats = stats_df.copy()
                    
                    # Change column names for better display
                    formatted_stats = formatted_stats.rename(columns={
                        'StdDev': 'Std Dev',
                        'ChangePct': 'Change %'
                    })
                    
                    # Format the Change and Change % columns
                    formatted_stats['Change'] = formatted_stats['Change'].apply(
                        lambda x: f"+€{x:.2f}" if x > 0 else f"€{x:.2f}"
                    )
                    
                    formatted_stats['Change %'] = formatted_stats['Change %'].apply(
                        lambda x: f"+{x:.1f}%" if x > 0 else f"{x:.1f}%"
                    )
                    
                    # Add € symbol to price columns
                    for col in ['Min', 'Max', 'Average', 'Current']:
                        formatted_stats[col] = formatted_stats[col].apply(lambda x: f"€{x:.2f}")
                    
                    # Display the table
                    st.dataframe(
                        formatted_stats,
                        use_container_width=True,
                        hide_index=True
                    )
            
            # Tab 4: Price Matrix
            with price_tabs[3]:
                st.subheader("Price Comparison Matrix")
                
                # Price matrix visualization
                matrix_fig = create_competitor_price_matrix(price_history, product_name)
                st.plotly_chart(matrix_fig, use_container_width=True)
                
                # Explanation of the matrix
                st.info(
                    "The price matrix above shows a heatmap of prices over time. " +
                    "Each row represents a date, and each column represents a different source. " +
                    "This visualization helps identify patterns in pricing strategies."
                )
            
            # Tab 5: Advanced Visualizations
            with price_tabs[4]:
                st.subheader("Advanced Price Visualizations")
                
                # Price Radar Chart
                st.markdown("### Price Radar Comparison")
                radar_fig = create_price_radar_chart(price_history, product_name)
                st.plotly_chart(radar_fig, use_container_width=True)
                
                st.info(
                    "The radar chart above provides a normalized view of your price compared to competitors. "
                    "This visualization makes it easy to see how your pricing relates to each competitor, "
                    "with percentage differences clearly labeled."
                )
                
                # Price Parity Chart
                st.markdown("### Price Parity Analysis Over Time")
                parity_fig = create_price_parity_chart(price_history, product_name)
                st.plotly_chart(parity_fig, use_container_width=True)
                
                st.info(
                    "The price parity chart uses bubble size to show price magnitude and color to show "
                    "the percentage difference from your price (blue = lower than yours, red = higher than yours). "
                    "This visualization helps track price changes across competitors over time."
                )
            
            # Tab 6: Data Table
            with price_tabs[5]:
                st.subheader("Raw Price Data")
                
                # Create DataFrame for our prices
                our_price_df = price_history[['timestamp', 'our_price']].copy()
                our_price_df.rename(columns={'our_price': 'price'}, inplace=True)
                our_price_df['source'] = 'Our Store'
                
                # Create DataFrames for competitor prices
                all_prices_df = our_price_df.copy()
                
                for _, row in price_history.iterrows():
                    competitor_prices = row['competitor_prices']
                    
                    for competitor, price in competitor_prices.items():
                        # Add competitor price to the main DataFrame
                        all_prices_df = pd.concat([
                            all_prices_df, 
                            pd.DataFrame({
                                'timestamp': [row['timestamp']],
                                'price': [price],
                                'source': [competitor]
                            })
                        ], ignore_index=True)
                
                # Sort by timestamp then source
                all_prices_df = all_prices_df.sort_values(['timestamp', 'source'])
                
                # Format the timestamp
                all_prices_df['timestamp'] = all_prices_df['timestamp'].dt.strftime('%Y-%m-%d %H:%M')
                
                # Format the price
                all_prices_df['price'] = all_prices_df['price'].apply(lambda x: f"€{x:.2f}")
                
                # Display the table
                st.dataframe(
                    all_prices_df,
                    use_container_width=True,
                    column_config={
                        "timestamp": "Date & Time",
                        "price": "Price",
                        "source": "Source"
                    }
                )
                
                # Export options
                export_col1, export_col2 = st.columns([1, 3])
                with export_col1:
                    if st.button("Export Data"):
                        st.info("Export functionality would be implemented in a production environment")

# Run the app
app()
