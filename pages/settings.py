import streamlit as st
from datetime import datetime, timedelta
import pandas as pd
import os
from utils.database import get_settings, update_settings
from utils.scheduler import start_scheduler, stop_scheduler, get_scheduler_status

def app():
    st.title("Application Settings")
    
    # Get current settings
    settings = get_settings()
    scheduler_status = get_scheduler_status()
    
    # Create tabs for different settings
    tab1, tab2, tab3, tab4 = st.tabs([
        "Scraper Settings", 
        "AI Analysis Settings", 
        "Display & Notifications",
        "About"
    ])
    
    with tab1:
        st.header("Scraper Configuration")
        
        # Display scheduler status
        status_col1, status_col2 = st.columns([3, 1])
        
        with status_col1:
            status_text = "Running" if scheduler_status["running"] else "Stopped"
            st.info(f"Scraper Status: **{status_text}**")
            
            if scheduler_status["running"] and "next_run" in scheduler_status:
                next_run = scheduler_status["next_run"]
                time_remaining = next_run - datetime.now()
                minutes_remaining = max(0, int(time_remaining.total_seconds() / 60))
                st.caption(f"Next run in approximately {minutes_remaining} minutes")
        
        with status_col2:
            if scheduler_status["running"]:
                if st.button("Stop Scheduler", type="primary"):
                    result = stop_scheduler()
                    st.success(result)
                    st.rerun()
            else:
                if st.button("Start Scheduler", type="primary"):
                    result = start_scheduler()
                    st.success(result)
                    st.rerun()
        
        # Scraping interval settings
        with st.form("scraper_settings_form"):
            st.subheader("Scraping Configuration")
            
            # Interval settings
            interval_options = {
                "5 minutes": 300,
                "15 minutes": 900,
                "30 minutes": 1800,
                "1 hour": 3600,
                "2 hours": 7200,
                "4 hours": 14400,
                "6 hours": 21600,
                "12 hours": 43200,
                "24 hours": 86400
            }
            
            # Find the nearest matching interval
            current_interval = settings.get("scrape_interval", 3600)
            current_option = "1 hour"  # default
            
            for option, seconds in interval_options.items():
                if seconds == current_interval:
                    current_option = option
                    break
            
            selected_interval = st.selectbox(
                "Select how often to update product prices",
                options=list(interval_options.keys()),
                index=list(interval_options.keys()).index(current_option)
            )
            
            interval_seconds = interval_options[selected_interval]
            
            # User agent setting
            user_agent = settings.get(
                "user_agent", 
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            )
            
            new_user_agent = st.text_input(
                "Scraper User Agent", 
                value=user_agent,
                help="The User-Agent header to use for scraping requests"
            )
            
            # Request timeout
            timeout = settings.get("request_timeout", 30)
            new_timeout = st.number_input(
                "Request Timeout (seconds)",
                min_value=5,
                max_value=120,
                value=int(timeout),
                help="Maximum time to wait for website responses"
            )
            
            # History retention
            history_limit = settings.get("price_history_limit", 90)
            new_history_limit = st.number_input(
                "Price History Retention (days)",
                min_value=7,
                max_value=365,
                value=int(history_limit),
                help="Number of days to keep price history data"
            )
            
            # Save button for scraper settings
            submit_button = st.form_submit_button("Save Scraper Settings")
            
            if submit_button:
                # Update settings
                update_settings(
                    scrape_interval=interval_seconds,
                    user_agent=new_user_agent,
                    request_timeout=new_timeout,
                    price_history_limit=new_history_limit
                )
                
                # Restart scheduler if it was running
                if scheduler_status["running"]:
                    stop_scheduler()
                    start_scheduler()
                
                st.success("Scraper settings updated successfully!")
                st.rerun()
    
    with tab2:
        st.header("AI Analysis Settings")
        
        # Analysis settings form
        with st.form("analysis_settings_form"):
            st.subheader("AI Analysis Configuration")
            
            # Analysis period settings
            period_options = {
                "3 days": 3,
                "7 days": 7,
                "14 days": 14,
                "30 days": 30,
                "90 days": 90
            }
            
            # Find the nearest matching period
            current_period = settings.get("analysis_period", 7)
            current_period_option = "7 days"  # default
            
            for option, days in period_options.items():
                if days == current_period:
                    current_period_option = option
                    break
            
            selected_period = st.selectbox(
                "Default time period for AI analysis",
                options=list(period_options.keys()),
                index=list(period_options.keys()).index(current_period_option)
            )
            
            period_days = period_options[selected_period]
            
            # Price alert threshold
            threshold = settings.get("price_alert_threshold", 5)
            new_threshold = st.slider(
                "Price Alert Threshold (%)",
                min_value=1,
                max_value=25,
                value=int(threshold),
                help="Minimum price change percentage to trigger alerts"
            )
            
            # Competitor weight
            weight = settings.get("competitor_weight", 70)
            new_weight = st.slider(
                "Competitor Influence on Price Recommendations (%)",
                min_value=0,
                max_value=100,
                value=int(weight),
                help="How much competitor prices should influence AI recommendations"
            )
            
            # Trend forecast days
            forecast_days = settings.get("trend_forecast_days", 7)
            new_forecast_days = st.select_slider(
                "Trend Forecast Days",
                options=[3, 5, 7, 10, 14, 30],
                value=int(forecast_days),
                help="Number of days to forecast in trend analysis"
            )
            
            # Feature toggles
            enable_forecasting = settings.get("enable_trend_forecasting", True)
            new_enable_forecasting = st.checkbox(
                "Enable trend forecasting",
                value=bool(enable_forecasting),
                help="Show price trend forecasts in analysis"
            )
            
            # Submit button
            submit_button = st.form_submit_button("Save Analysis Settings")
            
            if submit_button:
                # Update settings
                update_settings(
                    analysis_period=period_days,
                    price_alert_threshold=new_threshold,
                    competitor_weight=new_weight,
                    trend_forecast_days=new_forecast_days,
                    enable_trend_forecasting=new_enable_forecasting
                )
                
                st.success("Analysis settings updated successfully!")
                st.rerun()
        
        # OpenAI API key section
        st.subheader("OpenAI API Key")
        
        # Check if key is set
        openai_key = os.environ.get("OPENAI_API_KEY", "")
        
        if openai_key:
            st.success("OpenAI API key is set in environment variables.")
            st.info(
                "The AI analysis feature uses GPT-4o to provide pricing recommendations. "
                "Your API key is not stored in the application and is only used for API calls."
            )
        else:
            st.warning(
                "OpenAI API key is not set. To use AI analysis features, "
                "please set the OPENAI_API_KEY environment variable."
            )
            st.info(
                "You need an OpenAI API key to use the AI analysis features. "
                "Get your API key from https://platform.openai.com/"
            )
    
    with tab3:
        st.header("Display & Notifications")
        
        # Display settings form
        with st.form("display_settings_form"):
            st.subheader("UI Settings")
            
            # Theme setting
            theme_options = {
                "light": "Light Mode",
                "dark": "Dark Mode"
            }
            current_theme = settings.get("theme", "light")
            
            selected_theme = st.radio(
                "Application Theme",
                options=list(theme_options.values()),
                index=0 if current_theme == "light" else 1,
                horizontal=True
            )
            theme_key = "light" if selected_theme == "Light Mode" else "dark"
            
            # Price alerts toggle
            enable_alerts = settings.get("enable_price_alerts", True)
            new_enable_alerts = st.checkbox(
                "Enable price change alerts",
                value=bool(enable_alerts),
                help="Show alerts for significant price changes"
            )
            
            # Email reports toggle
            enable_email = settings.get("enable_email_reports", False)
            new_enable_email = st.checkbox(
                "Enable email reports (Not implemented yet)",
                value=bool(enable_email),
                help="Send scheduled price reports via email",
                disabled=True
            )
            
            # Submit button
            submit_button = st.form_submit_button("Save Display Settings")
            
            if submit_button:
                # Update settings
                update_settings(
                    theme=theme_key,
                    enable_price_alerts=new_enable_alerts,
                    enable_email_reports=new_enable_email
                )
                
                st.success("Display settings updated successfully!")
                st.rerun()
    
    with tab4:
        st.header("About Price Monitor & Analyzer")
        
        st.image("https://images.unsplash.com/photo-1526628953301-3e589a6a8b74")
        
        st.markdown("""
        ### Purpose
        
        This application helps e-commerce businesses monitor competitor prices and optimize their pricing strategy. It provides:
        
        - Automated web scraping to track product prices across multiple websites
        - Historical price tracking and visualization
        - AI-powered price analysis and recommendations
        
        ### How It Works
        
        1. **Add Products**: Add your products and competitor URLs with HTML selectors for price extraction
        2. **Schedule Scraping**: Set up automatic price checking at regular intervals
        3. **Monitor Prices**: Track price changes over time with interactive visualizations
        4. **Get AI Analysis**: Leverage OpenAI's GPT-4o for intelligent pricing recommendations
        
        ### Privacy & Data
        
        All data is stored locally in an SQLite database. No data is shared with external services
        except for the OpenAI API when generating price analysis.
        
        ### Feedback & Support
        
        For feedback or support, please contact the development team.
        """)

# Run the app
app()
