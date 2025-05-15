# Price Monitor App - Project Structure

## Overview
The entire application has been simplified into a clean, flat structure with only 6 main files:

```
price_monitor/
├── app.py              # Main application with navigation
├── pages.py            # All UI pages combined into one file
├── database.py         # Database operations and schema
├── scraper.py          # Web scraping and scheduling functionality
├── analyzers.py        # AI analysis and data visualization
└── price_monitor.db    # SQLite database file
```

## File Descriptions

### app.py (4.9 KB)
- Entry point of the application
- Contains navigation and sidebar setup
- Initializes database and scheduler
- Routes to various pages based on user selection

### pages.py (70.3 KB)
- Contains all the UI pages combined:
  - Monitor Products
  - Add Product
  - Price Analysis
  - Multi-Product Analysis
  - Price Management
  - Settings

### database.py (21.6 KB)
- Database connection and initialization
- Schema definition
- CRUD operations for products, prices, settings
- Export functionality

### scraper.py (21.5 KB)
- Web scraping functionality
- Price extraction with support for various formats
- CSS selector parsing and handling
- Scheduling of automatic scraping

### analyzers.py (42.6 KB)
- AI-powered price analysis using OpenAI
- Data visualization with Plotly
- Price forecasting
- Price comparison analytics

## Key Features

1. **Price Monitoring**: Track prices across multiple websites
2. **Multi-Competitor Tracking**: Compare prices with multiple competitors
3. **AI Analysis**: Get AI-powered pricing suggestions
4. **Flexible Visualizations**: Various chart types for price trend analysis
5. **Automatic Scraping**: Schedule automatic price checks
6. **Price Management**: Apply suggested prices or set manual prices
7. **Data Export**: Export data as JSON or CSV for other systems
8. **Multi-Product Analysis**: Compare and analyze multiple products at once