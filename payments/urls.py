from django.urls import path
from . import views

urlpatterns = [
    path('pay/<int:invoice_id>/', views.make_payment, name='make_payment'),
]
