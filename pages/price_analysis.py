import streamlit as st
import pandas as pd
import json
from datetime import datetime, timedelta
from utils.database import get_products, get_settings
from utils.ai_analyzer import get_price_analysis

def app():
    st.title("AI Price Analysis")
    
    # Check if OpenAI API key is set
    if not st.session_state.get('openai_key_checked'):
        import os
        openai_key = os.environ.get("OPENAI_API_KEY", "")
        if not openai_key:
            st.warning(
                "OpenAI API key is not set. Please set the OPENAI_API_KEY environment variable to use the AI analysis features."
            )
            st.session_state['openai_key_checked'] = True
            st.session_state['openai_key_available'] = False
        else:
            st.session_state['openai_key_checked'] = True
            st.session_state['openai_key_available'] = True
    
    # If OpenAI API key is not available, show instructions
    if st.session_state.get('openai_key_checked') and not st.session_state.get('openai_key_available'):
        st.info(
            "To use AI analysis features, you need to set the OpenAI API key. "
            "Please restart the application with the OPENAI_API_KEY environment variable set."
        )
    
    # Get all products
    products_df = get_products()
    
    if products_df.empty:
        st.info("No products have been added yet. Please add products in the 'Add Product' tab.")
        return
    
    # Settings
    settings = get_settings()
    default_analysis_period = settings["analysis_period"]
    
    # Product selection
    st.subheader("Select Product for AI Analysis")
    
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
        col1, col2 = st.columns([3, 1])
        
        with col1:
            time_options = {
                "Last 3 Days": 3,
                "Last 7 Days": 7,
                "Last 14 Days": 14,
                "Last 30 Days": 30,
                "All Time": None
            }
            
            selected_time = st.select_slider(
                "Analysis Period",
                options=list(time_options.keys()),
                value="Last 7 Days"
            )
            
            days = time_options[selected_time]
        
        with col2:
            st.write("")
            st.write("")
            if st.button("Generate Analysis", type="primary"):
                if st.session_state.get('openai_key_available', False):
                    with st.spinner("Analyzing price data with OpenAI GPT-4o..."):
                        analysis = get_price_analysis(selected_id, days)
                        
                        if "error" in analysis:
                            st.error(f"Error generating analysis: {analysis['error']}")
                        else:
                            st.session_state["current_analysis"] = analysis
                else:
                    st.error("OpenAI API key is required for AI analysis.")
        
        # Display analysis results if available
        if "current_analysis" in st.session_state:
            analysis = st.session_state["current_analysis"]
            
            if analysis["product_id"] == selected_id:
                st.header(f"Price Analysis for {analysis['product_name']}")
                
                # Display date range
                st.caption(f"Analysis period: {analysis['date_range']['start']} to {analysis['date_range']['end']}")
                
                # Create card style containers for each section
                st.subheader("Market Position")
                st.markdown(f"**{analysis['market_position']}**")
                
                col1, col2 = st.columns(2)
                
                with col1:
                    st.subheader("Price Trends")
                    st.write(analysis['price_trends'])
                
                with col2:
                    st.subheader("Competitive Analysis")
                    st.write(analysis['competitive_analysis'])
                
                st.subheader("Recommendations")
                st.write(analysis['recommendations'])
                
                # Suggested price with big display
                st.subheader("Suggested Price")
                
                col1, col2 = st.columns([1, 3])
                
                with col1:
                    st.markdown(f"<h1 style='color:#FF4B4B;'>€{analysis['suggested_price']:.2f}</h1>", unsafe_allow_html=True)
                
                with col2:
                    st.markdown("**Reasoning:**")
                    st.write(analysis['reasoning'])
                
                # Action buttons - these would need implementation in a real app
                st.subheader("Actions")
                col1, col2, col3 = st.columns(3)
                
                with col1:
                    if st.button("Accept Suggested Price"):
                        st.success("Price update would be implemented here in a real application")
                
                with col2:
                    if st.button("Download Analysis Report"):
                        st.info("Report download would be implemented here in a real application")
                
                with col3:
                    if st.button("Share Analysis"):
                        st.info("Sharing functionality would be implemented here in a real application")
            else:
                # Clear previous analysis if different product is selected
                del st.session_state["current_analysis"]
                st.info("Please generate analysis for this product.")
        else:
            st.info("Click 'Generate Analysis' to get AI-powered pricing recommendations.")

# Run the app
app()
