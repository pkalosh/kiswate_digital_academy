from django.shortcuts import render, redirect,get_object_or_404
from django.contrib.auth import authenticate, login, logout,update_session_auth_hash
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import PasswordChangeForm
from school.models import Timetable,TeacherStreamAssignment,Streams, Lesson, Session, Enrollment, StaffProfile, Student, Parent,Attendance,DisciplineRecord,TimeSlot
from django.utils import timezone
from collections import defaultdict
from userauths.models import User


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


@login_required
def parent_dashboard(request):
    """
    Parent Dashboard:
    - Child list
    - Lessons + Sessions
    - Attendance Summary (New Status Types Supported)
    - Discipline Summary
    - Active Term Display
    """
    user = request.user

    # Ensure this user is a parent
    if not hasattr(user, "parent"):
        messages.error(request, "Access denied: Parent account required.")
        return redirect("userauths:sign-in")

    parent = user.parent

    # Ensure parent has children
    children = parent.children.all()
    if not children.exists():
        return render(
            request,
            "school/parent/dashboard.html",
            {
                "message": "No children enrolled under your account.",
                "children": [],
            },
        )

    today = timezone.now().date()
    child_data = []

    for child in children:

        # -------------------------------------------------------------
        # ACTIVE TIMETABLE FOR CHILD'S GRADE
        # -------------------------------------------------------------
        active_timetable = Timetable.objects.filter(
            school=parent.school,
            grade=child.grade_level,
            start_date__lte=today,
            end_date__gte=today,
        ).first()

        # Lessons & Sessions
        if active_timetable:
            lessons = (
                Lesson.objects.filter(timetable=active_timetable)
                .select_related("subject", "teacher")
                .order_by("lesson_date")
            )

            sessions = (
                Session.objects.filter(lesson__in=lessons)
                .select_related("lesson", "subject", "teacher")
                .order_by("scheduled_at")
            )
        else:
            lessons = []
            sessions = []

        # -------------------------------------------------------------
        # ATTENDANCE — FIXED
        # -------------------------------------------------------------
        attendance_qs = Attendance.objects.filter(
            enrollment__student=child
        ).select_related("lesson", "session", "enrollment")

        # New Status Mappings
        status_counts = {
            "P": 0,
            "ET": 0,
            "UT": 0,
            "EA": 0,
            "UA": 0,
            "IB": 0,
            "18": 0,
            "20": 0,
        }

        for st in status_counts.keys():
            status_counts[st] = attendance_qs.filter(status=st).count()

        status_counts["total"] = attendance_qs.count()

        # -------------------------------------------------------------
        # DISCIPLINE RECORDS
        # -------------------------------------------------------------
        if hasattr(child, "discipline_records"):
            discipline_list = child.discipline_records.all().order_by("-date")
            discipline_score = 0  # Could summarize points if needed
        else:
            discipline_list = []
            discipline_score = 0

        # -------------------------------------------------------------
        # SUBJECT ENROLLMENTS
        # -------------------------------------------------------------
        enrollments = child.enrollments.filter(status="active").select_related(
            "subject"
        )

        # -------------------------------------------------------------
        # Add to child data bundle
        # -------------------------------------------------------------
        child_data.append(
            {
                "child": child,
                "lessons": lessons,
                "sessions": sessions,
                "attendance": status_counts,
                "discipline_records": discipline_list,
                "discipline_score": discipline_score,
                "enrollments": enrollments,
                "active_term": (
                    f"Term {active_timetable.term} {active_timetable.year}"
                    if active_timetable
                    else None
                ),
            }
        )

    # -------------------------------------------------------------
    # CHILD SELECTION
    # -------------------------------------------------------------
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

@login_required
def student_dashboard(request):
    user = request.user
    if not hasattr(user, 'student'):
        messages.error(request, "Access denied: Student role required.")
        return redirect('userauths:sign-in')

    student = user.student
    today = timezone.now().date()
    enrollments = student.enrollments.filter(status='active').select_related('subject')

    lessons_qs = Lesson.objects.filter(
        subject__in=enrollments.values_list('subject', flat=True),
        timetable__school=student.school
    ).select_related('timetable', 'subject', 'teacher', 'stream', 'time_slot')

    # Apply filters
    term_id = request.GET.get('term')
    lesson_id = request.GET.get('lesson')
    session_id = request.GET.get('session')
    date_filter = request.GET.get('date')

    if term_id:
        lessons_qs = lessons_qs.filter(timetable__term_id=term_id)
    if date_filter:
        lessons_qs = lessons_qs.filter(lesson_date=date_filter)
    if lesson_id:
        lessons_qs = lessons_qs.filter(id=lesson_id)
    if session_id:
        lessons_qs = lessons_qs.filter(sessions__id=session_id)

    lessons_qs = lessons_qs.order_by('lesson_date')

    # Prepare timetable grid
    time_slots = TimeSlot.objects.filter(school=student.school).order_by('start_time')
    weekdays = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]

    # Initialize timetable_grid with empty dicts
    timetable_grid = {day: {} for day in weekdays}

    for lesson in lessons_qs:
        if lesson.day_of_week and lesson.time_slot:
            # Normalize to capitalized weekday to match the keys
            day = lesson.day_of_week.capitalize()
            timetable_grid[day][lesson.time_slot.id] = lesson

    context = {
        'student': student,
        'grade': student.grade_level,
        'enrollments': enrollments,
        'today_lessons': lessons_qs.filter(lesson_date=today),
        'timetable_grid': timetable_grid,
        'time_slots': time_slots,
        'weekdays': weekdays,
        'request': request,
    }

    return render(request, 'school/student/dashboard.html', context)



from datetime import timedelta
@login_required
def teacher_dashboard(request):
    try:
        if not (request.user.is_teacher or request.user.school_staff):
            messages.error(request, "Access denied: Teacher/Staff role required.")
            return redirect('userauths:sign-in')

        teacher = request.user.staffprofile
        today = timezone.now().date()

        # Lessons assigned to teacher
        assigned_lessons = Lesson.objects.filter(
            teacher=teacher,
            timetable__start_date__lte=today,
            timetable__end_date__gte=today,
            timetable__school=teacher.school
        ).select_related('timetable__grade', 'subject', 'time_slot').order_by('lesson_date', 'time_slot__start_time')

        # Prepare weekly timetable (Monday-Sunday)
        week_start = today - timedelta(days=today.weekday())
        week_days = [week_start + timedelta(days=i) for i in range(7)]

        # Unique time slots
        time_slots = sorted({lesson.time_slot for lesson in assigned_lessons}, key=lambda ts: ts.start_time)

        # Build timetable: {grade_id: {TimeSlot obj: {date obj: lesson}}}
        timetable = {}
        grades_dict = {}
        for lesson in assigned_lessons:
            grade = lesson.timetable.grade
            grades_dict[grade.id] = grade
            timetable.setdefault(grade.id, {})
            timetable[grade.id].setdefault(lesson.time_slot, {})
            timetable[grade.id][lesson.time_slot][lesson.lesson_date] = lesson

        context = {
            'school': teacher.school,
            'subjects': teacher.subjects.all(),
            'sessions': Session.objects.filter(lesson__in=assigned_lessons, teacher=teacher),
            'today_lessons': assigned_lessons.filter(lesson_date=today),
            'grades_list': sorted(grades_dict.items(), key=lambda x: x[1].name),
            'timetable': timetable,
            'week_days': week_days,
            'time_slots': time_slots,
        }

        return render(request, 'school/teacher/dashboard.html', context)

    except StaffProfile.DoesNotExist:
        messages.error(request, "Staff profile not found.")
        return redirect('userauths:teacher-dashboard')

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
