import streamlit as st
from datetime import datetime, timedelta
import pandas as pd
from utils.database import get_settings, update_settings
from utils.scheduler import start_scheduler, stop_scheduler, get_scheduler_status

def app():
    st.title("Application Settings")
    
    # Get current settings
    settings = get_settings()
    scheduler_status = get_scheduler_status()
    
    # Create tabs for different settings
    tab1, tab2, tab3 = st.tabs(["Scraper Settings", "AI Analysis Settings", "About"])
    
    with tab1:
        st.header("Scraper Configuration")
        
        # Display scheduler status
        status_col1, status_col2 = st.columns(2)
        
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
                if st.button("Stop Scheduler"):
                    result = stop_scheduler()
                    st.success(result)
                    st.rerun()
            else:
                if st.button("Start Scheduler"):
                    result = start_scheduler()
                    st.success(result)
                    st.rerun()
        
        # Scraping interval settings
        st.subheader("Scraping Interval")
        
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
        current_interval = settings["scrape_interval"]
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
        
        # Save button for interval
        if st.button("Save Interval Setting"):
            update_settings(scrape_interval=interval_seconds)
            
            # Restart scheduler if it was running
            if scheduler_status["running"]:
                stop_scheduler()
                start_scheduler()
            
            st.success(f"Scraping interval updated to {selected_interval}")
            st.rerun()
    
    with tab2:
        st.header("AI Analysis Settings")
        
        # Analysis period settings
        st.subheader("Default Analysis Period")
        
        period_options = {
            "3 days": 3,
            "7 days": 7,
            "14 days": 14,
            "30 days": 30
        }
        
        # Find the nearest matching period
        current_period = settings["analysis_period"]
        current_period_option = "7 days"  # default
        
        for option, days in period_options.items():
            if days == current_period:
                current_period_option = option
                break
        
        selected_period = st.selectbox(
            "Select default time period for AI analysis",
            options=list(period_options.keys()),
            index=list(period_options.keys()).index(current_period_option)
        )
        
        period_days = period_options[selected_period]
        
        # Save button for analysis period
        if st.button("Save Analysis Setting"):
            update_settings(analysis_period=period_days)
            st.success(f"Default analysis period updated to {selected_period}")
            st.rerun()
        
        # OpenAI API key section
        st.subheader("OpenAI API Key")
        
        # Check if key is set
        import os
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
