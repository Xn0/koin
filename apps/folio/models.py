import datetime
import logging
import pandas
from typing import Literal
from django.db import models
from django.conf import settings
from django.core.cache import cache
from django.db.models import F, Q
from django.contrib.auth.models import User

PERIOD = Literal['DAILY', 'WEEKLY']


class Ticker(models.Model):
    ticker = models.CharField(max_length=10, unique=True)
    name = models.CharField(max_length=50)

    def __str__(self):
        return self.ticker


class ChartManager(models.Manager):
    def get_ohlc_df(self, ticker: Ticker) -> pandas.DataFrame | None:
        """
        Get OHLC data from cache or database
        """
        key = f'Chart_{datetime.date.today().strftime("%Y-%m-%d")}_' \
              f'{self.model.__name__}_{ticker}'
        df = cache.get(key)
        if df is None:
            df = self._build_ohlc_df(ticker)
            if df is not None:
                cache.set(key, df)
        return df

    def _build_ohlc_df(self, ticker: Ticker) -> pandas.DataFrame | None:
        """
        Get OHLC data from database
        """
        if ticker.ticker == 'USD':
            return self._build_usd_df()

        q = self.model.objects.filter(ticker=ticker)
        if not q.exists():
            return None
        df = pandas.DataFrame.from_records(
            q.values('date', 'open', 'high', 'low', 'close'))
        df.set_index('date', inplace=True)
        df.index = pandas.to_datetime(df.index)
        return df

    def _build_usd_df(self) -> pandas.DataFrame:
        """
        Generate dataframe with USD OHLC data
        """
        q = self.model.objects.filter(ticker__ticker__exact='BTC')
        df = pandas.DataFrame.from_records(q.values('date'))
        df['open'] = df['high'] = df['low'] = df['close'] = 1
        df.set_index('date', inplace=True)
        df.index = pandas.to_datetime(df.index)
        return df


class Chart(models.Model):
    ticker = models.ForeignKey(Ticker, on_delete=models.CASCADE)
    date = models.DateField(default=datetime.date.fromisoformat('2000-01-01'))
    open = models.FloatField(default=0)
    high = models.FloatField(default=0)
    low = models.FloatField(default=0)
    close = models.FloatField(default=0)
    objects = ChartManager()

    class Meta:
        unique_together = ['ticker', 'date']
        ordering = ['-date']
        abstract = True

    def __str__(self):
        return f'{self.ticker} | {self.date}'


class WeeklyChart(Chart):
    ...

class DailyChart(Chart):
    ...


class CommonInfo(models.Model):
    owner = models.ForeignKey(User, on_delete=models.CASCADE)
    ticker = models.ForeignKey(Ticker, on_delete=models.PROTECT)
    amount = models.FloatField(default=0)
    price = models.FloatField(default=0)

    class Meta:
        abstract = True

    def __str__(self):
        return f'{self.amount} {self.ticker} | ${self.price:.2f} | {self.owner}'


class Transaction(CommonInfo):
    date = models.DateField(default=datetime.date.today)
    usd_transaction = models.OneToOneField(
        'self',
        on_delete=models.CASCADE,
        related_name='ticker_transactions',
        blank=True,
        null=True,
    )

    class Meta:
        ordering = ['date']

    def save(self, *args, **kwargs):
        """
        Checking that a negative transaction does not exceed the position amount,
         and if it true change transaction amount to equal negative.
        """
        if self.ticker.ticker != 'USD' and self.amount < 0:
            position = Position.objects.get(ticker=self.ticker,
                                            owner=self.owner)
            if (position.amount + self.amount) < 0:
                self.amount = -position.amount

        return super(Transaction, self).save(*args, **kwargs)

    def __str__(self):
        return super(Transaction, self).__str__() + f' | {self.date}'


class Position(CommonInfo):
    transactions_list = models.JSONField(default=dict)
    # signal levels
    low_price_level = models.FloatField(default=0)
    high_price_level = models.FloatField(default=0)

    class Meta:
        unique_together = ['ticker', 'owner']

    def calculate(self) -> None:
        # Calculate or update position
        transactions = Transaction.objects.filter(ticker=self.ticker).filter(
            owner=self.owner)

        # delete Position in no transactions left
        if not transactions:
            self.delete()
            return None

        # Build list of all transactions
        self.transactions_list = [{
            'date': t.date.strftime('%Y-%m-%d'),
            'amount': t.amount,
            'money': t.amount * t.price,
        } for t in transactions]

        # Total volume of all transactions
        self.amount = sum(t.amount for t in transactions)

        # Average buy price
        if self.amount:
            self.price = sum(
                t.price * t.amount for t in transactions) / self.amount
        else:
            self.price = 0

        # Set signal levels
        self.low_price_level = self.price / 2
        self.high_price_level = self.price * 2

        self.save()

    def _build_dataframe(self) -> pandas.DataFrame:
        df = pandas.DataFrame(self.transactions_list)
        df['date'] = pandas.to_datetime(df['date'])
        df = df.sort_values(by='date')
        df_first_date = df.min()['date']

        # Merge all transactions from the same day in to the one
        df = df.groupby(['date'])[['amount', 'money']].sum()

        # Create data frame with a date range from the earliest transaction date
        # to today and merge with transaction df
        date_range = pandas.date_range(df_first_date, datetime.date.today(),
                                       freq='D')
        df_dates = pandas.DataFrame({'date': date_range})
        df = df_dates.merge(df, on='date', how='left')

        # Replace NaN values in 'amount' and 'money' column with 0
        df['amount'] = df['amount'].fillna(0)
        df['money'] = df['money'].fillna(0)

        # Add total amount and total_money column and calculate cumulative sum
        df['total'] = df['amount'].cumsum()
        df['total_money'] = df['money'].cumsum()
        df.set_index('date', inplace=True)

        return df

    def _build_ohlc_df(self, ohlc_df: pandas.DataFrame) -> pandas.DataFrame:

        df = self._build_dataframe()

        # merge OHLC data with position data
        ohlc_df = ohlc_df.join(df, on='date', how='left')

        # multiply OHLC values by total amount of position
        ohlc_df['open'] *= ohlc_df['total']
        ohlc_df['high'] *= ohlc_df['total']
        ohlc_df['low'] *= ohlc_df['total']
        ohlc_df['close'] *= ohlc_df['total']

        return ohlc_df

    def build_ohlc_weekly(self) -> pandas.DataFrame:
        """
        Build OHLC data frame for weekly period
        """
        df = WeeklyChart.objects.get_ohlc_df(self.ticker)
        return self._build_ohlc_df(df)

    def build_ohlc_daily(self) -> pandas.DataFrame:
        """
        Build OHLC data frame for daily period
        """
        df = DailyChart.objects.get_ohlc_df(self.ticker)
        return self._build_ohlc_df(df)
