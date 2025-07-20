# -*- coding: utf-8 -*-
"""
Created on Sun Jul 20 21:02:34 2025

@author: Hemal
"""
import requests
import pandas as pd
import numpy as np
from datetime import datetime

# Function to round to nearest strike price (NIFTY uses 50-point intervals)
def round_nearest_strike(x, num=50):
    return int(np.ceil(float(x) / num) * num)

# Function to calculate weighted average price
def calculate_weighted_avg_price(df, atm_strike, price_col, strike_interval=50):
    # Calculate weights: Inverse distance from ATM strike
    df['distance'] = abs(df['strikePrice'] - atm_strike)
    df['weight'] = 1 / (1 + df['distance'] / strike_interval)  # Weight formula
    # Calculate weighted price
    df['weighted_price'] = df[price_col] * df['weight']
    weighted_avg_price = df['weighted_price'].sum() / df['weight'].sum()
    return weighted_avg_price

# Headers for NSE API request
headers = {
    'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/80.0.3987.149 Safari/537.36',
    'accept-language': 'en,gu;q=0.9,hi;q=0.8',
    'accept-encoding': 'gzip, deflate, br'
}

# Initialize session
session = requests.Session()

# Function to set cookies
def set_cookie():
    url_oc = "https://www.nseindia.com/option-chain"
    response = session.get(url_oc, headers=headers, timeout=5)
    return dict(response.cookies)

# Function to fetch option chain data
def get_option_chain(symbol, expiry_date):
    url = f"https://www.nseindia.com/api/option-chain-indices?symbol={symbol}"
    cookies = set_cookie()
    response = session.get(url, headers=headers, cookies=cookies, timeout=5)
    if response.status_code == 200:
        return response.json()
    else:
        raise Exception(f"Failed to fetch data: {response.status_code}")

# Main function to process option chain
def process_option_chain(symbol="NIFTY", expiry_date=None):
    # Fetch option chain data
    data = get_option_chain(symbol, expiry_date)
    
    # Get underlying value (LTP of the symbol)
    underlying_price = data['records']['underlyingValue']
    
    # Get all expiry dates and select the nearest one if not provided
    expiry_dates = data['records']['expiryDates']
    if not expiry_date:
        expiry_date = expiry_dates[0]  # Select nearest expiry
    
    # Filter data for the selected expiry
    filtered_data = [d for d in data['records']['data'] if d['expiryDate'] == expiry_date]
    
    # Create DataFrame
    df = pd.DataFrame(filtered_data)
    
    # Initialize lists for CE and PE data
    ce_data = []
    pe_data = []
    
    for index, row in df.iterrows():
        strike = row['strikePrice']
        if 'CE' in row:
            ce_data.append({
                'strikePrice': strike,
                'lastPrice': row['CE']['lastPrice'],
                'openInterest': row['CE']['openInterest'],
                'changeinOpenInterest': row['CE']['changeinOpenInterest'],
                'impliedVolatility': row['CE']['impliedVolatility']
            })
        if 'PE' in row:
            pe_data.append({
                'strikePrice': strike,
                'lastPrice': row['PE']['lastPrice'],
                'openInterest': row['PE']['openInterest'],
                'changeinOpenInterest': row['PE']['changeinOpenInterest'],
                'impliedVolatility': row['PE']['impliedVolatility']
            })
    
    ce_df = pd.DataFrame(ce_data)
    pe_df = pd.DataFrame(pe_data)
    
    # Find ATM strike
    atm_strike = round_nearest_strike(underlying_price)
    
    # Filter for 10 strikes above and below ATM
    strike_range = 10 * 50  # 10 strikes, assuming 50-point intervals
    ce_filtered = ce_df[(ce_df['strikePrice'] >= atm_strike - strike_range) & 
                       (ce_df['strikePrice'] <= atm_strike + strike_range)]
    pe_filtered = pe_df[(pe_df['strikePrice'] >= atm_strike - strike_range) & 
                       (pe_df['strikePrice'] <= atm_strike + strike_range)]
    
    # Sort by strike price
    ce_filtered = ce_filtered.sort_values('strikePrice')
    pe_filtered = pe_filtered.sort_values('strikePrice')
    
    # Calculate weighted average prices
    ce_weighted_avg = calculate_weighted_avg_price(ce_filtered, atm_strike, 'lastPrice')
    pe_weighted_avg = calculate_weighted_avg_price(pe_filtered, atm_strike, 'lastPrice')
    
    # Merge CE and PE data
    option_chain = ce_filtered.merge(pe_filtered, on='strikePrice', suffixes=('_CE', '_PE'), how='outer')
    
    return option_chain, atm_strike, underlying_price, ce_weighted_avg, pe_weighted_avg

# Execute and display results
if __name__ == "__main__":
    try:
        # User input for ticker symbol
        symbol = input("Enter ticker symbol (e.g., NIFTY, BANKNIFTY): ").strip().upper() or "NIFTY"
        
        # Fetch and process option chain
        option_chain_df, atm_strike, underlying_price, ce_weighted_avg, pe_weighted_avg = process_option_chain(symbol=symbol)
        
        # Print results
        print(f"Underlying Price ({symbol}): {underlying_price}")
        print(f"ATM Strike: {atm_strike}")
        print(f"Weighted Average Price (CE): {ce_weighted_avg:.2f}")
        print(f"Weighted Average Price (PE): {pe_weighted_avg:.2f}")
        print("\nOption Chain Data (10 strikes above and below ATM):")
        print(option_chain_df[['strikePrice', 
                              'lastPrice_CE', 'openInterest_CE', 'impliedVolatility_CE',
                              'lastPrice_PE', 'openInterest_PE', 'impliedVolatility_PE']])
        
        # Save to CSV
        option_chain_df.to_csv(f'{symbol.lower()}_option_chain.csv', index=False)
        print(f"\nData saved to '{symbol.lower()}_option_chain.csv'")
        
    except Exception as e:
        print(f"Error: {str(e)}")
