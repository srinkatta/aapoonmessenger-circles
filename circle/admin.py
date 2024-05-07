from mptt.admin import MPTTModelAdmin
from django.contrib import admin

from circle.models import (
    Circle,
    CircleRole,
    CircleSubscriberRole,
    Customer,
    CustomField,
    SubscriptionPlan,
    Topic,
    CircleInvite,
)


class CircleAdmin(MPTTModelAdmin):
    search_fields = ["name"]


admin.site.register(Circle, CircleAdmin)
admin.site.register(CircleRole)
admin.site.register(CircleSubscriberRole)
admin.site.register(Customer)
admin.site.register(CustomField)
admin.site.register(SubscriptionPlan)
admin.site.register(Topic)
admin.site.register(CircleInvite)
