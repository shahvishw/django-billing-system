from django.urls import path
from . import views

urlpatterns = [
    path('', views.catalog_list, name='catalog_list'),
    path('add/', views.catalog_create, name='catalog_add'),
    path('<uuid:pk>/edit/', views.catalog_update, name='catalog_edit'),
    path('<uuid:pk>/status/', views.catalog_toggle_active, name='catalog_toggle_active'),
    path('<uuid:pk>/delete/', views.catalog_delete, name='catalog_delete'),
    path('search/', views.search_products, name='search_products'),
]
