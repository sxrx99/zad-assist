from django.contrib import admin
from zbot import models
# Register your models here.

admin.site.register(models.TextMessage)
admin.site.register(models.ImageMessage)