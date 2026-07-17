from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView
from .dil_views import (
    # Subjects catalog
    DILSubjectsView,
    # Programs
    DILProgramsView, DILProgramDetailView, DILEnrollView,
    # Virtual Classes
    DILClassesView, DILClassDetailView, DILClassJoinView,
    DILClassAttendanceView, DILClassRecordingView, DILClassReminderView,
    # Lessons
    DILLessonsView, DILLessonDetailView,
    # Assignments
    DILAssignmentsView, DILAssignmentDetailView, DILAssignmentSubmitView,
    DILSubmissionsView, DILSubmissionGradeView,
    # Assessments
    DILAssessmentsView, DILAssessmentDetailView,
    DILAssessmentQuestionsView, DILQuestionDetailView,
    DILTakeAssessmentView, DILAttemptResultView, DILPublishResultsView,
    # Notification templates
    DILNotificationTemplatesView,
    # Tuition
    TuitionProgramsView, TuitionEnrollView, TuitionPaymentSTKPushView,
    TuitionTeacherDashboardView, TuitionStudentDashboardView, TuitionParentView,
)
from .views import (
    # Auth
    register, login, LogoutView,
    # Static
    StaticDataView,
    # Timetables & lessons
    TeacherTimetableView, StudentTimetableView, TeacherLessonsView,
    # Students list
    StudentsListView,
    # Attendance
    AttendanceRecordsView, AttendanceDetailView, StreamAttendanceRecordsView,
    # Discipline
    DisciplineRecordsView, DisciplineDetailView,
    # Assignments
    AssignmentsView, AssignmentDetailView,
    # Announcements (Notification model)
    AnnouncementsView,
    # Stats
    StudentStatsView, ParentStatsView, TeacherStatsView, ParentChildrenView,

    # ── Extended views ──────────────────────────────────────────────────────
    # Profile
    ProfileView,
    # School info
    SchoolInfoView,
    # Grades
    GradesView, GradeDetailView,
    # Streams
    StreamsView, StreamDetailView,
    # Terms
    TermsView, TermDetailView,
    # Subjects
    SubjectsView, SubjectDetailView,
    # Staff
    StaffListView, StaffDetailView,
    # Students (manage)
    StudentDetailManageView, StudentStatusView,
    # Parents
    ParentsListView, ParentDetailView,
    # Lessons (manage)
    LessonsManageView, LessonManageDetailView,
    # Submissions
    SubmissionsView, SubmissionDetailView,
    # Exams
    ExamSessionsView, ExamSessionDetailView, ExamPublishView,
    ExamResultsView, MyExamResultsView,
    # Finance
    FeeInvoicesView, FeeInvoiceDetailView, FeePaymentView,
    FeeStructuresView, StudentFeesView,
    # Complaints
    ComplaintsView, ComplaintDetailView,
    # School Announcements (Announcement model)
    SchoolAnnouncementsView, SchoolAnnouncementDetailView,
    # Notifications
    SendNotificationView, MarkNotificationReadView,
    # Admin actions
    GradePromoteView, ClassTeacherAssignView,
    # Dashboards
    DashboardView, PolicyDashboardView,
    # Time slots & timetables
    TimeSlotsView, TimetablesView,

    # ── Sprint 1: Core school management ────────────────────────────────────
    StudentCreateView, StaffCreateView, ParentCreateView,
    UserPasswordResetView,
    StaffSubjectsView, StaffSubjectRemoveView,
    ParentStudentLinkView,
    EnrollmentsView, EnrollmentDetailView,
    TimetableDetailView, TimeSlotDetailView,
    ClassTeacherListView, ClassTeacherRosterView, ClassTeacherRollCallView,
    ClassTeacherAttendanceSummaryView, ClassTeacherSubjectSummaryView,
    AttendanceSummaryView, TeacherAttendanceSummaryView, SmartAttendanceView,

    # ── Sprint 2: Finance, Exams, Attendance ─────────────────────────────
    FeeTypesView, FeeTypeDetailView,
    FeeStructureDetailView,
    FeeInvoiceBulkGenerateView, FeeSTKPushView,
    FeeInvoiceReceiptView, FeeCollectionReportView, StudentFeeStatementView,
    ExamGradeRankingView, ExamStreamRankingView,
    ExamSubjectPerformanceView, ExamResultSlipView, ExamResultDetailView,
)

urlpatterns = [
    # ── Auth ──────────────────────────────────────────────────────────────────
    path('auth/register/', register, name='register'),
    path('auth/login/', login, name='login'),
    path('auth/logout/', LogoutView.as_view(), name='logout'),
    path('auth/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),

    # ── Profile ───────────────────────────────────────────────────────────────
    path('profile/', ProfileView.as_view(), name='profile'),

    # ── Static ────────────────────────────────────────────────────────────────
    path('static/data/', StaticDataView.as_view(), name='static_data'),

    # ── School Info ───────────────────────────────────────────────────────────
    path('school/', SchoolInfoView.as_view(), name='school_info'),

    # ── Grades ────────────────────────────────────────────────────────────────
    path('grades/', GradesView.as_view(), name='grades'),
    path('grades/<int:pk>/', GradeDetailView.as_view(), name='grade_detail'),

    # ── Streams ───────────────────────────────────────────────────────────────
    path('streams/', StreamsView.as_view(), name='streams'),
    path('streams/<int:pk>/', StreamDetailView.as_view(), name='stream_detail'),

    # ── Terms ─────────────────────────────────────────────────────────────────
    path('terms/', TermsView.as_view(), name='terms'),
    path('terms/<int:pk>/', TermDetailView.as_view(), name='term_detail'),

    # ── Subjects ──────────────────────────────────────────────────────────────
    path('subjects/', SubjectsView.as_view(), name='subjects'),
    path('subjects/<int:pk>/', SubjectDetailView.as_view(), name='subject_detail'),

    # ── Time Slots ────────────────────────────────────────────────────────────
    path('time-slots/', TimeSlotsView.as_view(), name='time_slots'),

    # ── Timetables ────────────────────────────────────────────────────────────
    path('timetables/', TimetablesView.as_view(), name='timetables'),
    path('timetable/teacher/<str:teacher_id>/', TeacherTimetableView.as_view(), name='teacher_timetable'),
    path('timetable/student/<str:student_id>/', StudentTimetableView.as_view(), name='student_timetable'),

    # ── Lessons ───────────────────────────────────────────────────────────────
    path('lessons/', LessonsManageView.as_view(), name='lessons_manage'),
    path('lessons/<int:pk>/', LessonManageDetailView.as_view(), name='lesson_manage_detail'),
    path('lessons/teacher/<str:teacher_id>/', TeacherLessonsView.as_view(), name='teacher_lessons'),

    # ── Staff ─────────────────────────────────────────────────────────────────
    path('staff/', StaffListView.as_view(), name='staff_list'),
    path('staff/<int:pk>/', StaffDetailView.as_view(), name='staff_detail'),
    path('staff/<int:pk>/assign-class-teacher/', ClassTeacherAssignView.as_view(),
         name='assign_class_teacher'),

    # ── Students ──────────────────────────────────────────────────────────────
    path('school/students/', StudentsListView.as_view(), name='school_students'),
    path('students/<int:pk>/', StudentDetailManageView.as_view(), name='student_detail'),
    path('students/<int:pk>/status/', StudentStatusView.as_view(), name='student_status'),

    # ── Parents ───────────────────────────────────────────────────────────────
    path('parents/', ParentsListView.as_view(), name='parents_list'),
    path('parents/<int:pk>/', ParentDetailView.as_view(), name='parent_detail'),
    path('parent/children/', ParentChildrenView.as_view(), name='parent_children'),

    # ── Attendance ────────────────────────────────────────────────────────────
    path('attendance/', AttendanceRecordsView.as_view(), name='attendance_records'),
    path('attendance/<int:pk>/', AttendanceDetailView.as_view(), name='attendance_detail'),
    path('stream/<int:pk>/attendance/', StreamAttendanceRecordsView.as_view(), name='stream_attendance'),

    # ── Submissions ───────────────────────────────────────────────────────────
    path('submissions/', SubmissionsView.as_view(), name='submissions'),
    path('submissions/<int:pk>/', SubmissionDetailView.as_view(), name='submission_detail'),

    # ── Assignments ───────────────────────────────────────────────────────────
    path('assignments/', AssignmentsView.as_view(), name='assignments'),
    path('assignments/<int:pk>/', AssignmentDetailView.as_view(), name='assignment_detail'),

    # ── Discipline ────────────────────────────────────────────────────────────
    path('discipline/', DisciplineRecordsView.as_view(), name='discipline_records'),
    path('discipline/<int:pk>/', DisciplineDetailView.as_view(), name='discipline_detail'),

    # ── Exams ─────────────────────────────────────────────────────────────────
    path('exams/', ExamSessionsView.as_view(), name='exam_sessions'),
    path('exams/<int:pk>/', ExamSessionDetailView.as_view(), name='exam_session_detail'),
    path('exams/<int:pk>/publish/', ExamPublishView.as_view(), name='exam_publish'),
    path('exams/<int:pk>/results/', ExamResultsView.as_view(), name='exam_results'),
    path('my/exam-results/', MyExamResultsView.as_view(), name='my_exam_results'),

    # ── Finance ───────────────────────────────────────────────────────────────
    path('finance/invoices/', FeeInvoicesView.as_view(), name='fee_invoices'),
    path('finance/invoices/<int:pk>/', FeeInvoiceDetailView.as_view(), name='fee_invoice_detail'),
    path('finance/invoices/<int:pk>/payment/', FeePaymentView.as_view(), name='fee_payment'),
    path('finance/structures/', FeeStructuresView.as_view(), name='fee_structures'),
    path('my/fees/', StudentFeesView.as_view(), name='my_fees'),

    # ── Complaints ────────────────────────────────────────────────────────────
    path('complaints/', ComplaintsView.as_view(), name='complaints'),
    path('complaints/<int:pk>/', ComplaintDetailView.as_view(), name='complaint_detail'),

    # ── School Announcements (Announcement model) ─────────────────────────────
    path('announcements/school/', SchoolAnnouncementsView.as_view(), name='school_announcements'),
    path('announcements/school/<int:pk>/', SchoolAnnouncementDetailView.as_view(),
         name='school_announcement_detail'),

    # ── Notifications (Notification model — user-targeted) ────────────────────
    path('announcements/', AnnouncementsView.as_view(), name='announcements'),
    path('notifications/send/', SendNotificationView.as_view(), name='send_notification'),
    path('notifications/<int:pk>/read/', MarkNotificationReadView.as_view(), name='mark_read'),
    path('notifications/mark-read/', MarkNotificationReadView.as_view(), name='mark_read_bulk'),

    # ── Admin Actions ─────────────────────────────────────────────────────────
    path('grades/promote/', GradePromoteView.as_view(), name='grade_promote'),
    path('class-teacher/assign/', ClassTeacherAssignView.as_view(), name='class_teacher_assign'),

    # ── Dashboards ────────────────────────────────────────────────────────────
    path('dashboard/', DashboardView.as_view(), name='dashboard'),
    path('policy/dashboard/', PolicyDashboardView.as_view(), name='policy_dashboard'),

    # ── Stats ─────────────────────────────────────────────────────────────────
    path('stats/student/<str:student_id>/', StudentStatsView.as_view(), name='student_stats'),
    path('stats/parent/', ParentStatsView.as_view(), name='parent_stats'),
    path('stats/teacher/', TeacherStatsView.as_view(), name='teacher_stats'),

    # ═══════════════════════════════════════════════════════════════════════
    # SPRINT 1 — Core School Management Gaps
    # ═══════════════════════════════════════════════════════════════════════

    # ── Create users ─────────────────────────────────────────────────────
    path('students/create/', StudentCreateView.as_view(), name='student_create'),
    path('staff/create/', StaffCreateView.as_view(), name='staff_create'),
    path('parents/create/', ParentCreateView.as_view(), name='parent_create'),
    path('users/<int:pk>/reset-password/', UserPasswordResetView.as_view(), name='user_reset_password'),

    # ── Staff subjects ────────────────────────────────────────────────────
    path('staff/<int:pk>/subjects/', StaffSubjectsView.as_view(), name='staff_subjects'),
    path('staff/<int:pk>/subjects/<int:subject_pk>/remove/', StaffSubjectRemoveView.as_view(), name='staff_subject_remove'),

    # ── Parent-student link ───────────────────────────────────────────────
    path('parent-student/link/', ParentStudentLinkView.as_view(), name='parent_student_link'),

    # ── Enrollments ───────────────────────────────────────────────────────
    path('enrollments/', EnrollmentsView.as_view(), name='enrollments'),
    path('enrollments/<int:pk>/', EnrollmentDetailView.as_view(), name='enrollment_detail'),

    # ── Timetable detail ──────────────────────────────────────────────────
    path('timetables/<int:pk>/', TimetableDetailView.as_view(), name='timetable_detail'),

    # ── Time slot detail ──────────────────────────────────────────────────
    path('time-slots/<int:pk>/', TimeSlotDetailView.as_view(), name='time_slot_detail'),

    # ── Class Teacher portal ──────────────────────────────────────────────
    path('class-teacher/list/', ClassTeacherListView.as_view(), name='class_teacher_list'),
    path('class-teacher/roster/', ClassTeacherRosterView.as_view(), name='class_teacher_roster'),
    path('class-teacher/roll-call/', ClassTeacherRollCallView.as_view(), name='class_teacher_roll_call'),
    path('class-teacher/attendance-summary/', ClassTeacherAttendanceSummaryView.as_view(), name='class_teacher_attendance_summary'),
    path('class-teacher/subject-summary/', ClassTeacherSubjectSummaryView.as_view(), name='class_teacher_subject_summary'),

    # ── Attendance summaries & smart mark ────────────────────────────────
    path('attendance/summary/', AttendanceSummaryView.as_view(), name='attendance_summary'),
    path('teacher/attendance/summary/', TeacherAttendanceSummaryView.as_view(), name='teacher_attendance_summary'),
    path('teacher/attendance/<int:lesson_id>/smart/', SmartAttendanceView.as_view(), name='smart_attendance'),

    # ═══════════════════════════════════════════════════════════════════════
    # SPRINT 2 — Finance, Exams, Attendance Completeness
    # ═══════════════════════════════════════════════════════════════════════

    # ── Fee Types ─────────────────────────────────────────────────────────
    path('finance/fee-types/', FeeTypesView.as_view(), name='fee_types'),
    path('finance/fee-types/<int:pk>/', FeeTypeDetailView.as_view(), name='fee_type_detail'),

    # ── Fee Structure detail ──────────────────────────────────────────────
    path('finance/structures/<int:pk>/', FeeStructureDetailView.as_view(), name='fee_structure_detail'),

    # ── Fee Invoice extras ────────────────────────────────────────────────
    path('finance/invoices/generate/', FeeInvoiceBulkGenerateView.as_view(), name='fee_invoice_generate'),
    path('finance/invoices/<int:pk>/stk-push/', FeeSTKPushView.as_view(), name='fee_stk_push'),
    path('finance/invoices/<int:pk>/receipt/', FeeInvoiceReceiptView.as_view(), name='fee_invoice_receipt'),
    path('finance/collection-report/', FeeCollectionReportView.as_view(), name='fee_collection_report'),
    path('finance/student/<int:pk>/statement/', StudentFeeStatementView.as_view(), name='student_fee_statement'),

    # ── Exam rankings & reports ───────────────────────────────────────────
    path('exams/<int:pk>/ranking/grade/', ExamGradeRankingView.as_view(), name='exam_grade_ranking'),
    path('exams/<int:pk>/ranking/stream/<int:stream_pk>/', ExamStreamRankingView.as_view(), name='exam_stream_ranking'),
    path('exams/<int:pk>/subjects/', ExamSubjectPerformanceView.as_view(), name='exam_subject_performance'),
    path('exams/<int:pk>/slip/<int:student_pk>/', ExamResultSlipView.as_view(), name='exam_result_slip'),
    path('exams/results/<int:pk>/', ExamResultDetailView.as_view(), name='exam_result_detail'),

    # ═══════════════════════════════════════════════════════════════════════
    # SPRINT 3 — DIL (Digital Interactive Learning) Module
    # ═══════════════════════════════════════════════════════════════════════

    # ── Subject catalog ───────────────────────────────────────────────────
    path('dil/subjects/', DILSubjectsView.as_view(), name='dil_subjects'),

    # ── Programs ──────────────────────────────────────────────────────────
    path('dil/programs/', DILProgramsView.as_view(), name='dil_programs'),
    path('dil/programs/<int:pk>/', DILProgramDetailView.as_view(), name='dil_program_detail'),
    path('dil/programs/enroll/', DILEnrollView.as_view(), name='dil_enroll'),

    # ── Virtual Classes ───────────────────────────────────────────────────
    path('dil/classes/', DILClassesView.as_view(), name='dil_classes'),
    path('dil/classes/<int:pk>/', DILClassDetailView.as_view(), name='dil_class_detail'),
    path('dil/classes/<int:pk>/join/', DILClassJoinView.as_view(), name='dil_class_join'),
    path('dil/classes/<int:pk>/attendance/', DILClassAttendanceView.as_view(), name='dil_class_attendance'),
    path('dil/classes/<int:pk>/recording/', DILClassRecordingView.as_view(), name='dil_class_recording'),
    path('dil/classes/<int:pk>/remind/', DILClassReminderView.as_view(), name='dil_class_remind'),

    # ── Lessons ───────────────────────────────────────────────────────────
    path('dil/lessons/', DILLessonsView.as_view(), name='dil_lessons'),
    path('dil/lessons/<int:pk>/', DILLessonDetailView.as_view(), name='dil_lesson_detail'),

    # ── Assignments ───────────────────────────────────────────────────────
    path('dil/assignments/', DILAssignmentsView.as_view(), name='dil_assignments'),
    path('dil/assignments/<int:pk>/', DILAssignmentDetailView.as_view(), name='dil_assignment_detail'),
    path('dil/assignments/<int:pk>/submit/', DILAssignmentSubmitView.as_view(), name='dil_assignment_submit'),
    path('dil/submissions/', DILSubmissionsView.as_view(), name='dil_submissions'),
    path('dil/submissions/<int:pk>/grade/', DILSubmissionGradeView.as_view(), name='dil_submission_grade'),

    # ── Assessments ───────────────────────────────────────────────────────
    path('dil/assessments/', DILAssessmentsView.as_view(), name='dil_assessments'),
    path('dil/assessments/<int:pk>/', DILAssessmentDetailView.as_view(), name='dil_assessment_detail'),
    path('dil/assessments/<int:pk>/questions/', DILAssessmentQuestionsView.as_view(), name='dil_assessment_questions'),
    path('dil/questions/<int:pk>/', DILQuestionDetailView.as_view(), name='dil_question_detail'),
    path('dil/assessments/<int:pk>/take/', DILTakeAssessmentView.as_view(), name='dil_take_assessment'),
    path('dil/attempts/<int:pk>/result/', DILAttemptResultView.as_view(), name='dil_attempt_result'),
    path('dil/assessments/<int:pk>/publish/', DILPublishResultsView.as_view(), name='dil_publish_results'),

    # ── Notification Templates ────────────────────────────────────────────
    path('dil/notification-templates/', DILNotificationTemplatesView.as_view(), name='dil_notif_templates'),
    path('dil/notification-templates/<int:pk>/', DILNotificationTemplatesView.as_view(), name='dil_notif_template_detail'),

    # ═══════════════════════════════════════════════════════════════════════
    # SPRINT 4 — Tuition Platform
    # ═══════════════════════════════════════════════════════════════════════

    path('tuition/programs/', TuitionProgramsView.as_view(), name='tuition_programs'),
    path('tuition/enroll/', TuitionEnrollView.as_view(), name='tuition_enroll'),
    path('tuition/payments/<int:pk>/stk-push/', TuitionPaymentSTKPushView.as_view(), name='tuition_stk_push'),
    path('tuition/teacher/dashboard/', TuitionTeacherDashboardView.as_view(), name='tuition_teacher_dashboard'),
    path('tuition/student/dashboard/', TuitionStudentDashboardView.as_view(), name='tuition_student_dashboard'),
    path('tuition/parent/', TuitionParentView.as_view(), name='tuition_parent'),
]
