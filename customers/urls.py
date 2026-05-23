from django.urls import path
from . import views

urlpatterns = [
    path('', views.customer_list, name='customer_list'),
    path('add/', views.customer_create, name='customer_add'),
    path('edit/<uuid:pk>/', views.customer_update, name='customer_edit'),
    path('delete/<uuid:pk>/', views.customer_delete, name='customer_delete'),
    path('check/', views.check_customer, name='check_customer'),
]
