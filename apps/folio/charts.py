import pandas
import plotly.graph_objects as go


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