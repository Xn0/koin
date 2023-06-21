import datetime
import json
import pandas as pd
from unittest.mock import patch
from django.test import TestCase, override_settings
from django.contrib.auth.models import User
from django.conf import settings
from ..models import Position, Transaction, Ticker, DailyChart, WeeklyChart, \
    ChartManager


class TickerTests(TestCase):
    """
    Testing Ticker model
    """

    @classmethod
    def setUpTestData(cls):
        cls.ticker = Ticker.objects.create(ticker='BTC', name='Bitcoin')

    def test_str_type(self):
        self.assertIsInstance(self.ticker.__str__(), str)

    def test_str_return(self):
        self.assertEqual(str(self.ticker), str(self.ticker.ticker))

    def test_ticker_max_length(self):
        max_length = self.ticker._meta.get_field('ticker').max_length
        self.assertEqual(max_length, 10)

    def test_name_max_length(self):
        max_length = self.ticker._meta.get_field('name').max_length
        self.assertEqual(max_length, 50)

    def test_ticker_unique(self):
        unique = self.ticker._meta.get_field('ticker').unique
        self.assertTrue(unique)

    def test_name_not_unique(self):
        unique = self.ticker._meta.get_field('name').unique
        self.assertFalse(unique)


class CommonInfoMixin:
    """
    Tests for common info in Transaction and Position models
    """

    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(username='testuser',
                                            password='12345')
        cls.ticker = Ticker.objects.create(ticker='BTC', name='Bitcoin')
        cls.usd_ticker = Ticker.objects.create(ticker='USD', name='US Dollar')
        cls.transaction = Transaction.objects.create(
            owner=cls.user,
            ticker=cls.ticker,
            amount=1.1,
            price=2.2,
        )
        cls.position = Position.objects.get(owner=cls.user, ticker=cls.ticker)

    def test_owner_type(self):
        self.assertIsInstance(self.instance.owner, User)

    def test_amount_type(self):
        self.assertIsInstance(self.instance.amount, float)

    def test_price_type(self):
        self.assertIsInstance(self.instance.price, float)

    def test_ticker_type(self):
        self.assertIsInstance(self.instance.ticker, Ticker)

    def test_str_type(self):
        self.assertIsInstance(self.instance.__str__(), str)

    def test_str_return(self):
        self.assertEqual(str(self.instance),
                         f'{self.instance.amount} '
                         f'{self.instance.ticker} | '
                         f'${self.instance.price:.2f} | '
                         f'{self.instance.owner}')


class TransactionTests(CommonInfoMixin, TestCase):
    """
    Testing Transaction model
    """

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.instance = cls.transaction

    def test_ordering(self):
        self.assertEqual(self.transaction._meta.ordering, ['date'])

    def test_str_return(self):
        self.assertEqual(str(self.transaction),
                         f'{self.transaction.amount} '
                         f'{self.transaction.ticker} | '
                         f'${self.transaction.price:.2f} | '
                         f'{self.transaction.owner} | '
                         f'{self.transaction.date}')

    def test_price_value(self):
        self.assertEqual(self.transaction.price, 2.2)

    def test_amount_value(self):
        self.assertEqual(self.transaction.amount, 1.1)

    def test_data_default(self):
        self.assertEqual(datetime.datetime.now().date(),
                         self.transaction._meta.get_field('date').default())

    def test_date_type(self):
        self.assertIsInstance(self.transaction.date, datetime.date)

    def test_usd_transaction_type(self):
        self.assertIsInstance(self.transaction.usd_transaction, Transaction)

    def test_usd_transaction_owner(self):
        self.assertEqual(self.transaction.usd_transaction.owner,
                         self.transaction.owner)

    def test_usd_transaction_date(self):
        self.assertEqual(self.transaction.usd_transaction.date,
                         self.transaction.date)

    def test_usd_transaction_ticker(self):
        self.assertEqual(self.transaction.usd_transaction.ticker, self.usd_ticker)

    def test_usd_transaction_amount(self):
        self.assertEqual(self.transaction.usd_transaction.amount,
                         -self.transaction.amount * self.transaction.price)

    def test_usd_transaction_price(self):
        self.assertEqual(self.transaction.usd_transaction.price, 1)

    def test_usd_transaction_blank(self):
        blank = self.transaction._meta.get_field('usd_transaction').blank
        self.assertTrue(blank)

    def test_usd_transaction_null(self):
        null = self.transaction._meta.get_field('usd_transaction').null
        self.assertTrue(null)

    def test_usd_transaction_usd_transaction(self):
        self.assertEqual(self.transaction.usd_transaction.usd_transaction,
                         None)

    def test_save_negative_amount_more_than_pos(self):
        initial_position_amount = self.position.amount
        self.negative_transaction = Transaction.objects.create(
            owner=self.user,
            ticker=self.ticker,
            amount=-2.2,
            price=2.2,
        )
        # must get position again to update it
        position = Position.objects.get(owner=self.user, ticker=self.ticker)
        self.assertEqual(self.negative_transaction.amount,
                         -initial_position_amount)
        self.assertEqual(position.amount, 0)

    def test_usd_transaction_auto_delete(self):
        self.transaction.delete()
        self.assertFalse(Transaction.objects.filter(ticker=self.usd_ticker).exists())


#
class PositionTests(CommonInfoMixin, TestCase):
    """
    Testing Position model
    """

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.transaction2 = Transaction.objects.create(
            owner=cls.user,
            ticker=cls.ticker,
            amount=1.1,
            price=4.4,
            date=datetime.date.today() - datetime.timedelta(days=4),
        )
        # update position
        cls.position = Position.objects.get(owner=cls.user, ticker=cls.ticker)
        cls.instance = cls.position

    def test_unique_together(self):
        unique_together = self.position._meta.unique_together
        self.assertEqual(unique_together, (('ticker', 'owner'),))

    def test_transactions_list_type(self):
        self.assertIsInstance(self.position.transactions_list, list)

    def test_low_price_level_type(self):
        self.assertIsInstance(self.position.low_price_level, float)

    def test_high_price_level_type(self):
        self.assertIsInstance(self.position.high_price_level, float)

    def test_calculate_low_price_level(self):
        self.assertEqual(self.position.low_price_level,
                         (self.transaction.price + self.transaction2.price) / 4)

    def test_calculate_high_price_level(self):
        self.assertEqual(self.position.high_price_level,
                         self.transaction.price + self.transaction2.price)

    def test_calculate_amount(self):
        self.assertEqual(self.position.amount,
                         self.transaction.amount + self.transaction2.amount)

    def test_calculate_price(self):
        self.assertEqual(self.position.price,
                         (self.transaction.price + self.transaction2.price) / 2)

    def test_calculate_transactions_list(self):
        transactions_list = [
            {'date': self.transaction2.date.strftime('%Y-%m-%d'),
             'money': 4.840000000000001,
             'amount': 1.1},
            {'date': self.transaction.date.strftime('%Y-%m-%d'),
             'money': 2.4200000000000004,
             'amount': 1.1},
        ]
        self.assertEqual(self.position.transactions_list, transactions_list)

    def test_calculate_no_transactions(self):
        self.transaction.delete()
        self.transaction2.delete()
        self.assertFalse(Position.objects.filter(ticker=self.ticker).exists())

    def test_post_save_calculation(self):
        # signal 'post_save' test
        init_amount = self.position.amount
        new_transaction = Transaction.objects.create(
            owner=self.user,
            ticker=self.ticker,
            amount=1.1,
            price=4.4,
        )
        # update position
        position = Position.objects.get(owner=self.user, ticker=self.ticker)
        self.assertEqual(position.amount, init_amount + new_transaction.amount)

    def test_post_delete_calculation(self):
        # signal 'post_delete' test
        init_amount = self.position.amount
        self.transaction.delete()
        # update position
        position = Position.objects.get(owner=self.user, ticker=self.ticker)
        self.assertEqual(position.amount, init_amount - self.transaction.amount)

    def test_position_created_post_save(self):
        # signal 'post_save' test
        eth_ticker = Ticker.objects.create(ticker='ETH')
        transaction = Transaction.objects.create(
            owner=self.user,
            ticker=eth_ticker,
            amount=1.1,
            price=4.4,
        )
        self.assertTrue(
            Position.objects.filter(ticker=eth_ticker).exists())

    def expected_df(self) -> pd.DataFrame:
        return pd.DataFrame(
            {
                'date': pd.date_range(
                    self.transaction2.date, self.transaction.date, freq='D'
                ),
                'amount': [1.1, 0.0, 0.0, 0.0, 1.1],
                'money': [4.840000000000001, 0.0, 0.0, 0.0, 2.4200000000000004],
                'total': [1.1, 1.1, 1.1, 1.1, 2.2],
                'total_money': [
                    4.840000000000001,
                    4.840000000000001,
                    4.840000000000001,
                    4.840000000000001,
                    7.260000000000002,
                ],
            }
        ).set_index('date')

    def expected_ohcl_df(self) -> pd.DataFrame:
        return pd.DataFrame(
            {
                'date': pd.date_range(
                    self.transaction2.date, self.transaction.date, freq='D'
                ),
                'open': [1, 2, 3, 4, 5],
                'high': [1, 2, 3, 4, 5],
                'low': [1, 2, 3, 4, 5],
                'close': [1, 2, 3, 4, 5],
            }
        ).set_index('date')

    def expected_build_ohlc_df(self) -> pd.DataFrame:
        ohlc_df = self.expected_ohcl_df().join(self.expected_df(), on='date',
                                               how='left')
        ohlc_df['open'] *= ohlc_df['total']
        ohlc_df['high'] *= ohlc_df['total']
        ohlc_df['low'] *= ohlc_df['total']
        ohlc_df['close'] *= ohlc_df['total']
        return ohlc_df

    def test_build_dataframe(self):
        self.assertTrue(self.position._build_dataframe().equals(self.expected_df()))

    def test_build_ohcl_dataframe(self):
        with patch('apps.folio.models.Position._build_dataframe',
                   return_value=self.expected_df()):
            self.assertTrue(self.position._build_ohlc_df(self.expected_ohcl_df())
                            .equals(self.expected_build_ohlc_df()))


class ChartMixin:
    """
    Tests for common info in WeeklyChart and DailyChart models
    """

    @classmethod
    def setUpTestData(cls):
        cls.ticker = Ticker.objects.create(ticker='BTC', name='Bitcoin')
        cls.usd_ticker = Ticker.objects.create(ticker='USD', name='US Dollar')
        for i in range(1, 5):
            cls.model.objects.create(
                ticker=cls.ticker,
                open=i,
                high=i * 2,
                low=i * 3,
                close=i * 4,
                date=datetime.date.today() - datetime.timedelta(days=i),
            )
        cls.instance = cls.model.objects.first()

    def test_unique_together(self):
        self.model._meta.unique_together = ('ticker', 'date')

    def test_ordering(self):
        self.assertEqual(self.model._meta.ordering, ['-date'])

    def test_str(self):
        self.assertEqual(str(self.instance),
                         f'{self.instance.ticker} | {self.instance.date}')

    def test_str_type(self):
        self.assertIsInstance(self.instance.__str__(), str)

    def test_open_type(self):
        self.assertIsInstance(self.instance.open, float)

    def test_high_type(self):
        self.assertIsInstance(self.instance.high, float)

    def test_low_type(self):
        self.assertIsInstance(self.instance.low, float)

    def test_close_type(self):
        self.assertIsInstance(self.instance.close, float)

    def test_date_type(self):
        self.assertIsInstance(self.instance.date, datetime.date)

    def test_ticker_type(self):
        self.assertIsInstance(self.instance.ticker, Ticker)

    def test_date_default(self):
        self.assertEqual(self.instance._meta.get_field('date').default,
                         datetime.date.fromisoformat('2000-01-01'))

    def test_objects_manager(self):
        self.assertIsInstance(self.model.objects, ChartManager)

    """ Tests for objects manager ChartManager"""

    def expected_usd_df(self) -> pd.DataFrame:
        df = pd.DataFrame(
            {'date': pd.date_range(
                datetime.date.today() - datetime.timedelta(days=4),
                self.instance.date,
                freq='D'), })
        df['open'] = df['high'] = df['low'] = df['close'] = 1
        return df.set_index('date').sort_index(ascending=False)

    def expected_btc_df(self) -> pd.DataFrame:
        df = pd.DataFrame(
            {'date': pd.date_range(
                datetime.date.today() - datetime.timedelta(days=4),
                self.instance.date,
                freq='D'),
            'open': [4.0, 3.0, 2.0, 1.0],
            'high': [8.0, 6.0, 4.0, 2.0],
            'low': [12.0, 9.0, 6.0, 3.0],
            'close': [16.0, 12.0, 8.0, 4.0],
            })
        return df.set_index('date').sort_index(ascending=False)

    def test_build_usd_df(self):
        self.assertTrue(
            self.model.objects._build_usd_df().equals(self.expected_usd_df()))

    def test_build_ohlc_df_usd(self):
        self.assertTrue(
            self.model.objects._build_ohlc_df(self.usd_ticker)
            .equals(self.expected_usd_df()))

    def test_build_ohlc_df(self):
        self.assertTrue(
            self.model.objects._build_ohlc_df(self.ticker)
            .equals(self.expected_btc_df()))

    @override_settings(CACHES=settings.TEST_CACHES)
    def test_get_ohlc_df_from_db(self):
        print(self.model.objects.get_ohlc_df(self.ticker))
        print(self.expected_btc_df())
        self.assertTrue(
            self.model.objects.get_ohlc_df(self.ticker)
            .equals(self.expected_btc_df()))

    @override_settings(CACHES=settings.TEST_CACHES)
    def test_get_ohlc_df_from_cache(self):
        self.instance.delete()
        with patch('apps.folio.models.cache.get', return_value=self.expected_btc_df()):
            self.assertTrue(
                self.model.objects.get_ohlc_df(self.ticker)
                .equals(self.expected_btc_df()))


class DailyChartTest(ChartMixin, TestCase):
    """
    Tests for DailyChart model
    """

    @classmethod
    def setUpTestData(cls):
        cls.model = DailyChart
        super().setUpTestData()


class WeeklyChartTest(ChartMixin, TestCase):
    """
    Tests for WeeklyChart model
    """

    @classmethod
    def setUpTestData(cls):
        cls.model = WeeklyChart
        super().setUpTestData()
