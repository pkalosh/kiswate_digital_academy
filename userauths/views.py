from django.shortcuts import render, redirect,get_object_or_404
from django.contrib.auth import authenticate, login, logout,update_session_auth_hash
from django.contrib import messages
from django.urls import reverse
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import PasswordChangeForm
from school.models import (
    Timetable,TeacherStreamAssignment,Streams, Term, Lesson, Session, Enrollment, Subject,
    StaffProfile, Student, Parent,Attendance,DisciplineRecord,TimeSlot,Assignment, Notification
)
from django.utils import timezone
from collections import defaultdict
from userauths.models import User
from django.db.models import Sum


def index(request):
    return render(request, "landing/index.html",{})

def about(request):
    return render(request, "landing/about.html",{})

def modules(request):
    return render(request, "landing/modules.html",{})

def how_it_works(request):
    return render(request, "landing/how_it_works.html",{})

def pricing(request):
    return render(request, "landing/pricing.html",{})

def faqs(request):
    return render(request, "landing/faqs.html",{})

def demo(request):
    return render(request, "landing/demo.html",{})

# Integrated LoginView with Role-Based Redirects
from django.contrib.auth import authenticate, login
from django.contrib import messages
from django.shortcuts import redirect, render
from django.contrib.auth.models import User

def LoginView(request):
    if request.method == "POST":
        email = request.POST.get("email")
        password = request.POST.get("password")

        user = authenticate(request, email=email, password=password)
        if user is None:
            messages.warning(request, "Invalid email or password")
            return redirect("userauths:sign-in")

        login(request, user)
        messages.success(request, f"Welcome back, {user.get_full_name()}!")

        # Role-based redirects — check in priority order
        if user.is_superuser:
            return redirect("kiswate_digital_app:kiswate_admin_dashboard")

        # Check groups (recommended for policymakers and future roles)
        if user.groups.filter(name="policymakers").exists():
            return redirect("school:policy-dashboard")  # ← your policymaker dashboard

        # Boolean fields on User (your current style)
        elif getattr(user, "is_parent", False):
            return redirect("userauths:parent-dashboard")

        elif getattr(user, "is_student", False):
            return redirect("userauths:student-dashboard")

        elif getattr(user, "is_teacher", False) or getattr(user, "school_staff", False):
            if getattr(user, "is_teacher", False):
                return redirect("userauths:teacher-dashboard")
            return redirect("school:dashboard")

        elif getattr(user, "is_admin", False):
            return redirect("school:dashboard")

        # Default/fallback
        else:
            return redirect("school:dashboard")

    # GET request: if already logged in, redirect based on role
    if request.user.is_authenticated:
        if request.user.is_superuser:
            return redirect("kiswate_digital_app:kiswate_admin_dashboard")

        if request.user.groups.filter(name="policymakers").exists():
            return redirect("school:policy-dashboard")

        elif getattr(request.user, "is_parent", False):
            return redirect("userauths:parent-dashboard")

        elif getattr(request.user, "is_student", False):
            return redirect("userauths:student-dashboard")

        elif getattr(request.user, "is_teacher", False) or getattr(request.user, "school_staff", False):
            if getattr(request.user, "is_teacher", False):
                return redirect("userauths:teacher-dashboard")
            return redirect("school:dashboard")

        elif getattr(request.user, "is_admin", False):
            return redirect("school:dashboard")

        else:
            return redirect("school:dashboard")

    return render(request, "landing/login.html")


# Updated Dashboard Views (Adjusted for User Model Booleans and Profile Access)
# Note: Assumes OneToOneFields (e.g., user.parent for is_parent=True users).
# For school attr, derive from profile (e.g., parent.school) since User lacks direct 'school'.

from collections import defaultdict

def generate_timetable_grid(student, timetable):
    """
    Returns a nested dict of lessons by weekday and time slot for the student's grade.
    Format: { 'monday': {1: [lesson1, lesson2], 2: [...] }, ... }
    """
    from collections import defaultdict

    grid = defaultdict(lambda: defaultdict(list))

    # Fix: use __in if streams is a RelatedManager
    student_streams = student.grade_level.streams.all()  # RelatedManager -> queryset

    lessons = Lesson.objects.filter(
        timetable=timetable,
        stream__in=student_streams
    ).select_related("subject", "teacher", "time_slot")

    for lesson in lessons:
        if lesson.day_of_week and lesson.time_slot:
            grid[lesson.day_of_week][lesson.time_slot.id].append(lesson)

    return grid

from django.utils.timezone import now, timedelta
from django.db.models import Avg

@login_required
def parent_dashboard(request):
    parent = getattr(request.user, "parent", None)
    if not parent:
        return render(request, "school/parent/dashboard.html", {"schools": {}, "today": now().date()})

    today = now().date()
    next_7_days = [today + timedelta(days=i) for i in range(7)]

    # Get current active term per school
    active_terms = {t.school_id: t for t in Term.objects.filter(is_active=True)}

    # Get all students for this parent
    students = Student.objects.filter(parents=parent)

    schools = defaultdict(list)  # {school: [student_data, ...]}

    for student in students:
        # Get active enrollments for current term
        student_enrollments = Enrollment.objects.filter(
            student=student,
            status="active",
            school__in=active_terms.keys()
        ).select_related("school", "lesson")

        if not student_enrollments.exists():
            continue

        # Group enrollments by school
        enrollments_by_school = defaultdict(list)
        for enr in student_enrollments:
            enrollments_by_school[enr.school].append(enr)

        for school, enrollments in enrollments_by_school.items():
            term = active_terms.get(school.id)
            
            # Stats
            total_lessons = len(enrollments)
            
            # Attendance: count Present (P)
            attendance_qs = Attendance.objects.filter(
                enrollment__in=enrollments,
                date__lte=today,
                date__gte=term.start_date if term else today - timedelta(days=30)
            )
            attended = attendance_qs.filter(status="P").count()

            # Discipline count
            discipline_count = DisciplineRecord.objects.filter(
                student=student,
                school=school
            ).count()

            # Upcoming lessons next 7 days
            upcoming_lessons = Lesson.objects.filter(
                l_enrollments__in=enrollments,
                lesson_date__range=[today, today + timedelta(days=6)],
                is_canceled=False
            ).select_related("subject", "teacher", "time_slot", "timetable").order_by("lesson_date", "time_slot__start_time")

            # Notifications per school
            notifications = Notification.objects.filter(
                recipient=request.user,
                school=school
            ).order_by("-sent_at")[:10]

            # Build student data
            student_data = {
                "student": student,
                "total_lessons": total_lessons,
                "attended": attended,
                "discipline_count": discipline_count,
                "upcoming_lessons": upcoming_lessons,
                "notifications": notifications,
            }

            schools[school].append(student_data)

    context = {
        "schools": dict(schools),
        "today": today,
    }

    return render(request, "school/parent/dashboard.html", context)

from collections import defaultdict

from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from school.models import Lesson, TimeSlot, Enrollment, Session, Term
WEEKDAYS = [
    ("monday", "Monday"),
    ("tuesday", "Tuesday"),
    ("wednesday", "Wednesday"),
    ("thursday", "Thursday"),
    ("friday", "Friday"),
    ("saturday", "Saturday"),
    ("sunday", "Sunday"),
]

@login_required
def student_dashboard(request):
    user = request.user

    try:
        student = user.student
    except Student.DoesNotExist:
        messages.error(request, "Student profile not found.")
        return redirect("userauths:sign-in")

    today = timezone.now().date()
    today_weekday = today.strftime("%A").lower()  # "monday", "tuesday", ...

    enrollments = (
        student.enrollments
        .filter(status="active")
        .select_related(
            "lesson__subject",
            "lesson__teacher__user",
            "lesson__time_slot",
            "lesson__stream"
        )
    )

    lesson_ids = enrollments.values_list("lesson_id", flat=True)

    start_week = today - timedelta(days=today.weekday())
    end_week = start_week + timedelta(days=6)

    lessons_qs = (
        Lesson.objects
        .filter(
            id__in=lesson_ids,
            lesson_date__range=[start_week, end_week],
            timetable__school=student.school
        )
        .select_related(
            "subject",
            "teacher__user",
            "time_slot",
            "stream"
        )
        .order_by("day_of_week", "time_slot__start_time")
    )

    time_slots = TimeSlot.objects.filter(
        school=student.school
    ).order_by("start_time")

    timetable_grid = {key: {} for key, _ in WEEKDAYS}

    for lesson in lessons_qs:
        if not lesson.day_of_week or not lesson.time_slot:
            continue
        day = lesson.day_of_week.lower()
        timetable_grid[day].setdefault(lesson.time_slot.id, []).append(lesson)

    # ATTENDANCE HEATMAP (week)
    attendance_records = (
        Attendance.objects
        .filter(
            enrollment__student=student,
            date__range=[start_week, end_week]
        )
        .values("date", "status")
    )

    attendance_map = {record["date"]: record["status"] for record in attendance_records}

    heatmap = []
    for i in range(7):
        date = start_week + timedelta(days=i)
        raw_status = attendance_map.get(date, "absent")
        status = str(raw_status).lower().strip() if raw_status else "absent"
        heatmap.append({
            "date": date,
            "status": status
        })

    student_subject_ids = (
        enrollments
        .values_list("lesson__subject_id", flat=True)
        .distinct()
    )

    assignments_due = (
        Assignment.objects
        .filter(
            subject_id__in=student_subject_ids,
            school=student.school,
            due_date__gte=today
        )
        .exclude(submissions__enrollment__student=student)
        .distinct()
        .count()
    )

    # Stats
    stats = [
        {
            "title": "This Week",
            "value": lessons_qs.count(),
            "icon": "bi-calendar-week",
            "color": "success",
            "url": ""
        },
        {
            "title": "Subjects",
            "value": enrollments.count(),
            "icon": "bi-book",
            "color": "primary",
            "url": ""
        },
        {
            "title": "Attendance",
            "value": "95%",  # ← replace with real calculation if available
            "icon": "bi-bar-chart-line",
            "color": "info",
            "url": ""
        },
        {
            "title": "Assignments Due",
            "value": assignments_due,
            "icon": "bi-exclamation-circle",
            "color": "danger",
            "url": ""
        },
    ]

    context = {
        "student": student,
        "weekdays": WEEKDAYS,
        "time_slots": time_slots,
        "timetable_grid": timetable_grid,
        "stats": stats,
        "teachers": StaffProfile.objects.filter(position="teacher"),
        "subjects": Subject.objects.filter(id__in=lesson_ids),
        "heatmap": heatmap,
        "today_weekday": today_weekday,
        "grade": student.stream.grade if hasattr(student.stream, 'grade') else None,
    }

    return render(request, "school/student/dashboard.html", context)

from datetime import timedelta
import datetime

from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from datetime import timedelta
from school.models import Lesson, Session


@login_required
def teacher_dashboard(request):
    user = request.user

    # ----------------------------
    # Authorization
    # ----------------------------
    try:
        teacher_profile = user.staffprofile
    except StaffProfile.DoesNotExist:
        return render(
            request,
            'school/teacher/not_authorized.html',
            status=403
        )

    if teacher_profile.position != 'teacher':
        return render(
            request,
            'school/teacher/not_authorized.html',
            status=403
        )

    school = teacher_profile.school

    # ----------------------------
    # Date Handling
    # ----------------------------
    today = timezone.localdate()
    selected_date = today

    selected_date_str = request.GET.get('date')
    if selected_date_str:
        try:
            selected_date = timezone.datetime.strptime(
                selected_date_str, "%Y-%m-%d"
            ).date()
        except ValueError:
            pass

    # ----------------------------
    # Week Calculation
    # ----------------------------
    week_start = selected_date - timedelta(days=selected_date.weekday())
    week_end = week_start + timedelta(days=6)
    week_days = [week_start + timedelta(days=i) for i in range(7)]

    # ----------------------------
    # Lessons (Weekly)
    # ----------------------------
    assigned_lessons = Lesson.objects.filter(
        teacher=teacher_profile,
        lesson_date__range=(week_start, week_end),
        timetable__school=school
    ).select_related(
        'timetable__grade',
        'subject',
        'time_slot',
        'stream'
    ).order_by(
        'lesson_date',
        'time_slot__start_time'
    )

    # ----------------------------
    # Time Slots
    # ----------------------------
    time_slots = sorted(
        {lesson.time_slot for lesson in assigned_lessons if lesson.time_slot},
        key=lambda ts: ts.start_time
    )

    # ----------------------------
    # Timetable Structure
    # { Grade : { TimeSlot : { date : [lessons] } } }
    # ----------------------------
    timetable_by_grade = {}

    for lesson in assigned_lessons:
        if not lesson.time_slot:
            continue

        grade = lesson.timetable.grade
        timetable_by_grade.setdefault(grade, {})
        timetable_by_grade[grade].setdefault(lesson.time_slot, {})
        timetable_by_grade[grade][lesson.time_slot].setdefault(
            lesson.lesson_date, []
        )
        timetable_by_grade[grade][lesson.time_slot][lesson.lesson_date].append(lesson)

    # ----------------------------
    # Dashboard Statistics
    # ----------------------------

    # 1. Discipline records
    discipline_count = DisciplineRecord.objects.filter(
        teacher=teacher_profile,
        school=school
    ).count()

    # 2. Assignments (from teacher subjects)
    assignment_count = Assignment.objects.filter(
        subject__in=teacher_profile.subjects.all(),
        school=school
    ).count()

    # 3. Lessons today
    today_lessons_count = assigned_lessons.filter(
        lesson_date=selected_date
    ).count()

    # 4. Lessons this week
    week_lessons_count = assigned_lessons.count()

    stats = [
        {
            'title': "Today's Lessons",
            'value': today_lessons_count,
            'icon': 'fa-chalkboard-teacher',
            'color': 'success',
            'url': '#',  # future: teacher_today_lessons
        },
        {
            'title': "This Week's Lessons",
            'value': week_lessons_count,
            'icon': 'fa-calendar-week',
            'color': 'primary',
            'url': '#',  # future: teacher_week_lessons
        },
        {
            'title': "Discipline",
            'value': discipline_count,
            'icon': 'fa-gavel',
            'color': 'warning',
            'url': '#',  # future: teacher_discipline_list
        },
        {
            'title': "Assignments",
            'value': assignment_count,
            'icon': 'fa-tasks',
            'color': 'info',
            'url': '#',  # future: teacher_assignments
        },
    ]

    # ----------------------------
    # Context
    # ----------------------------
    context = {
        'school': school,
        'today': today,
        'selected_date': selected_date,
        'week_days': week_days,
        'time_slots': time_slots,
        'assigned_lessons': assigned_lessons,
        'today_lessons': assigned_lessons.filter(lesson_date=selected_date),
        'timetable_by_grade': timetable_by_grade,
        'stats': stats,
    }

    return render(
        request,
        'school/teacher/dashboard.html',
        context
    )




@login_required
def logoutView(request):
    logout(request)
    messages.success(request, "You have been logged out.")
    return redirect("userauths:sign-in")




@login_required
def change_passwordView(request):
    if request.method == 'POST':
        form = PasswordChangeForm(user=request.user, data=request.POST)
        if form.is_valid():
            user = form.save()
            update_session_auth_hash(request, user)  # Keep the user logged in
            messages.success(request, 'Your password was successfully updated!')
            return redirect('userauths:sign-in')
        else:
            messages.error(request, 'Please correct the error below.')
    else:
        form = PasswordChangeForm(user=request.user)
    
    return render(request, "users/changepassword.html", {'form': form})
