import datetime
import pandas
from django.db import models
from django.contrib.auth.models import User


class CommonInfo(models.Model):
    owner = models.ForeignKey(User, on_delete=models.CASCADE)
    ticker = models.CharField(max_length=5)
    amount = models.FloatField()
    price = models.FloatField()

    class Meta:
        abstract = True

    def __str__(self):
        return f'{self.amount} {self.ticker} | ${self.price} | {self.date}'


class Transaction(CommonInfo):
    date = models.DateField(default=datetime.date.today)

    class Meta:
        ordering = ['date']

    def save(self, *args, **kwargs):
        # TODO send signal or call Position.calculate method
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        # TODO send signal or call Position.calculate method
        return super().delete(*args, **kwargs)




class Position(CommonInfo):
    low_price_level = models.FloatField()
    high_price_level = models.FloatField()

    class Meta:
        unique_together = ['ticker', 'owner']

    def calculate(self):
        # Calculate or update the position
        pass

    def build_dataframe(self) -> pandas.DataFrame:
        pass
