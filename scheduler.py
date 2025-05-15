import time
import threading
import schedule
from datetime import datetime, timedelta
import streamlit as st
from scraper import scrape_all_products
from database import get_settings, update_last_scrape

# Global variables to manage the scheduler
_stop_event = threading.Event()
_scheduler_thread = None
_last_run_time = None

def _run_scraper():
    """Run the scraper and update last run time"""
    global _last_run_time
    
    try:
        results = scrape_all_products()
        _last_run_time = datetime.now()
        return results
    except Exception as e:
        return f"Error: {str(e)}"

def _scheduler_loop():
    """Main scheduler loop that runs in a background thread"""
    while not _stop_event.is_set():
        schedule.run_pending()
        time.sleep(1)

def start_scheduler():
    """Start the scheduler with the configured interval"""
    global _scheduler_thread, _stop_event
    
    if _scheduler_thread and _scheduler_thread.is_alive():
        stop_scheduler()
    
    _stop_event.clear()
    
    # Get interval from settings (in seconds)
    settings = get_settings()
    interval_seconds = settings["scrape_interval"]
    
    # Convert to minutes for schedule
    interval_minutes = max(1, interval_seconds // 60)
    
    # Clear existing jobs
    schedule.clear()
    
    # Schedule the scraper to run at the specified interval
    schedule.every(interval_minutes).minutes.do(_run_scraper)
    
    # Start the scheduler in a background thread
    _scheduler_thread = threading.Thread(target=_scheduler_loop, daemon=True)
    _scheduler_thread.start()
    
    return f"Scheduler started with interval: {interval_minutes} minutes"

def stop_scheduler():
    """Stop the scheduler"""
    global _scheduler_thread, _stop_event
    
    if _scheduler_thread and _scheduler_thread.is_alive():
        _stop_event.set()
        _scheduler_thread.join(timeout=5)
        _scheduler_thread = None
        schedule.clear()
        return "Scheduler stopped"
    
    return "Scheduler is not running"

def get_scheduler_status():
    """Get the current status of the scheduler"""
    global _scheduler_thread, _last_run_time
    
    settings = get_settings()
    interval_seconds = settings["scrape_interval"]
    
    # Format interval for display
    if interval_seconds < 60:
        interval_str = f"{interval_seconds} seconds"
    elif interval_seconds < 3600:
        interval_str = f"{interval_seconds // 60} minutes"
    else:
        interval_str = f"{interval_seconds // 3600} hours"
    
    status = {
        "running": _scheduler_thread is not None and _scheduler_thread.is_alive(),
        "interval": interval_str,
        "interval_seconds": interval_seconds,
        "last_run": _last_run_time
    }
    
    # Calculate next run time
    if status["running"] and _last_run_time:
        next_run = _last_run_time + timedelta(seconds=interval_seconds)
        status["next_run"] = next_run
    
    return status

def run_scraper_now():
    """Run the scraper immediately"""
    return _run_scraper()
