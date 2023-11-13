from django.contrib import admin
from mptt.admin import MPTTModelAdmin

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

admin.site.register(Circle, MPTTModelAdmin)
admin.site.register(CircleRole)
admin.site.register(CircleSubscriberRole)
admin.site.register(Customer)
admin.site.register(CustomField)
admin.site.register(SubscriptionPlan)
admin.site.register(Topic)
admin.site.register(CircleInvite)
