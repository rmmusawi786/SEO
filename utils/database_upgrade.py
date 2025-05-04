import sqlite3
import json
from utils.database import DB_PATH

def upgrade_settings_table():
    """Upgrade the settings table schema to support more configuration options"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    try:
        # Check the existing schema
        cursor.execute("PRAGMA table_info(settings)")
        columns = [row[1] for row in cursor.fetchall()]
        
        # Create a new temporary table with all desired fields
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS settings_new (
            id INTEGER PRIMARY KEY,
            name TEXT UNIQUE NOT NULL,
            value TEXT NOT NULL
        )
        ''')
        
        # Insert default settings
        # First, migrate existing settings if the old format exists
        if 'scrape_interval' in columns and 'analysis_period' in columns:
            cursor.execute("SELECT scrape_interval, last_scrape, analysis_period FROM settings WHERE id = 1")
            old_settings = cursor.fetchone()
            
            if old_settings:
                # Convert existing settings to new format
                scrape_interval, last_scrape, analysis_period = old_settings
                
                # Insert old settings with new format
                settings_to_migrate = [
                    ('scrape_interval', str(scrape_interval)),
                    ('analysis_period', str(analysis_period))
                ]
                
                if last_scrape:
                    settings_to_migrate.append(('last_scrape', str(last_scrape)))
                
                for name, value in settings_to_migrate:
                    cursor.execute(
                        "INSERT OR REPLACE INTO settings_new (name, value) VALUES (?, ?)",
                        (name, value)
                    )
        
        # Add default settings if they don't exist yet
        default_settings = [
            ('scrape_interval', '3600'),
            ('analysis_period', '7'),
            ('user_agent', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'),
            ('request_timeout', '30'),  # seconds
            ('price_alert_threshold', '5'),  # percentage
            ('competitor_weight', '70'),  # percentage importance in price recommendations
            ('price_history_limit', '90'),  # days to keep history
            ('trend_forecast_days', '7'),  # days to forecast
            ('enable_price_alerts', 'true'),
            ('enable_email_reports', 'false'),
            ('enable_trend_forecasting', 'true'),
            ('theme', 'light')
        ]
        
        for name, value in default_settings:
            cursor.execute(
                "INSERT OR IGNORE INTO settings_new (name, value) VALUES (?, ?)",
                (name, value)
            )
        
        # Drop the old table and rename the new one
        cursor.execute("DROP TABLE IF EXISTS settings_old")
        cursor.execute("ALTER TABLE settings RENAME TO settings_old")
        cursor.execute("ALTER TABLE settings_new RENAME TO settings")
        
        # If everything went well, drop the backup table
        cursor.execute("DROP TABLE IF EXISTS settings_old")
        
        conn.commit()
        print("Settings table upgraded successfully!")
        return True
    except Exception as e:
        conn.rollback()
        print(f"Error upgrading settings table: {e}")
        return False
    finally:
        conn.close()

if __name__ == "__main__":
    upgrade_settings_table()