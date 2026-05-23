from django.urls import path
from . import views

urlpatterns = [
   path('search/', views.search_products, name='search_products'),
]