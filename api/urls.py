from django.urls import path

from . import views


app_name = 'api'

urlpatterns = [
    path('customers/', views.CustomerListView.as_view(), name='customer-list'),
    path(
        'customers/<uuid:pk>/',
        views.CustomerDetailView.as_view(),
        name='customer-detail',
    ),
    path('catalog-items/', views.CatalogItemListView.as_view(), name='catalog-list'),
    path(
        'catalog-items/<uuid:pk>/',
        views.CatalogItemDetailView.as_view(),
        name='catalog-detail',
    ),
    path('invoices/', views.InvoiceListView.as_view(), name='invoice-list'),
    path('invoices/<int:pk>/', views.InvoiceDetailView.as_view(), name='invoice-detail'),
    path('payments/', views.PaymentListView.as_view(), name='payment-list'),
    path('payments/<int:pk>/', views.PaymentDetailView.as_view(), name='payment-detail'),
]
