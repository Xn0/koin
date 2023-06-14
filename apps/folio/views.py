import logging
from django.shortcuts import render
from django.views.decorators.cache import cache_page
from koin.utils import get_data_alphavantage, make_chart, merge_chart_df, fake_usd_df
from .models import Position

logger = logging.getLogger(__name__)

# @cache_page(60 * 15) # TODO
def homepage(request):
    # TODO TemplateView
    # get_data_alphavantage('BTC', 'DAILY')
    # get_data_alphavantage('BTC', 'WEEKLY')
    # get_data_alphavantage('ETH', 'DAILY')
    # get_data_alphavantage('ETH', 'WEEKLY')
    # fake_usd_df('WEEKLY')
    # fake_usd_df('DAILY')

    weekly_df = merge_chart_df(
        [
            position.build_ohlc_weekly() for position in
            request.user.position_set.exclude(ticker='USD')
        ])
    daily_delta_df = merge_chart_df(
        [
            position.build_ohlc_daily()[:30] for position in
            request.user.position_set.all()
        ])
    weekly_delta_df = merge_chart_df(
        [
            position.build_ohlc_weekly() for position in
            request.user.position_set.all()
        ])

    context = {
        'current_balance': daily_delta_df.iloc[0]['close'],
        'chart_daily_delta': make_chart(daily_delta_df),
        'chart_weekly_delta': make_chart(weekly_delta_df, True),
        'chart_weekly': make_chart(weekly_df, True),
    }
    return render(request, 'folio.html', context)


def position_detail(request, pk):
    # TODO ListView
    pass
