import sqlite3
import pandas as pd
import json
import os
from datetime import datetime

# Database file path
DB_PATH = "price_monitor.db"

def init_db():
    """Initialize database with required tables if they don't exist"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Create products table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS products (
        id INTEGER PRIMARY KEY,
        name TEXT NOT NULL,
        our_url TEXT NOT NULL,
        our_name_selector TEXT NOT NULL,
        our_price_selector TEXT NOT NULL,
        competitor_urls TEXT,
        competitor_selectors TEXT,
        last_checked TIMESTAMP,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    ''')
    
    # Create price_history table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS price_history (
        id INTEGER PRIMARY KEY,
        product_id INTEGER,
        timestamp TIMESTAMP NOT NULL,
        our_price REAL,
        competitor_prices TEXT,
        FOREIGN KEY (product_id) REFERENCES products (id)
    )
    ''')
    
    # Create settings table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS settings (
        id INTEGER PRIMARY KEY,
        scrape_interval INTEGER DEFAULT 3600,
        last_scrape TIMESTAMP,
        analysis_period INTEGER DEFAULT 7
    )
    ''')
    
    # Create suggested prices table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS suggested_prices (
        id INTEGER PRIMARY KEY,
        product_id INTEGER,
        suggested_price REAL,
        manual_price REAL,
        is_applied BOOLEAN DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        applied_at TIMESTAMP,
        source TEXT DEFAULT 'ai',
        notes TEXT,
        FOREIGN KEY (product_id) REFERENCES products (id)
    )
    ''')
    
    # Insert default settings if none exist
    cursor.execute("SELECT COUNT(*) FROM settings")
    if cursor.fetchone()[0] == 0:
        cursor.execute('''
        INSERT INTO settings (scrape_interval, analysis_period) 
        VALUES (3600, 7)
        ''')
    
    conn.commit()
    conn.close()

def get_connection():
    """Get a database connection"""
    return sqlite3.connect(DB_PATH)

def add_product(name, our_url, our_name_selector, our_price_selector, competitor_urls=None, competitor_selectors=None):
    """Add a new product to the database"""
    conn = get_connection()
    cursor = conn.cursor()
    
    competitor_urls_str = ",".join(competitor_urls) if competitor_urls else ""
    competitor_selectors_str = json.dumps(competitor_selectors) if competitor_selectors else "{}"
    
    cursor.execute('''
    INSERT INTO products (
        name,
        our_url,
        our_name_selector,
        our_price_selector,
        competitor_urls,
        competitor_selectors,
        created_at
    ) VALUES (?, ?, ?, ?, ?, ?, ?)
    ''', (name, our_url, our_name_selector, our_price_selector, competitor_urls_str, 
          competitor_selectors_str, datetime.now()))
    
    product_id = cursor.lastrowid
    conn.commit()
    conn.close()
    
    return product_id

def update_product(product_id, name=None, our_url=None, our_name_selector=None, our_price_selector=None, 
                  competitor_urls=None, competitor_selectors=None):
    """Update an existing product"""
    conn = get_connection()
    cursor = conn.cursor()
    
    # Get current product data
    cursor.execute("SELECT * FROM products WHERE id = ?", (product_id,))
    product = cursor.fetchone()
    
    if not product:
        conn.close()
        return False
    
    # Update only the provided fields
    update_fields = []
    update_values = []
    
    if name is not None:
        update_fields.append("name = ?")
        update_values.append(name)
    
    if our_url is not None:
        update_fields.append("our_url = ?")
        update_values.append(our_url)
    
    if our_name_selector is not None:
        update_fields.append("our_name_selector = ?")
        update_values.append(our_name_selector)
    
    if our_price_selector is not None:
        update_fields.append("our_price_selector = ?")
        update_values.append(our_price_selector)
    
    if competitor_urls is not None:
        competitor_urls_str = ",".join(competitor_urls) if competitor_urls else ""
        update_fields.append("competitor_urls = ?")
        update_values.append(competitor_urls_str)
    
    if competitor_selectors is not None:
        competitor_selectors_str = json.dumps(competitor_selectors) if competitor_selectors else "{}"
        update_fields.append("competitor_selectors = ?")
        update_values.append(competitor_selectors_str)
    
    if update_fields:
        query = f"UPDATE products SET {', '.join(update_fields)} WHERE id = ?"
        update_values.append(product_id)
        
        cursor.execute(query, update_values)
        conn.commit()
    
    conn.close()
    return True

def delete_product(product_id):
    """Delete a product and its price history"""
    conn = get_connection()
    cursor = conn.cursor()
    
    # Delete price history for the product
    cursor.execute("DELETE FROM price_history WHERE product_id = ?", (product_id,))
    
    # Delete the product
    cursor.execute("DELETE FROM products WHERE id = ?", (product_id,))
    
    conn.commit()
    conn.close()
    
    return True

def get_products():
    """Get all products as a DataFrame"""
    conn = get_connection()
    
    query = "SELECT * FROM products"
    df = pd.read_sql_query(query, conn)
    
    conn.close()
    
    return df

def get_product(product_id):
    """Get a specific product by ID"""
    conn = get_connection()
    
    query = "SELECT * FROM products WHERE id = ?"
    df = pd.read_sql_query(query, conn, params=(product_id,))
    
    conn.close()
    
    if df.empty:
        return None
    
    # Parse competitor URLs and selectors
    if 'competitor_urls' in df.columns and not pd.isna(df.iloc[0]['competitor_urls']):
        df.at[0, 'competitor_urls'] = df.iloc[0]['competitor_urls'].split(',')
    else:
        df.at[0, 'competitor_urls'] = []
    
    if 'competitor_selectors' in df.columns and not pd.isna(df.iloc[0]['competitor_selectors']):
        df.at[0, 'competitor_selectors'] = json.loads(df.iloc[0]['competitor_selectors'])
    else:
        df.at[0, 'competitor_selectors'] = {}
    
    return df.iloc[0].to_dict()

def add_price_data(product_id, our_price, competitor_prices=None):
    """Add price data for a product"""
    conn = get_connection()
    cursor = conn.cursor()
    
    timestamp = datetime.now()
    competitor_prices_str = json.dumps(competitor_prices) if competitor_prices else "{}"
    
    cursor.execute('''
    INSERT INTO price_history (
        product_id,
        timestamp,
        our_price,
        competitor_prices
    ) VALUES (?, ?, ?, ?)
    ''', (product_id, timestamp, our_price, competitor_prices_str))
    
    # Update last_checked time in products table
    cursor.execute('''
    UPDATE products SET last_checked = ? WHERE id = ?
    ''', (timestamp, product_id))
    
    conn.commit()
    conn.close()
    
    return True

def get_price_history(product_id, days=None):
    """Get price history for a product as a DataFrame"""
    conn = get_connection()
    
    query = "SELECT * FROM price_history WHERE product_id = ?"
    params = [product_id]
    
    if days:
        query += " AND timestamp >= datetime('now', '-' || ? || ' days')"
        params.append(str(days))
    
    query += " ORDER BY timestamp"
    
    df = pd.read_sql_query(query, conn, params=params)
    
    conn.close()
    
    if not df.empty:
        # Parse competitor prices from JSON
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        df['competitor_prices'] = df['competitor_prices'].apply(
            lambda x: json.loads(x) if x and x != "{}" else {})
    
    return df

def update_settings(**kwargs):
    """Update application settings
    
    Args:
        **kwargs: Settings to update, where the key is the setting name and value is the setting value
    
    Returns:
        bool: True if successful
    """
    conn = get_connection()
    cursor = conn.cursor()
    
    try:
        # Check if we're using the new settings table format
        cursor.execute("PRAGMA table_info(settings)")
        columns = [row[1] for row in cursor.fetchall()]
        
        if 'name' in columns:
            # New format (name-value pairs)
            for setting_name, setting_value in kwargs.items():
                cursor.execute(
                    "INSERT OR REPLACE INTO settings (name, value) VALUES (?, ?)",
                    (setting_name, str(setting_value))
                )
        else:
            # Old format (columns)
            update_fields = []
            update_values = []
            
            if 'scrape_interval' in kwargs:
                update_fields.append("scrape_interval = ?")
                update_values.append(kwargs['scrape_interval'])
            
            if 'analysis_period' in kwargs:
                update_fields.append("analysis_period = ?")
                update_values.append(kwargs['analysis_period'])
            
            if update_fields:
                query = f"UPDATE settings SET {', '.join(update_fields)} WHERE id = 1"
                cursor.execute(query, update_values)
        
        conn.commit()
        return True
    except Exception as e:
        print(f"Error updating settings: {e}")
        return False
    finally:
        conn.close()

def get_settings():
    """Get application settings"""
    conn = get_connection()
    cursor = conn.cursor()
    
    try:
        # Check if we're using the new settings table format
        cursor.execute("PRAGMA table_info(settings)")
        columns = [row[1] for row in cursor.fetchall()]
        
        if 'name' in columns:
            # New format (name-value pairs)
            cursor.execute("SELECT name, value FROM settings")
            settings_rows = cursor.fetchall()
            
            settings = {}
            for name, value in settings_rows:
                # Try to convert numeric values
                try:
                    if value.isdigit():
                        settings[name] = int(value)
                    elif value.replace('.', '', 1).isdigit():
                        settings[name] = float(value)
                    elif value.lower() in ('true', 'false'):
                        settings[name] = value.lower() == 'true'
                    else:
                        settings[name] = value
                except (ValueError, AttributeError):
                    settings[name] = value
            
            # Ensure required settings have defaults
            if 'scrape_interval' not in settings:
                settings['scrape_interval'] = 3600
            if 'analysis_period' not in settings:
                settings['analysis_period'] = 7
                
            return settings
        else:
            # Old format (columns)
            cursor.execute("SELECT * FROM settings WHERE id = 1")
            settings = cursor.fetchone()
            
            if settings:
                return {
                    "scrape_interval": settings[1],
                    "last_scrape": settings[2],
                    "analysis_period": settings[3]
                }
            else:
                return {
                    "scrape_interval": 3600,
                    "last_scrape": None,
                    "analysis_period": 7
                }
    except Exception as e:
        print(f"Error getting settings: {e}")
        return {
            "scrape_interval": 3600,
            "last_scrape": None,
            "analysis_period": 7
        }
    finally:
        conn.close()

def update_last_scrape():
    """Update the last scrape timestamp"""
    conn = get_connection()
    cursor = conn.cursor()
    
    try:
        # Check if we're using the new settings table format
        cursor.execute("PRAGMA table_info(settings)")
        columns = [row[1] for row in cursor.fetchall()]
        
        now = datetime.now()
        
        if 'name' in columns:
            # New format (name-value pairs)
            cursor.execute(
                "INSERT OR REPLACE INTO settings (name, value) VALUES (?, ?)",
                ('last_scrape', now.isoformat())
            )
        else:
            # Old format (columns)
            cursor.execute('''
            UPDATE settings SET last_scrape = ? WHERE id = 1
            ''', (now,))
        
        conn.commit()
        return True
    except Exception as e:
        print(f"Error updating last scrape time: {e}")
        return False
    finally:
        conn.close()

def get_suggested_prices(product_id=None):
    """
    Get suggested prices for one or all products
    
    Args:
        product_id (int, optional): Product ID to get suggestions for. If None, get all suggestions.
    
    Returns:
        DataFrame: Suggested prices data
    """
    conn = get_connection()
    
    if product_id:
        query = """
        SELECT sp.*, p.name as product_name 
        FROM suggested_prices sp
        JOIN products p ON sp.product_id = p.id
        WHERE sp.product_id = ?
        ORDER BY sp.created_at DESC
        """
        df = pd.read_sql_query(query, conn, params=(product_id,))
    else:
        query = """
        SELECT sp.*, p.name as product_name 
        FROM suggested_prices sp
        JOIN products p ON sp.product_id = p.id
        ORDER BY sp.created_at DESC
        """
        df = pd.read_sql_query(query, conn)
    
    conn.close()
    
    if not df.empty:
        # Convert timestamp columns
        for col in ['created_at', 'applied_at']:
            if col in df.columns:
                df[col] = pd.to_datetime(df[col])
    
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
    
    try:
        cursor.execute('''
        INSERT INTO suggested_prices (
            product_id,
            suggested_price,
            manual_price,
            source,
            notes,
            created_at
        ) VALUES (?, ?, ?, ?, ?, ?)
        ''', (product_id, suggested_price, manual_price, source, notes, datetime.now()))
        
        suggestion_id = cursor.lastrowid
        conn.commit()
        return suggestion_id
    except Exception as e:
        print(f"Error adding suggested price: {e}")
        return None
    finally:
        conn.close()

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
    
    try:
        update_fields = []
        update_values = []
        
        if manual_price is not None:
            update_fields.append("manual_price = ?")
            update_values.append(manual_price)
        
        if is_applied is not None:
            update_fields.append("is_applied = ?")
            update_values.append(1 if is_applied else 0)
            
            if is_applied:
                update_fields.append("applied_at = ?")
                update_values.append(datetime.now())
        
        if notes is not None:
            update_fields.append("notes = ?")
            update_values.append(notes)
        
        if update_fields:
            query = f"UPDATE suggested_prices SET {', '.join(update_fields)} WHERE id = ?"
            update_values.append(suggestion_id)
            
            cursor.execute(query, update_values)
            conn.commit()
            return True
        
        return False
    except Exception as e:
        print(f"Error updating suggested price: {e}")
        return False
    finally:
        conn.close()

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
    
    try:
        cursor.execute("DELETE FROM suggested_prices WHERE id = ?", (suggestion_id,))
        conn.commit()
        return True
    except Exception as e:
        print(f"Error deleting suggested price: {e}")
        return False
    finally:
        conn.close()

def get_latest_prices():
    """
    Get the latest price for each product along with any active price suggestions
    
    Returns:
        DataFrame: Latest prices and suggestions
    """
    conn = get_connection()
    
    try:
        # This query gets the latest price history and latest suggestion for each product
        query = """
        WITH LatestPrices AS (
            SELECT ph.product_id, 
                   ph.our_price, 
                   ph.competitor_prices,
                   ph.timestamp,
                   ROW_NUMBER() OVER (PARTITION BY ph.product_id ORDER BY ph.timestamp DESC) as row_num
            FROM price_history ph
        ),
        LatestSuggestions AS (
            SELECT sp.product_id,
                   sp.id as suggestion_id,
                   sp.suggested_price,
                   sp.manual_price,
                   sp.is_applied,
                   sp.source,
                   sp.notes,
                   sp.created_at,
                   ROW_NUMBER() OVER (PARTITION BY sp.product_id ORDER BY sp.created_at DESC) as row_num
            FROM suggested_prices sp
        )
        SELECT p.id as product_id, 
               p.name as product_name,
               lp.our_price as current_price,
               lp.competitor_prices,
               lp.timestamp as price_updated_at,
               ls.suggestion_id,
               ls.suggested_price,
               ls.manual_price,
               ls.is_applied,
               ls.source as suggestion_source,
               ls.notes as suggestion_notes,
               ls.created_at as suggestion_created_at
        FROM products p
        LEFT JOIN LatestPrices lp ON p.id = lp.product_id AND lp.row_num = 1
        LEFT JOIN LatestSuggestions ls ON p.id = ls.product_id AND ls.row_num = 1
        ORDER BY p.name
        """
        
        df = pd.read_sql_query(query, conn)
        
        # Convert competitor_prices from JSON string to dict
        if not df.empty and 'competitor_prices' in df.columns:
            df['competitor_prices'] = df['competitor_prices'].apply(
                lambda x: json.loads(x) if x and x != "{}" else {})
            
            # Convert timestamp columns
            for col in ['price_updated_at', 'suggestion_created_at']:
                if col in df.columns:
                    df[col] = pd.to_datetime(df[col])
        
        return df
    except Exception as e:
        print(f"Error getting latest prices: {e}")
        return pd.DataFrame()
    finally:
        conn.close()

def export_prices_to_json(output_file=None):
    """
    Export all products with their current and suggested prices to JSON
    
    Args:
        output_file (str, optional): Path to output file. If None, return the JSON string.
    
    Returns:
        str: JSON string if output_file is None, otherwise None
    """
    prices_df = get_latest_prices()
    
    if prices_df.empty:
        return json.dumps({"error": "No price data available"})
    
    # Prepare data for export
    export_data = []
    
    for _, row in prices_df.iterrows():
        price_data = {
            "product_id": int(row["product_id"]),
            "product_name": row["product_name"],
            "current_price": float(row["current_price"]) if not pd.isna(row["current_price"]) else None
        }
        
        # Add pricing data
        if not pd.isna(row.get("suggestion_id")):
            if not pd.isna(row.get("manual_price")):
                price_data["new_price"] = float(row["manual_price"])
                price_data["price_source"] = "manual"
            elif not pd.isna(row.get("suggested_price")):
                price_data["new_price"] = float(row["suggested_price"])
                price_data["price_source"] = row.get("suggestion_source", "ai")
            
            if "new_price" in price_data:
                price_data["is_applied"] = bool(row.get("is_applied", False))
                price_data["notes"] = row.get("suggestion_notes")
        
        # Add competitor data
        competitor_prices = row.get("competitor_prices", {})
        if competitor_prices:
            price_data["competitor_prices"] = competitor_prices
        
        export_data.append(price_data)
    
    json_data = json.dumps({"products": export_data}, indent=2)
    
    if output_file:
        with open(output_file, 'w') as f:
            f.write(json_data)
        return None
    else:
        return json_data

def export_prices_to_csv(output_file=None):
    """
    Export all products with their current and suggested prices to CSV
    
    Args:
        output_file (str, optional): Path to output file. If None, return the CSV string.
    
    Returns:
        str: CSV string if output_file is None, otherwise None
    """
    prices_df = get_latest_prices()
    
    if prices_df.empty:
        return "Error: No price data available"
    
    # Prepare data for export
    export_data = []
    
    for _, row in prices_df.iterrows():
        price_data = {
            "product_id": row["product_id"],
            "product_name": row["product_name"],
            "current_price": row["current_price"] if not pd.isna(row["current_price"]) else ""
        }
        
        # Add pricing data
        if not pd.isna(row.get("suggestion_id")):
            if not pd.isna(row.get("manual_price")):
                price_data["new_price"] = row["manual_price"]
                price_data["price_source"] = "manual"
            elif not pd.isna(row.get("suggested_price")):
                price_data["new_price"] = row["suggested_price"]
                price_data["price_source"] = row.get("suggestion_source", "ai")
            
            if "new_price" in price_data:
                price_data["is_applied"] = "Yes" if row.get("is_applied", False) else "No"
                price_data["notes"] = row.get("suggestion_notes", "")
        else:
            price_data["new_price"] = ""
            price_data["price_source"] = ""
            price_data["is_applied"] = ""
            price_data["notes"] = ""
        
        # Add simplified competitor data
        competitor_prices = row.get("competitor_prices", {})
        if competitor_prices:
            # Get minimum, maximum and average competitor price
            prices = list(competitor_prices.values())
            price_data["min_competitor_price"] = min(prices) if prices else ""
            price_data["max_competitor_price"] = max(prices) if prices else ""
            price_data["avg_competitor_price"] = sum(prices) / len(prices) if prices else ""
            
            # Add first three competitors specifically
            competitors = list(competitor_prices.items())
            for i in range(min(3, len(competitors))):
                comp_name, comp_price = competitors[i]
                price_data[f"competitor_{i+1}_name"] = comp_name
                price_data[f"competitor_{i+1}_price"] = comp_price
        
        export_data.append(price_data)
    
    # Convert to DataFrame for CSV export
    export_df = pd.DataFrame(export_data)
    
    if output_file:
        export_df.to_csv(output_file, index=False)
        return None
    else:
        return export_df.to_csv(index=False)
