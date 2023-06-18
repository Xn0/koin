import pandas
import io
import logging
import requests
import json
from typing import Literal, Type
from django.conf import settings
from .models import DailyChart, Chart, WeeklyChart, Ticker

PERIOD = Literal['DAILY', 'WEEKLY']

logger = logging.getLogger(__name__)


def get_data(ticker: str, period: PERIOD) -> bytes | None:
    apikey = settings.ALPHAVANTAGE_KEY
    api_response = requests.get(
        'https://www.alphavantage.co/query?function=' +
        f'DIGITAL_CURRENCY_{period}&symbol={ticker}&market=USD&apikey={apikey}'
    )
    if api_response.status_code != 200 or b'close' not in api_response.content:
        logger.error(
            f'API response error. Ticker: {ticker}, period: {period},' +
            f' code: {api_response.status_code},' +
            f' content: {api_response.content}'
        )
        return
    return api_response.content


def normalize_data(data: json) -> pandas.DataFrame | None:
    if not data:
        return
    data = json.loads(data)
    # remove unnecessary data and extra nesting level
    data.pop('Meta Data')
    data = data[list(data.keys())[0]]
    # convert to pandas dataframe and drop unnecessary columns
    df = pandas.DataFrame.from_dict(data, orient='index')
    df.index = pandas.to_datetime(df.index)
    df.drop(
        columns=[
            '1a. open (USD)', '2a. high (USD)', '3a. low (USD)',
            '4a. close (USD)', '5. volume', '6. market cap (USD)'
        ],
        inplace=True,
        axis=1)
    # rename columns
    df.rename(
        columns={
            '1b. open (USD)': 'open',
            '2b. high (USD)': 'high',
            '3b. low (USD)': 'low',
            '4b. close (USD)': 'close',
        },
        inplace=True
    )
    return df


def store_to_db(ticker: str, data: bytes, model: Type[Chart]) -> None:
    df = normalize_data(data)
    if ticker == 'USD' or df is None:
        return
    q = model.objects.filter(ticker=ticker).order_by('-date')
    if q.exists():
        # slice df to include only new data
        # plus the last row because its data may be before close of the market
        latest_date = q[1].date
        df = df.loc[(df.index.date > latest_date)]
    for index, row in df.iterrows():
        model.objects.create(
            ticker=ticker,
            date=index,
            open=row['open'],
            high=row['high'],
            low=row['low'],
            close=row['close']
        )


def store_to_db_weekly(ticker: str) -> None:
    data = get_data(ticker, 'WEEKLY')
    store_to_db(ticker, data, WeeklyChart)


def store_to_db_daily(ticker: str) -> None:
    data = get_data(ticker, 'DAILY')
    store_to_db(ticker, data, DailyChart)


def get_tickers() -> bytes | None:
    response = requests.get(
        'https://www.alphavantage.co/digital_currency_list/')
    if response.status_code != 200 or b'BTC' not in response.content:
        logger.error(
            f'Tickers list request error. code: {response.status_code},' +
            f' content: {response.content}'
        )
        return
    return response.content


def make_tickers_df(data: bytes) -> pandas.DataFrame | None:
    if not data:
        return
    return pandas.read_csv(io.StringIO(data.decode('utf-8')))


def update_tickers(df: pandas.DataFrame) -> None:
    for _, row in df.iterrows():
        Ticker.objects.get_or_create(
            ticker=row['currency code'],
            name=row['currency name']
        )
