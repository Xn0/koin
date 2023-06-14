import pandas
import logging
import requests
import redis
import json
from typing import Literal
import plotly.graph_objects as go
from django.conf import settings

PERIOD = Literal['DAILY', 'WEEKLY']

redis_instance = redis.StrictRedis(host=settings.REDIS_HOST,
                                   port=settings.REDIS_PORT,
                                   db=1)

logger = logging.getLogger(__name__)


# TODO mb rewrite in OOP style

def get_data_alphavantage(ticker: str, period: PERIOD) -> None:
    apikey = settings.ALPHAVANTAGE_KEY
    api_response = requests.get(  # TODO change market to USD
        f'https://www.alphavantage.co/query?function=DIGITAL_CURRENCY_{period}&symbol={ticker}&market=EUR&apikey={apikey}'
    )
    data = json.loads(api_response.content)
    # remove unnecessary data and extra nesting level
    data.pop('Meta Data')
    data = data[list(data.keys())[0]]
    # convert to pandas dataframe and drop unnecessary columns
    df = pandas.DataFrame.from_dict(data, orient='index')
    df.drop(
        columns=[
        '1a. open (EUR)', '2a. high (EUR)', '3a. low (EUR)',
        '4a. close (EUR)', '5. volume', '6. market cap (USD)'
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

    redis_instance.set(f'{ticker}_{period}', df.to_json(orient='index'))


def fake_usd_df(period: PERIOD) -> None:
    """
    Create dataframe with OHLC data of USD
    :param period: DAILY or WEEKLY
    """
    data = json.loads(redis_instance.get(f'BTC_{period}'))
    df = pandas.DataFrame.from_dict(data, orient='index')
    df['open'] = 1
    df['high'] = 1
    df['low'] = 1
    df['close'] = 1
    redis_instance.set(f'USD_{period}', df.to_json(orient='index'))


def merge_chart_df(df_list: list) -> pandas.DataFrame:
    """
    Merge dataframes from list to one dataframe

    :param df_list: list of dataframes
    :return: merged dataframe
    """
    final_df = df_list[0]

    for df in df_list[1:]:
        final_df['open'] += df['open']
        final_df['high'] += df['high']
        final_df['low'] += df['low']
        final_df['close'] += df['close']
        final_df['total_money'] += df['total_money']
    return final_df


def make_chart(df: pandas.DataFrame, show_investments=False) -> str:
    """
    This function makes a candlestick chart from dataframe with
    optional line chart of the invest amount

    :param df: dataframe with OHLC data
    :param show_investments: dataframe with cumulative invests amount
    :return: html code of chart
    """

    # remove all empty rows
    df = df.drop(df[df['open'].isnull()].index)

    data = [
        go.Candlestick(
            x=df.index,
            open=df['open'],
            high=df['high'],
            low=df['low'],
            close=df['close'])
    ]
    if show_investments:
        data.append(
            go.Scatter(
                x=df.index,
                y=df['total_money'],
            )
        )

    fig = go.Figure(data)
    fig.update_xaxes(
        type='category',
        visible=False,
        autorange="reversed",
    )
    # chart layout settings
    fig.update_layout(
        xaxis_rangeslider_visible=False,
        margin=dict(l=30, r=10, t=20, b=20),
        showlegend=False,
        height=300,
    )
    return fig.to_html(full_html=False, config={'displayModeBar': False})