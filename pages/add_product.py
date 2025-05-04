import streamlit as st
import pandas as pd
from utils.database import add_product, get_products, update_product, delete_product
from utils.scraper import test_scrape

def app():
    st.title("Add & Manage Products")
    
    # Create tabs for Add and Manage
    tab1, tab2 = st.tabs(["Add New Product", "Manage Products"])
    
    with tab1:
        st.header("Add a New Product to Monitor")
        
        with st.form("add_product_form"):
            # Basic product information
            product_name = st.text_input("Product Name")
            
            # Our product information
            st.subheader("Our Product")
            our_url = st.text_input("Our Product URL")
            our_name_selector = st.text_input("Name Element Selector (CSS)", placeholder="e.g., .product-title")
            our_price_selector = st.text_input("Price Element Selector (CSS)", placeholder="e.g., .product-price")
            
            # Test button for our product
            st.markdown("You can test the selectors before adding the product:")
            test_our_col1, test_our_col2 = st.columns([1, 3])
            with test_our_col1:
                test_our = st.button("Test Our Selectors")
            with test_our_col2:
                if test_our and our_url and our_price_selector:
                    result = test_scrape(our_url, our_price_selector, our_name_selector)
                    if 'error' in result:
                        st.error(f"Error: {result['error']}")
                    else:
                        name = result.get('name', 'N/A')
                        price = result.get('price', 'N/A')
                        st.success(f"Name: {name}, Price: {price}")
            
            # Competitor section
            st.subheader("Competitor Products (Optional)")
            st.markdown("Add up to 5 competitor products to compare")
            
            competitor_urls = []
            competitor_selectors = {}
            
            # Create expandable sections for each competitor
            for i in range(5):
                with st.expander(f"Competitor {i+1}", expanded=i==0):
                    comp_url = st.text_input(f"Competitor URL #{i+1}", key=f"comp_url_{i}")
                    comp_name_selector = st.text_input(f"Name Element Selector #{i+1} (CSS)", 
                                                    placeholder="e.g., .product-title", 
                                                    key=f"comp_name_{i}")
                    comp_price_selector = st.text_input(f"Price Element Selector #{i+1} (CSS)", 
                                                     placeholder="e.g., .product-price", 
                                                     key=f"comp_price_{i}")
                    
                    # Test button for competitor
                    test_comp_col1, test_comp_col2 = st.columns([1, 3])
                    with test_comp_col1:
                        test_comp = st.button(f"Test Competitor {i+1}", key=f"test_comp_{i}")
                    with test_comp_col2:
                        if test_comp and comp_url and comp_price_selector:
                            result = test_scrape(comp_url, comp_price_selector, comp_name_selector)
                            if 'error' in result:
                                st.error(f"Error: {result['error']}")
                            else:
                                name = result.get('name', 'N/A')
                                price = result.get('price', 'N/A')
                                st.success(f"Name: {name}, Price: {price}")
                    
                    if comp_url:
                        competitor_urls.append(comp_url)
                        competitor_selectors[f"name_{i}"] = comp_name_selector
                        competitor_selectors[f"price_{i}"] = comp_price_selector
            
            # Submit button
            submit_button = st.form_submit_button("Add Product")
            
            if submit_button:
                if not product_name:
                    st.error("Product name is required")
                elif not our_url:
                    st.error("Our product URL is required")
                elif not our_price_selector:
                    st.error("Our price selector is required")
                else:
                    product_id = add_product(
                        product_name, 
                        our_url, 
                        our_name_selector, 
                        our_price_selector, 
                        competitor_urls, 
                        competitor_selectors
                    )
                    
                    if product_id:
                        st.success(f"Product '{product_name}' added successfully!")
                        st.balloons()
                    else:
                        st.error("Failed to add product. Please try again.")
    
    with tab2:
        st.header("Manage Existing Products")
        
        # Get all products
        products_df = get_products()
        
        if products_df.empty:
            st.info("No products have been added yet. Add your first product in the 'Add New Product' tab.")
        else:
            # Display products in a table
            st.dataframe(
                products_df[['id', 'name', 'our_url', 'last_checked']],
                column_config={
                    "id": "ID",
                    "name": "Product Name",
                    "our_url": "Our URL",
                    "last_checked": "Last Updated"
                },
                use_container_width=True,
                hide_index=True
            )
            
            # Product editing section
            st.subheader("Edit/Delete Product")
            
            # Select product to edit
            product_ids = products_df['id'].tolist()
            product_names = products_df['name'].tolist()
            product_options = [f"{id}: {name}" for id, name in zip(product_ids, product_names)]
            
            if product_options:
                selected_product = st.selectbox("Select Product to Edit", product_options)
                
                if selected_product:
                    # Extract product ID from selection
                    selected_id = int(selected_product.split(":")[0])
                    
                    # Get product details
                    product_row = products_df[products_df['id'] == selected_id].iloc[0]
                    
                    # Create edit form
                    with st.form("edit_product_form"):
                        st.write(f"Editing: {product_row['name']}")
                        
                        # Basic product information
                        edit_name = st.text_input("Product Name", value=product_row['name'])
                        
                        # Our product information
                        st.subheader("Our Product")
                        edit_our_url = st.text_input("Our Product URL", value=product_row['our_url'])
                        edit_our_name_selector = st.text_input("Name Element Selector (CSS)", 
                                                           value=product_row['our_name_selector'])
                        edit_our_price_selector = st.text_input("Price Element Selector (CSS)", 
                                                            value=product_row['our_price_selector'])
                        
                        # Competitor section
                        st.subheader("Competitor Products")
                        
                        # Parse competitor URLs and selectors
                        competitor_urls = []
                        if product_row['competitor_urls'] and not pd.isna(product_row['competitor_urls']):
                            competitor_urls = product_row['competitor_urls'].split(',')
                        
                        competitor_selectors = {}
                        if product_row['competitor_selectors'] and not pd.isna(product_row['competitor_selectors']):
                            competitor_selectors = eval(product_row['competitor_selectors'])
                        
                        edit_competitor_urls = []
                        edit_competitor_selectors = {}
                        
                        # Create fields for each competitor
                        for i in range(5):
                            with st.expander(f"Competitor {i+1}", expanded=i < len(competitor_urls)):
                                comp_url_value = competitor_urls[i] if i < len(competitor_urls) else ""
                                comp_name_selector_value = competitor_selectors.get(f"name_{i}", "")
                                comp_price_selector_value = competitor_selectors.get(f"price_{i}", "")
                                
                                edit_comp_url = st.text_input(f"Competitor URL #{i+1}", 
                                                          value=comp_url_value, 
                                                          key=f"edit_comp_url_{i}")
                                edit_comp_name_selector = st.text_input(f"Name Element Selector #{i+1} (CSS)", 
                                                                    value=comp_name_selector_value, 
                                                                    key=f"edit_comp_name_{i}")
                                edit_comp_price_selector = st.text_input(f"Price Element Selector #{i+1} (CSS)", 
                                                                     value=comp_price_selector_value, 
                                                                     key=f"edit_comp_price_{i}")
                                
                                if edit_comp_url:
                                    edit_competitor_urls.append(edit_comp_url)
                                    edit_competitor_selectors[f"name_{i}"] = edit_comp_name_selector
                                    edit_competitor_selectors[f"price_{i}"] = edit_comp_price_selector
                        
                        # Submit buttons
                        col1, col2 = st.columns(2)
                        with col1:
                            update_button = st.form_submit_button("Update Product")
                        with col2:
                            delete_button = st.form_submit_button("Delete Product", type="primary")
                        
                        if update_button:
                            if not edit_name:
                                st.error("Product name is required")
                            elif not edit_our_url:
                                st.error("Our product URL is required")
                            elif not edit_our_price_selector:
                                st.error("Our price selector is required")
                            else:
                                success = update_product(
                                    selected_id,
                                    edit_name, 
                                    edit_our_url, 
                                    edit_our_name_selector, 
                                    edit_our_price_selector, 
                                    edit_competitor_urls, 
                                    edit_competitor_selectors
                                )
                                
                                if success:
                                    st.success(f"Product '{edit_name}' updated successfully!")
                                    st.rerun()
                                else:
                                    st.error("Failed to update product. Please try again.")
                        
                        if delete_button:
                            success = delete_product(selected_id)
                            
                            if success:
                                st.success(f"Product '{product_row['name']}' deleted successfully!")
                                st.rerun()
                            else:
                                st.error("Failed to delete product. Please try again.")

# Run the app
app()
