from django.urls import path

from .views import login_view,logout_view,membership_inactive,organization_setup,register_owner

urlpatterns = [
    path('login/', login_view, name='login'),
    path('register/', register_owner, name='register'),
    path('organization-setup/',organization_setup,name='organization_setup'),
    path('access-inactive/',membership_inactive,name='membership_inactive'),
    path('logout/', logout_view, name='logout'),
]