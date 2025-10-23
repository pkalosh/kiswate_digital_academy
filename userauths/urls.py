from django.urls import path
from userauths import views

app_name = "userauths"

urlpatterns = [
    path("", views.index, name="index"),
    path("sign-in", views.LoginView, name="sign-in"),
    path("sign-out/", views.logoutView, name="sign-out"),
    path("change-password/", views.change_passwordView, name="change-password"),
]