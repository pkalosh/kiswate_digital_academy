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
    path("subscription-plans/", views.subscription_plans, name="subscription_plans"),
    path("invoice-list/", views.invoice_list, name="invoice_list"),
    path("create-invoice/", views.create_invoice, name="create_invoice"),
    path("payment-history/", views.payment_history, name="payment_history"),
    path("reports/", views.reports, name="reports"),
    path("support/", views.support, name="support"),
    path("scholarships/", views.scholarships, name="scholarships"),
    path("new-scholarship/", views.new_scholarship, name="new_scholarship"),
    path("edit-scholarship/", views.edit_scholarship, name="edit_scholarship"),
    path("delete-scholarship/", views.delete_scholarship, name="delete_scholarship"),
    
]