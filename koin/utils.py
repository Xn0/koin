import pandas
import logging
import requests
from typing import Literal
import plotly.graph_objects as go
from django.conf import settings
from django.contrib.auth.models import User
from apps.folio.models import Position

PERIOD = Literal['DAILY', 'WEEKLY']

logger = logging.getLogger(__name__)

# TODO add cache

def get_data_alphavantage(ticker: str, period: PERIOD) -> None:
    """
    Get data from AlphaVantage API and save it to csv file
    TODO save to redis

    TODO mb I should rename all columns and remove unnecessary, /
    TODO / it can be usefull if I'll use some other extra source of data

    :param ticker:
    :param period: DAILY or WEEKLY
    """
    apikey = settings.ALPHAVANTAGE_KEY
    api_response = requests.get(
        f'https://www.alphavantage.co/query?function=DIGITAL_CURRENCY_{period}&symbol={ticker}&market=USD&apikey={apikey}&datatype=csv'
    )
    with open(f'{ticker}_{period}.csv', 'wb') as the_file:
        the_file.write(api_response.content)


def ticker_chart_df(
        ticker: str,
        user: User,
        period: PERIOD
) -> pandas.DataFrame:
    """
    Build dataframe with OHLC data of position value by days
    for given ticker and user

    :param ticker: ticker
    :param user: user
    :param period: WEEKLY or DAILY
    :return: dataframe with OHLC data of position value by days/weeks
    """

    df_pos = Position.objects.get(ticker=ticker, owner=user).build_dataframe()
    # hack to make ohlc data for USD
    if ticker == 'USD':
        df_ohlc = pandas.read_csv(f'BTC_{period}.csv')
        df_ohlc['open (USD)'] = 1
        df_ohlc['high (USD)'] = 1
        df_ohlc['low (USD)'] = 1
        df_ohlc['close (USD)'] = 1
    else:
        df_ohlc = pandas.read_csv(f'{ticker}_{period}.csv') # TODO get data from redis

    df_ohlc['timestamp'] = pandas.to_datetime(df_ohlc['timestamp'])
    df_ohlc = df_ohlc.merge(df_pos, on='timestamp', how='left')

    # multiply OHLC prices by total amount of position
    df_ohlc['open (USD)'] *= df_ohlc['total']
    df_ohlc['high (USD)'] *= df_ohlc['total']
    df_ohlc['low (USD)'] *= df_ohlc['total']
    df_ohlc['close (USD)'] *= df_ohlc['total']

    return df_ohlc


def merge_chart_df(df_list: list) -> pandas.DataFrame:
    """
    Merge dataframes from list to one dataframe

    :param df_list: list of dataframes
    :return: merged dataframe
    """
    final_df = df_list[0]

    for df in df_list[1:]:
        final_df['open (USD)'] += df['open (USD)']
        final_df['high (USD)'] += df['high (USD)']
        final_df['low (USD)'] += df['low (USD)']
        final_df['close (USD)'] += df['close (USD)']
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
    df = df.drop(df[df['open (USD)'].isnull()].index)

    data = [
        go.Candlestick(
            x=df['timestamp'],
            open=df['open (USD)'],
            high=df['high (USD)'],
            low=df['low (USD)'],
            close=df['close (USD)'])
    ]
    if show_investments:
        data.append(
            go.Scatter(
                x=df['timestamp'],
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
