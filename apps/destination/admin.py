from django.contrib import admin

from .models import Destination


class DestinationAdmin(admin.ModelAdmin):
    list_display = ('title', 'trip', 'uid',)

admin.site.register(Destination, DestinationAdmin)
