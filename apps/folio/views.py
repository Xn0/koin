import logging
from django.views.generic import TemplateView
from django.shortcuts import render
from django.contrib.auth.decorators import user_passes_test
from django.views.decorators.cache import cache_page
from .charts import make_chart, merge_chart_df
from .alphavantage import get_data
from .models import Position

logger = logging.getLogger(__name__)

# @cache_page(60 * 15) # TODO
def homepage(request):
    # TODO TemplateView
    # get_data('USD', 'WEEKLY')
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


@user_passes_test(lambda u: u.is_superuser)
def logs_view(request):
    with open('general.log', 'r') as f:
        logs = [line.strip() for line in f]
    return render(request, 'logs.html', {'logs': logs})