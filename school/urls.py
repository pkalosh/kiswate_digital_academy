from django.urls import path
from school import views

app_name = "school"

urlpatterns = [
    path("school-dashboard/", views.dashboard, name="dashboard"),
    #grades
    path("school-grade/", views.school_grades, name="school-grades"),
    path("create-grade/", views.grade_create, name="grade-create"),
    path("edit-grade/<int:pk>/", views.grade_edit, name="edit-grade"),
    path("delete-grade/<int:pk>/", views.grade_delete, name="delete-grade"),
    #parents
    path('parents/', views.parent_list_create, name='parent_list_create'),
    path('parents/<int:pk>/edit/', views.parent_edit, name='parent_edit'),
    path('parents/<int:pk>/delete/', views.parent_delete, name='parent_delete'),
    #Staffprofile
    path('staff/', views.staff_list_create, name='staff_list_create'),
    path('staff/<int:pk>/edit/', views.staff_edit, name='staff_edit'),
    path('staff/<int:pk>/delete/', views.staff_delete, name='staff_delete'),
    #Students
    path('students/', views.student_list_create, name='student_list_create'),
    path('students/<int:pk>/edit/', views.student_edit, name='student_edit'),
    path('students/<int:pk>/delete/', views.student_delete, name='student_delete'),
    path('students/<int:pk>/delete/', views.student_delete, name='student_delete'),

    #Scan logs
    path('scan-logs/', views.scan_logs_view, name='scan_logs'),
]