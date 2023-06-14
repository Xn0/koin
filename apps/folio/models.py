import datetime
import redis
import logging
import json
import pandas
from typing import Literal
from django.db import models
from django.conf import settings
from django.contrib.auth.models import User

PERIOD = Literal['DAILY', 'WEEKLY']

redis_instance = redis.StrictRedis(host=settings.REDIS_HOST,
                                   port=settings.REDIS_PORT,
                                   db=1)

class CommonInfo(models.Model):
    owner = models.ForeignKey(User, on_delete=models.CASCADE)
    ticker = models.CharField(max_length=5)
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
        if self.ticker != 'USD' and self.amount < 0:
            position = Position.objects.get(ticker=self.ticker, owner=self.owner)
            if (position.amount + self.amount) < 0:
                self.amount = -position.amount

        return super(Transaction, self).save(*args, **kwargs)

    def __str__(self):
        return super(Transaction, self).__str__() + f' | {self.date}'


class Position(CommonInfo):
    low_price_level = models.FloatField(default=0)
    high_price_level = models.FloatField(default=0)
    transactions_list = models.JSONField(default=dict)

    class Meta:
        unique_together = ['ticker', 'owner']

    def calculate(self) -> None:
        # Calculate or update the position
        transactions = Transaction.objects.filter(ticker=self.ticker).filter(
            owner=self.owner)

        # delete Position in no transactions left
        if not transactions:
            self.delete()
            return None

        # Build list of all transactions
        self.transactions_list = [{
            'timestamp': t.date.strftime('%Y-%m-%d'),
            'amount': t.amount,
            'money': t.amount * t.price,
        } for t in transactions]

        # Total volume of all transactions
        self.amount = sum(t.amount for t in transactions)

        # Average buy price
        if self.amount:
            self.price = sum(t.price * t.amount for t in transactions) / self.amount
        else:
            self.price = 0

        # Set signal levels
        self.low_price_level = self.price / 2
        self.high_price_level = self.price * 2

        self.save()

    def build_dataframe(self) -> pandas.DataFrame:
        df = pandas.DataFrame(self.transactions_list)
        df['timestamp'] = pandas.to_datetime(df['timestamp'])
        df = df.sort_values(by='timestamp')
        df_first_date = df.min()['timestamp']

        # Merge all transactions from the same day in to the one
        df = df.groupby(['timestamp'])[['amount', 'money']].sum()

        # Create data frame with a date range from the earliest transaction date
        # to today and merge with transaction df
        date_range = pandas.date_range(df_first_date, datetime.date.today(),
                                       freq='D')
        df_dates = pandas.DataFrame({'timestamp': date_range})
        df_merged = df_dates.merge(df, on='timestamp', how='left')

        # Replace NaN values in 'amount' column with 0
        df_merged['amount'] = df_merged['amount'].fillna(0)
        df_merged['money'] = df_merged['money'].fillna(0)

        # Add total amount column and calculate it
        df_merged['total'] = df_merged['amount'].cumsum()
        df_merged['total_money'] = df_merged['money'].cumsum()
        df_merged.set_index('timestamp', inplace=True)

        return df_merged


    def get_data_redis(self, period: PERIOD) -> pandas.DataFrame:
        """
        Get OHLC data from Redis
        :param period: 'DAILY' or 'WEEKLY'
        :return: OHLC data frame
        """
        data = json.loads(redis_instance.get(f'{self.ticker}_{period}'))
        df = pandas.DataFrame.from_dict(data, orient='index')
        df.index.name = 'timestamp'

        # convert columns type
        df.index = pandas.to_datetime(df.index)
        df = df.astype(float)

        return df


    def build_ohlc_df(self, period: PERIOD) -> pandas.DataFrame:
        """
        Build OHLC data frame
        :param period: 'DAILY' or 'WEEKLY'
        :return: OHLC data frame
        """
        df = self.build_dataframe()
        ohlc_df = self.get_data_redis(period)

        # merge OHLC data with position data
        ohlc_df = ohlc_df.join(df, on='timestamp', how='left')

        # multiply OHLC values by total amount of position
        ohlc_df['open'] *= ohlc_df['total']
        ohlc_df['high'] *= ohlc_df['total']
        ohlc_df['low'] *= ohlc_df['total']
        ohlc_df['close'] *= ohlc_df['total']

        return ohlc_df


    def build_ohlc_weekly(self) -> pandas.DataFrame:
        """
        Build OHLC data frame for weekly period
        :return: OHLC data frame
        """
        return self.build_ohlc_df('WEEKLY')


    def build_ohlc_daily(self) -> pandas.DataFrame:
        """
        Build OHLC data frame for daily period
        :return: OHLC data frame
        """
        return self.build_ohlc_df('DAILY')