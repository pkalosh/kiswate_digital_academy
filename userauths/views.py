from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout,update_session_auth_hash
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import PasswordChangeForm
from school.models import Timetable, Lesson, Session, Enrollment, StaffProfile, Student, Parent
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
    Parent dashboard showing children, lessons, sessions, and attendance summary.
    Displays upcoming sessions, lessons, and enrollments per child.
    """
    try:
        if not hasattr(request.user, 'parent'):
            messages.error(request, "Access denied: Parent role required.")
            return redirect('userauths:sign-in')

        parent = request.user.parent  # OneToOneField to Parent
        children = parent.children.all()  # M2M to Student

        if not children.exists():
            return render(request, 'school/parent/dashboard.html', {'message': 'No children enrolled.'})

        today = timezone.now().date()

        # Prepare child-specific data
        child_data = []
        for child in children:
            # Active timetable for child's grade
            active_timetable = Timetable.objects.filter(
                grade=child.grade_level,
                start_date__lte=today,
                end_date__gte=today,
                school=parent.school
            ).first()

            # Lessons and sessions
            if active_timetable:
                lessons = Lesson.objects.filter(
                    timetable=active_timetable
                ).select_related('subject', 'teacher').order_by('date', 'start_time')

                sessions = Session.objects.filter(
                    lesson__in=lessons
                ).select_related('lesson', 'subject', 'teacher').order_by('scheduled_at')
            else:
                lessons = []
                sessions = []

            # Active enrollments for subjects
            enrollments = child.enrollments.filter(status='active').select_related('subject')

            child_data.append({
                'child': child,
                'lessons': lessons,
                'sessions': sessions,
                'enrollments': enrollments,
                'active_term': f"Term {active_timetable.term} {active_timetable.year}" if active_timetable else None,
            })

        # Auto-select child via GET
        child_id = request.GET.get('child_id')
        selected_child = None
        if child_id:
            selected_child = next((c['child'] for c in child_data if str(c['child'].id) == str(child_id)), None)
        if not selected_child:
            selected_child = children.first()

        context = {
            'children': children,
            'child_data': child_data,  # List of dicts for each child
            'selected_child': selected_child,
        }

        return render(request, 'school/parent/dashboard.html', context)

    except Parent.DoesNotExist:
        messages.error(request, "Parent profile not found.")
        return redirect('userauths:sign-in')
    except Student.DoesNotExist:
        messages.error(request, "Selected child not found.")
        return redirect('userauths:parent-dashboard')

@login_required
def student_dashboard(request):
    user = request.user
    if not hasattr(user, 'student'):
        messages.error(request, "Access denied: Student role required.")
        return redirect('userauths:sign-in')
    
    student = user.student
    today = timezone.now().date()

    # Base enrollments
    enrollments = student.enrollments.filter(status='active').select_related('subject')

    # Active term filter
    term_id = request.GET.get('term')
    lesson_id = request.GET.get('lesson')
    session_id = request.GET.get('session')
    date_filter = request.GET.get('date')

    # Start with lessons for student's subjects
    lessons_qs = Lesson.objects.filter(
        subject__in=enrollments.values_list('subject', flat=True),
        timetable__school=student.school
    ).select_related('timetable', 'subject', 'teacher')  # remove room, session


    # Apply term/date/lesson/session filters
    if term_id:
        lessons_qs = lessons_qs.filter(timetable__term_id=term_id)
    if date_filter:
        lessons_qs = lessons_qs.filter(date=date_filter)
    if lesson_id:
        lessons_qs = lessons_qs.filter(id=lesson_id)
    if session_id:
        lessons_qs = lessons_qs.filter(session_id=session_id)

    # Order by date and time
    lessons_qs = lessons_qs.order_by('date', 'start_time')

    # Today's lessons
    today_lessons = lessons_qs.filter(date=today)

    # Sessions
    sessions_qs = Session.objects.filter(
        lesson__in=lessons_qs
    ).select_related('lesson', 'subject', 'platform').order_by('scheduled_at')

    # Group lessons by weekday for template
    lessons_by_weekday = defaultdict(list)
    for lesson in lessons_qs:
        weekday = lesson.day_of_week  # e.g., 'Monday'
        lessons_by_weekday[weekday].append(lesson)
    print(lessons_by_weekday)

    # Terms and sessions for filters
    # terms = Term.objects.filter(school=student.school)
    sessions_list = Session.objects.filter(
        lesson__subject__in=enrollments.values_list('subject', flat=True)
    ).distinct()
    lessons_list = lessons_qs.distinct().order_by('subject__name', 'date')

    context = {
        'student': student,
        'grade': student.grade_level,
        'enrollments': enrollments,  # For subject count
        'today_lessons': today_lessons,
        'lessons_by_weekday': dict(lessons_by_weekday),  # This is what template needs, not lessons_by_weekday,  # This is what template needs
        'lessons_list': lessons_list,
        'sessions_list': sessions_list,
        'request': request,
    }

    return render(request, 'school/student/dashboard.html', context)

@login_required
def teacher_dashboard(request):
    try:
        # Check role
        if not (request.user.is_teacher or request.user.school_staff):
            messages.error(request, "Access denied: Teacher/Staff role required.")
            return redirect('userauths:sign-in')

        teacher = request.user.staffprofile  # OneToOneField
        today = timezone.now().date()

        # Lessons assigned to teacher
        assigned_lessons = Lesson.objects.filter(
            teacher=teacher,
            timetable__start_date__lte=today,
            timetable__end_date__gte=today,
            timetable__school=teacher.school
        ).select_related('timetable__grade', 'subject').order_by('date', 'start_time')

        # Sessions assigned to teacher
        sessions = Session.objects.filter(
            lesson__in=assigned_lessons,
            teacher=teacher
        ).select_related('lesson', 'subject', 'platform').order_by('scheduled_at')

        # Group lessons by grade (Grade objects, not names)
        lessons_by_grade = {}
        grades_set = set()
        for lesson in assigned_lessons:
            grade = lesson.timetable.grade
            grades_set.add(grade)
            lessons_by_grade.setdefault(grade, []).append(lesson)

        # Subjects taught by teacher
        subjects = teacher.subjects.all()

        context = {
            'lessons': assigned_lessons,
            'lessons_by_grade': lessons_by_grade,
            'sessions': sessions,
            'grades': sorted(grades_set, key=lambda g: g.name),  # Actual Grade objects
            'subjects': subjects,
            'school': teacher.school,
            'today_lessons': assigned_lessons.filter(date=today),
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
