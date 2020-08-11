from datetime import datetime
import lxml
from lxml import html
import requests
import numpy as np
import pandas as pd

def get_page(url):
    # Set up the request headers that we're going to use, to simulate
    # a request by the Chrome browser. Simulating a request from a browser
    # is generally good practice when building a scraper
    headers = {
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3',
        'Accept-Encoding': 'gzip, deflate, br',
        'Accept-Language': 'en-US,en;q=0.9',
        'Cache-Control': 'max-age=0',
        'Pragma': 'no-cache',
        'Referrer': 'https://google.com',
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/77.0.3865.120 Safari/537.36'
    }

    return requests.get(url, headers=headers)

def parse_rows(table_rows):
    parsed_rows = []

    for table_row in table_rows:
        parsed_row = []
        el = table_row.xpath("./div")

        none_count = 0

        for rs in el:
            try:
                (text,) = rs.xpath('.//span/text()[1]')
                parsed_row.append(text)
            except ValueError:
                parsed_row.append(np.NaN)
                none_count += 1

        if (none_count < 4):
            parsed_rows.append(parsed_row)
            
    return pd.DataFrame(parsed_rows)

def clean_data(df):
    df = df.set_index(0) # Set the index to the first column: 'Period Ending'.
    df = df.transpose() # Transpose the DataFrame, so that our header contains the account names
    
    # Rename the "Breakdown" column to "Date"
    cols = list(df.columns)
    cols[0] = 'Date'
    df = df.set_axis(cols, axis='columns', inplace=False)
    
    numeric_columns = list(df.columns)[1::] # Take all columns, except the first (which is the 'Date' column)

    for column_index in range(1, len(df.columns)): # Take all columns, except the first (which is the 'Date' column)
        df.iloc[:,column_index] = df.iloc[:,column_index].str.replace(',', '') # Remove the thousands separator
        df.iloc[:,column_index] = df.iloc[:,column_index].astype(np.float64) # Convert the column to float64

    return df

def scrape_table(url):
    # Fetch the page that we're going to parse
    page = get_page(url)

    # Parse the page with LXML, so that we can start doing some XPATH queries
    # to extract the data that we want
    tree = html.fromstring(page.content)

    # Fetch all div elements which have class 'D(tbr)'
    table_rows = tree.xpath("//div[contains(@class, 'D(tbr)')]")
    
    # Ensure that some table rows are found; if none are found, then it's possible
    # that Yahoo Finance has changed their page layout, or have detected
    # that you're scraping the page.
    assert len(table_rows) > 0
    
    df = parse_rows(table_rows)
    df = clean_data(df)

    return df

def scrape_analysis(symbol):

    url = 'https://finance.yahoo.com/quote/' + symbol + '/analysis?p=' + symbol

    # Fetch the page that we're going to parse
    page = get_page(url)

    # Parse the page with LXML, so that we can start doing some XPATH queries
    # to extract the data that we want
    tree = html.fromstring(page.content)

    # Fetch all div elements which have class 'D(tbr)'
    tables = tree.xpath("//table[contains(@class, 'W(100%) M(0)')]")
    
    # Ensure that some table rows are found; if none are found, then it's possible
    # that Yahoo Finance has changed their page layout, or have detected
    # that you're scraping the page.
    
    name_to_table_map = {}
    df = pd.DataFrame()
    for i in range(0, len(tables)):
        table = tables[i]
        table_rows = table.xpath(".//tr")
        if i == len(tables) - 1:
            pr = parse_rows_analysis(table_rows, last=True)
        else:
            pr = parse_rows_analysis(table_rows)
        name_to_table_map[pr.loc[0, 0]] = pr.set_index(0)
        assert len(table_rows) > 0
        
    return name_to_table_map

def parse_rows_analysis(table_rows, last=False):
    parsed_rows = []
    
    for i in range(0, len(table_rows)):
        table_row = table_rows[i]
        el = table_row.xpath(".//td")
        if i == 0:
            el = table_row.xpath(".//th")
            
        parsed_row = []
        none_count = 0

        for j in range(len(el)):
            rs = el[j]
            try:
                t = rs.xpath('.//span/text()')
                if last and (j != 0 or i == 0):
                    t = rs.xpath('./text()')
                text = ""
                for txt in t:
                    text = text + txt
                parsed_row.append(text)
            except ValueError:
                parsed_row.append(np.NaN)
                none_count += 1

        if (none_count < 4):
            parsed_rows.append(parsed_row)

    return pd.DataFrame(parsed_rows)

def scrape_three_fs(symbol):
    print('Attempting to scrape data for ' + symbol)

    df_balance_sheet = scrape_table('https://finance.yahoo.com/quote/' + symbol + '/balance-sheet?p=' + symbol)
    df_balance_sheet = df_balance_sheet.set_index('Date')

    df_income_statement = scrape_table('https://finance.yahoo.com/quote/' + symbol + '/financials?p=' + symbol)
    df_income_statement = df_income_statement.set_index('Date')
    
    df_cash_flow = scrape_table('https://finance.yahoo.com/quote/' + symbol + '/cash-flow?p=' + symbol)
    df_cash_flow = df_cash_flow.set_index('Date')
    
    df_joined = df_balance_sheet \
        .join(df_income_statement, on='Date', how='outer', rsuffix=' - Income Statement') \
        .join(df_cash_flow, on='Date', how='outer', rsuffix=' - Cash Flow') \
        .dropna(axis=1, how='all') \
        .reset_index()
            
    df_joined.insert(1, 'Symbol', symbol)

    new_indices = []
    for i in range(len(df_joined) - 1):
        new_indices.append(len(df_joined) - 2 - i)
    new_indices.append(len(df_joined) - 1)
    df_joined = df_joined.reindex(new_indices)
    df_joined = df_joined.reset_index(drop=True)
    
    return df_joined

def scrape_multi(symbols):
    return pd.concat([scrape(symbol) for symbol in symbols], sort=False)