import datetime
import logging
import pandas
from django.db import models
from django.conf import settings
from django.contrib.auth.models import User


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

    class Meta:
        ordering = ['date']

    def __str__(self):
        return super(Transaction, self).__str__() + f' | {self.date}'

    def save(self, *args, **kwargs):
        Position.objects.get_or_create(owner=self.owner, ticker=self.ticker)
        # TODO send signal or call Position.calculate method
        # TODO add USD transaction, maybe create transaction with
        #  self Foreign key for USD transaction
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        # TODO send signal or call Position.calculate method
        # TODO remove USD transaction
        return super().delete(*args, **kwargs)


class Position(CommonInfo):
    low_price_level = models.FloatField(default=0)
    high_price_level = models.FloatField(default=0)
    trans_list = models.JSONField(default=dict)

    class Meta:
        unique_together = ['ticker', 'owner']

    def calculate(self) -> None:
        # Calculate or update the position
        transactions = Transaction.objects.filter(ticker=self.ticker).filter(
            owner=self.owner)

        # Build list of all transactions
        self.trans_list = [{
            'timestamp': t.date.strftime('%Y-%m-%d'),
            'amount': t.amount,
        } for t in transactions]

        # Total volume of all transactions
        self.amount = sum(t.amount for t in transactions)
        # Average price
        self.price = sum(t.price * t.amount for t in transactions) / self.amount

        # Set signal levels
        self.low_price_level = self.price / 2
        self.high_price_level = self.price * 2

        self.save()

    def build_dataframe(self) -> pandas.DataFrame:
        """
        Build a pandas DataFrame from the transaction list associated with
         current model.
        """
        df = pandas.DataFrame(self.trans_list)
        df['timestamp'] = pandas.to_datetime(df['timestamp'])
        df = df.sort_values(by='timestamp')

        # Create data frame with a date range from the first transaction date
        # to today and merge with transaction df
        init_date = df['timestamp'].min()
        date_range = pandas.date_range(init_date, datetime.date.today(),
                                       freq='D')
        df_dates = pandas.DataFrame({'timestamp': date_range})
        df_merged = df_dates.merge(df, on='timestamp', how='left')

        # Replace NaN values in 'amount' column with 0
        df_merged['amount'] = df_merged['amount'].fillna(0)

        # Add total amount column and calculate it
        df_merged['total'] = df_merged['amount'].cumsum()

        if settings.DEBUG:
            df_merged.to_csv('dataframe.csv', index=False)

        return df_merged
