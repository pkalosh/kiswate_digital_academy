from django.urls import path
from kiswate_digital_app import views

app_name = "kiswate_digital_app"

urlpatterns = [
    #dashboard
    path("Kiswate-admin-dashboard/", views.kiswate_dashboard, name="kiswate_admin_dashboard"),
    #schools
    path("new-school/", views.new_school, name="new_school"),
    path("school-list/", views.school_list, name="school_list"),
    path("edit-school/<int:pk>/", views.edit_school, name="edit_school"),
    path("delete-school/<int:pk>/", views.delete_school, name="delete_school"),
    #school admins
    path("school-admins/", views.school_admin_list, name="school_admin_list"),
    path("school-admins/<int:school_pk>/edit/", views.edit_school_admin, name="edit_school_admin"),
    path("school-admins/<int:school_pk>/delete/", views.delete_school_admin, name="delete_school_admin"),


    path("kiswate-settings/", views.kiswate_settings, name="kiswate_settings"),

    # Subscription Plans
    path('plans/', views.subscription_plan_list, name='subscription_plan_list'),
    path('plans/create/', views.subscription_plan_create, name='create_subscription_plan'),
    path('plans/<int:pk>/edit/', views.subscription_plan_update, name='edit_subscription_plan'),
    path('plans/<int:pk>/delete/', views.subscription_plan_delete, name='delete_subscription_plan'),
 
    
    # School Subscriptions
    
    path("invoice-list/", views.invoice_list, name="invoice_list"),
    path("create-invoice/", views.create_invoice, name="create_invoice"),
    path("payment-history/", views.payment_history, name="payment_history"),
    path("reports/", views.reports, name="reports"),
    path("support/", views.support, name="support"),
    #scholarships
    path('scholarship-list/', views.scholarship_list_create, name='scholarship_list_create'),
    path('scholarship/<int:pk>/edit/', views.scholarship_edit, name='scholarship_edit'),
    path('scholarship/<int:pk>/delete/', views.scholarship_delete, name='scholarship_delete'),
    
]