from django.shortcuts import render
from koin.utils import get_data_alphavantage, ticker_chart_df, make_chart, \
    merge_chart_df
from .models import Position


def homepage(request):
    # TODO TemplateView
    tickers_list = request.user.position_set.values_list('ticker', flat=True)
    df_weekly_list = [ticker_chart_df(ticker, request.user, 'WEEKLY')
                      for ticker in tickers_list if ticker != 'USD']
    df_weekly_delta_list = [ticker_chart_df(ticker, request.user, 'WEEKLY')
                            for ticker in tickers_list]
    df_daily_delta_list = [ticker_chart_df(ticker, request.user, 'DAILY')[:30]
                            for ticker in tickers_list]
    # TODO make USD chart separately and add to delta charts
    df_weekly = merge_chart_df(df_weekly_list)
    df_weekly_delta = merge_chart_df(df_weekly_delta_list)
    df_daily_delta = merge_chart_df(df_daily_delta_list)
    current_balance = df_daily_delta.iloc[0]['close (USD)']
    context = {
               'chart_weekly': make_chart(df_weekly, True),
               'chart_weekly_delta': make_chart(df_weekly_delta, True),
               'chart_daily_delta': make_chart(df_daily_delta),
                'current_balance': current_balance,
               }
    return render(request, 'folio.html', context)


def postion_detail(request, pk):
    # TODO ListView
    pass
