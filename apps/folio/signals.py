from django.dispatch import receiver
from django.db.models.signals import post_save, post_delete, pre_save
from django.db.models import F, Q
from .models import Transaction, Position, Ticker


@receiver([post_save, post_delete], sender=Transaction)
def create_and_update_position(instance, **kwargs) -> None:
    """
    Create and update or update existed position
    """
    position, created = Position.objects.get_or_create(
        owner=instance.owner,
        ticker=instance.ticker
    )
    position.calculate()


@receiver(pre_save, sender=Transaction)
def create_usd_transaction(instance, **kwargs) -> None:
    """
    Auto create corresponding USD transaction for each transaction
    """
    usd_ticker = Ticker.objects.get(ticker='USD')
    if instance.ticker != usd_ticker:
        instance.usd_transaction = Transaction.objects.create(
            owner=instance.owner,
            date=instance.date,
            ticker=usd_ticker,
            price=1,
            amount=-instance.amount*instance.price,
        )


@receiver(post_delete, sender=Transaction)
def delete_usd_transaction(instance, **kwargs) -> None:
    """
    Auto delete corresponding USD transaction for each transaction
    """
    if instance.ticker.ticker != 'USD':
        instance.usd_transaction.delete()
