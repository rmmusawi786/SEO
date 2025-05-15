import streamlit as st
import os
import pandas as pd
from database import init_db, get_products, get_settings
from database import upgrade_settings_table, upgrade_products_table
from scheduler import start_scheduler, get_scheduler_status
from pages import (
    monitor_products_page, add_product_page, price_analysis_page,
    price_management_page, settings_page, multi_product_analysis_page
)

# Set page configuration
st.set_page_config(
    page_title="Price Monitor & Analyzer",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Initialize database
init_db()

# Upgrade database if needed
with st.spinner("Updating database schema..."):
    upgrade_settings_table()
    upgrade_products_table()
    
# Auto-start the scheduler if it's not already running
scheduler_status = get_scheduler_status()
if not scheduler_status["running"]:
    start_scheduler()

# Navigation in sidebar
st.sidebar.title("Navigation")
page = st.sidebar.radio(
    "Go to", 
    [
        "Home",
        "Monitor Products",
        "Add Product",
        "Price Analysis",
        "Multi-Product Analysis",
        "Price Management",
        "Settings"
    ]
)

# Main app
if page == "Home":
    st.title("Price Monitor & Analyzer")
    
    # App description
    st.markdown("""
    ### Track competitor prices and optimize your pricing strategy
    This application helps you monitor product prices across multiple platforms,
    analyze pricing trends, and get AI-powered price recommendations to stay competitive.
    """)
    
    # Dashboard summary
    st.subheader("Dashboard Summary")
    
    # Get products from database
    products_df = get_products()
    
    # Create metrics
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.metric("Products Monitored", len(products_df) if not products_df.empty else 0)
    
    with col2:
        # Count unique competitors
        if not products_df.empty and 'competitor_urls' in products_df.columns:
            competitors = set()
            for urls in products_df['competitor_urls']:
                if urls:
                    if isinstance(urls, dict):
                        competitors.update(urls.keys())
                    elif isinstance(urls, list):
                        competitors.update(range(len(urls)))
            competitor_count = len(competitors)
        else:
            competitor_count = 0
        st.metric("Competitors Tracked", competitor_count)
    
    with col3:
        # Get last update time if available
        if not products_df.empty and 'last_checked' in products_df.columns:
            # Handle mixed string and datetime types
            try:
                # Convert any strings to datetime
                products_df['last_checked'] = pd.to_datetime(products_df['last_checked'], errors='coerce')
                # Get max value after conversion
                max_date = products_df['last_checked'].max()
                if pd.notna(max_date):
                    # Convert timestamp to string for display
                    last_check = max_date.strftime('%Y-%m-%d %H:%M')
                else:
                    last_check = "Never"
            except:
                last_check = "Never"
        else:
            last_check = "Never"
        st.metric("Last Price Check", last_check)
    
    # Feature highlights with images
    st.subheader("Key Features")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("""
        ### Price Monitoring
        - Track prices across multiple platforms
        - Schedule automatic price checks
        - Get notified of price changes
        """)
    
    with col2:
        st.markdown("""
        ### Data Analysis
        - Visualize price trends over time
        - Compare your prices with competitors
        - Get AI-powered pricing recommendations
        """)
    
    # Quick guide
    st.subheader("Getting Started")
    st.markdown("""
    1. Add products with the "Add Product" page
    2. Set up scraping schedules in "Settings"
    3. Monitor products and track prices
    4. Generate AI price analysis for individual products
    5. Use "Multi-Product Analysis" to compare and analyze multiple products at once
    6. Manage and apply pricing suggestions using "Price Management"
    7. Export suggested prices in JSON or CSV format for your systems
    """)

elif page == "Monitor Products":
    monitor_products_page()
elif page == "Add Product":
    add_product_page()
elif page == "Price Analysis":
    price_analysis_page()
elif page == "Multi-Product Analysis":
    multi_product_analysis_page()
elif page == "Price Management":
    price_management_page()
elif page == "Settings":
    settings_page()

# Add a footer
st.sidebar.markdown("---")
st.sidebar.markdown("### Price Monitor & Analyzer")
st.sidebar.markdown("Version 1.0")
st.sidebar.markdown("© 2025 All Rights Reserved")