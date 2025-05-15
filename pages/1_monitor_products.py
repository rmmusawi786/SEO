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
    
    st.markdown("## Dashboard Overview")
    
    # Top metrics row
    metric_col1, metric_col2, metric_col3, metric_col4 = st.columns(4)
    
    with metric_col1:
        st.metric("Products Monitored", len(products_df))
    
    with metric_col2:
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
    
    with metric_col3:
        # Calculate price data freshness
        last_updated_times = []
        for _, product in products_df.iterrows():
            if 'last_checked' in product and product['last_checked'] is not None and not pd.isna(product['last_checked']):
                last_updated_times.append(product['last_checked'])
        
        if last_updated_times:
            latest_update = max(last_updated_times)
            # Convert to datetime object if it's a string
            if isinstance(latest_update, str):
                try:
                    latest_update = datetime.strptime(latest_update, "%Y-%m-%d %H:%M:%S")
                except ValueError:
                    try:
                        latest_update = datetime.strptime(latest_update, "%Y-%m-%d %H:%M:%S.%f")
                    except ValueError:
                        latest_update = datetime.now()  # Fallback if parsing fails
            
            time_since_update = datetime.now() - latest_update
            hours_since_update = int(time_since_update.total_seconds() / 3600)
            
            if hours_since_update < 1:
                freshness_text = "< 1 hour ago"
            elif hours_since_update < 24:
                freshness_text = f"{hours_since_update} hours ago"
            else:
                days = int(hours_since_update / 24)
                freshness_text = f"{days} days ago"
                
            st.metric("Last Price Update", freshness_text)
        else:
            st.metric("Last Price Update", "Never")
    
    with metric_col4:
        # Get scheduler status
        if scheduler_status["running"]:
            status_text = f"Running (every {scheduler_status['interval']})"
            next_run = scheduler_status.get("next_run")
            if next_run:
                time_remaining = next_run - datetime.now()
                minutes_remaining = int(time_remaining.total_seconds() / 60)
                if minutes_remaining > 0:
                    status_text += f" - Next run in {minutes_remaining} mins"
            
            # Show status with a green color
            st.markdown(f"<div style='background-color: #d4edda; padding: 10px; border-radius: 5px;'><strong>Scraper Status:</strong> {status_text}</div>", unsafe_allow_html=True)
        else:
            # Show status with a red color
            st.markdown(f"<div style='background-color: #f8d7da; padding: 10px; border-radius: 5px;'><strong>Scraper Status:</strong> Not Running</div>", unsafe_allow_html=True)
    
    # Button to run scraper now
    col1, col2 = st.columns([1, 3])
    with col1:
        if st.button("Update Prices Now", type="primary"):
            with st.spinner("Scraping product prices..."):
                results = run_scraper_now()
                if isinstance(results, str) and "Error" in results:
                    st.error(results)
                elif isinstance(results, list) and results:
                    # Check for and display any issues
                    issues_found = False
                    
                    # Create tabs for success and issues
                    scrape_tabs = st.tabs(["Results Summary", "Scraping Issues"])
                    
                    with scrape_tabs[0]:
                        st.success(f"Successfully updated prices for {len(results)} products!")
                    
                    with scrape_tabs[1]:
                        # Collect all issues
                        all_issues = []
                        
                        for result in results:
                            # Check for our product issues
                            if 'our_product_issues' in result:
                                issues_found = True
                                all_issues.append({
                                    'product': result['product_name'],
                                    'source': 'Our Store',
                                    'issue': result['our_product_issues']
                                })
                            
                            # Check for competitor issues
                            if 'competitor_issues' in result and result['competitor_issues']:
                                issues_found = True
                                for comp_name, comp_data in result['competitor_issues'].items():
                                    all_issues.append({
                                        'product': result['product_name'],
                                        'source': comp_name,
                                        'url': comp_data['url'],
                                        'issue': comp_data['issue']
                                    })
                        
                        if issues_found:
                            st.warning("Some data sources had issues during scraping")
                            
                            # Create a DataFrame from issues and display it
                            if all_issues:
                                issues_df = pd.DataFrame(all_issues)
                                st.dataframe(
                                    issues_df,
                                    use_container_width=True,
                                    column_config={
                                        "product": "Product",
                                        "source": "Source",
                                        "url": "URL",
                                        "issue": "Issue"
                                    }
                                )
                        else:
                            st.success("No issues were found during scraping")
                    
                    # Refresh the page to show updated data
                    st.rerun()
                else:
                    st.info("No products updated or no results returned.")
    
    # Product Status Overview
    st.markdown("## Product Status Overview")
    
    # Create a dataframe for product status
    status_data = []
    for _, product in products_df.iterrows():
        # Get last price history entry
        price_history = get_price_history(product['id'], days=7)
        
        product_status = {
            "id": product['id'],
            "name": product['name'],
            "url": product['our_url'],
            "price": "N/A",
            "last_update": product.get('last_checked', None),
            "status": "Unknown"
        }
        
        if not price_history.empty:
            # Get the latest price
            latest_price = price_history.iloc[-1]['our_price']
            product_status["price"] = f"€{latest_price:.2f}"
            
            # Determine status based on last update time
            if product.get('last_checked'):
                last_checked = product['last_checked']
                # Convert to datetime object if it's a string
                if isinstance(last_checked, str):
                    try:
                        last_checked = datetime.strptime(last_checked, "%Y-%m-%d %H:%M:%S")
                    except ValueError:
                        try:
                            last_checked = datetime.strptime(last_checked, "%Y-%m-%d %H:%M:%S.%f")
                        except ValueError:
                            last_checked = datetime.now()  # Fallback if parsing fails
                            
                hours_since_update = (datetime.now() - last_checked).total_seconds() / 3600
                if hours_since_update < 24:
                    product_status["status"] = "Active"
                elif hours_since_update < 48:
                    product_status["status"] = "Warning"
                else:
                    product_status["status"] = "Stale"
        
        status_data.append(product_status)
    
    # Create a dataframe
    status_df = pd.DataFrame(status_data)
    
    # Add status icons using custom HTML
    def format_status(status):
        if status == "Active":
            return "🟢 Active"
        elif status == "Warning":
            return "🟠 Warning"
        elif status == "Stale":
            return "🔴 Stale"
        else:
            return "⚪ Unknown"
    
    status_df["status_display"] = status_df["status"].apply(format_status)
    
    # Display the status table
    st.dataframe(
        status_df[["id", "name", "price", "last_update", "status_display"]],
        column_config={
            "id": st.column_config.NumberColumn("ID"),
            "name": st.column_config.TextColumn("Product Name"),
            "price": st.column_config.TextColumn("Current Price"),
            "last_update": st.column_config.DatetimeColumn("Last Updated", format="DD/MM/YYYY HH:mm"),
            "status_display": st.column_config.TextColumn("Status")
        },
        use_container_width=True,
        hide_index=True
    )
    
    # Product selection for detailed view
    st.markdown("## Product Price History")
    
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
        
        # Time period selection
        col1, col2, col3 = st.columns([2, 1, 1])
        
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
                "Time Period",
                options=list(time_options.keys()),
                value="Last 7 Days"
            )
            
            days = time_options[selected_time]
        
        with col2:
            chart_type = st.selectbox(
                "Chart Type",
                ["Line", "Area", "Bar", "Candlestick"]
            )
        
        with col3:
            # Get price history for the selected product
            price_history = get_price_history(selected_id, days)
            
            if price_history.empty:
                st.warning("No price data available for the selected period.")
                view_mode = "line"
            else:
                view_mode = chart_type.lower()
        
        # Display the price history chart
        if not price_history.empty:
            st.subheader(f"Price History for {product_name}")
            
            # Create tabs for different visualizations
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
                our_price_df = our_price_df.rename(columns={'our_price': 'price'})
                our_price_df['source'] = 'Our Store'
                
                # Create DataFrames for competitor prices
                all_prices_df = our_price_df.copy()
                
                for _, row in price_history.iterrows():
                    competitor_prices = row['competitor_prices']
                    
                    for competitor, price in competitor_prices.items():
                        # Add competitor price to the main DataFrame
                        comp_df = pd.DataFrame({
                            'timestamp': [row['timestamp']],
                            'price': [price],
                            'source': [competitor]
                        })
                        all_prices_df = pd.concat([all_prices_df, comp_df], ignore_index=True)
                
                # Sort by timestamp and source
                all_prices_df = all_prices_df.sort_values(by=['timestamp', 'source']).reset_index(drop=True)
                
                # Format price column
                all_prices_df['price'] = all_prices_df['price'].apply(lambda x: f"€{x:.2f}" if pd.notnull(x) else "N/A")
                
                # Display the DataFrame
                st.dataframe(
                    all_prices_df,
                    use_container_width=True,
                    column_config={
                        "timestamp": st.column_config.DatetimeColumn("Date & Time"),
                        "source": "Source",
                        "price": "Price"
                    }
                )
        else:
            st.info("No price data available for the selected time period. Try running the scraper or selecting a different time range.")
    
    # Add a note about the scheduler
    st.markdown("---")
    st.info("""
    **Note:** The price monitoring system runs automatically based on the configured schedule.
    You can check the current schedule status in the Dashboard Overview section and
    run the scraper manually by clicking "Update Prices Now" if you need the latest data immediately.
    """)

app()