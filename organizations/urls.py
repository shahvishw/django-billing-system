from django.urls import path

from . import views


urlpatterns = [
    path('settings/',views.organization_settings,name='organization_settings'),
    path('staff/', views.staff_list, name='staff_list'),
    path('staff/add/', views.staff_create, name='staff_add'),
    path('staff/<int:pk>/edit/',views.staff_update,name='staff_edit'),
    path('staff/<int:pk>/deactivate/',views.staff_deactivate,name='staff_deactivate'),
    path('staff/<int:pk>/activate/', views.staff_activate, name='staff_activate'),
]
