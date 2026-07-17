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
    path('school-subscriptions/', views.school_subscription_list, name='school_subscription_list'),
    path('school-subscriptions/<uuid:pk>/update/', views.school_subscription_update, name='school_subscription_update'),
    path('school-subscriptions/<uuid:pk>/delete/', views.school_subscription_delete, name='school_subscription_delete'),

    path("invoice-list/", views.invoice_list, name="invoice_list"),
    path("create-invoice/", views.create_invoice, name="create_invoice"),
    path("payment-history/", views.payment_history, name="payment_history"),
    path("reports/", views.reports, name="reports"),
    path("support/", views.support, name="support"),
    path("dim/escalations/", views.kiswate_escalations, name="kiswate_escalations"),
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
    path('users/<int:pk>/assign-lessons/', views.assign_lessons_to_teacher, name='assign_lessons_to_teacher'),
    path('users/<int:student_pk>/guardian/add/', views.add_guardian, name='add_guardian'),
 
    path('school-enrollments/', views.enrollment_list, name='enrollment_list'),
    path('enrollments/new/', views.enroll_student, name='enroll_student'),
 
    # ── VIRTUAL LEARNING ─────────────────────────────────────────────────────
    path('dil/classes/', views.virtual_class_list, name='virtual_class_list'),
    path('dil/classes/new/', views.virtual_class_create, name='virtual_class_create'),
    path('dil/classes/<int:pk>/', views.virtual_class_detail, name='virtual_class_detail'),
    path('dil/classes/<int:pk>/edit/', views.virtual_class_edit, name='virtual_class_edit'),
    path('dil/classes/<int:pk>/cancel/', views.virtual_class_cancel, name='virtual_class_cancel'),
    path('dil/classes/<int:pk>/join/', views.join_class, name='join_class'),
    path('dil/classes/<int:pk>/attendance/', views.mark_attendance_manual, name='mark_attendance'),
    path('dil/classes/<int:pk>/nil/', views.mark_nil_attendance, name='mark_nil_attendance'),
    path('dil/classes/<int:pk>/recording/', views.upload_recording, name='upload_recording'),
    path('dil/classes/<int:pk>/remind/', views.send_class_reminder, name='send_class_reminder'),

    path('dil/lessons/', views.lesson_list, name='lesson_list'),
    path('dil/lessons/new/', views.lesson_create, name='lesson_create'),
    path('dil/lessons/<int:pk>/', views.lesson_detail, name='lesson_detail'),
    path('dil/lessons/<int:pk>/edit/', views.lesson_edit, name='lesson_edit'),

    path('dil/assignments/', views.assignment_list, name='assignment_list'),
    path('dil/assignments/new/', views.assignment_create, name='assignment_create'),
    path('dil/assignments/<int:pk>/', views.assignment_detail, name='assignment_detail'),
    path('dil/assignments/<int:pk>/submit/', views.submit_assignment, name='submit_assignment'),
    path('dil/submissions/<int:pk>/grade/', views.grade_submission, name='grade_submission'),

    # ── ASSESSMENTS ──────────────────────────────────────────────────────────
    path('dil/assessments/', views.assessment_list, name='assessment_list'),
    path('dil/assessments/new/', views.assessment_create, name='assessment_create'),
    path('dil/assessments/<int:pk>/', views.assessment_detail, name='assessment_detail'),
    path('dil/assessments/<int:pk>/questions/', views.assessment_questions, name='assessment_questions'),
    path('dil/assessments/<int:assessment_pk>/questions/add/', views.question_create, name='question_create'),
    path('dil/questions/<int:pk>/edit/', views.question_edit, name='question_edit'),
    path('dil/assessments/<int:pk>/take/', views.take_assessment, name='take_assessment'),
    path('dil/attempts/<int:pk>/result/', views.assessment_result, name='assessment_result'),
    path('dil/assessments/<int:pk>/publish/', views.publish_results, name='publish_results'),

    # ── COMMUNICATION ─────────────────────────────────────────────────────────
    path('dil/notifications/', views.notification_list, name='notification_list'),
    path('dil/notifications/templates/', views.notification_template_list, name='notification_template_list'),
    path('dil/notifications/templates/new/', views.notification_template_create, name='notification_template_create'),
    path('dil/notifications/templates/<int:pk>/edit/', views.notification_template_edit, name='notification_template_edit'),
    path('dil/notifications/bulk/', views.send_bulk_notification, name='send_bulk_notification'),
 
    # ── REPORTS ───────────────────────────────────────────────────────────────
    path('school-reports/', views.reports_dashboard, name='reports_dashboard'),
    path('reports/performance/', views.student_performance_report, name='student_performance_report'),
    path('reports/attendance/', views.attendance_report, name='attendance_report'),
    path('reports/teachers/', views.teacher_activity_report, name='teacher_activity_report'),
    path('reports/schools/', views.school_utilization_report, name='school_utilization_report'),
    path('reports/my/', views.my_performance, name='my_performance'),

    # ── TUITION — ADMIN ───────────────────────────────────────────────────────
    path('tuition/programs/', views.tuition_program_list, name='tuition_program_list'),
    path('tuition/programs/new/', views.tuition_program_create, name='tuition_program_create'),
    path('tuition/programs/<int:pk>/edit/', views.tuition_program_edit, name='tuition_program_edit'),
    path('tuition/programs/<int:pk>/delete/', views.tuition_program_delete, name='tuition_program_delete'),
    path('tuition/programs/<int:pk>/assign-teacher/', views.tuition_assign_teacher, name='tuition_assign_teacher'),

    # ── TUITION — PUBLIC ──────────────────────────────────────────────────────
    path('tuition/', views.tuition_browse, name='tuition_browse'),
    path('tuition/<int:pk>/', views.tuition_program_detail, name='tuition_program_detail'),
    path('tuition/<int:pk>/enroll/', views.tuition_enroll, name='tuition_enroll'),

    # ── TUITION — TEACHER ─────────────────────────────────────────────────────
    path('tuition/teacher/', views.teacher_tuition_dashboard, name='teacher_tuition_dashboard'),
    path('tuition/teacher/programs/new/', views.teacher_program_create, name='teacher_program_create'),
    path('tuition/teacher/programs/<int:pk>/edit/', views.teacher_program_edit, name='teacher_program_edit'),
    path('tuition/teacher/lessons/new/', views.lesson_create, name='teacher_lesson_create'),
    path('tuition/teacher/classes/new/', views.virtual_class_create, name='teacher_class_create'),

    # ── TUITION — STUDENT ─────────────────────────────────────────────────────
    path('tuition/student/', views.student_tuition_dashboard, name='student_tuition_dashboard'),
    path('tuition/student/guardian/', views.student_add_guardian_self, name='student_add_guardian_self'),

    # ── TUITION — PARENT ──────────────────────────────────────────────────────
    path('tuition/parent/', views.parent_tuition_view, name='parent_tuition_view'),
    path('tuition/parent/enroll/', views.parent_enroll_child, name='parent_enroll_child'),
    path('tuition/parent/payments/<int:enrollment_pk>/stk-push/', views.parent_stk_push, name='parent_stk_push'),

    # ── GLOBAL SUBJECTS ────────────────────────────────────────────────────────
    # Prefixed with 'dim/' to avoid shadowing school's /subjects/ URL
    path('dim/subjects/', views.subject_list, name='subject_list'),
    path('dim/subjects/create/', views.subject_create, name='subject_create'),
    path('dim/subjects/<int:pk>/edit/', views.subject_edit, name='subject_edit'),
    path('dim/subjects/<int:pk>/delete/', views.subject_delete, name='subject_delete'),
    path('dim/subjects/upload/', views.subject_bulk_upload, name='subject_bulk_upload'),

    # ── PRINCIPAL TUITION ENROLLMENT ───────────────────────────────────────────
    path('tuition/principal/enroll/', views.principal_enroll_tuition, name='principal_enroll_tuition'),

    # ── IMPERSONATION ──────────────────────────────────────────────────────────
    path('schools/<int:school_pk>/impersonate/<str:role>/', views.impersonate_school, name='impersonate_school'),
    path('impersonate/stop/', views.stop_impersonating, name='stop_impersonating'),

    # ── SYSTEM USERS ───────────────────────────────────────────────────────────
    path('system-users/', views.system_users, name='system_users'),
    path('system-users/<int:pk>/edit/', views.system_user_edit, name='system_user_edit'),

    # ── GUARDIAN MANAGEMENT ────────────────────────────────────────────────────
    path('guardians/', views.guardian_list, name='guardian_list'),
    path('guardians/<int:pk>/edit/', views.guardian_edit, name='guardian_edit'),
    path('guardians/<int:pk>/delete/', views.guardian_delete, name='guardian_delete'),

    # ── TUITION PAYMENTS ───────────────────────────────────────────────────────
    path('tuition/payments/', views.tuition_payment_list, name='tuition_payment_list'),
    path('tuition/payments/<int:pk>/', views.tuition_payment_detail, name='tuition_payment_detail'),
    path('tuition/payments/<int:pk>/update/', views.tuition_payment_update, name='tuition_payment_update'),
    path('tuition/student/payments/', views.student_payment_view, name='student_payment_view'),
    path('tuition/payments/<int:enrollment_pk>/stk-push/', views.tuition_stk_push, name='tuition_stk_push'),
    path('tuition/mpesa/callback/', views.tuition_mpesa_callback, name='tuition_mpesa_callback'),
]