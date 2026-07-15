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
    path('policy-dashboard/', views.policymaker_dashboard, name='policy-dashboard'),
    
    # grades
    path('grades/', views.school_grades, name='school-grades'),
    path('grades/create/', views.grade_create, name='grade-create'),
    path('grades/uploads/', views.upload_grade_file, name='upload-grade-file'),
    path('grades/<int:pk>/edit/', views.grade_edit, name='edit-grade'),
    path('grades/<int:pk>/delete/', views.grade_delete, name='delete-grade'),

    # streams
    path("grade/<int:grade_id>/streams/", views.grade_streams_view, name="grade-streams"),
    path("grade/<int:grade_id>/streams/create/", views.create_stream, name="stream-create"),
    path("stream/<int:stream_id>/edit/", views.edit_stream, name="stream-edit"),
    path("stream/<int:stream_id>/delete/", views.delete_stream, name="stream-delete"),

    # Term
    # path("terms/", views.terms, name="terms"),

    path("school-users/", views.school_users, name="school-users"),

    # Student
    path("student/<int:pk>/details/", views.student_details, name="student_details"),
    path("student/<int:pk>/edit/", views.update_student, name="update_student"),
    path("student/<int:pk>/delete/", views.delete_student, name="delete_student"),

    # Staff
    path("staff/<int:pk>/edit/", views.update_staff, name="update_staff"),
    path("staff/<int:pk>/delete/", views.delete_staff, name="delete_staff"),

    # Parents
    path("parent/<int:pk>/edit/", views.update_parent, name="update_parent"),
    path("parent/<int:pk>/delete/", views.delete_parent, name="delete_parent"),

    # Password reset (staff / student / parent)
    path("<str:user_type>/<int:pk>/reset-password/", views.reset_user_password, name="reset_user_password"),

    path("ajax/subcounties/", views.ajax_subcounties, name="ajax-subcounties"),
    path("ajax/schools/", views.ajax_schools, name="ajax-schools"),
    path("ajax/grades/", views.ajax_grades, name="ajax-grades"),
    path("ajax/subjects/", views.ajax_subjects, name="ajax-subjects"),
    path("ajax/students/", views.ajax_students_search, name="ajax-students-search"),

    # # Parents Management
    # path('parents/', views.parent_list_create, name='parent_list_create'),
    # path('parents/<int:pk>/edit/', views.parent_edit, name='parent-edit'),
    # path('parents/<int:pk>/delete/', views.parent_delete, name='parent-delete'),
    
    # Staff Management
    # path('staff/', views.staff_list_create, name='staff_list_create'),
    # path('staff/<int:pk>/edit/', views.staff_edit, name='staff-edit'),
    # path('staff/<int:pk>/delete/', views.staff_delete, name='staff-delete'),
    
    # Students Management
    # path('students/', views.student_list_create, name='student_list_create'),
    # path('students/<int:pk>/edit/', views.student_edit, name='student-edit'),
    # path('students/<int:pk>/delete/', views.student_delete, name='student-delete'),  # Duplicate removed
    
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
    path('parent-student/create/', views.create_parent_student, name='parent-student-create'),
    #school Teacher Subjects
    # Subjects Management
    path('school/<int:staff_id>/subjects/', views.school_teacher_subjects, name='school-teacher-subjects'),
    path('subjects/<int:staff_id>/create/', views.subject_teacher_create, name='subject-teacher-create'),
    path('subjects/<int:staff_id>/<int:pk>/edit/', views.subject_teacher_edit, name='subject-teacher-edit'),
    path('subjects/<int:staff_id>/<int:pk>/delete/', views.subject_teacher_delete, name='subject-teacher-delete'),

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
    path('attendance/<int:lesson_id>/', views.lesson_attendance, name='lesson-attendance'),
    path("lessons/<int:lesson_id>/edit/", views.lesson_edit, name="lesson-edit"),
    
    # Lessons Management
    path('timetable/<int:timetable_id>/lessons/', views.lesson_list, name='lesson-list'),
    path('lessons/create/', views.lesson_create, name='lesson-create'),
    # path('lessons/<int:lesson_id>/edit/', views.lesson_edit, name='lesson-edit'),
    path('lessons/<int:lesson_id>/delete/', views.lesson_delete, name='lesson-delete'),

    # Time Slots
    path('time-slots/', views.time_slot_list, name='time-slot-list'),
    path('time-slots/create/', views.time_slot_create, name='time-slot-create'),
    path('time-slots/<int:pk>/edit/', views.time_slot_edit, name='time-slot-edit'),
    path('time-slots/<int:pk>/delete/', views.time_slot_delete, name='time-slot-delete'),

    # Terms Management
    path("terms/", views.term_list, name="term-list"),
    path("terms/create/", views.create_term, name="create-term"),
    path("terms/<int:term_id>/delete/", views.delete_term, name="delete-term"),
    path("terms/<int:term_id>/edit/", views.edit_term, name="edit-term"),


    path('ajax/get-streams/', views.get_streams_for_grade, name='ajax-get-streams'),
    path('generate-timetable/', views.generate_timetable_view, name='generate_timetable'),
    path('timetable/week/', views.view_timetable_week, name='timetable_week'),
    path('timetable/teacher/', views.teacher_timetable_view, name='teacher_timetable'),

    #Lesson from Teachers
    path('teacher/<int:staff_id>/lessons/', views.teacher_lessons, name='teacher-lessons'),
    path('teacher/lessons/create/', views.teacher_lesson_create, name='teacher-lesson-create'),
    path('teacher/lessons/<int:lesson_id>/edit/', views.teacher_lesson_edit, name='teacher-lesson-edit'),
    path('teacher/lessons/<int:lesson_id>/delete/', views.teacher_lesson_delete, name='teacher-lesson-delete'),
    
    # Sessions/Virtual Classes
    path('sessions/', views.school_virtual_classes, name='school-sessions'),
    path('classes/create/', views.session_create, name='session-create'),
    path('classes/<int:session_id>/edit/', views.session_edit, name='session-edit'),
    path('classes/<int:session_id>/delete/', views.session_delete, name='session-delete'),

    
    # Attendance Management
    path('attendance/', views.attendance_dashboard, name='attendance-dashboard'),
    path('attendance/export/csv/', views.export_attendance_csv, name='attendance-export-csv'),
    path('attendance/export/pdf/', views.export_attendance_pdf, name='attendance-export-pdf'),
    path('attendance/<int:lesson_id>/mark/', views.attendance_mark, name='attendance-mark'),
    path('attendance/summary/', views.attendance_summary, name='attendance-summary'),
    path('attendance/<int:attendance_id>/delete/', views.attendance_delete, name='attendance-delete'),
    path('attendance/<int:attendance_id>/edit/', views.attendance_edit, name='attendance-edit'),
    path('attendance/export/csv/', views.export_attendance_csv, name='attendance_export_csv'),
    path('ajax/streams/', views.get_streams_by_grade, name='get_streams_by_grade'),
    # Attendance Reports
    path('teacher/attendance/', views.teacher_attendance, name='teacher-attendance'),
    path('teacher/attendance/summary/', views.teacher_attendance_summary, name='teacher-attendance-summary'),
    path('teacher/attendance/<int:lesson_id>/mark/', views.teacher_attendance_mark, name='teacher-attendance-mark'),
    path('teacher/attendance/<int:attendance_id>/edit/', views.teacher_attendance_edit, name='teacher-attendance-edit'),
    path('teacher/attendance/<int:attendance_id>/delete/', views.teacher_attendance_delete, name='teacher-attendance-delete'),
    path('teacher/attendance/<int:stream_id>/class/', views.teacher_class_attendance_report, name='teacher-class-attendance-report'),
    path('assign-class-teacher/<int:teacher_id>/', views.assign_class_teacher_for_teacher, name='assign-class-teacher-for-teacher'),
    
    # Discipline Management
    path('discipline/', views.school_discipline, name='school-discipline'),
    path('discipline/create/', views.discipline_create, name='discipline-create'),
    path('discipline/<int:pk>/edit/', views.discipline_edit, name='discipline-edit'),
    path('discipline/<int:pk>/delete/', views.discipline_delete, name='discipline-delete'),
    # Add edit/delete as needed
    #teacher discipline'
    path('teacher/discipline/', views.teacher_discipline, name='teacher-discipline'),
    path('teacher/discipline/create/', views.teacher_discipline_create, name='teacher-discipline-create'),
    path('teacher/discipline/<int:record_id>/edit/', views.teacher_discipline_edit, name='teacher-discipline-edit'),
    path('teacher/discipline/<int:record_id>/delete/', views.teacher_discipline_delete, name='teacher-discipline-delete'),
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

    path('submissions/<int:pk>/', views.school_students_submissions, name='assignment-submissions'),
    path('submissions/<int:pk>/grade/', views.submission_grade, name='submission-grade'),
    # student submission create
    path('submissions/create/', views.submission_create, name='submission-create'),
    path('student-submissions/', views.student_submissions, name='student-submissions'),
    path('student/assignments/', views.student_assignments_portal, name='student-assignments'),
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
    
    # Exam Module
    path('exams/', views.school_exams, name='school-exams'),
    path('exams/create/', views.exam_session_create, name='exam-session-create'),
    path('exams/<int:pk>/', views.exam_session_detail, name='exam-session-detail'),
    path('exams/<int:session_pk>/publish/', views.exam_publish, name='exam-publish'),
    path('exams/<int:session_pk>/upload/', views.exam_result_upload, name='exam-result-upload'),
    path('exams/upload/job/<uuid:job_pk>/', views.exam_upload_progress, name='exam-upload-progress'),
    path('exams/upload/job/<uuid:job_pk>/status/', views.exam_upload_status, name='exam-upload-status'),
    path('exams/<int:session_pk>/ranking/grade/', views.exam_ranking_grade, name='exam-ranking-grade'),
    path('exams/<int:session_pk>/ranking/grade/pdf/', views.exam_ranking_grade_pdf, name='exam-ranking-grade-pdf'),
    path('exams/<int:session_pk>/ranking/stream/<int:stream_pk>/', views.exam_ranking_stream, name='exam-ranking-stream'),
    path('exams/<int:session_pk>/ranking/stream/<int:stream_pk>/pdf/', views.exam_ranking_stream_pdf, name='exam-ranking-stream-pdf'),
    path('exams/<int:session_pk>/subjects/', views.exam_subject_performance, name='exam-subject-performance'),
    path('exams/<int:session_pk>/entry/<int:stream_pk>/<int:subject_pk>/', views.exam_result_entry, name='exam-result-entry'),
    path('exams/<int:session_pk>/slip/<int:student_pk>/', views.report_slip_html, name='report-slip-html'),
    path('exams/<int:session_pk>/slip/<int:student_pk>/pdf/', views.report_slip_pdf, name='report-slip-pdf'),
    path('student/exam-results/', views.student_exam_results, name='student-exam-results'),
    path("teacher/attendance/<int:lesson_id>/smart/", views.teacher_attendance_smart, name="teacher-attendance-smart"),
    path("teacher/discipline/create/ajax/", views.teacher_discipline_create_ajax, name="teacher-discipline-create-ajax"),
    path('upload-excel/', views.universal_excel_upload, name='universal_excel_upload'),
    path('upload-page/', views.upload_excel_page, name='upload_excel_page'),
    path('upload-status/<int:pk>/', views.upload_job_status, name='upload_job_status'),

    # Subject Catalog (Kiswate admin)
    path('catalog/subjects/', views.catalog_subject_list, name='catalog-subject-list'),
    path('catalog/subjects/create/', views.catalog_subject_create, name='catalog-subject-create'),
    path('catalog/subjects/<int:pk>/edit/', views.catalog_subject_edit, name='catalog-subject-edit'),
    path('catalog/subjects/<int:pk>/delete/', views.catalog_subject_delete, name='catalog-subject-delete'),
    path('catalog/subjects/<int:pk>/toggle/', views.catalog_subject_toggle, name='catalog-subject-toggle'),
    path('catalog/subjects/bulk-upload/', views.catalog_subject_bulk_upload, name='catalog-subject-bulk-upload'),

    # Subject Activation (school principal)
    path('subjects/from-catalog/', views.subject_activate_from_catalog, name='subject-activate-catalog'),

    # Parent Self-Service Portal
    path('parent-dashboard/', views.parent_dashboard, name='parent-dashboard'),
    path('parent/portal/', views.parent_portal, name='parent-portal'),
    path('parent/notifications/', views.parent_notifications, name='parent-notifications'),
    path('parent/complaints/', views.parent_complaints, name='parent-complaints'),
    path('parent/assignments/', views.parent_assignments, name='parent-assignments'),
    path('parent/exam-results/', views.parent_exam_results, name='parent-exam-results'),
    path('parent/fees/', views.parent_fee_updates, name='parent-fees'),
    path('parent/attendance/', views.parent_attendance, name='parent-attendance'),

    # Student status actions (principal/deputy only)
    path('students/<int:student_id>/suspend/', views.student_suspend, name='student-suspend'),
    path('students/<int:student_id>/expel/', views.student_expel, name='student-expel'),
    path('students/<int:student_id>/reinstate/', views.student_reinstate, name='student-reinstate'),

    # Admin: view complaints
    path('manage-complaints/', views.admin_complaints_list, name='admin-complaints'),

    # Bulk notifications
    path('notifications/bulk/', views.bulk_notify, name='bulk-notify'),

    # Student notifications (in-app)
    path('student/notifications/', views.student_notifications, name='student-notifications'),

    # Announcements
    path('announcements/', views.announcement_list, name='announcements'),
    path('announcements/create/', views.announcement_create, name='announcement-create'),
    path('announcements/<int:pk>/delete/', views.announcement_delete, name='announcement-delete'),
    path('announcements/<int:pk>/disable/', views.announcement_disable, name='announcement-disable'),
    path('parent/announcements/', views.parent_announcements, name='parent-announcements'),
    path('student/announcements/', views.student_announcements, name='student-announcements'),

    # Finance Dashboard
    path('finance-dashboard/', views.finance_dashboard, name='finance-dashboard'),
    path('finance/invoice/create/', views.finance_create_invoice, name='finance-create-invoice'),
    path('finance/invoice/<int:invoice_id>/payment/', views.finance_record_payment, name='finance-record-payment'),
    path('finance/invoice/<int:invoice_id>/receipt/', views.finance_receipt, name='finance-receipt'),
    path('finance/invoice/<int:invoice_id>/stk-push/', views.finance_stk_push, name='finance-stk-push'),
    path('finance/invoice/<int:invoice_id>/delete/', views.fee_invoice_delete, name='fee-invoice-delete'),

    # Fee Structures & Fee Types
    path('fee-types/create/', views.fee_type_create_ajax, name='fee-type-create-ajax'),
    path('fee-structures/', views.fee_structure_list, name='fee-structure-list'),
    path('fee-structures/create/', views.fee_structure_create, name='fee-structure-create'),
    path('fee-structures/<int:pk>/edit/', views.fee_structure_edit, name='fee-structure-edit'),
    path('fee-structures/<int:pk>/delete/', views.fee_structure_delete, name='fee-structure-delete'),
    path('fee-structures/generate/<int:term_id>/', views.bulk_generate_invoices, name='bulk-generate-invoices'),

    # Payment upload & reports
    path('finance/payment-upload/', views.fee_payment_upload, name='fee-payment-upload'),
    path('finance/statement/<int:student_pk>/', views.student_fee_statement, name='student-fee-statement'),
    path('finance/statement/<int:student_pk>/pdf/', views.student_fee_statement_pdf, name='student-fee-statement-pdf'),
    path('finance/payment-statement/', views.finance_payment_statement, name='finance-payment-statement'),
    path('finance/payment-statement/csv/', views.finance_payment_statement_csv, name='finance-payment-statement-csv'),
    path('finance/collection-report/', views.finance_collection_report, name='finance-collection-report'),
    path('finance/collection-report/csv/', views.finance_collection_report_csv, name='finance-collection-report-csv'),

    # Student fee portal
    path('student/fees/', views.student_fees_portal, name='student-fees'),

    # Grade Promotion (principals, deputy, class teachers)
    path('grades/promote/', views.grade_promote_view, name='grade-promote'),

    # Class Teacher Portal
    path('class/teachers/', views.manage_class_teachers, name='manage-class-teachers'),
    path('class/roster/', views.class_teacher_roster, name='class-teacher-roster'),
    path('class/roll-call/', views.class_teacher_roll_call, name='class-teacher-roll-call'),
    path('class/attendance-summary/', views.class_teacher_attendance_summary, name='class-teacher-attendance-summary'),
    path('class/subject-summary/', views.class_teacher_subject_summary, name='class-teacher-subject-summary'),
    path('class/discipline/', views.class_teacher_discipline, name='class-teacher-discipline'),
]