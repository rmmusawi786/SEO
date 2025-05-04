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
                
                # Use tabs for all the analysis sections
                analysis_tabs = st.tabs([
                    "Price Suggestion", 
                    "Market Analysis", 
                    "Price Factors", 
                    "Detailed Insights"
                ])
                
                # Check if price constraints are available in the analysis
                has_constraints = "price_constraints" in analysis
                
                with analysis_tabs[0]:
                    # Suggested price with big display
                    col1, col2 = st.columns([1, 2])
                    
                    with col1:
                        st.markdown(f"<h1 style='color:#FF4B4B;'>€{analysis['suggested_price']:.2f}</h1>", unsafe_allow_html=True)
                        
                        if has_constraints:
                            constraints = analysis['price_constraints']
                            current_price = constraints['current_price']
                            price_diff = analysis['suggested_price'] - current_price
                            percent_diff = (price_diff / current_price) * 100
                            
                            # Color code the difference
                            if price_diff > 0:
                                diff_color = "#4CAF50"  # Green for increase
                                direction = "+"
                            else:
                                diff_color = "#FFA500"  # Orange for decrease
                                direction = ""
                                
                            st.markdown(
                                f"<p>Current: <b>€{current_price:.2f}</b></p>"
                                f"<p>Change: <span style='color:{diff_color}'>{direction}{price_diff:.2f} ({direction}{percent_diff:.1f}%)</span></p>",
                                unsafe_allow_html=True
                            )
                    
                    with col2:
                        st.markdown("### Key Rationale")
                        st.write(analysis.get('rationale', analysis.get('reasoning', 'No reasoning provided')))
                    
                    st.subheader("Recommendations")
                    st.write(analysis['recommendations'])
                    
                    # Show price constraints visual
                    if has_constraints:
                        st.markdown("### Price Threshold Analysis")
                        constraints = analysis['price_constraints']
                        
                        # Create a progress bar to show where the suggested price falls within the allowed range
                        min_price = constraints['min_allowed_price']
                        max_price = constraints['max_allowed_price']
                        current_price = constraints['current_price']
                        price_range = max_price - min_price
                        
                        if price_range > 0:
                            # Calculate positions as percentage of the range
                            current_pos = ((current_price - min_price) / price_range) * 100
                            suggestion_pos = ((analysis['suggested_price'] - min_price) / price_range) * 100
                            
                            # Create metrics to show min, current, and max allowed prices
                            col1, col2, col3 = st.columns(3)
                            with col1:
                                st.metric("Minimum Price", f"€{min_price:.2f}")
                            
                            with col2:
                                st.metric("Current Price", f"€{current_price:.2f}")
                            
                            with col3:
                                st.metric("Maximum Price", f"€{max_price:.2f}")
                                
                            st.markdown(
                                f"<p>Min: <b>€{min_price:.2f}</b> ({constraints['min_threshold_eur']}€ from current)</p>"
                                f"<p>Max: <b>€{max_price:.2f}</b> (+{constraints['max_threshold_eur']}€ from current)</p>",
                                unsafe_allow_html=True
                            )
                            
                            # Show a visual range using Streamlit's progress bar
                            st.progress(suggestion_pos / 100)
                            st.caption(f"Suggested price relative to allowed range (Min → Max)")
                
                with analysis_tabs[1]:
                    st.subheader("Market Position")
                    st.write(analysis['market_position'])
                    
                    st.subheader("Competitive Analysis")
                    st.write(analysis['competitive_analysis'])
                    
                    if 'market_segment_impact' in analysis:
                        st.subheader("Market Segment Impact")
                        st.write(analysis['market_segment_impact'])
                
                with analysis_tabs[2]:
                    st.subheader("Price Trends")
                    st.write(analysis['price_trends'])
                    
                    if 'pricing_factors' in analysis:
                        st.subheader("Key Pricing Factors")
                        st.write(analysis['pricing_factors'])
                    
                    if 'profit_margin_analysis' in analysis:
                        st.subheader("Profit Margin Analysis")
                        st.write(analysis['profit_margin_analysis'])
                
                with analysis_tabs[3]:
                    if 'psychological_factors' in analysis:
                        st.subheader("Psychological Pricing Factors")
                        st.write(analysis['psychological_factors'])
                    
                    if 'long_term_strategy' in analysis:
                        st.subheader("Long-term Strategy")
                        st.write(analysis['long_term_strategy'])
                    
                
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
