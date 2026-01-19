from django.shortcuts import render, redirect,get_object_or_404
from django.contrib.auth import authenticate, login, logout,update_session_auth_hash
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import PasswordChangeForm
from school.models import Timetable,TeacherStreamAssignment,Streams, Term, Lesson, Session, Enrollment, StaffProfile, Student, Parent,Attendance,DisciplineRecord,TimeSlot
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
def LoginView(request):
    if request.method == "POST":
        email = request.POST.get("email")
        password = request.POST.get("password")
        try:
            user = User.objects.get(email=email)
            user = authenticate(request, email=email, password=password)
            if user is not None:
                login(request, user)
                messages.success(request, "Welcome Back!")
                print("User authenticated successfully")
                # Role-based redirects using boolean fields
                if user.is_superuser:
                    return redirect("kiswate_digital_app:kiswate_admin_dashboard")
                elif user.is_parent:  # Parent role
                    return redirect("userauths:parent-dashboard")
                elif user.is_student:  # Student role
                    return redirect("userauths:student-dashboard")
                elif user.is_teacher or user.school_staff:  # Teacher/Staff role
                    if user.is_teacher:  # Specific teacher check
                        return redirect("userauths:teacher-dashboard")
                    else:
                        return redirect("school:dashboard")  # Other staff to general dashboard
                elif user.is_admin:
                    return redirect("school:dashboard")  # Admin dashboard
                else:
                    return redirect("school:dashboard")  # Default for other users
            else:
                messages.warning(request, "Username or password does not exist")
                return redirect("userauths:sign-in")
        except User.DoesNotExist:
            messages.warning(request, "User does not exist")
            return redirect("userauths:sign-in")
    
    # GET request: Handle already authenticated users
    if request.user.is_authenticated:
        # Redirect based on current role (using booleans)
        if request.user.is_superuser:
            return redirect("kiswate_digital_app:kiswate_admin_dashboard")
        elif request.user.is_parent:
            return redirect("userauths:parent-dashboard")
        elif request.user.is_student:
            return redirect("userauths:student-dashboard")
        elif request.user.is_teacher or request.user.school_staff:
            if request.user.is_teacher:
                return redirect("userauths:teacher-dashboard")
            else:
                return redirect("school:dashboard")
        elif request.user.is_admin:
            return redirect("school:dashboard")
        else:
            return redirect("school:dashboard")
    
    return render(request, "landing/login.html", {})

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


WEEKDAY_CHOICES = [
    ('monday', 'Monday'),
    ('tuesday', 'Tuesday'),
    ('wednesday', 'Wednesday'),
    ('thursday', 'Thursday'),
    ('friday', 'Friday'),
    ('saturday', 'Saturday'),
    ('sunday', 'Sunday'),
]


@login_required
def parent_dashboard(request):
    """
    Parent Dashboard:
    - Children overview
    - Lessons & Sessions
    - Attendance Summary (P/A included)
    - Discipline Summary
    - Fee Overview
    """
    user = request.user

    if not hasattr(user, "parent"):
        messages.error(request, "Access denied: Parent account required.")
        return redirect("userauths:sign-in")

    parent = user.parent
    children = parent.children.all()

    if not children.exists():
        return render(
            request,
            "school/parent/dashboard.html",
            {"message": "No children enrolled under your account.", "children": []},
        )

    today = timezone.now().date()
    child_data = []

    for child in children:
        # ------------------------
        # ACTIVE TIMETABLE
        # ------------------------
        active_timetable = (
            Timetable.objects.filter(
                school=parent.school,
                grade=child.grade_level,
                start_date__lte=today,
                end_date__gte=today,
            )
            .first()
        )

        if active_timetable and hasattr(child, "stream") and child.stream:
            lessons = (
                Lesson.objects.filter(timetable=active_timetable, stream=child.stream)
                .select_related("subject", "teacher", "time_slot")
                .order_by("lesson_date", "time_slot__start_time")
            )
        else:
            lessons = []

        # ------------------------
        # ATTENDANCE
        # ------------------------
        attendance_qs = Attendance.objects.filter(enrollment__student=child)
        status_keys = ["P", "A", "ET", "UT", "EA", "UA", "IB", "18", "20"]
        status_counts = {key: attendance_qs.filter(status=key).count() for key in status_keys}
        status_counts["total"] = attendance_qs.count()
        status_counts["present_percentage"] = int((status_counts.get("P", 0) / status_counts["total"] * 100) if status_counts["total"] else 0)

        # ------------------------
        # DISCIPLINE
        # ------------------------
        if hasattr(child, "discipline_records"):
            discipline_list = child.discipline_records.all().order_by("-date")
            discipline_score = 0
        else:
            discipline_list = []
            discipline_score = 0

        # ------------------------
        # SUBJECT ENROLLMENTS
        # ------------------------
        enrollments = child.enrollments.filter(status="active").select_related("lesson__subject")

        # ------------------------
        # FEE OVERVIEW
        # ------------------------
        fee_total = getattr(child, "fee_total", 0) or 0
        fee_paid = getattr(child, "fee_paid", 0) or 0
        fee_balance = fee_total - fee_paid
        fee_percentage = int((fee_paid / fee_total * 100) if fee_total else 0)

        # ------------------------
        # Bundle child data
        # ------------------------
        child_data.append(
            {
                "child": child,
                "lessons": lessons,
                "attendance": status_counts,
                "discipline_records": discipline_list,
                "discipline_score": discipline_score,
                "enrollments": enrollments,
                "active_term": f"Term {active_timetable.term} {active_timetable.year}" if active_timetable else "N/A",
                "fee_total": fee_total,
                "fee_paid": fee_paid,
                "fee_balance": fee_balance,
                "fee_percentage": fee_percentage,
            }
        )

    # ------------------------
    # CHILD SELECTION
    # ------------------------
    requested_child_id = request.GET.get("child_id")
    selected_child = None
    if requested_child_id:
        for data in child_data:
            if str(data["child"].id) == requested_child_id:
                selected_child = data["child"]
                break
    if not selected_child:
        selected_child = children.first()

    context = {
        "children": children,
        "child_data": child_data,
        "selected_child": selected_child,
    }

    return render(request, "school/parent/dashboard.html", context)

from collections import defaultdict

from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from school.models import Lesson, TimeSlot, Enrollment, Session, Term

@login_required
def student_dashboard(request):
    user = request.user
    try:
        # Ensure the user is a student
        student = user.student
    except Student.DoesNotExist:
        messages.error(request, "Student profile not found.")
        return redirect("userauths:sign-in")
    student = user.student
    today = timezone.now().date()

    # Get active enrollments
    enrollments = student.enrollments.filter(status='active').select_related('lesson__subject', 'lesson__teacher', 'lesson__time_slot', 'lesson__stream')

    # Extract lesson IDs from enrollments
    lesson_ids = enrollments.values_list('lesson_id', flat=True)

    # Filter lessons
    lessons_qs = Lesson.objects.filter(
        id__in=lesson_ids,
        timetable__school=student.school
    ).select_related('subject', 'teacher', 'time_slot', 'stream').prefetch_related('sessions')

    # Apply filters
    term_id = request.GET.get('term')
    lesson_id = request.GET.get('lesson')
    session_id = request.GET.get('session')
    date_filter = request.GET.get('date')

    if term_id:
        lessons_qs = lessons_qs.filter(timetable__term_id=term_id)
    if lesson_id:
        lessons_qs = lessons_qs.filter(id=lesson_id)
    if session_id:
        lessons_qs = lessons_qs.filter(sessions__id=session_id)
    if date_filter:
        lessons_qs = lessons_qs.filter(lesson_date=date_filter)

    lessons_qs = lessons_qs.order_by('day_of_week', 'time_slot__start_time')

    # Prepare timetable grid
    time_slots = TimeSlot.objects.filter(school=student.school).order_by('start_time')
    weekdays = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]

    # Initialize timetable_grid
    timetable_grid = {day: {} for day in weekdays}
    for lesson in lessons_qs:
        if lesson.day_of_week and lesson.time_slot:
            day = lesson.day_of_week.capitalize()  # normalize weekday
            timetable_grid[day].setdefault(lesson.time_slot.id, []).append(lesson)

    # Stats cards
    stats = [
        {'title': "Today's Schedule", 'value': lessons_qs.filter(lesson_date=today).count(), 'icon': 'bi-calendar-day', 'color': 'success'},
        {'title': "Subjects", 'value': enrollments.count(), 'icon': 'bi-book', 'color': 'success'},
        {'title': "Attendance Rate", 'value': '95%', 'icon': 'bi-bar-chart-line', 'color': 'success'},
        {'title': "Assignments Due", 'value': 2, 'icon': 'bi-journal-check', 'color': 'success'},
    ]

    # For filters
    terms = Timetable.objects.filter(school=student.school).order_by('start_date')
    lessons_list = lessons_qs
    sessions_list = Session.objects.filter(lesson__in=lessons_qs).distinct()

    context = {
        'student': student,
        'grade': student.grade_level,
        'enrollments': enrollments,
        'today_lessons': lessons_qs.filter(lesson_date=today),
        'timetable_grid': timetable_grid,
        'time_slots': time_slots,
        'weekdays': weekdays,
        'stats': stats,
        'terms': terms,
        'lessons_list': lessons_list,
        'sessions_list': sessions_list,
        'request': request,
    }

    return render(request, 'school/student/dashboard.html', context)


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

    try:
        teacher_profile = user.staffprofile
    except:
        return render(request, 'school/teacher/not_authorized.html', status=403)

    # Only allow teachers (position='teacher') to access
    if teacher_profile.position != 'teacher':
        return render(request, 'school/teacher/not_authorized.html', status=403)

    # Get selected date from query param
    selected_date_str = request.GET.get('date')
    today = timezone.localdate()
    selected_date = today
    if selected_date_str:
        try:
            selected_date = timezone.datetime.strptime(selected_date_str, "%Y-%m-%d").date()
        except ValueError:
            pass

    # Calculate current week
    week_start = selected_date - timedelta(days=selected_date.weekday())
    week_end = week_start + timedelta(days=6)
    week_days = [week_start + timedelta(days=i) for i in range(7)]

    # Fetch lessons for this teacher in the week
    assigned_lessons = Lesson.objects.filter(
        teacher=teacher_profile,
        lesson_date__range=(week_start, week_end),
        timetable__school=teacher_profile.school
    ).select_related('timetable__grade', 'subject', 'time_slot', 'stream').order_by(
        'lesson_date', 'time_slot__start_time'
    )

    # Unique time slots
    time_slots = sorted({lesson.time_slot for lesson in assigned_lessons if lesson.time_slot}, key=lambda ts: ts.start_time)

    # Build timetable: {Grade obj: {TimeSlot obj: {date: [lessons]}}}
    timetable_by_grade = {}
    for lesson in assigned_lessons:
        if not lesson.time_slot:
            continue
        grade = lesson.timetable.grade
        timetable_by_grade.setdefault(grade, {})
        timetable_by_grade[grade].setdefault(lesson.time_slot, {})
        timetable_by_grade[grade][lesson.time_slot].setdefault(lesson.lesson_date, [])
        timetable_by_grade[grade][lesson.time_slot][lesson.lesson_date].append(lesson)

    # Stats for dashboard
    stats = [
        {'title': "Today's Lessons", 'value': assigned_lessons.filter(lesson_date=selected_date).count(), 'icon': 'fa-chalkboard-teacher', 'color': 'success'},
        {'title': "This Week's Lessons", 'value': assigned_lessons.count(), 'icon': 'fa-calendar-week', 'color': 'primary'},
        {'title': "Subjects", 'value': teacher_profile.subjects.count(), 'icon': 'fa-book', 'color': 'warning'},
        {'title': "Sessions", 'value': Session.objects.filter(lesson__in=assigned_lessons, teacher=teacher_profile).count(), 'icon': 'fa-hourglass', 'color': 'info'},
    ]

    context = {
        'school': teacher_profile.school,
        'subjects': teacher_profile.subjects.all(),
        'today_lessons': assigned_lessons.filter(lesson_date=selected_date),
        'assigned_lessons': assigned_lessons,
        'timetable_by_grade': timetable_by_grade,
        'week_days': week_days,
        'time_slots': time_slots,
        'selected_date': selected_date,
        'stats': stats,
    }

    return render(request, 'school/teacher/dashboard.html', context)



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
