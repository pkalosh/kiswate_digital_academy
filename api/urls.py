# api/urls.py - Minor Update for Auth (email-based)
# Unchanged from previous, but ensure login uses email
from django.urls import path, include
from rest_framework_simplejwt.views import TokenRefreshView
from .views import (
    register, login, LogoutView, StaticDataView,
    TeacherTimetableView, StudentTimetableView,
    AttendanceRecordsView, DisciplineRecordsView,
    AssignmentsView, AnnouncementsView,
    StudentStatsView, ParentStatsView,AttendanceDetailView,TeacherStatsView,ParentChildrenView
)

urlpatterns = [
    # Auth
    path('auth/register/', register, name='register'),
    path('auth/login/', login, name='login'),
    path('auth/logout/', LogoutView.as_view(), name='logout'),
    path('auth/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    
    # Static
    path('static/data/', StaticDataView.as_view(), name='static_data'),
    
    # Timetables
    path('timetable/teacher/<str:teacher_id>/', TeacherTimetableView.as_view(), name='teacher_timetable'),
    path('timetable/student/<str:student_id>/', StudentTimetableView.as_view(), name='student_timetable'),

    #Lessons
    path('lessons/teacher/<str:teacher_id>/', TeacherTimetableView.as_view(), name='teacher_lessons'),
    
    # Records
    path('attendance/', AttendanceRecordsView.as_view(), name='attendance_records'),
    path('attendance/<int:pk>/', AttendanceDetailView.as_view(), name='attendance_detail'),

    path('discipline/', DisciplineRecordsView.as_view(), name='discipline_records'),
    path('discipline/<int:pk>/', DisciplineRecordsView.as_view(), name='discipline_detail'),
    path('assignments/', AssignmentsView.as_view(), name='assignments'),
    path('assignments/<int:pk>/', AssignmentsView.as_view(), name='assignment_detail'),
    
    path('announcements/', AnnouncementsView.as_view(), name='announcements'),
    
    # Stats
    path('stats/student/<str:student_id>/', StudentStatsView.as_view(), name='student_stats'),
    path('stats/parent/', ParentStatsView.as_view(), name='parent_stats'),
    path('stats/teacher/', TeacherStatsView.as_view(), name='teacher_stats'),
    path('parent/children/', ParentChildrenView.as_view(), name='parent_children'),


]