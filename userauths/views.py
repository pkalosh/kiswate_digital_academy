from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout,update_session_auth_hash
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import PasswordChangeForm
from school.models import Timetable, Lesson, Session, Enrollment, StaffProfile, Student, Parent
from django.utils import timezone

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
                    return redirect("school:parent-dashboard")
                elif user.is_student:  # Student role
                    return redirect("school:student-dashboard")
                elif user.is_teacher or user.school_staff:  # Teacher/Staff role
                    if user.is_teacher:  # Specific teacher check
                        return redirect("school:teacher-dashboard")
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
            return redirect("school:parent-dashboard")
        elif request.user.is_student:
            return redirect("school:student-dashboard")
        elif request.user.is_teacher or request.user.school_staff:
            if request.user.is_teacher:
                return redirect("school:teacher-dashboard")
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
    try:
        if not request.user.is_parent:
            messages.error(request, "Access denied: Parent role required.")
            return redirect('school:dashboard')
        
        parent = request.user.parent  # Access via OneToOneField
        children = parent.children.all()  # M2M to Student
        if not children.exists():
            return render(request, 'school/parent/dashboard.html', {'message': 'No children enrolled.'})
       
        # Auto-select first child or via GET
        child_id = request.GET.get('child_id')
        if child_id:
            student = Student.objects.get(id=child_id, parent=parent)
        else:
            student = children.first()
       
        # Active timetable for child's grade
        today = timezone.now().date()  # Nov 20, 2025
        active_timetable = Timetable.objects.filter(
            grade=student.grade_level,
            start_date__lte=today,
            end_date__gte=today,
            school=parent.school  # Derive from parent profile (adjust if needed)
        ).first()
       
        if active_timetable:
            lessons = Lesson.objects.filter(
                timetable=active_timetable
            ).select_related('subject', 'teacher').order_by('date', 'start_time')
           
            sessions = Session.objects.filter(
                lesson__in=lessons
            ).select_related('lesson', 'subject', 'platform').order_by('scheduled_at')
        else:
            lessons = sessions = []
       
        # Enrollments for filters
        enrollments = student.enrollments.filter(status='active').select_related('subject')
       
        context = {
            'child': student,
            'lessons': lessons,
            'sessions': sessions,
            'timetable': active_timetable,
            'enrollments': enrollments,  # For subject filter
            'children': children,  # Dropdown for multiple kids
            'active_term': f"Term {active_timetable.term} {active_timetable.year}" if active_timetable else None,
        }
        return render(request, 'school/parent/dashboard.html', context)
   
    except Parent.DoesNotExist:
        messages.error(request, "Parent profile not found.")
        return redirect('school:dashboard')
    except Student.DoesNotExist:
        messages.error(request, "Selected child not found.")
        return redirect('school:parent-dashboard')

@login_required
def student_dashboard(request):
    try:
        if not request.user.is_student:
            messages.error(request, "Access denied: Student role required.")
            return redirect('school:dashboard')
        
        student = request.user.student  # Access via OneToOneField
        today = timezone.now().date()
       
        # Lessons/Sessions for enrolled subjects in active term
        enrollments = student.enrollments.filter(status='active').select_related('subject')
        active_lessons = Lesson.objects.filter(
            subject__in=enrollments.values('subject'),
            timetable__start_date__lte=today,
            timetable__end_date__gte=today,
            timetable__school=student.school  # Derive from student profile
        ).select_related('timetable', 'subject', 'teacher').order_by('date', 'start_time')
       
        sessions = Session.objects.filter(
            lesson__in=active_lessons
        ).select_related('lesson', 'subject', 'platform').order_by('scheduled_at')
       
        # Today's lessons for quick view
        today_lessons = active_lessons.filter(date=today)
       
        context = {
            'lessons': active_lessons,
            'today_lessons': today_lessons,
            'sessions': sessions,
            'enrollments': enrollments,  # For filters
            'grade': student.grade_level,
        }
        return render(request, 'school/student/dashboard.html', context)
   
    except Student.DoesNotExist:
        messages.error(request, "Student profile not found.")
        return redirect('school:dashboard')

@login_required
def teacher_dashboard(request):
    try:
        if not (request.user.is_teacher or request.user.school_staff):
            messages.error(request, "Access denied: Teacher/Staff role required.")
            return redirect('school:dashboard')
        
        teacher = request.user.staffprofile  # Access via OneToOneField
        today = timezone.now().date()
       
        # Multi-grade: Lessons where teacher is assigned
        assigned_lessons = Lesson.objects.filter(
            teacher=teacher,
            timetable__start_date__lte=today,
            timetable__end_date__gte=today,
            timetable__school=teacher.school  # Derive from staff profile
        ).select_related('timetable__grade', 'subject').order_by('date', 'start_time')
       
        sessions = Session.objects.filter(
            lesson__in=assigned_lessons, teacher=teacher
        ).select_related('lesson', 'subject', 'platform').order_by('scheduled_at')
       
        # Group by grade for tabs/filter
        lessons_by_grade = {}
        for lesson in assigned_lessons:
            grade_name = lesson.timetable.grade.name
            lessons_by_grade.setdefault(grade_name, []).append(lesson)
       
        context = {
            'lessons': assigned_lessons,
            'lessons_by_grade': lessons_by_grade,
            'sessions': sessions,
            'grades': list(lessons_by_grade.keys()),  # For filter dropdown
            'subjects': teacher.subjects.split(',') if teacher.subjects else [],  # For filters
        }
        return render(request, 'school/teacher/dashboard.html', context)
   
    except StaffProfile.DoesNotExist:
        messages.error(request, "Staff profile not found.")
        return redirect('school:dashboard')
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
