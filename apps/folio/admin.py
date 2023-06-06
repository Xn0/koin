from django.contrib import admin
from .models import Transaction, Position


admin.site.register(Position)
admin.site.register(Transaction)
