import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import numpy as np
from datetime import datetime, timedelta

def create_price_history_chart(price_history_df, product_name, view_mode="line"):
    """
    Create an enhanced price history visualization
    
    Args:
        price_history_df (DataFrame): Price history data
        product_name (str): Name of the product
        view_mode (str): Visualization type ('line', 'area', 'bar', 'candlestick')
        
    Returns:
        plotly.graph_objects.Figure: Plotly figure object
    """
    if price_history_df.empty:
        # Return empty figure if no data
        fig = go.Figure()
        fig.update_layout(
            title=f"No price history data available for {product_name}",
            height=500
        )
        return fig
    
    # Create dataframe for our prices
    our_price_df = price_history_df[['timestamp', 'our_price']].copy()
    our_price_df.rename(columns={'our_price': 'price'}, inplace=True)
    our_price_df['source'] = 'Our Store'
    
    # Create DataFrames for competitor prices
    all_prices_df = our_price_df.copy()
    
    competitor_colors = {}
    
    for _, row in price_history_df.iterrows():
        competitor_prices = row['competitor_prices']
        
        for competitor, price in competitor_prices.items():
            # Add competitor to the color map if not there
            if competitor not in competitor_colors:
                competitor_colors[competitor] = len(competitor_colors) + 1
            
            # Add competitor price to the main DataFrame
            all_prices_df = pd.concat([
                all_prices_df, 
                pd.DataFrame({
                    'timestamp': [row['timestamp']],
                    'price': [price],
                    'source': [competitor]
                })
            ], ignore_index=True)
    
    # Sort by timestamp
    all_prices_df = all_prices_df.sort_values('timestamp')
    
    # Create figure based on view mode
    if view_mode == "line":
        fig = px.line(
            all_prices_df, 
            x='timestamp', 
            y='price', 
            color='source',
            title=f'Price Comparison for {product_name}',
            labels={'timestamp': 'Date', 'price': 'Price', 'source': 'Source'},
            markers=True
        )
        
    elif view_mode == "area":
        fig = px.area(
            all_prices_df, 
            x='timestamp', 
            y='price', 
            color='source',
            title=f'Price Trends for {product_name}',
            labels={'timestamp': 'Date', 'price': 'Price', 'source': 'Source'},
            line_shape='spline'
        )
        
    elif view_mode == "bar":
        # Group by date and source for bar chart
        all_prices_df['date'] = all_prices_df['timestamp'].dt.date
        grouped_df = all_prices_df.groupby(['date', 'source']).agg({'price': 'mean'}).reset_index()
        
        fig = px.bar(
            grouped_df, 
            x='date', 
            y='price', 
            color='source',
            title=f'Daily Average Prices for {product_name}',
            barmode='group',
            labels={'date': 'Date', 'price': 'Price', 'source': 'Source'}
        )
        
    elif view_mode == "candlestick":
        # Create OHLC data for our store
        our_df = all_prices_df[all_prices_df['source'] == 'Our Store'].copy()
        our_df['date'] = our_df['timestamp'].dt.date
        
        ohlc_df = our_df.groupby('date').agg({
            'price': ['first', 'max', 'min', 'last']
        }).reset_index()
        
        ohlc_df.columns = ['date', 'open', 'high', 'low', 'close']
        
        fig = go.Figure(data=[
            go.Candlestick(
                x=ohlc_df['date'],
                open=ohlc_df['open'],
                high=ohlc_df['high'],
                low=ohlc_df['low'],
                close=ohlc_df['close'],
                name='Our Store'
            )
        ])
        
        # Add competitor lines
        for competitor in competitor_colors.keys():
            comp_df = all_prices_df[all_prices_df['source'] == competitor]
            if not comp_df.empty:
                fig.add_trace(go.Scatter(
                    x=comp_df['timestamp'], 
                    y=comp_df['price'],
                    mode='lines+markers',
                    name=competitor
                ))
        
        fig.update_layout(
            title=f'Price Analysis for {product_name}',
            xaxis_title='Date',
            yaxis_title='Price'
        )
    
    else:  # Default to line chart
        fig = px.line(
            all_prices_df, 
            x='timestamp', 
            y='price', 
            color='source',
            title=f'Price Comparison for {product_name}',
            labels={'timestamp': 'Date', 'price': 'Price', 'source': 'Source'},
            markers=True
        )
    
    # Enhance the figure
    fig.update_layout(
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        height=500,
        hovermode="x unified",
        xaxis=dict(
            showgrid=True,
            gridwidth=1,
            gridcolor='rgba(211,211,211,0.3)'
        ),
        yaxis=dict(
            showgrid=True,
            gridwidth=1,
            gridcolor='rgba(211,211,211,0.3)'
        ),
        plot_bgcolor='white'
    )
    
    return fig

def create_price_statistics_table(price_history_df):
    """
    Create enhanced price statistics
    
    Args:
        price_history_df (DataFrame): Price history data
        
    Returns:
        DataFrame: Statistics dataframe
    """
    if price_history_df.empty:
        return pd.DataFrame()
    
    # Create DataFrame for our prices
    our_price_df = price_history_df[['timestamp', 'our_price']].copy()
    our_price_df.rename(columns={'our_price': 'price'}, inplace=True)
    our_price_df['source'] = 'Our Store'
    
    # Create DataFrames for competitor prices
    all_prices_df = our_price_df.copy()
    
    for _, row in price_history_df.iterrows():
        competitor_prices = row['competitor_prices']
        
        for competitor, price in competitor_prices.items():
            # Add competitor price to the main DataFrame
            all_prices_df = pd.concat([
                all_prices_df, 
                pd.DataFrame({
                    'timestamp': [row['timestamp']],
                    'price': [price],
                    'source': [competitor]
                })
            ], ignore_index=True)
    
    # Group by source and calculate statistics
    stats_df = all_prices_df.groupby('source').agg({
        'price': ['min', 'max', 'mean', 'std', 'count']
    }).reset_index()
    
    stats_df.columns = ['Source', 'Min', 'Max', 'Average', 'StdDev', 'Count']
    
    # Add latest price
    latest_prices = {}
    for source in stats_df['Source'].unique():
        source_df = all_prices_df[all_prices_df['source'] == source]
        if not source_df.empty:
            latest_timestamp = source_df['timestamp'].max()
            latest_price = source_df[source_df['timestamp'] == latest_timestamp]['price'].values[0]
            latest_prices[source] = latest_price
    
    stats_df['Current'] = stats_df['Source'].map(latest_prices)
    
    # Add price change (first to last)
    price_changes = {}
    for source in stats_df['Source'].unique():
        source_df = all_prices_df[all_prices_df['source'] == source].sort_values('timestamp')
        if len(source_df) >= 2:
            first_price = source_df['price'].iloc[0]
            last_price = source_df['price'].iloc[-1]
            change = last_price - first_price
            change_pct = (change / first_price) * 100 if first_price else 0
            price_changes[source] = {
                'change': change,
                'change_pct': change_pct
            }
        else:
            price_changes[source] = {
                'change': 0,
                'change_pct': 0
            }
    
    stats_df['Change'] = stats_df['Source'].apply(lambda x: price_changes[x]['change'])
    stats_df['ChangePct'] = stats_df['Source'].apply(lambda x: price_changes[x]['change_pct'])
    
    # Format values
    stats_df['Min'] = stats_df['Min'].round(2)
    stats_df['Max'] = stats_df['Max'].round(2)
    stats_df['Average'] = stats_df['Average'].round(2)
    stats_df['StdDev'] = stats_df['StdDev'].round(2)
    stats_df['Current'] = stats_df['Current'].round(2)
    stats_df['Change'] = stats_df['Change'].round(2)
    stats_df['ChangePct'] = stats_df['ChangePct'].round(2)
    
    return stats_df

def create_price_comparison_gauge_chart(price_history_df, product_name):
    """
    Create a gauge chart comparing our price vs competition
    
    Args:
        price_history_df (DataFrame): Price history data
        product_name (str): Name of the product
        
    Returns:
        plotly.graph_objects.Figure: Plotly figure object
    """
    if price_history_df.empty:
        # Return empty figure if no data
        fig = go.Figure()
        fig.update_layout(
            title=f"No price history data available for {product_name}",
            height=350
        )
        return fig
    
    # Get latest entry
    latest_entry = price_history_df.iloc[-1]
    our_price = latest_entry['our_price']
    competitor_prices = latest_entry['competitor_prices']
    
    if not competitor_prices:
        # No competitor data
        fig = go.Figure()
        fig.update_layout(
            title=f"No competitor data available for {product_name}",
            height=350
        )
        return fig
    
    # Calculate statistics
    comp_prices = list(competitor_prices.values())
    avg_comp_price = sum(comp_prices) / len(comp_prices)
    min_comp_price = min(comp_prices)
    max_comp_price = max(comp_prices)
    
    # Calculate our price position
    price_range = max_comp_price - min_comp_price
    if price_range == 0:
        price_position = 50  # All prices are the same
    else:
        price_position = ((our_price - min_comp_price) / price_range) * 100
    
    # Create gauge chart
    fig = go.Figure(go.Indicator(
        mode = "gauge+number+delta",
        value = our_price,
        number = {'prefix': "€", 'suffix': ""},
        domain = {'x': [0, 1], 'y': [0, 1]},
        title = {'text': f"Our Price vs Competition"},
        delta = {'reference': avg_comp_price, 'relative': True, 'valueformat': '.1%'},
        gauge = {
            'axis': {'range': [min_comp_price * 0.9, max_comp_price * 1.1]},
            'bar': {'color': "#FF4B4B"},
            'steps': [
                {'range': [min_comp_price * 0.9, min_comp_price], 'color': "#C2FADB"},
                {'range': [min_comp_price, avg_comp_price], 'color': "#90EAC5"},
                {'range': [avg_comp_price, max_comp_price], 'color': "#2CCDA3"},
                {'range': [max_comp_price, max_comp_price * 1.1], 'color': "#25A280"}
            ],
            'threshold': {
                'line': {'color': "blue", 'width': 2},
                'thickness': 0.75,
                'value': avg_comp_price
            }
        }
    ))
    
    # Competitor price references
    annotations = []
    for i, (comp_name, comp_price) in enumerate(competitor_prices.items()):
        y_pos = 0.1 - (i * 0.06)
        annotations.append(dict(
            xref='paper',
            yref='paper',
            x=0.01,
            y=y_pos,
            xanchor='left',
            text=f"{comp_name}: €{comp_price:.2f}",
            font=dict(size=10),
            showarrow=False
        ))
    
    # Add price position indicator
    if price_position <= 10:
        price_status = "Much Lower"
        status_color = "green"
    elif price_position <= 30:
        price_status = "Lower"
        status_color = "green"
    elif price_position <= 50:
        price_status = "Slightly Lower"
        status_color = "lightgreen"
    elif price_position <= 70:
        price_status = "Slightly Higher"
        status_color = "orange"
    elif price_position <= 90:
        price_status = "Higher"
        status_color = "red"
    else:
        price_status = "Much Higher"
        status_color = "darkred"
    
    annotations.append(dict(
        xref='paper',
        yref='paper',
        x=0.99,
        y=0.1,
        xanchor='right',
        text=f"Price Position: <span style='color:{status_color};'>{price_status}</span>",
        font=dict(size=11),
        showarrow=False,
        align='left'
    ))
    
    # Add delta explanation
    diff_pct = ((our_price - avg_comp_price) / avg_comp_price) * 100
    if diff_pct < 0:
        diff_text = f"{abs(diff_pct):.1f}% lower than average competition"
    else:
        diff_text = f"{diff_pct:.1f}% higher than average competition"
    
    annotations.append(dict(
        xref='paper',
        yref='paper',
        x=0.5,
        y=0.25,
        xanchor='center',
        text=diff_text,
        font=dict(size=11),
        showarrow=False
    ))
    
    fig.update_layout(
        height=350,
        margin=dict(t=50, b=30, l=30, r=30),
        annotations=annotations
    )
    
    return fig

def create_price_trend_forecast(price_history_df, product_name, days_to_forecast=7):
    """
    Create a price trend forecast visualization
    
    Args:
        price_history_df (DataFrame): Price history data
        product_name (str): Name of the product
        days_to_forecast (int): Number of days to forecast
        
    Returns:
        plotly.graph_objects.Figure: Plotly figure object
    """
    if price_history_df.empty or len(price_history_df) < 3:
        # Return empty figure if not enough data
        fig = go.Figure()
        fig.update_layout(
            title=f"Not enough data for trend forecast for {product_name}",
            height=400
        )
        return fig
    
    # Create dataframe for our prices
    our_price_df = price_history_df[['timestamp', 'our_price']].copy()
    
    # Sort by timestamp
    our_price_df = our_price_df.sort_values('timestamp')
    
    # Convert to numpy arrays for trend calculation
    x = np.array([(t - our_price_df['timestamp'].min()).total_seconds() for t in our_price_df['timestamp']])
    y = np.array(our_price_df['our_price'])
    
    # Calculate linear trend
    z = np.polyfit(x, y, 1)
    p = np.poly1d(z)
    
    # Forecast future prices
    last_timestamp = our_price_df['timestamp'].max()
    future_timestamps = [last_timestamp + timedelta(days=i) for i in range(1, days_to_forecast+1)]
    future_seconds = np.array([(t - our_price_df['timestamp'].min()).total_seconds() for t in future_timestamps])
    forecast_prices = p(future_seconds)
    
    # Prepare data for visualization
    historical_df = pd.DataFrame({
        'timestamp': our_price_df['timestamp'],
        'price': our_price_df['our_price'],
        'type': 'Historical'
    })
    
    forecast_df = pd.DataFrame({
        'timestamp': future_timestamps,
        'price': forecast_prices,
        'type': 'Forecast'
    })
    
    combined_df = pd.concat([historical_df, forecast_df], ignore_index=True)
    
    # Create visualization
    fig = px.line(
        combined_df, 
        x='timestamp', 
        y='price', 
        color='type',
        title=f'Price Trend Forecast for {product_name}',
        labels={'timestamp': 'Date', 'price': 'Price', 'type': 'Data Type'},
        markers=True,
        color_discrete_map={
            'Historical': '#1F77B4',
            'Forecast': '#FF7F0E'
        }
    )
    
    # Add confidence interval for forecast
    std_dev = np.std(our_price_df['our_price'])
    upper_bound = forecast_prices + std_dev
    lower_bound = forecast_prices - std_dev
    
    fig.add_trace(go.Scatter(
        x=future_timestamps + future_timestamps[::-1],
        y=list(upper_bound) + list(lower_bound)[::-1],
        fill='toself',
        fillcolor='rgba(255,127,14,0.2)',
        line=dict(color='rgba(255,127,14,0)'),
        hoverinfo='skip',
        showlegend=False
    ))
    
    # Calculate trend values
    slope = z[0]
    slope_per_day = slope * 86400  # Convert seconds to days
    
    # Add trend information as annotations
    annotations = []
    
    if slope_per_day > 0:
        trend_text = f"Upward trend: +€{slope_per_day:.2f} per day"
        trend_color = "green"
    elif slope_per_day < 0:
        trend_text = f"Downward trend: -€{abs(slope_per_day):.2f} per day"
        trend_color = "red"
    else:
        trend_text = "Stable price (no significant trend)"
        trend_color = "blue"
    
    annotations.append(dict(
        xref='paper',
        yref='paper',
        x=0.01,
        y=0.95,
        xanchor='left',
        text=f"<b>{trend_text}</b>",
        font=dict(size=12, color=trend_color),
        showarrow=False
    ))
    
    # Add average forecasted price
    avg_forecast = np.mean(forecast_prices)
    annotations.append(dict(
        xref='paper',
        yref='paper',
        x=0.01,
        y=0.90,
        xanchor='left',
        text=f"Average forecasted price: €{avg_forecast:.2f}",
        font=dict(size=11),
        showarrow=False
    ))
    
    fig.update_layout(
        height=400,
        margin=dict(t=50, b=30, l=30, r=30),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        annotations=annotations,
        xaxis=dict(
            showgrid=True,
            gridwidth=1,
            gridcolor='rgba(211,211,211,0.3)'
        ),
        yaxis=dict(
            showgrid=True,
            gridwidth=1,
            gridcolor='rgba(211,211,211,0.3)'
        ),
        plot_bgcolor='white'
    )
    
    return fig

def create_competitor_price_matrix(price_history_df, product_name):
    """
    Create a heat map visualization of competitor prices
    
    Args:
        price_history_df (DataFrame): Price history data
        product_name (str): Name of the product
        
    Returns:
        plotly.graph_objects.Figure: Plotly figure object
    """
    if price_history_df.empty:
        # Return empty figure if no data
        fig = go.Figure()
        fig.update_layout(
            title=f"No price history data available for {product_name}",
            height=400
        )
        return fig
    
    # Extract all dates and competitors
    dates = price_history_df['timestamp'].dt.date.unique()
    
    # Get all competitor names
    all_competitors = set()
    for _, row in price_history_df.iterrows():
        all_competitors.update(row['competitor_prices'].keys())
    
    # Create sources list with Our Store first
    sources = ['Our Store'] + list(all_competitors)
    
    # Create matrix data
    matrix_data = []
    
    for date in dates:
        date_rows = price_history_df[price_history_df['timestamp'].dt.date == date]
        
        if date_rows.empty:
            continue
            
        # Use the last entry for each date
        row = date_rows.iloc[-1]
        
        # Our price
        our_price = row['our_price']
        
        # Competitor prices
        competitor_prices = row['competitor_prices']
        
        # Create a row for the matrix
        matrix_row = {'date': date}
        matrix_row['Our Store'] = our_price
        
        for competitor in all_competitors:
            matrix_row[competitor] = competitor_prices.get(competitor, None)
        
        matrix_data.append(matrix_row)
    
    # Convert to DataFrame
    matrix_df = pd.DataFrame(matrix_data)
    
    # Create annotation text matrix
    annotations = []
    
    for i, date in enumerate(matrix_df['date']):
        for j, source in enumerate(sources):
            if source in matrix_df.columns and not pd.isna(matrix_df.iloc[i][source]):
                price = matrix_df.iloc[i][source]
                annotations.append(dict(
                    x=source,
                    y=date,
                    text=f"€{price:.2f}",
                    font=dict(color='white'),
                    showarrow=False
                ))
    
    # Create heatmap
    fig = px.imshow(
        matrix_df[sources],
        x=sources,
        y=matrix_df['date'],
        color_continuous_scale='RdBu_r',
        labels=dict(x='Source', y='Date', color='Price'),
        title=f'Price Comparison Matrix for {product_name}'
    )
    
    fig.update_layout(
        height=400,
        margin=dict(t=50, b=30, l=30, r=30),
        xaxis=dict(side='top'),
        coloraxis_colorbar=dict(
            title='Price',
            tickprefix='€'
        ),
        annotations=annotations
    )
    
    return fig

def create_price_difference_chart(price_history_df, product_name):
    """
    Create a chart showing price differences between our store and competitors
    
    Args:
        price_history_df (DataFrame): Price history data
        product_name (str): Name of the product
        
    Returns:
        plotly.graph_objects.Figure: Plotly figure object
    """
    if price_history_df.empty:
        # Return empty figure if no data
        fig = go.Figure()
        fig.update_layout(
            title=f"No price history data available for {product_name}",
            height=400
        )
        return fig
    
    # Get all competitor names
    all_competitors = set()
    for _, row in price_history_df.iterrows():
        all_competitors.update(row['competitor_prices'].keys())
    
    if not all_competitors:
        # No competitor data
        fig = go.Figure()
        fig.update_layout(
            title=f"No competitor data available for {product_name}",
            height=400
        )
        return fig
    
    # Create difference data
    diff_data = []
    
    for _, row in price_history_df.iterrows():
        our_price = row['our_price']
        timestamp = row['timestamp']
        
        for competitor, comp_price in row['competitor_prices'].items():
            price_diff = our_price - comp_price
            diff_pct = (price_diff / comp_price) * 100 if comp_price else 0
            
            diff_data.append({
                'timestamp': timestamp,
                'competitor': competitor,
                'diff_absolute': price_diff,
                'diff_percent': diff_pct
            })
    
    if not diff_data:
        # No difference data
        fig = go.Figure()
        fig.update_layout(
            title=f"No price difference data available for {product_name}",
            height=400
        )
        return fig
    
    diff_df = pd.DataFrame(diff_data)
    
    # Create subplot with two y-axes
    fig = make_subplots(specs=[[{"secondary_y": True}]])
    
    # Add absolute difference lines
    for competitor in diff_df['competitor'].unique():
        comp_df = diff_df[diff_df['competitor'] == competitor]
        
        fig.add_trace(
            go.Scatter(
                x=comp_df['timestamp'],
                y=comp_df['diff_absolute'],
                mode='lines+markers',
                name=f"{competitor} (€)",
                line=dict(width=2)
            ),
            secondary_y=False
        )
    
    # Add percentage difference lines
    for competitor in diff_df['competitor'].unique():
        comp_df = diff_df[diff_df['competitor'] == competitor]
        
        fig.add_trace(
            go.Scatter(
                x=comp_df['timestamp'],
                y=comp_df['diff_percent'],
                mode='lines+markers',
                name=f"{competitor} (%)",
                line=dict(width=2, dash='dot')
            ),
            secondary_y=True
        )
    
    # Add horizontal line at 0
    fig.add_shape(
        type="line",
        x0=diff_df['timestamp'].min(),
        x1=diff_df['timestamp'].max(),
        y0=0,
        y1=0,
        line=dict(color="black", width=1, dash="dash"),
        layer="below"
    )
    
    # Update layout
    fig.update_layout(
        title=f'Price Difference Analysis for {product_name}',
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        height=400,
        hovermode="x unified",
        xaxis=dict(
            title="Date",
            showgrid=True,
            gridwidth=1,
            gridcolor='rgba(211,211,211,0.3)'
        ),
        plot_bgcolor='white'
    )
    
    # Update y-axes
    fig.update_yaxes(
        title_text="Absolute Difference (€)",
        secondary_y=False,
        showgrid=True,
        gridwidth=1,
        gridcolor='rgba(211,211,211,0.3)'
    )
    
    fig.update_yaxes(
        title_text="Percentage Difference (%)",
        secondary_y=True,
        showgrid=False
    )
    
    return fig


def create_price_radar_chart(price_history_df, product_name):
    """
    Create a radar chart comparing our prices to competitors
    
    Args:
        price_history_df (DataFrame): Price history data
        product_name (str): Name of the product
        
    Returns:
        plotly.graph_objects.Figure: Plotly figure object
    """
    if price_history_df.empty:
        # Return empty figure if no data
        fig = go.Figure()
        fig.update_layout(
            title=f"No price history data available for {product_name}",
            height=500
        )
        return fig
    
    # Get latest entry
    latest_entry = price_history_df.iloc[-1]
    our_price = latest_entry['our_price']
    competitor_prices = latest_entry['competitor_prices']
    
    if not competitor_prices:
        # No competitor data
        fig = go.Figure()
        fig.update_layout(
            title=f"No competitor data available for {product_name}",
            height=500
        )
        return fig
    
    # Create data for radar chart
    categories = ['Our Store'] + list(competitor_prices.keys())
    values = [our_price] + list(competitor_prices.values())
    
    # Normalize prices for better comparison
    max_price = max(values)
    normalized_values = [v / max_price * 100 for v in values]
    
    # Create radar chart
    fig = go.Figure()
    
    # Add price points
    fig.add_trace(go.Scatterpolar(
        r=normalized_values,
        theta=categories,
        fill='toself',
        name='Normalized Price',
        line=dict(color='rgba(255, 75, 75, 0.8)'),
        fillcolor='rgba(255, 75, 75, 0.2)'
    ))
    
    # Add actual price annotations
    annotations = []
    for i, (cat, val, norm_val) in enumerate(zip(categories, values, normalized_values)):
        angle = (i / len(categories)) * 2 * np.pi
        if i == 0:  # Our store
            r = norm_val + 15  # Offset for annotation
            annotations.append(dict(
                x=r * np.cos(angle),
                y=r * np.sin(angle),
                text=f"€{val:.2f}",
                showarrow=False,
                font=dict(size=12, color='red', weight='bold')
            ))
        else:  # Competitors
            r = norm_val + 10  # Offset for annotation
            annotations.append(dict(
                x=r * np.cos(angle),
                y=r * np.sin(angle),
                text=f"€{val:.2f}",
                showarrow=False,
                font=dict(size=10)
            ))
    
    # Calculate price difference percentages compared to our price
    diff_values = [(v - our_price) / our_price * 100 for v in values]
    
    # Add difference annotations
    for i, (cat, diff) in enumerate(zip(categories[1:], diff_values[1:])):
        angle = ((i + 1) / len(categories)) * 2 * np.pi
        r = normalized_values[i + 1] - 15  # Inside offset for difference
        
        # Color coding based on difference
        if diff < 0:
            color = "green"  # Competitor is cheaper
            diff_text = f"{abs(diff):.1f}% lower"
        elif diff > 0:
            color = "red"  # Competitor is more expensive
            diff_text = f"{diff:.1f}% higher"
        else:
            color = "black"
            diff_text = "Same price"
            
        annotations.append(dict(
            x=r * np.cos(angle),
            y=r * np.sin(angle),
            text=diff_text,
            showarrow=False,
            font=dict(size=9, color=color)
        ))
    
    # Update layout
    fig.update_layout(
        polar=dict(
            radialaxis=dict(
                visible=True,
                range=[0, 120]
            )
        ),
        title=f"Price Comparison Radar for {product_name}",
        annotations=annotations,
        height=600
    )
    
    return fig


def create_price_parity_chart(price_history_df, product_name):
    """
    Create an interactive bubble chart showing price parity across time
    
    Args:
        price_history_df (DataFrame): Price history data
        product_name (str): Name of the product
        
    Returns:
        plotly.graph_objects.Figure: Plotly figure object
    """
    # Create empty figure for error cases
    empty_fig = go.Figure()
    
    # Check if dataframe is empty or too small
    if price_history_df.empty or len(price_history_df) < 2:
        empty_fig.add_annotation(
            text="Not enough price history data available",
            showarrow=False,
            font=dict(size=16)
        )
        empty_fig.update_layout(
            title=f"Insufficient price history for {product_name}",
            height=500
        )
        return empty_fig
    
    # Safely process the data
    try:
        # Create a list to hold our data rows
        data_rows = []
        
        for idx, row in price_history_df.iterrows():
            date = row['timestamp']
            our_price = row['our_price']
            
            # Skip if competitor_prices is not a dict
            if not isinstance(row.get('competitor_prices'), dict):
                continue
            
            for competitor, price in row['competitor_prices'].items():
                # Skip invalid prices
                if price is None or not isinstance(price, (int, float)) or price <= 0:
                    continue
                    
                # Skip invalid our_price
                if our_price is None or not isinstance(our_price, (int, float)) or our_price <= 0:
                    continue
                
                # Calculate metrics
                try:
                    price_diff = ((price - our_price) / our_price) * 100
                    relative_price = price / our_price
                    
                    # Only add valid calculations
                    data_rows.append({
                        'date': date,
                        'competitor': competitor,
                        'our_price': our_price,
                        'competitor_price': price,
                        'price_diff_pct': price_diff,
                        'relative_price': relative_price
                    })
                except (TypeError, ZeroDivisionError):
                    continue
        
        # Create dataframe from the valid data rows 
        if not data_rows:
            empty_fig.add_annotation(
                text="No valid price comparison data available",
                showarrow=False,
                font=dict(size=16)
            )
            empty_fig.update_layout(
                title=f"No valid comparison data for {product_name}",
                height=500
            )
            return empty_fig
            
        comparison_df = pd.DataFrame(data_rows)
        
        # Check for empty dataframe after processing
        if comparison_df.empty:
            empty_fig.add_annotation(
                text="No valid price comparison data available after processing",
                showarrow=False,
                font=dict(size=16)
            )
            empty_fig.update_layout(
                title=f"No valid comparison data for {product_name}",
                height=500
            )
            return empty_fig
        
        # Create bubble chart with error handling
        fig = go.Figure()
        
        # Add a scatter trace for each competitor
        for competitor in comparison_df['competitor'].unique():
            df_comp = comparison_df[comparison_df['competitor'] == competitor]
            
            # Add scatter plot
            fig.add_trace(go.Scatter(
                x=df_comp['date'],
                y=[competitor] * len(df_comp),
                mode='markers',
                marker=dict(
                    size=df_comp['competitor_price'],
                    sizemode='area',
                    sizeref=2.*max(comparison_df['competitor_price'])/(40.**2),
                    sizemin=4,
                    color=df_comp['price_diff_pct'],
                    colorscale='RdBu_r',
                    cmin=-20,
                    cmax=20,
                    colorbar=dict(
                        title='Price Difference (%)',
                        tickvals=[-20, -10, 0, 10, 20],
                        ticktext=['-20%', '-10%', '0%', '+10%', '+20%'],
                    ),
                ),
                name=competitor,
                hovertemplate='<b>%{text}</b><br>' +
                              'Date: %{x}<br>' +
                              'Our Price: €%{customdata[0]:.2f}<br>' +
                              'Competitor Price: €%{customdata[1]:.2f}<br>' +
                              'Difference: %{customdata[2]:.1f}%<br>' +
                              '<extra></extra>',
                text=[competitor] * len(df_comp),
                customdata=np.column_stack((
                    df_comp['our_price'], 
                    df_comp['competitor_price'],
                    df_comp['price_diff_pct']
                ))
            ))
        
        # Customize layout
        fig.update_layout(
            title=f'Price Parity Analysis for {product_name}',
            height=max(300, len(comparison_df['competitor'].unique()) * 100 + 100),
            hovermode='closest',
            xaxis=dict(
                title='Date',
                showgrid=True,
                gridcolor='rgba(211,211,211,0.3)'
            ),
            yaxis=dict(
                title='Competitor',
                showgrid=True,
                gridcolor='rgba(211,211,211,0.3)'
            ),
            plot_bgcolor='white'
        )
        
        return fig
        
    except Exception as e:
        # Handle any unexpected errors
        empty_fig.add_annotation(
            text=f"Error creating chart: {str(e)}",
            showarrow=False,
            font=dict(size=16)
        )
        empty_fig.update_layout(
            title=f"Error in chart for {product_name}",
            height=500
        )
        return empty_fig