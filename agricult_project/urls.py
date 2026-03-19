from django.urls import path, include
from django.contrib.auth import views as auth_views

urlpatterns = [
    path('', include('planting.urls')),
    path('login/',  auth_views.LoginView.as_view(template_name='planting/login.html'),  name='login'),
    path('logout/', auth_views.LogoutView.as_view(next_page='/login/'), name='logout'),
]
