from django.contrib import admin
from django.urls import path
from core.views import home, rooms, healthcheck
from core.views_auth import signup
from core.views_announce import announcement_list
from django.contrib.auth import views as auth_views

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", home, name="home"),
    path(
        "login/",
        auth_views.LoginView.as_view(template_name="core/login.html"),
        name="login",
    ),
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),
    path("signup/", signup, name="signup"),
    path("rooms/", rooms, name="rooms"),
    path("announcements/", announcement_list, name="announcements"),
    path("healthcheck/", healthcheck, name="healthcheck"),
]
