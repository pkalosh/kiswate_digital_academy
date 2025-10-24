from django.urls import path
from userauths import views

app_name = "userauths"

urlpatterns = [
    path("", views.index, name="index"),
    path("modules/", views.modules, name="modules"),
    path("how-it-works/", views.how_it_works, name="how_it_works"),
    path("pricing/", views.pricing, name="pricing"),
    path("faqs/", views.faqs, name="faqs"),
    path("demo/", views.demo, name="demo"),
    path("sign-in", views.LoginView, name="sign-in"),
    path("sign-out/", views.logoutView, name="sign-out"),
    path("change-password/", views.change_passwordView, name="change-password"),
]