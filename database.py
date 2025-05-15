import sqlite3
import pandas as pd
import json
import datetime
import os
from io import StringIO
import csv

# Database configuration
DATABASE_FILE = "price_monitor.db"

def get_connection():
    """Get a database connection"""
    conn = sqlite3.connect(DATABASE_FILE)
    conn.row_factory = sqlite3.Row  # This enables column access by name
    return conn

def init_db():
    """Initialize database with required tables if they don't exist"""
    conn = get_connection()
    cursor = conn.cursor()
    
    # Create products table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS products (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        our_url TEXT NOT NULL,
        our_name_selector TEXT,
        our_price_selector TEXT NOT NULL,
        competitor_urls TEXT,
        competitor_selectors TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        last_checked TIMESTAMP,
        min_price_threshold REAL,
        max_price_threshold REAL
    )
    ''')
    
    # Create price_history table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS price_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        product_id INTEGER NOT NULL,
        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        our_price REAL,
        competitor_prices TEXT,
        FOREIGN KEY (product_id) REFERENCES products (id)
    )
    ''')
    
    # Create settings table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS settings (
        key TEXT PRIMARY KEY,
        value TEXT,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    ''')
    
    # Create suggested_prices table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS suggested_prices (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        product_id INTEGER NOT NULL,
        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        suggested_price REAL,
        manual_price REAL,
        is_applied BOOLEAN DEFAULT 0,
        source TEXT DEFAULT 'ai',
        notes TEXT,
        FOREIGN KEY (product_id) REFERENCES products (id)
    )
    ''')
    
    # Initialize default settings if not exists
    cursor.execute("INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)", 
                  ("scraping_interval", "720"))  # Default to 12 hours (720 minutes)
    cursor.execute("INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)", 
                  ("last_scrape", ""))
    cursor.execute("INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)",
                  ("global_min_price_threshold", "-5.0"))  # Default to -5.0€
    cursor.execute("INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)",
                  ("global_max_price_threshold", "15.0"))  # Default to +15.0€
    cursor.execute("INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)",
                  ("analysis_period", "7"))  # Default to 7 days
    
    conn.commit()
    conn.close()

def add_product(name, our_url, our_name_selector, our_price_selector, competitor_urls=None, competitor_selectors=None, 
              min_price_threshold=None, max_price_threshold=None):
    """Add a new product to the database"""
    conn = get_connection()
    cursor = conn.cursor()
    
    # Convert lists to JSON strings
    competitor_urls_json = json.dumps(competitor_urls) if competitor_urls else None
    competitor_selectors_json = json.dumps(competitor_selectors) if competitor_selectors else None
    
    cursor.execute('''
    INSERT INTO products 
    (name, our_url, our_name_selector, our_price_selector, competitor_urls, competitor_selectors, 
     min_price_threshold, max_price_threshold)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    ''', (name, our_url, our_name_selector, our_price_selector, competitor_urls_json, 
          competitor_selectors_json, min_price_threshold, max_price_threshold))
    
    product_id = cursor.lastrowid
    conn.commit()
    conn.close()
    
    return product_id

def update_product(product_id, name=None, our_url=None, our_name_selector=None, our_price_selector=None, 
                  competitor_urls=None, competitor_selectors=None, min_price_threshold=None, max_price_threshold=None):
    """Update an existing product"""
    conn = get_connection()
    cursor = conn.cursor()
    
    # Get current product data
    cursor.execute("SELECT * FROM products WHERE id = ?", (product_id,))
    product = cursor.fetchone()
    
    if not product:
        conn.close()
        return False
    
    # Prepare update data
    update_data = {}
    if name is not None:
        update_data['name'] = name
    if our_url is not None:
        update_data['our_url'] = our_url
    if our_name_selector is not None:
        update_data['our_name_selector'] = our_name_selector
    if our_price_selector is not None:
        update_data['our_price_selector'] = our_price_selector
    if competitor_urls is not None:
        update_data['competitor_urls'] = json.dumps(competitor_urls)
    if competitor_selectors is not None:
        update_data['competitor_selectors'] = json.dumps(competitor_selectors)
    if min_price_threshold is not None:
        update_data['min_price_threshold'] = min_price_threshold
    if max_price_threshold is not None:
        update_data['max_price_threshold'] = max_price_threshold
    
    if not update_data:
        conn.close()
        return False
    
    # Build and execute update query
    placeholders = ", ".join([f"{k} = ?" for k in update_data.keys()])
    values = list(update_data.values())
    values.append(product_id)
    
    cursor.execute(f"UPDATE products SET {placeholders} WHERE id = ?", values)
    conn.commit()
    conn.close()
    
    return True

def delete_product(product_id):
    """Delete a product and its price history"""
    conn = get_connection()
    cursor = conn.cursor()
    
    # Delete price history
    cursor.execute("DELETE FROM price_history WHERE product_id = ?", (product_id,))
    
    # Delete suggested prices
    cursor.execute("DELETE FROM suggested_prices WHERE product_id = ?", (product_id,))
    
    # Delete product
    cursor.execute("DELETE FROM products WHERE id = ?", (product_id,))
    
    conn.commit()
    conn.close()
    
    return True

def get_products():
    """Get all products as a DataFrame"""
    conn = get_connection()
    
    # Get products with additional columns for last price
    query = '''
    SELECT p.*, 
           ph.our_price as current_price,
           ph.competitor_prices as current_competitor_prices,
           ph.timestamp as last_updated
    FROM products p
    LEFT JOIN (
        SELECT ph1.*
        FROM price_history ph1
        LEFT JOIN price_history ph2
            ON ph1.product_id = ph2.product_id AND ph1.timestamp < ph2.timestamp
        WHERE ph2.timestamp IS NULL
    ) ph ON p.id = ph.product_id
    '''
    
    try:
        # Read the data
        df = pd.read_sql_query(query, conn)
        
        # Parse JSON columns
        for col in ['competitor_urls', 'competitor_selectors', 'current_competitor_prices']:
            if col in df.columns:
                df[col] = df[col].apply(lambda x: json.loads(x) if x and pd.notna(x) else None)
        
        conn.close()
        return df
    except Exception as e:
        print(f"Error getting products: {e}")
        conn.close()
        return pd.DataFrame()

def get_product(product_id):
    """Get a specific product by ID"""
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
    SELECT p.*, 
           ph.our_price as current_price,
           ph.competitor_prices as current_competitor_prices,
           ph.timestamp as last_updated
    FROM products p
    LEFT JOIN (
        SELECT ph1.*
        FROM price_history ph1
        LEFT JOIN price_history ph2
            ON ph1.product_id = ph2.product_id AND ph1.timestamp < ph2.timestamp
        WHERE ph2.timestamp IS NULL
    ) ph ON p.id = ph.product_id
    WHERE p.id = ?
    """, (product_id,))
    
    product = cursor.fetchone()
    conn.close()
    
    if not product:
        return None
    
    # Convert to dict and parse JSON
    product_dict = dict(product)
    for key in ['competitor_urls', 'competitor_selectors', 'current_competitor_prices']:
        if key in product_dict and product_dict[key]:
            try:
                product_dict[key] = json.loads(product_dict[key])
            except:
                product_dict[key] = {}
    
    return product_dict

def add_price_data(product_id, our_price, competitor_prices=None):
    """Add price data for a product"""
    conn = get_connection()
    cursor = conn.cursor()
    
    # Convert competitor prices to JSON
    competitor_prices_json = json.dumps(competitor_prices) if competitor_prices else None
    
    cursor.execute('''
    INSERT INTO price_history (product_id, our_price, competitor_prices, timestamp)
    VALUES (?, ?, ?, CURRENT_TIMESTAMP)
    ''', (product_id, our_price, competitor_prices_json))
    
    # Update the last_checked timestamp for the product
    cursor.execute('''
    UPDATE products
    SET last_checked = CURRENT_TIMESTAMP
    WHERE id = ?
    ''', (product_id,))
    
    conn.commit()
    conn.close()
    
    return True

def get_price_history(product_id, days=None):
    """Get price history for a product as a DataFrame"""
    conn = get_connection()
    
    # Build the query with optional time filter
    query = "SELECT * FROM price_history WHERE product_id = ?"
    params = [product_id]
    
    if days:
        cutoff_date = (datetime.datetime.now() - datetime.timedelta(days=days)).strftime('%Y-%m-%d %H:%M:%S')
        query += " AND timestamp >= ?"
        params.append(cutoff_date)
    
    query += " ORDER BY timestamp"
    
    try:
        df = pd.read_sql_query(query, conn, params=params)
        
        # Parse competitor_prices JSON
        if 'competitor_prices' in df.columns:
            df['competitor_prices'] = df['competitor_prices'].apply(lambda x: json.loads(x) if x and pd.notna(x) else {})
        
        conn.close()
        return df
    except Exception as e:
        print(f"Error getting price history: {e}")
        conn.close()
        return pd.DataFrame()

def update_settings(**kwargs):
    """Update application settings
    
    Args:
        **kwargs: Settings to update, where the key is the setting name and value is the setting value
    
    Returns:
        bool: True if successful
    """
    if not kwargs:
        return False
    
    conn = get_connection()
    cursor = conn.cursor()
    success = True
    
    try:
        for key, value in kwargs.items():
            # Convert values to strings for storage
            str_value = str(value) if value is not None else ""
            
            cursor.execute('''
            INSERT OR REPLACE INTO settings (key, value, updated_at)
            VALUES (?, ?, CURRENT_TIMESTAMP)
            ''', (key, str_value))
        
        conn.commit()
    except Exception as e:
        print(f"Error updating settings: {e}")
        success = False
    
    conn.close()
    return success

def get_settings():
    """Get application settings"""
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute("SELECT key, value FROM settings")
    settings_rows = cursor.fetchall()
    conn.close()
    
    settings = {}
    for row in settings_rows:
        settings[row['key']] = row['value']
    
    return settings

def update_last_scrape():
    """Update the last scrape timestamp"""
    return update_settings(last_scrape=datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'))

def get_suggested_prices(product_id=None):
    """
    Get suggested prices for one or all products
    
    Args:
        product_id (int, optional): Product ID to get suggestions for. If None, get all suggestions.
    
    Returns:
        DataFrame: Suggested prices data
    """
    conn = get_connection()
    
    query = """
    SELECT sp.*, p.name as product_name, 
           p.our_url, p.our_price_selector,
           ph.our_price as current_price
    FROM suggested_prices sp
    JOIN products p ON sp.product_id = p.id
    LEFT JOIN (
        SELECT product_id, MAX(timestamp) as max_timestamp
        FROM price_history
        GROUP BY product_id
    ) latest_ph ON p.id = latest_ph.product_id
    LEFT JOIN price_history ph ON latest_ph.product_id = ph.product_id AND latest_ph.max_timestamp = ph.timestamp
    """
    
    if product_id:
        query += " WHERE sp.product_id = ?"
        df = pd.read_sql_query(query, conn, params=[product_id])
    else:
        df = pd.read_sql_query(query, conn)
    
    conn.close()
    return df

def add_suggested_price(product_id, suggested_price=None, manual_price=None, source='ai', notes=None):
    """
    Add a new suggested price for a product
    
    Args:
        product_id (int): Product ID
        suggested_price (float, optional): AI suggested price
        manual_price (float, optional): Manual price override
        source (str, optional): Source of the suggestion ('ai' or 'manual')
        notes (str, optional): Notes about the suggestion
    
    Returns:
        int: ID of the new suggestion
    """
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
    INSERT INTO suggested_prices 
    (product_id, suggested_price, manual_price, source, notes, timestamp)
    VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
    ''', (product_id, suggested_price, manual_price, source, notes))
    
    suggestion_id = cursor.lastrowid
    conn.commit()
    conn.close()
    
    return suggestion_id

def update_suggested_price(suggestion_id, manual_price=None, is_applied=None, notes=None):
    """
    Update a suggested price - either apply it or set a manual price
    
    Args:
        suggestion_id (int): Suggestion ID
        manual_price (float, optional): Manual price override
        is_applied (bool, optional): Whether the suggestion has been applied
        notes (str, optional): Notes about the suggestion
    
    Returns:
        bool: True if successful
    """
    conn = get_connection()
    cursor = conn.cursor()
    
    update_parts = []
    values = []
    
    if manual_price is not None:
        update_parts.append("manual_price = ?")
        values.append(manual_price)
    
    if is_applied is not None:
        update_parts.append("is_applied = ?")
        values.append(1 if is_applied else 0)
    
    if notes is not None:
        update_parts.append("notes = ?")
        values.append(notes)
    
    if not update_parts:
        conn.close()
        return False
    
    query = f"UPDATE suggested_prices SET {', '.join(update_parts)} WHERE id = ?"
    values.append(suggestion_id)
    
    cursor.execute(query, values)
    conn.commit()
    conn.close()
    
    return True

def delete_suggested_price(suggestion_id):
    """
    Delete a suggested price
    
    Args:
        suggestion_id (int): Suggestion ID
    
    Returns:
        bool: True if successful
    """
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute("DELETE FROM suggested_prices WHERE id = ?", (suggestion_id,))
    conn.commit()
    conn.close()
    
    return True

def get_latest_prices():
    """
    Get the latest price for each product along with any active price suggestions
    
    Returns:
        DataFrame: Latest prices and suggestions
    """
    conn = get_connection()
    
    query = """
    SELECT p.id, p.name, p.our_url, 
           ph.our_price as current_price, 
           ph.competitor_prices,
           ph.timestamp as price_timestamp,
           sp.suggested_price,
           sp.manual_price,
           CASE 
               WHEN sp.manual_price IS NOT NULL THEN sp.manual_price 
               ELSE sp.suggested_price 
           END as final_suggested_price,
           sp.source as suggestion_source,
           sp.timestamp as suggestion_timestamp,
           sp.notes
    FROM products p
    LEFT JOIN (
        SELECT ph1.*
        FROM price_history ph1
        LEFT JOIN price_history ph2
            ON ph1.product_id = ph2.product_id AND ph1.timestamp < ph2.timestamp
        WHERE ph2.timestamp IS NULL
    ) ph ON p.id = ph.product_id
    LEFT JOIN (
        SELECT sp1.*
        FROM suggested_prices sp1
        LEFT JOIN suggested_prices sp2
            ON sp1.product_id = sp2.product_id AND sp1.timestamp < sp2.timestamp
        WHERE sp2.timestamp IS NULL AND sp1.is_applied = 0
    ) sp ON p.id = sp.product_id
    """
    
    df = pd.read_sql_query(query, conn)
    
    # Parse competitor_prices JSON
    if 'competitor_prices' in df.columns:
        df['competitor_prices'] = df['competitor_prices'].apply(lambda x: json.loads(x) if x and pd.notna(x) else {})
    
    conn.close()
    return df

def export_prices_to_json(output_file=None):
    """
    Export all products with their current and suggested prices to JSON
    
    Args:
        output_file (str, optional): Path to output file. If None, return the JSON string.
    
    Returns:
        str: JSON string if output_file is None, otherwise None
    """
    df = get_latest_prices()
    
    if df.empty:
        result = "[]"
    else:
        # Create a clean structure for export
        export_data = []
        
        for _, row in df.iterrows():
            product_data = {
                "id": int(row['id']),
                "name": row['name'],
                "current_price": float(row['current_price']) if pd.notna(row['current_price']) else None,
                "suggested_price": float(row['final_suggested_price']) if pd.notna(row['final_suggested_price']) else None,
                "competitor_prices": row['competitor_prices'] if pd.notna(row['competitor_prices']) else {},
                "last_updated": row['price_timestamp'] if pd.notna(row['price_timestamp']) else None
            }
            export_data.append(product_data)
        
        result = json.dumps(export_data, indent=2)
    
    if output_file:
        with open(output_file, 'w') as f:
            f.write(result)
        return None
    else:
        return result

def export_prices_to_csv(output_file=None):
    """
    Export all products with their current and suggested prices to CSV
    
    Args:
        output_file (str, optional): Path to output file. If None, return the CSV string.
    
    Returns:
        str: CSV string if output_file is None, otherwise None
    """
    df = get_latest_prices()
    
    if df.empty:
        result = ""
    else:
        # Create a clean DataFrame for export
        export_df = pd.DataFrame({
            "id": df['id'],
            "name": df['name'],
            "current_price": df['current_price'],
            "suggested_price": df['final_suggested_price']
        })
        
        # Add competitor prices as separate columns
        competitors = set()
        for _, row in df.iterrows():
            if pd.notna(row['competitor_prices']) and row['competitor_prices']:
                competitors.update(row['competitor_prices'].keys())
        
        for competitor in competitors:
            export_df[f"{competitor}_price"] = df.apply(
                lambda row: row['competitor_prices'].get(competitor) 
                if pd.notna(row['competitor_prices']) and row['competitor_prices'] else None, 
                axis=1
            )
        
        # Write to CSV string
        output = StringIO()
        export_df.to_csv(output, index=False)
        result = output.getvalue()
    
    if output_file:
        with open(output_file, 'w', newline='') as f:
            f.write(result)
        return None
    else:
        return result

def upgrade_settings_table():
    """Upgrade the settings table schema to support more configuration options"""
    conn = get_connection()
    cursor = conn.cursor()
    
    # Check if new settings exist, if not add them
    cursor.execute("SELECT key FROM settings WHERE key = ?", ("global_min_price_threshold",))
    if not cursor.fetchone():
        cursor.execute("INSERT INTO settings (key, value) VALUES (?, ?)", 
                      ("global_min_price_threshold", "-5.0"))  # Default to -5.0€
    
    cursor.execute("SELECT key FROM settings WHERE key = ?", ("global_max_price_threshold",))
    if not cursor.fetchone():
        cursor.execute("INSERT INTO settings (key, value) VALUES (?, ?)", 
                      ("global_max_price_threshold", "15.0"))  # Default to +15.0€
    
    cursor.execute("SELECT key FROM settings WHERE key = ?", ("analysis_period",))
    if not cursor.fetchone():
        cursor.execute("INSERT INTO settings (key, value) VALUES (?, ?)", 
                      ("analysis_period", "7"))  # Default to 7 days
    
    conn.commit()
    conn.close()
    print("Settings table upgraded successfully!")
    return True

def upgrade_products_table():
    """Upgrade products table to add price threshold columns"""
    conn = get_connection()
    cursor = conn.cursor()
    
    # Check if min_price_threshold column exists
    cursor.execute("PRAGMA table_info(products)")
    columns = [col[1] for col in cursor.fetchall()]
    
    # Add min_price_threshold column if it doesn't exist
    if "min_price_threshold" not in columns:
        cursor.execute("ALTER TABLE products ADD COLUMN min_price_threshold REAL")
    
    # Add max_price_threshold column if it doesn't exist
    if "max_price_threshold" not in columns:
        cursor.execute("ALTER TABLE products ADD COLUMN max_price_threshold REAL")
    
    conn.commit()
    conn.close()
    return True