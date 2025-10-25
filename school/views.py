from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Q
from userauths.models import User
from .models import Grade, School, Parent,StaffProfile,Student
from .forms import GradeForm,ParentCreationForm, ParentEditForm,StaffCreationForm, StaffEditForm,StudentCreationForm, StudentEditForm
import logging
from django.conf import settings
from django.core.mail import send_mail
import random
import string
logger = logging.getLogger(__name__)
# Create your views here.
def dashboard(request):
    return render(request, "school/dashboard.html", {})

@login_required
def school_grades(request):
    # Ensure user is a school admin
    print("Accessing grades view as user:", request.user)  # Keep for console
    logger.info(f"Accessing grades view as user: {request.user.email} (ID: {request.user.id})")
    try:
        school = request.user.school_admin_profile  # <-- FIXED: Remove .school
        logger.info(f"User's school: {school.name} (ID: {school.id})")
        print("User's school:", school.name)  # Keep for console
    except AttributeError as e:
        logger.warning(f"Permission denied for user {request.user.email}: {e}")
        messages.error(request, f"You do not have permission to access this page. (User: {request.user.email})")
        return redirect('school:dashboard')

    if request.method == 'POST':
        form = GradeForm(request.POST, school=school)
        if form.is_valid():
            grade = form.save(commit=False)
            grade.school = school
            grade.save()
            messages.success(request, f'Grade "{grade.name}" created successfully.')
            return redirect('school:school-grades')  # Note: Ensure URL name matches urls.py
    else:
        form = GradeForm(school=school)

    # Fetch grades for the school, with search/filter
    query = request.GET.get('q', '')
    grades = Grade.objects.filter(school=school, is_active=True)
    if query:
        grades = grades.filter(Q(name__icontains=query) | Q(code__icontains=query))

    context = {
        'grades': grades,
        'form': form,
        'school': school,
        'query': query,
    }
    return render(request, "school/grade.html", context)
@login_required
def grade_edit(request, pk):
    school = request.user.school_admin_profile
    grade = get_object_or_404(Grade, pk=pk, school=school)
    
    if request.method == 'POST':
        form = GradeForm(request.POST, instance=grade, school=school)
        if form.is_valid():
            form.save()
            messages.success(request, f'Grade "{grade.name}" updated successfully.')
            return redirect('school:school-grades')
    else:
        form = GradeForm(instance=grade, school=school)

    context = {
        'form': form,
        'grade': grade,
        'school': school,
    }
    return render(request, "school/grade_edit.html", context)  # Separate template for edit, or inline in grade.html

@login_required
def grade_delete(request, pk):
    school = request.user.school_admin_profile
    grade = get_object_or_404(Grade, pk=pk, school=school)
    if request.method == 'POST':
        grade.is_active = False  # Soft delete
        grade.save()
        messages.success(request, f'Grade "{grade.name}" deactivated.')
        return redirect('school:school-grades')
    context = {'grade': grade}
    return render(request, "school/grade_confirm_delete.html", context)

@login_required
def parent_list_create(request):
    """
    List parents with search/filter.
    Handles creation via POST (from add modal).
    """
    try:
        school = request.user.school_admin_profile
    except AttributeError:
        messages.error(request, "Access denied: Admin privileges required.")
        return redirect('school:dashboard')

    if request.method == 'POST':
        form = ParentCreationForm(request.POST, request.FILES, school=school)
        if form.is_valid():
            parent, password = form.save()
            messages.success(
                request,
                f'Successfully created parent "{parent.user.get_full_name()}" ({parent.parent_id}). '
                f'Temporary password: <strong>{password}</strong>. '
                f'Email sent: {"Yes" if form.cleaned_data["send_email"] else "No"}.'
            )
            logger.info(f"Created parent {parent.parent_id} for school {school.name}.")
            return redirect('school:parent_list_create')  # Back to list
        # Errors: Re-render list with bound form
    else:
        form = ParentCreationForm(school=school)

    # List parents
    query = request.GET.get('q', '')
    parents = Parent.objects.filter(school=school).select_related('user').order_by('-user__created_at')
    if query:
        parents = parents.filter(
            Q(user__first_name__icontains=query) |
            Q(user__last_name__icontains=query) |
            Q(parent_id__icontains=query) |
            Q(phone__icontains=query) |
            Q(user__email__icontains=query)
        )

    context = {
        'parents': parents,
        'form': form,  # For add modal
        'school': school,
        'query': query,
    }
    return render(request, 'school/parents.html', context)


@login_required
def parent_edit(request, pk):
    """
    Edit via modal form POST.
    Redirects back to list on success/error.
    """
    try:
        school = request.user.school_admin_profile
    except AttributeError:
        messages.error(request, "Access denied: Admin privileges required.")
        return redirect('school:parent_list_create')

    parent = get_object_or_404(Parent, pk=pk, school=school)

    if request.method == 'POST':
        form = ParentEditForm(request.POST, request.FILES, instance=parent)
        if form.is_valid():
            form.save()
            messages.success(
                request,
                f'Successfully updated parent "{parent.user.get_full_name()}". '
                f'Email sent: {"Yes" if form.cleaned_data["send_email"] else "No"}. '
                f'Password reset: {"Yes" if form.cleaned_data["reset_password"] else "No"}.'
            )
            logger.info(f"Updated parent {parent.parent_id}.")
            return redirect('school:parent_list_create')  # Back to list (modal closes)
        else:
            messages.error(request, "Please correct the form errors.")
            # Re-render list with errors (modal will show on reopen, but since redirect, user sees list)
    # For GET (if direct access): Redirect to list or render full edit (but modal-driven, so redirect)
    messages.info(request, "Use the edit button in the list to modify.")
    return redirect('school:parent_list_create')


@login_required
def parent_delete(request, pk):
    """
    Delete via modal form POST.
    Redirects back to list on success.
    """
    try:
        school = request.user.school_admin_profile
    except AttributeError:
        messages.error(request, "Access denied: Admin privileges required.")
        return redirect('school:parent_list_create')

    parent = get_object_or_404(Parent, pk=pk, school=school)

    if request.method == 'POST':
        user = parent.user
        user.is_active = False
        user.save()
        parent.delete()
        messages.success(request, f'Parent "{parent.user.get_full_name()}" ({parent.parent_id}) has been deleted.')
        logger.info(f"Deleted parent {parent.parent_id}.")
        return redirect('school:parent_list_create')  # Back to list (modal closes)
    
    # For GET (direct access): Redirect to list
    messages.warning(request, "Use the delete button in the list to confirm.")
    return redirect('school:parent_list_create')

@login_required
def staff_list_create(request):
    """
    List staff with search/filter.
    Handles creation via POST (from add modal).
    """
    try:
        school = request.user.school_admin_profile
    except AttributeError:
        messages.error(request, "Access denied: Admin privileges required.")
        return redirect('school:dashboard')

    if request.method == 'POST':
        form = StaffCreationForm(request.POST, request.FILES, school=school)
        if form.is_valid():
            staff, password = form.save()
            messages.success(
                request,
                f'Successfully created staff "{staff.user.get_full_name()}" ({staff.staff_id}). '
                f'Position: {staff.get_position_display()}. '
                f'Temporary password: <strong>{password}</strong>. '
                f'Email sent: {"Yes" if form.cleaned_data["send_email"] else "No"}.'
            )
            logger.info(f"Created staff {staff.staff_id} for school {school.name}.")
            return redirect('school:staff_list_create')
        else:
            messages.error(request, "Please correct the form errors below.")
    else:
        form = StaffCreationForm(school=school)

    # List staff
    query = request.GET.get('q', '')
    staff_list = StaffProfile.objects.filter(school=school).select_related('user').order_by('-user__created_at')
    if query:
        staff_list = staff_list.filter(
            Q(user__first_name__icontains=query) |
            Q(user__last_name__icontains=query) |
            Q(staff_id__icontains=query) |
            Q(phone__icontains=query) |
            Q(user__email__icontains=query) |
            Q(position__icontains=query)
        )

    context = {
        'staff_list': staff_list,
        'form': form,
        'school': school,
        'query': query,
    }
    return render(request, 'school/staff.html', context)


@login_required
def staff_edit(request, pk):
    """
    Edit via modal form POST.
    Redirects back to list on success/error.
    """
    try:
        school = request.user.school_admin_profile
    except AttributeError:
        messages.error(request, "Access denied: Admin privileges required.")
        return redirect('school:staff_list_create')

    staff = get_object_or_404(StaffProfile, pk=pk, school=school)

    if request.method == 'POST':
        form = StaffEditForm(request.POST, request.FILES, instance=staff)
        if form.is_valid():
            form.save()
            messages.success(
                request,
                f'Successfully updated staff "{staff.user.get_full_name()}". '
                f'Email sent: {"Yes" if form.cleaned_data["send_email"] else "No"}. '
                f'Password reset: {"Yes" if form.cleaned_data["reset_password"] else "No"}.'
            )
            logger.info(f"Updated staff {staff.staff_id}.")
            return redirect('school:staff_list_create')
        else:
            messages.error(request, "Please correct the form errors.")
    # For GET: Redirect to list (modal-driven)
    messages.info(request, "Use the edit button in the list to modify.")
    return redirect('school:staff_list_create')


@login_required
def staff_delete(request, pk):
    """
    Delete via modal form POST.
    Redirects back to list on success.
    """
    try:
        school = request.user.school_admin_profile
    except AttributeError:
        messages.error(request, "Access denied: Admin privileges required.")
        return redirect('school:staff_list_create')

    staff = get_object_or_404(StaffProfile, pk=pk, school=school)

    if request.method == 'POST':
        user = staff.user
        user.is_active = False
        user.save()
        staff.delete()
        messages.success(request, f'Staff "{staff.user.get_full_name()}" ({staff.staff_id}) has been deleted.')
        logger.info(f"Deleted staff {staff.staff_id}.")
        return redirect('school:staff_list_create')
    
    # For GET: Redirect to list
    messages.warning(request, "Use the delete button in the list to confirm.")
    return redirect('school:staff_list_create')


@login_required
def student_list_create(request):
    """
    List students with search/filter.
    Handles creation via POST (from add modal).
    """
    try:
        school = request.user.school_admin_profile
    except AttributeError:
        messages.error(request, "Access denied: Admin privileges required.")
        return redirect('school:dashboard')

    if request.method == 'POST':
        form = StudentCreationForm(request.POST, request.FILES, school=school)
        if form.is_valid():
            student, password = form.save()
            messages.success(
                request,
                f'Successfully created student "{student.user.get_full_name()}" ({student.student_id}). '
                f'Grade: {student.grade_level}. '
                f'Temporary password: <strong>{password}</strong>. '
                f'Email sent: {"Yes" if form.cleaned_data["send_email"] else "No"}.'
            )
            logger.info(f"Created student {student.student_id} for school {school.name}.")
            return redirect('school:student_list_create')
        else:
            messages.error(request, "Please correct the form errors below.")
    else:
        form = StudentCreationForm(school=school)

    # List students
    query = request.GET.get('q', '')
    students = Student.objects.filter(school=school).select_related('user', 'grade_level').order_by('-user__created_at')
    if query:
        students = students.filter(
            Q(user__first_name__icontains=query) |
            Q(user__last_name__icontains=query) |
            Q(student_id__icontains=query) |
            Q(phone__icontains=query) |
            Q(user__email__icontains=query) |
            Q(grade_level__name__icontains=query)
        )

    context = {
        'students': students,
        'form': form,
        'school': school,
        'query': query,
    }
    return render(request, 'school/students.html', context)


@login_required
def student_edit(request, pk):
    """
    Edit via modal form POST.
    Redirects back to list on success/error.
    """
    try:
        school = request.user.school_admin_profile
    except AttributeError:
        messages.error(request, "Access denied: Admin privileges required.")
        return redirect('school:student_list_create')

    student = get_object_or_404(Student, pk=pk, school=school)

    if request.method == 'POST':
        form = StudentEditForm(request.POST, request.FILES, instance=student)
        if form.is_valid():
            form.save()
            messages.success(
                request,
                f'Successfully updated student "{student.user.get_full_name()}". '
                f'Email sent: {"Yes" if form.cleaned_data["send_email"] else "No"}. '
                f'Password reset: {"Yes" if form.cleaned_data["reset_password"] else "No"}.'
            )
            logger.info(f"Updated student {student.student_id}.")
            return redirect('school:student_list_create')
        else:
            messages.error(request, "Please correct the form errors.")
    # For GET: Redirect to list (modal-driven)
    messages.info(request, "Use the edit button in the list to modify.")
    return redirect('school:student_list_create')


@login_required
def student_delete(request, pk):
    """
    Delete via modal form POST.
    Redirects back to list on success.
    """
    try:
        school = request.user.school_admin_profile
    except AttributeError:
        messages.error(request, "Access denied: Admin privileges required.")
        return redirect('school:student_list_create')

    student = get_object_or_404(Student, pk=pk, school=school)

    if request.method == 'POST':
        user = student.user
        user.is_active = False
        user.save()
        student.delete()
        messages.success(request, f'Student "{student.user.get_full_name()}" ({student.student_id}) has been deleted.')
        logger.info(f"Deleted student {student.student_id}.")
        return redirect('school:student_list_create')
    
    # For GET: Redirect to list
    messages.warning(request, "Use the delete button in the list to confirm.")
    return redirect('school:student_list_create')

def school_subjects(request):
    return render(request, "school/subject.html", {})

def school_virtual_classes(request):
    return render(request, "school/class.html", {})

def school_attendance(request):
    return render(request, "school/attendance.html", {})

def school_enrollment(request):
    return render(request, "school/enrollment.html", {})

def school_student_assignments(request):
    return render(request, "school/assignment.html", {})

def school_exams(request):
    return render(request, "school/exam.html", {})

def school_timetable(request):
    return render(request, "school/timetable.html", {})

def school_students_submissions(request):
    return render(request, "school/submission.html", {})

def school_subscriptions(request):
    return render(request, "school/subscription.html", {})


def school_notifications(request):
    return render(request, "school/notification.html", {})

def school_settings(request):
    return render(request, "school/settings.html", {})

def school_reports(request):
    return render(request, "school/report.html", {})

def school_books(request):
    return render(request, "school/book.html", {})

def school_book_chapters(request):
    return render(request, "school/book_chapter.html", {})

def school_library_access(request):
    return render(request, "school/library.html", {})

def school_calendar(request):
    return render(request, "school/calendar.html", {})

def school_events(request):
    return render(request, "school/event.html", {})

def school_fees(request):
    return render(request, "school/fee.html", {})
def school_finance(request):
    return render(request, "school/finance.html", {})

def school_discipline(request):
    return render(request, "school/discipline.html", {})

def school_certificates(request):
    return render(request, "school/certificate.html", {})

def scholarships(request):
    return render(request, "school/scholarship.html", {})