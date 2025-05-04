import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import json
from datetime import datetime, timedelta
from utils.database import get_products, get_price_history
from utils.scheduler import run_scraper_now, get_scheduler_status

def app():
    st.title("Price Monitor Dashboard")
    
    # Get all products
    products_df = get_products()
    
    if products_df.empty:
        st.info("No products have been added yet. Please add products in the 'Add Product' tab.")
        return
    
    # Dashboard header with metrics
    scheduler_status = get_scheduler_status()
    
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
        if st.button("Update Prices Now"):
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
        
        # Time period selection
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
        
        # Get price history
        price_history = get_price_history(selected_id, days)
        
        if price_history.empty:
            st.warning(f"No price history available for this product in the selected time period. Try updating prices or selecting a different time period.")
        else:
            # Price history data
            st.subheader(f"Price History for {product_row['name']}")
            
            # Create DataFrame for our prices
            our_price_df = price_history[['timestamp', 'our_price']].copy()
            our_price_df.rename(columns={'our_price': 'price'}, inplace=True)
            our_price_df['source'] = 'Our Store'
            
            # Create DataFrames for competitor prices
            all_prices_df = our_price_df.copy()
            
            competitor_colors = {}
            
            for _, row in price_history.iterrows():
                competitor_prices = row['competitor_prices']
                
                for competitor, price in competitor_prices.items():
                    # Add competitor to the color map if not there
                    if competitor not in competitor_colors:
                        competitor_colors[competitor] = len(competitor_colors) + 1
                    
                    # Add competitor price to the main DataFrame
                    all_prices_df = pd.concat([
                        all_prices_df, 
                        pd.DataFrame({
                            'timestamp': [row['timestamp']],
                            'price': [price],
                            'source': [competitor]
                        })
                    ], ignore_index=True)
            
            # Plot the price history
            fig = px.line(
                all_prices_df, 
                x='timestamp', 
                y='price', 
                color='source',
                title=f'Price Comparison over Time',
                labels={'timestamp': 'Date', 'price': 'Price', 'source': 'Source'},
                markers=True
            )
            
            fig.update_layout(
                legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
                height=500,
                hovermode="x unified"
            )
            
            st.plotly_chart(fig, use_container_width=True)
            
            # Price comparison metrics
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
            
            # Price statistics
            st.subheader("Price Statistics")
            
            # Create statistics tables
            stats_data = []
            
            # Our price stats
            our_prices = our_price_df['price'].tolist()
            stats_data.append({
                'Source': 'Our Store',
                'Min': f"€{min(our_prices):.2f}",
                'Max': f"€{max(our_prices):.2f}",
                'Average': f"€{sum(our_prices)/len(our_prices):.2f}",
                'Current': f"€{our_prices[-1]:.2f}"
            })
            
            # Competitor price stats
            for competitor in competitor_colors.keys():
                comp_prices = all_prices_df[all_prices_df['source'] == competitor]['price'].tolist()
                if comp_prices:
                    stats_data.append({
                        'Source': competitor,
                        'Min': f"€{min(comp_prices):.2f}",
                        'Max': f"€{max(comp_prices):.2f}",
                        'Average': f"€{sum(comp_prices)/len(comp_prices):.2f}",
                        'Current': f"€{comp_prices[-1]:.2f}"
                    })
            
            # Display statistics table
            st.dataframe(
                pd.DataFrame(stats_data),
                use_container_width=True,
                hide_index=True
            )
            
            # Show raw data in expandable section
            with st.expander("Show Raw Price Data"):
                st.dataframe(all_prices_df, use_container_width=True)

# Run the app
app()
