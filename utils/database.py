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
