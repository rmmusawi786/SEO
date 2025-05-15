import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
import json

from utils.database import get_products, get_price_history, get_settings
from utils.ai_analyzer import get_bulk_analysis, get_price_analysis
from utils.visualizations import create_price_history_chart

st.set_page_config(
    page_title="Multi-Product Analysis",
    page_icon="📊",
    layout="wide"
)

def app():
    st.title("📊 Multi-Product Analysis")
    st.markdown("""
    Analyze and compare multiple products at once. Get AI-powered insights on pricing trends 
    across your product catalog and discover opportunities to optimize your pricing strategy.
    """)
    
    # Get all products
    products_df = get_products()
    
    if products_df.empty:
        st.warning("No products found. Please add products first.")
        return
    
    # Selection mode options
    selection_mode = st.radio(
        "Analysis Mode", 
        ["Analyze All Products", "Select Specific Products"],
        horizontal=True
    )
    
    selected_product_ids = []
    
    if selection_mode == "Analyze All Products":
        selected_product_ids = products_df['id'].tolist()
        st.success(f"Analyzing all {len(selected_product_ids)} products")
    else:
        # Create a multiselect for choosing products
        product_options = [(row['id'], row['name']) for _, row in products_df.iterrows()]
        selected_options = st.multiselect(
            "Select Products to Analyze",
            options=product_options,
            format_func=lambda x: f"{x[1]}"
        )
        
        if not selected_options:
            st.warning("Please select at least one product to analyze.")
            return
        
        selected_product_ids = [option[0] for option in selected_options]
        st.success(f"Analyzing {len(selected_product_ids)} selected products")
    
    # Time period selection
    st.subheader("Analysis Settings")
    col1, col2 = st.columns(2)
    
    with col1:
        time_options = {
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
        analyze_button = st.button("Analyze Products", type="primary")
    
    if analyze_button:
        with st.spinner("Analyzing products..."):
            st.subheader("AI Analysis Report")
            
            # Perform bulk analysis
            if len(selected_product_ids) > 1:
                # For multiple products, use bulk analysis
                analysis_results = get_bulk_analysis(days)
                
                # Filter for only selected products
                analysis_results = [r for r in analysis_results if r['product_id'] in selected_product_ids]
                
                if not analysis_results:
                    st.warning("No analysis data available for the selected products and time period.")
                    return
                
                # Extract key insights
                insights_tab, price_comp_tab, trends_tab, data_tab = st.tabs([
                    "Key Insights", "Price Comparison", "Price Trends", "Raw Data"
                ])
                
                with insights_tab:
                    # Create a summary of insights for all products
                    summary_cols = st.columns(3)
                    
                    # Calculate aggregate metrics
                    total_products = len(analysis_results)
                    products_with_price_changes = sum(1 for r in analysis_results if abs(r.get('price_change_percentage', 0)) > 0.5)
                    avg_price_change = np.mean([r.get('price_change_percentage', 0) for r in analysis_results])
                    products_above_market = sum(1 for r in analysis_results if r.get('price_position', '') == 'above market')
                    products_below_market = sum(1 for r in analysis_results if r.get('price_position', '') == 'below market')
                    products_at_market = total_products - products_above_market - products_below_market
                    
                    with summary_cols[0]:
                        st.metric("Products Analyzed", total_products)
                        st.metric("Products with Price Changes", products_with_price_changes)
                    
                    with summary_cols[1]:
                        st.metric("Average Price Change", f"{avg_price_change:.2f}%", 
                                 delta=f"{avg_price_change:.2f}%" if abs(avg_price_change) > 0.5 else None)
                        
                    with summary_cols[2]:
                        st.metric("Products Above Market", products_above_market)
                        st.metric("Products Below Market", products_below_market)
                    
                    # Show AI insights from bulk analysis
                    st.subheader("AI Insights")
                    
                    for result in analysis_results:
                        with st.expander(f"{result.get('product_name', 'Product')}", expanded=False):
                            # Show AI recommendations
                            if 'recommendation' in result:
                                st.markdown(f"**AI Recommendation:** {result['recommendation']}")
                            
                            # Show reasoning
                            if 'reasoning' in result:
                                st.markdown(f"**Analysis:** {result['reasoning']}")
                            
                            # Show any tips
                            if 'tips' in result:
                                st.markdown(f"**Tips:** {result['tips']}")
                
                with price_comp_tab:
                    # Create a comparative price positions chart
                    pos_data = []
                    for result in analysis_results:
                        # Extract data
                        product_name = result.get('product_name', 'Unknown')
                        our_price = result.get('current_price', 0)
                        avg_competitor = result.get('average_competitor_price', 0)
                        min_competitor = result.get('lowest_competitor_price', 0)
                        max_competitor = result.get('highest_competitor_price', 0)
                        
                        # Add to data list
                        pos_data.append({
                            'product': product_name,
                            'our_price': our_price,
                            'average_competitor': avg_competitor,
                            'lowest_competitor': min_competitor,
                            'highest_competitor': max_competitor,
                            'price_difference_pct': ((our_price - avg_competitor) / avg_competitor * 100) if avg_competitor else 0
                        })
                    
                    pos_df = pd.DataFrame(pos_data)
                    
                    if not pos_df.empty:
                        # Sort by price difference
                        pos_df = pos_df.sort_values('price_difference_pct')
                        
                        # Create the chart
                        fig = go.Figure()
                        
                        # Add trace for our price
                        fig.add_trace(go.Bar(
                            y=pos_df['product'],
                            x=pos_df['our_price'],
                            name='Our Price',
                            orientation='h',
                            marker=dict(color='rgba(58, 71, 80, 0.8)')
                        ))
                        
                        # Add range for competitor prices
                        for i, row in pos_df.iterrows():
                            fig.add_shape(
                                type="line",
                                x0=row['lowest_competitor'], 
                                y0=i,
                                x1=row['highest_competitor'],
                                y1=i,
                                line=dict(color="rgba(156, 165, 196, 1)", width=4),
                                name="Competitor Range"
                            )
                            
                            # Add marker for average
                            fig.add_trace(go.Scatter(
                                x=[row['average_competitor']],
                                y=[row['product']],
                                mode='markers',
                                marker=dict(symbol='diamond', size=10, color='rgba(255, 0, 0, 0.7)'),
                                name='Avg Competitor' if i == 0 else None,
                                showlegend=(i == 0)
                            ))
                        
                        # Update layout
                        fig.update_layout(
                            title='Our Prices vs Competitor Ranges',
                            xaxis_title='Price (€)',
                            yaxis_title='Product',
                            barmode='group',
                            height=max(400, len(pos_df) * 60),
                            legend=dict(
                                orientation="h",
                                yanchor="bottom",
                                y=1.02,
                                xanchor="right",
                                x=1
                            ),
                            margin=dict(l=20, r=20, t=50, b=50),
                        )
                        
                        st.plotly_chart(fig, use_container_width=True)
                        
                        # Add explanation
                        st.info("""
                        **Chart explanation:**
                        - **Blue bars** show our current prices
                        - **Gray lines** represent the range of competitor prices (min to max)
                        - **Red diamonds** show the average competitor price
                        """)
                
                with trends_tab:
                    # Create price trend mini-charts for each product
                    st.subheader("Price Trends by Product")
                    
                    # Create a grid of small charts
                    chart_cols = st.columns(2)
                    
                    for i, product_id in enumerate(selected_product_ids):
                        # Get product name
                        product_name = products_df[products_df['id'] == product_id]['name'].iloc[0]
                        
                        # Get price history
                        price_history = get_price_history(product_id, days)
                        
                        if not price_history.empty:
                            with chart_cols[i % 2]:
                                st.markdown(f"#### {product_name}")
                                fig = create_price_history_chart(price_history, product_name, view_mode="line")
                                # Make chart smaller
                                fig.update_layout(height=300, margin=dict(l=20, r=20, t=30, b=20))
                                st.plotly_chart(fig, use_container_width=True)
                
                with data_tab:
                    # Show raw data table
                    st.subheader("Raw Analysis Data")
                    
                    # Create a clean table of results
                    table_data = []
                    for result in analysis_results:
                        row = {
                            'Product': result.get('product_name', 'Unknown'),
                            'Our Price': f"€{result.get('current_price', 0):.2f}",
                            'Avg Competitor': f"€{result.get('average_competitor_price', 0):.2f}",
                            'Price Change': f"{result.get('price_change_percentage', 0):.2f}%",
                            'Position': result.get('price_position', 'Unknown'),
                            'Recommendation': result.get('short_recommendation', 'No recommendation')
                        }
                        table_data.append(row)
                    
                    table_df = pd.DataFrame(table_data)
                    st.dataframe(table_df, use_container_width=True)
            
            else:
                # For a single product, display detailed analysis
                product_id = selected_product_ids[0]
                product_name = products_df[products_df['id'] == product_id]['name'].iloc[0]
                
                st.subheader(f"Detailed Analysis for {product_name}")
                
                # Get single product analysis
                analysis = get_price_analysis(product_id, days)
                
                if not analysis:
                    st.warning("No analysis data available for this product and time period.")
                    return
                
                # Create tabs for different analysis views
                analysis_tab, viz_tab, data_tab = st.tabs([
                    "AI Analysis", "Visualizations", "Raw Data"
                ])
                
                with analysis_tab:
                    # Show current status metrics
                    metric_cols = st.columns(3)
                    
                    with metric_cols[0]:
                        st.metric("Current Price", f"€{analysis.get('current_price', 0):.2f}")
                        
                    with metric_cols[1]:
                        price_change = analysis.get('price_change_percentage', 0)
                        st.metric("Price Change", f"{price_change:.2f}%", 
                                 delta=f"{price_change:.2f}%" if abs(price_change) > 0.5 else None)
                        
                    with metric_cols[2]:
                        st.metric("Market Position", analysis.get('price_position', 'Unknown').title())
                    
                    # Show AI recommendation
                    st.markdown("### AI Recommendation")
                    st.info(analysis.get('recommendation', 'No recommendation available.'))
                    
                    # Show reasoning
                    st.markdown("### Analysis")
                    st.write(analysis.get('reasoning', 'No analysis available.'))
                    
                    # Show tips
                    if 'tips' in analysis:
                        st.markdown("### Tips")
                        st.write(analysis['tips'])
                
                with viz_tab:
                    # Get price history for visualization
                    price_history = get_price_history(product_id, days)
                    
                    if not price_history.empty:
                        # Price trend chart
                        st.markdown("### Price Trend")
                        fig = create_price_history_chart(price_history, product_name, view_mode="line")
                        st.plotly_chart(fig, use_container_width=True)
                        
                        # Price comparison with competitors
                        st.markdown("### Competitor Comparison")
                        
                        # Extract competitor data for the latest date
                        latest_data = price_history.iloc[-1]
                        our_price = latest_data['our_price']
                        competitor_prices = latest_data['competitor_prices']
                        
                        # Create comparison chart
                        if competitor_prices and isinstance(competitor_prices, dict):
                            comp_data = {
                                'Seller': ['Our Price'] + list(competitor_prices.keys()),
                                'Price': [our_price] + list(competitor_prices.values())
                            }
                            comp_df = pd.DataFrame(comp_data)
                            
                            # Sort by price
                            comp_df = comp_df.sort_values('Price')
                            
                            # Create bar chart
                            fig = px.bar(
                                comp_df, 
                                x='Seller', 
                                y='Price',
                                color='Seller',
                                color_discrete_map={'Our Price': 'rgba(58, 71, 80, 0.8)'},
                                title="Current Price Comparison"
                            )
                            
                            # Customize
                            fig.update_layout(height=400)
                            st.plotly_chart(fig, use_container_width=True)
                
                with data_tab:
                    # Show raw analysis data
                    st.json(analysis)
    
    # Add information about the feature
    with st.expander("About Multi-Product Analysis", expanded=False):
        st.markdown("""
        ### How to use this feature
        
        The Multi-Product Analysis tool allows you to analyze either all your products or a selected 
        subset to identify pricing trends and opportunities.
        
        **Analysis options:**
        - **Analyze All Products**: Get a comprehensive view of your entire product catalog
        - **Select Specific Products**: Choose specific products to compare and analyze together
        
        **What you get:**
        - AI-powered insights and recommendations for each product
        - Comparative price position analysis across products
        - Price trend visualization for each product
        - Market position assessment (above market, at market, below market)
        
        **Tips:**
        - Use the "Last 7 Days" or "Last 14 Days" timeframes for the most relevant analysis
        - Compare products in the same category to identify category-specific pricing trends
        - Use this analysis before making bulk price adjustments
        """)

if __name__ == "__main__":
    app()