import requests
import pandas
from typing import Literal
import plotly.graph_objects as go
from django.shortcuts import render
from django.conf import settings

PERIOD = Literal['DAILY', 'WEEKLY']


def get_data(ticker: str, period: PERIOD) -> None:
    apikey = settings.ALPHAVANTAGE_KEY
    api_response = requests.get(
        f'https://www.alphavantage.co/query?function=DIGITAL_CURRENCY_{period}&symbol={ticker}&market=USD&apikey={apikey}&datatype=csv'
    )
    with open(f'{ticker}_{period}.csv', 'wb') as the_file:
        the_file.write(api_response.content)
    return


def parse_csv(ticker: str, period: PERIOD) -> pandas.DataFrame:
    df = pandas.read_csv(f'{ticker}_{period}.csv')
    return df


def make_chart(df:pandas.DataFrame, df_entry_v=None) -> str:
    data = [
        go.Candlestick(
            x=df['timestamp'],
            open=df['open (USD)'],
            high=df['high (USD)'],
            low=df['low (USD)'],
            close=df['close (USD)'])
    ]
    if df_entry_v:
        data.append(
            go.Scatter(
                # TODO change later to invest amount in USD
                x=df['timestamp'],
                y=df['volume'] / 100,
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


def folio(request):
    # TODO TemplateView
    # get_data('BTC', 'WEEKLY')
    # get_data('BTC', 'DAILY')

    df_weekly = parse_csv('BTC', 'WEEKLY')
    df_daily = parse_csv('BTC', 'DAILY')[:30]
    context = {'chart_daily': make_chart(df_daily),
               'chart_weekly': make_chart(df_weekly, True)}
    return render(request, 'folio.html', context)
