# school/urls.py - Updated URL Configuration for KDADTR School App
# Fixes: Removed duplicates (e.g., student delete), standardized paths/names (e.g., 'grades/' for consistency),
# added missing paths from previous implementations (e.g., subjects, attendance, etc.).
# All paths are namespaced under app_name='school' for template reverses (e.g., {% url 'school:dashboard' %}).
# Integrate in main urls.py: path('school/', include('school.urls')).

from django.urls import path
from . import views

app_name = 'school'

urlpatterns = [
    # Dashboard (Admin/General)
    path('dashboard/', views.dashboard, name='dashboard'),
    
    # Grades Management
    path('grades/', views.school_grades, name='school-grades'),
    path('grades/create/', views.grade_create, name='grade-create'),
    path('grades/<int:pk>/edit/', views.grade_edit, name='edit-grade'),
    path('grades/<int:pk>/delete/', views.grade_delete, name='delete-grade'),
    
    # Parents Management
    path('parents/', views.parent_list_create, name='parent_list_create'),
    path('parents/<int:pk>/edit/', views.parent_edit, name='parent-edit'),
    path('parents/<int:pk>/delete/', views.parent_delete, name='parent-delete'),
    
    # Staff Management
    path('staff/', views.staff_list_create, name='staff_list_create'),
    path('staff/<int:pk>/edit/', views.staff_edit, name='staff-edit'),
    path('staff/<int:pk>/delete/', views.staff_delete, name='staff-delete'),
    
    # Students Management
    path('students/', views.student_list_create, name='student_list_create'),
    path('students/<int:pk>/edit/', views.student_edit, name='student-edit'),
    path('students/<int:pk>/delete/', views.student_delete, name='student-delete'),  # Duplicate removed
    
    # SmartID Management
    path('smartids/', views.smartid_list, name='smartid-list'),
    path('smartids/create/', views.smartid_create, name='smartid-create'),
    path('smartids/<int:pk>/edit/', views.smartid_edit, name='smartid-edit'),
    path('smartids/<int:pk>/delete/', views.smartid_delete, name='smartid-delete'),
    
    # Scan Logs
    path('scan-logs/', views.scan_logs_view, name='scan_logs'),
    
    # Subjects Management
    path('subjects/', views.school_subjects, name='school-subjects'),
    path('subjects/create/', views.subject_create, name='subject-create'),
    path('subjects/<int:pk>/edit/', views.subject_edit, name='subject-edit'),
    path('subjects/<int:pk>/delete/', views.subject_delete, name='subject-delete'),
    
    # Enrollment Management
    path('enrollments/', views.school_enrollment, name='school-enrollment'),
    path('enrollments/create/', views.enrollment_create, name='enrollment-create'),
    path('enrollments/<int:pk>/edit/', views.enrollment_edit, name='enrollment-edit'),
    path('enrollments/<int:pk>/delete/', views.enrollment_delete, name='enrollment-delete'),
    
    # Timetable Management
    path('timetables/', views.school_timetable, name='school-timetable'),
    path('timetables/create/', views.timetable_create, name='timetable-create'),
    path('timetables/<int:pk>/edit/', views.timetable_edit, name='timetable-edit'),
    path('timetables/<int:pk>/delete/', views.timetable_delete, name='timetable-delete'),
    
    # Lessons Management
    path('timetable/<int:timetable_id>/lessons/', views.lesson_list, name='lesson-list'),
    path('lessons/create/', views.lesson_create, name='lesson-create'),
    path('lessons/<int:lesson_id>/edit/', views.lesson_edit, name='lesson-edit'),
    path('lessons/<int:lesson_id>/delete/', views.lesson_delete, name='lesson-delete'),
    
    # Sessions/Virtual Classes
    path('sessions/', views.school_virtual_classes, name='school-sessions'),
    path('classes/create/', views.session_create, name='session-create'),
    path('classes/<int:session_id>/edit/', views.session_edit, name='session-edit'),
    path('classes/<int:session_id>/delete/', views.session_delete, name='session-delete'),

    
    # Attendance Management
    path('attendance/', views.school_attendance, name='school-attendance'),
    path('attendance/<int:lesson_id>/mark/', views.attendance_mark, name='attendance-mark'),
    path('attendance/summary/', views.attendance_summary, name='attendance-summary'),
    path('attendance/<int:attendance_id>/delete/', views.attendance_delete, name='attendance-delete'),
    path('attendance/<int:attendance_id>/edit/', views.attendance_edit, name='attendance-edit'),

    
    # Discipline Management
    path('discipline/', views.school_discipline, name='school-discipline'),
    path('discipline/create/', views.discipline_create, name='discipline-create'),
    path('discipline/<int:pk>/edit/', views.discipline_edit, name='discipline-edit'),
    path('discipline/<int:pk>/delete/', views.discipline_delete, name='discipline-delete'),
    # Add edit/delete as needed
    
    # Notifications
    path('notifications/', views.school_notifications, name='school-notifications'),
    path('notifications/send/', views.notification_send, name='notification-send'),
    
    # Reports & Exports
    path('reports/', views.school_reports, name='school-reports'),
    path('reports/export/', views.export_report, name='export-report'),
    path('reports/export/pdf/', views.export_pdf_report, name='export-pdf-report'),
    
    # Assignments & Submissions
    path('assignments/', views.school_student_assignments, name='school-assignments'),
    path('assignments/create/', views.assignment_create, name='assignment-create'),
    path('assignments/<int:pk>/edit/', views.assignment_edit, name='assignment-edit'),
    path('assignments/<int:pk>/delete/', views.assignment_delete, name='assignment-delete'),

    path('submissions/', views.school_students_submissions, name='school-submissions'),
    path('submissions/<int:pk>/grade/', views.submission_grade, name='submission-grade'),
    # student submission create
    path('submissions/create/', views.submission_create, name='submission-create'),
    path('student-submissions/', views.student_submissions, name='student-submissions'),
    path('submissions/<int:pk>/edit/', views.submission_edit, name='submission-edit'),
    path('submissions/<int:pk>/delete/', views.submission_delete, name='submission-delete'),

    # Fees & Payments
    path('fees/', views.school_fees, name='school-fees'),
    path('fees/mpesa/', views.process_mpesa_payment, name='process-mpesa-payment'),
    
    # Finance & Subscriptions
    path('finance/', views.school_finance, name='school-finance'),
    path('subscriptions/', views.school_subscriptions, name='school-subscriptions'),
    path('invoices/generate/', views.generate_invoice, name='generate-invoice'),
    
    # Events & Calendar
    path('calendar/', views.school_calendar, name='school-calendar'),
    path('events/', views.school_events, name='school-events'),
    
    # Settings & Permissions
    path('settings/', views.school_settings, name='school-settings'),
    path('permissions/', views.permissions_logs, name='permissions-logs'),
    
    # Contact Messages
    path('contact/', views.contact_messages, name='contact-messages'),
    

    
    # M-Pesa Callbacks (Public webhooks)
    path('mpesa/stk-callback/', views.mpesa_stk_callback, name='mpesa-stk-callback'),
    path('mpesa/payment-callback/', views.mpesa_payment_callback, name='mpesa-payment-callback'),
    
    path('exams/', views.school_exams, name='school-exams'),
]