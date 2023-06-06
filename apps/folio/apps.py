from django.apps import AppConfig
from django.core.signals import request_finished


class FolioConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.folio'

    def ready(self):
        from . import signals
