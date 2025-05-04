import streamlit as st
import os
import pandas as pd
from utils.database import init_db, get_products
from utils.database_upgrade import upgrade_settings_table

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

# Main app
def main():
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
                    competitors.update(urls.split(','))
            competitor_count = len(competitors)
        else:
            competitor_count = 0
        st.metric("Competitors Tracked", competitor_count)
    
    with col3:
        # Get last update time if available
        if not products_df.empty and 'last_checked' in products_df.columns:
            last_check = products_df['last_checked'].max() if not pd.isna(products_df['last_checked'].max()) else "Never"
        else:
            last_check = "Never"
        st.metric("Last Price Check", last_check)
    
    # Feature highlights with images
    st.subheader("Key Features")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.image("https://images.unsplash.com/photo-1714247046156-b575370e5c00")
        st.markdown("""
        ### Price Monitoring
        - Track prices across multiple platforms
        - Schedule automatic price checks
        - Get notified of price changes
        """)
    
    with col2:
        st.image("https://images.unsplash.com/photo-1551288049-bebda4e38f71")
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
    4. Generate AI price analysis for better decisions
    5. Manage and apply pricing suggestions using "Price Management"
    6. Export suggested prices in JSON or CSV format for your systems
    """)

if __name__ == "__main__":
    main()
