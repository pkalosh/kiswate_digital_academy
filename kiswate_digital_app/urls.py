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
    path('plans/<uuid:pk>/edit/', views.subscription_plan_update, name='edit_subscription_plan'),
    path('plans/<uuid:pk>/delete/', views.subscription_plan_delete, name='delete_subscription_plan'),
 
    
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
    
    #demo requests
    path('demo-requests/', views.demo_request_list, name='demo_request_list'),
    path('demo-requests/verify/<uuid:lead_id>/', views.mark_verified, name='mark_verified'),
    path('demo-requests/convert/<uuid:lead_id>/', views.convert_to_school, name='convert_to_school'),
    path('staff-members/', views.staff_members, name='staff-members'),
    path('new-staff-members/', views.new_staff_members, name='new-staff-members'),
    path('staff-members/<int:pk>/edit/', views.edit_staff_member, name='edit_staff_member'),
    path('staff-members/<int:pk>/delete/', views.delete_staff_member, name='delete_staff_member'),

 
    # ── USER MANAGEMENT ──────────────────────────────────────────────────────
    path('register/student/', views.student_register, name='student_register'),
    path('register/teacher/', views.teacher_register, name='teacher_register'),
    path('register/done/', views.register_done, name='student_register_done'),
    path('register/teacher/done/', views.register_done, name='teacher_register_done'),
 
    path('users/', views.user_list, name='user_list'),
    path('users/<int:pk>/', views.user_detail, name='user_detail'),
    path('users/<int:pk>/vet/', views.vet_user, name='vet_user'),
    path('users/<int:student_pk>/guardian/add/', views.add_guardian, name='add_guardian'),
 
    path('school-enrollments/', views.enrollment_list, name='enrollment_list'),
    path('enrollments/new/', views.enroll_student, name='enroll_student'),
 
    # ── VIRTUAL LEARNING ─────────────────────────────────────────────────────
    path('classes/', views.virtual_class_list, name='virtual_class_list'),
    path('classes/new/', views.virtual_class_create, name='virtual_class_create'),
    path('classes/<int:pk>/', views.virtual_class_detail, name='virtual_class_detail'),
    path('classes/<int:pk>/edit/', views.virtual_class_edit, name='virtual_class_edit'),
    path('classes/<int:pk>/cancel/', views.virtual_class_cancel, name='virtual_class_cancel'),
    path('classes/<int:pk>/join/', views.join_class, name='join_class'),
    path('classes/<int:pk>/attendance/', views.mark_attendance_manual, name='mark_attendance'),
    path('classes/<int:pk>/recording/', views.upload_recording, name='upload_recording'),
    path('classes/<int:pk>/remind/', views.send_class_reminder, name='send_class_reminder'),
 
    path('lessons/', views.lesson_list, name='lesson_list'),
    path('lessons/new/', views.lesson_create, name='lesson_create'),
    path('lessons/<int:pk>/', views.lesson_detail, name='lesson_detail'),
    path('lessons/<int:pk>/edit/', views.lesson_edit, name='lesson_edit'),
 
    path('assignments/', views.assignment_list, name='assignment_list'),
    path('assignments/new/', views.assignment_create, name='assignment_create'),
    path('assignments/<int:pk>/', views.assignment_detail, name='assignment_detail'),
    path('assignments/<int:pk>/submit/', views.submit_assignment, name='submit_assignment'),
    path('submissions/<int:pk>/grade/', views.grade_submission, name='grade_submission'),
 
    # ── ASSESSMENTS ──────────────────────────────────────────────────────────
    path('assessments/', views.assessment_list, name='assessment_list'),
    path('assessments/new/', views.assessment_create, name='assessment_create'),
    path('assessments/<int:pk>/', views.assessment_detail, name='assessment_detail'),
    path('assessments/<int:pk>/questions/', views.assessment_questions, name='assessment_questions'),
    path('assessments/<int:assessment_pk>/questions/add/', views.question_create, name='question_create'),
    path('questions/<int:pk>/edit/', views.question_edit, name='question_edit'),
    path('assessments/<int:pk>/take/', views.take_assessment, name='take_assessment'),
    path('attempts/<int:pk>/result/', views.assessment_result, name='assessment_result'),
    path('assessments/<int:pk>/publish/', views.publish_results, name='publish_results'),
 
    # ── COMMUNICATION ─────────────────────────────────────────────────────────
    path('notifications/', views.notification_list, name='notification_list'),
    path('notifications/templates/', views.notification_template_list, name='notification_template_list'),
    path('notifications/templates/new/', views.notification_template_create, name='notification_template_create'),
    path('notifications/templates/<int:pk>/edit/', views.notification_template_edit, name='notification_template_edit'),
    path('notifications/bulk/', views.send_bulk_notification, name='send_bulk_notification'),
 
    # ── REPORTS ───────────────────────────────────────────────────────────────
    path('school-reports/', views.reports_dashboard, name='reports_dashboard'),
    path('reports/performance/', views.student_performance_report, name='student_performance_report'),
    path('reports/attendance/', views.attendance_report, name='attendance_report'),
    path('reports/teachers/', views.teacher_activity_report, name='teacher_activity_report'),
    path('reports/schools/', views.school_utilization_report, name='school_utilization_report'),
    path('reports/my/', views.my_performance, name='my_performance'),


]