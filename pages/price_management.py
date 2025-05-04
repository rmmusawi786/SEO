import streamlit as st
import pandas as pd
import json
import os
import io
import base64
from datetime import datetime
from utils.database import (
    get_products, 
    get_latest_prices, 
    add_suggested_price, 
    update_suggested_price,
    delete_suggested_price,
    export_prices_to_json,
    export_prices_to_csv
)
from utils.ai_analyzer import get_price_analysis

def app():
    st.title("Price Management")
    
    # Main tabs
    tab1, tab2 = st.tabs(["Current Prices & Suggestions", "Export Prices"])
    
    with tab1:
        st.header("Price Management Dashboard")
        
        # Get all products with their latest prices and suggestions
        latest_prices_df = get_latest_prices()
        
        if latest_prices_df.empty:
            st.warning("No products with price data found. Add products and price data in the other tabs first.")
            return
        
        # Display products table with current prices
        st.subheader("Products & Current Prices")
        
        # Create a dataframe with the key information
        display_df = latest_prices_df[['product_id', 'product_name', 'current_price']].copy()
        
        # Add columns for competitor prices
        display_df['min_competitor'] = latest_prices_df['competitor_prices'].apply(
            lambda x: min(x.values()) if x and len(x) > 0 else None
        )
        
        display_df['max_competitor'] = latest_prices_df['competitor_prices'].apply(
            lambda x: max(x.values()) if x and len(x) > 0 else None
        )
        
        display_df['avg_competitor'] = latest_prices_df['competitor_prices'].apply(
            lambda x: sum(x.values()) / len(x) if x and len(x) > 0 else None
        )
        
        # Add columns for suggested prices
        display_df['suggested_price'] = latest_prices_df['suggested_price']
        display_df['manual_price'] = latest_prices_df['manual_price']
        display_df['is_applied'] = latest_prices_df['is_applied'].map({1: "✓", 0: ""})
        
        # Format the dataframe for display
        formatted_df = display_df.copy()
        
        # Convert price columns to formatted strings
        price_columns = ['current_price', 'min_competitor', 'max_competitor', 
                         'avg_competitor', 'suggested_price', 'manual_price']
        
        for col in price_columns:
            formatted_df[col] = formatted_df[col].apply(
                lambda x: f"€{x:.2f}" if pd.notnull(x) else ""
            )
        
        # Display the dataframe
        st.dataframe(
            formatted_df,
            column_config={
                "product_id": st.column_config.NumberColumn("ID", width="small"),
                "product_name": "Product Name",
                "current_price": "Current Price",
                "min_competitor": "Min Competitor",
                "max_competitor": "Max Competitor", 
                "avg_competitor": "Avg Competitor",
                "suggested_price": "AI Suggested",
                "manual_price": "Manual Price",
                "is_applied": st.column_config.TextColumn("Applied", width="small")
            },
            use_container_width=True,
            hide_index=True
        )
        
        # Select product to manage
        st.subheader("Manage Product Prices")
        
        # Create product options
        product_options = [f"{row['product_id']}: {row['product_name']}" 
                           for _, row in latest_prices_df.iterrows()]
        
        selected_product = st.selectbox("Select a product", product_options)
        
        if selected_product:
            # Extract product ID from selection
            product_id = int(selected_product.split(":")[0])
            
            # Get the selected product data
            product_data = latest_prices_df[latest_prices_df['product_id'] == product_id].iloc[0]
            product_name = product_data['product_name']
            
            # Current price and competitor info
            current_price = product_data['current_price']
            competitor_prices = product_data['competitor_prices']
            
            # Display current pricing information
            pricing_col1, pricing_col2 = st.columns(2)
            
            with pricing_col1:
                st.metric("Current Price", f"€{current_price:.2f}" if pd.notnull(current_price) else "N/A")
                
                if competitor_prices:
                    min_price = min(competitor_prices.values())
                    max_price = max(competitor_prices.values())
                    avg_price = sum(competitor_prices.values()) / len(competitor_prices)
                    
                    st.metric("Min Competitor", f"€{min_price:.2f}")
                    st.metric("Max Competitor", f"€{max_price:.2f}")
                    st.metric("Avg Competitor", f"€{avg_price:.2f}")
            
            with pricing_col2:
                # Show existing suggestion if available
                has_suggestion = pd.notnull(product_data.get('suggestion_id'))
                
                if has_suggestion:
                    suggestion_id = int(product_data['suggestion_id'])
                    suggested_price = product_data['suggested_price']
                    manual_price = product_data['manual_price']
                    is_applied = product_data['is_applied']
                    notes = product_data['suggestion_notes']
                    
                    # Display current suggestion
                    if pd.notnull(suggested_price):
                        st.metric("AI Suggested Price", f"€{suggested_price:.2f}")
                    
                    if pd.notnull(manual_price):
                        st.metric("Manual Price", f"€{manual_price:.2f}")
                    
                    # Display applied status
                    status = "Applied" if is_applied else "Not Applied"
                    st.info(f"Status: **{status}**")
                    
                    if notes:
                        st.text_area("Notes", notes, disabled=True)
                else:
                    st.info("No price suggestions yet for this product")
            
            # Price management actions
            st.subheader("Price Actions")
            
            price_tabs = st.tabs(["AI Suggestion", "Manual Price", "Apply Price"])
            
            # Tab 1: Get AI Suggestion
            with price_tabs[0]:
                st.markdown("Get AI-powered price recommendation based on competitor data")
                
                ai_col1, ai_col2 = st.columns([1, 1])
                
                with ai_col1:
                    if st.button("Generate AI Price Suggestion", type="primary"):
                        with st.spinner("Generating AI suggestion..."):
                            # Get AI price analysis
                            analysis = get_price_analysis(product_id)
                            
                            if not analysis or 'suggested_price' not in analysis:
                                st.error("Failed to generate AI price suggestion. Try again later.")
                            else:
                                # Create new suggestion in database
                                suggested_price = analysis['suggested_price']
                                rationale = analysis.get('rationale', '')
                                
                                suggestion_id = add_suggested_price(
                                    product_id=product_id,
                                    suggested_price=suggested_price,
                                    source='ai',
                                    notes=rationale
                                )
                                
                                if suggestion_id:
                                    st.success(f"AI suggested price: €{suggested_price:.2f}")
                                    st.info(f"Rationale: {rationale}")
                                    st.rerun()
                                else:
                                    st.error("Failed to save AI suggestion")
            
            # Tab 2: Set manual price
            with price_tabs[1]:
                st.markdown("Set your own price for this product")
                
                with st.form("manual_price_form"):
                    manual_price = st.number_input(
                        "Manual Price (€)",
                        min_value=0.01,
                        value=float(current_price) if pd.notnull(current_price) else 1.0,
                        step=0.01,
                        format="%.2f"
                    )
                    
                    notes = st.text_area("Notes", placeholder="Reason for price change...")
                    
                    if st.form_submit_button("Save Manual Price"):
                        if has_suggestion:
                            # Update existing suggestion with manual price
                            success = update_suggested_price(
                                suggestion_id=suggestion_id,
                                manual_price=manual_price,
                                notes=notes if notes else None
                            )
                        else:
                            # Create new suggestion with manual price
                            suggestion_id = add_suggested_price(
                                product_id=product_id,
                                suggested_price=None,
                                manual_price=manual_price,
                                source='manual',
                                notes=notes
                            )
                            success = suggestion_id is not None
                        
                        if success:
                            st.success(f"Manual price (€{manual_price:.2f}) saved successfully")
                            st.rerun()
                        else:
                            st.error("Failed to save manual price")
            
            # Tab 3: Apply price (mark as used)
            with price_tabs[2]:
                st.markdown("Mark a price suggestion as applied (used in your system)")
                
                if has_suggestion:
                    price_to_apply = None
                    
                    if pd.notnull(product_data.get('manual_price')):
                        price_to_apply = product_data['manual_price']
                        price_type = "manual"
                    elif pd.notnull(product_data.get('suggested_price')):
                        price_to_apply = product_data['suggested_price']
                        price_type = "AI-suggested"
                    
                    if price_to_apply is not None:
                        st.info(f"Price to apply: €{price_to_apply:.2f} ({price_type})")
                        
                        if product_data.get('is_applied'):
                            st.success("This price is already marked as applied")
                            
                            if st.button("Mark as Not Applied"):
                                success = update_suggested_price(
                                    suggestion_id=suggestion_id,
                                    is_applied=False
                                )
                                
                                if success:
                                    st.success("Price marked as not applied")
                                    st.rerun()
                                else:
                                    st.error("Failed to update application status")
                        else:
                            if st.button("Mark as Applied", type="primary"):
                                success = update_suggested_price(
                                    suggestion_id=suggestion_id,
                                    is_applied=True
                                )
                                
                                if success:
                                    st.success("Price marked as applied")
                                    st.rerun()
                                else:
                                    st.error("Failed to update application status")
                    else:
                        st.warning("No price available to apply. Set a manual price or get an AI suggestion first.")
                else:
                    st.warning("No price suggestion available to apply")
            
            # Delete suggestion button
            if has_suggestion:
                if st.button("Delete Current Suggestion", type="secondary"):
                    success = delete_suggested_price(suggestion_id)
                    
                    if success:
                        st.success("Price suggestion deleted")
                        st.rerun()
                    else:
                        st.error("Failed to delete price suggestion")
    
    with tab2:
        st.header("Export Price Data")
        st.markdown("""
        Export the current prices and suggestions for all products in either JSON or CSV format.
        This data can be used to update your pricing systems or for analysis.
        """)
        
        # Export format selection
        export_format = st.radio(
            "Select export format",
            ["JSON", "CSV"],
            horizontal=True,
            index=0
        )
        
        # Export options
        include_options = st.multiselect(
            "Data to include",
            ["Current Prices", "Suggested Prices", "Manual Prices", "Competitor Prices"],
            default=["Current Prices", "Suggested Prices", "Manual Prices"]
        )
        
        # Preview button
        if st.button("Preview Export Data"):
            with st.spinner("Generating preview..."):
                if export_format == "JSON":
                    export_data = export_prices_to_json()
                    
                    if export_data:
                        st.code(export_data, language="json")
                    else:
                        st.error("Failed to generate export data")
                else:
                    export_data = export_prices_to_csv()
                    
                    if export_data and not export_data.startswith("Error"):
                        st.code(export_data, language="text")
                    else:
                        st.error("Failed to generate export data")
        
        # Download button
        if st.button("Download Export File", type="primary"):
            try:
                if export_format == "JSON":
                    data = export_prices_to_json()
                    file_name = f"product_prices_{datetime.now().strftime('%Y%m%d')}.json"
                    mime_type = "application/json"
                else:
                    data = export_prices_to_csv()
                    file_name = f"product_prices_{datetime.now().strftime('%Y%m%d')}.csv"
                    mime_type = "text/csv"
                
                # Create download link
                if data:
                    b64 = base64.b64encode(data.encode()).decode()
                    href = f'<a href="data:{mime_type};base64,{b64}" download="{file_name}" target="_blank">Download {file_name}</a>'
                    st.markdown(href, unsafe_allow_html=True)
                    st.success(f"Export file {file_name} ready for download!")
                else:
                    st.error("Failed to generate export data")
            except Exception as e:
                st.error(f"Error generating export: {str(e)}")

if __name__ == "__main__":
    app()