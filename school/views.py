from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Q
from django.core.paginator import Paginator
from userauths.models import User
from .models import Grade, School, Parent,StaffProfile,Student, ScanLog, SmartID,Scholarship
import logging
from django.http import JsonResponse
from django.conf import settings
from django.template.loader import render_to_string
from django.utils.safestring import mark_safe
from django.core.mail import send_mail
import random
import string
from collections import defaultdict
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Q, Sum, Count
from django.core.paginator import Paginator
from django.core.exceptions import ValidationError
from django.http import JsonResponse, HttpResponse
from django.conf import settings
from django.template.loader import render_to_string
from django.utils.safestring import mark_safe
from django.core.mail import send_mail
from django.db import transaction
from django.utils import timezone
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph
from reportlab.lib.styles import getSampleStyleSheet
import csv
from io import StringIO
import logging
from decimal import Decimal
import uuid
from userauths.models import User
from .models import (
    Grade, School, Parent, StaffProfile, Student, Subject, Enrollment, Timetable, Lesson,
    Session, Attendance, DisciplineRecord, SummaryReport, Notification, SmartID, ScanLog,
    Payment, Assignment, Submission, Role, Invoice, SchoolSubscription, SubscriptionPlan,
    ContactMessage, MpesaStkPushRequestResponse, MpesaPayment
)
from .forms import (
    # Assuming forms exist or need to be created; placeholders for now
    GradeForm,ParentCreationForm, ParentEditForm,StaffCreationForm, StaffEditForm,
    StudentCreationForm, StudentEditForm,SmartIDForm,
    SubjectForm, EnrollmentForm, TimetableForm, LessonForm, SessionForm,
    AttendanceForm, DisciplineRecordForm, NotificationForm, PaymentForm,
    AssignmentForm, SubmissionForm, RoleForm, InvoiceForm, SchoolSubscriptionForm,
    ContactMessageForm
)


logger = logging.getLogger(__name__)
# Create your views here.
@login_required
def dashboard(request):
    school = request.user.school_admin_profile

    # -------------------------
    # Summary counts
    # -------------------------
    total_teachers = StaffProfile.objects.filter(school=school, position='teacher').count()
    total_students = Student.objects.filter(school=school).count()
    total_parents = Parent.objects.filter(school=school).count()
    total_discipline_cases = DisciplineRecord.objects.filter(school=school).count()
    total_timetable_slots = Timetable.objects.filter(school=school).count()

    # -------------------------
    # Recent discipline cases (last 5)
    # -------------------------
    recent_discipline = DisciplineRecord.objects.filter(school=school).order_by('-date')[:5]

    # -------------------------
    # Timetables with lessons
    # -------------------------
    timetables = Timetable.objects.filter(school=school).select_related('grade').order_by('-year', 'term')

    timetables_with_lessons = []
    for tt in timetables:
        lessons_qs = Lesson.objects.filter(timetable=tt)\
                                   .select_related('subject', 'teacher')\
                                   .order_by('date', 'start_time')[:20]  # limit for performance
        lessons_count = Lesson.objects.filter(timetable=tt).count()
        timetables_with_lessons.append({
            'timetable': tt,
            'lessons': lessons_qs,
            'lessons_count': lessons_count,
            'active': timezone.now().date() >= tt.start_date and timezone.now().date() <= tt.end_date,
        })

    # -------------------------
    # Context for template
    # -------------------------
    context = {
        "total_teachers": total_teachers,
        "total_students": total_students,
        "total_parents": total_parents,
        "total_discipline_cases": total_discipline_cases,
        "total_timetable_slots": total_timetable_slots,
        "recent_discipline": recent_discipline,
        "timetables_with_lessons": timetables_with_lessons,
    }

    return render(request, "school/dashboard.html", context)


@login_required
def school_grades(request):
    # Ensure user is a school admin
    print("Accessing grades view as user:", request.user)  # Keep for console
    logger.info(f"Accessing grades view as user: {request.user.email} (ID: {request.user.id})")
    try:
        school = request.user.school_admin_profile
        logger.info(f"User's school: {school.name} (ID: {school.id})")
        print("User's school:", school.name)  # Keep for console
    except AttributeError as e:
        logger.warning(f"Permission denied for user {request.user.email}: {e}")
        messages.error(request, f"You do not have permission to access this page. (User: {request.user.email})")
        return redirect('school:dashboard')

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
def smartid_list(request):

    school = getattr(request.user, "school_admin_profile", None)

    if not isinstance(school, School):
        logger.warning(f"Permission denied for user {request.user.email}")
        messages.error(request, "You do not have permission to access Smart IDs.")
        return redirect("school:dashboard")

    query = request.GET.get('q', '')

    smartids = SmartID.objects.filter(
        school=school,
        is_active=True
    ).select_related(
        'profile',
        'profile__student',
        'profile__staffprofile'
    )

    if query:
        smartids = smartids.filter(
            Q(profile__first_name__icontains=query) |
            Q(profile__last_name__icontains=query) |
            Q(card_id__icontains=query) |
            Q(user_f18_id__icontains=query)
        )

    form = SmartIDForm(school=school)

    return render(request, 'school/smartid_list.html', {
        'smartids': smartids,
        'form': form,
        'school': school,
        'query': query,
    })


@login_required
def smartid_create(request):
    try:
        school = request.user.school_admin_profile
    except AttributeError as e:
        logger.warning(f"Permission denied for user {request.user.email}: {e}")
        messages.error(request, f"You do not have permission to access this page. (User: {request.user.email})")
        return redirect('school:dashboard')
    
    if request.method != 'POST':
        return redirect('school:smartid-list')
    
    form = SmartIDForm(request.POST, school=school)
    if form.is_valid():
        smartid = form.save(commit=False)
        smartid.school = school
        smartid.save()
        messages.success(request, f'Smart ID "{smartid.card_id}" created successfully.')
        logger.info(f"Created Smart ID {smartid.card_id} for school {school.name} by {request.user.email}.")
        return redirect('school:smartid-list')
    else:
        # Add form errors to messages
        for field, error_list in form.errors.items():
            if field == '__all__':
                for error in error_list:
                    messages.error(request, error)
            else:
                label = form.fields[field].label
                for error in error_list:
                    messages.error(request, f"{label}: {error}")
        return redirect('school:smartid-list')

@login_required
def smartid_edit(request, pk):
    try:
        school = request.user.school_admin_profile
    except AttributeError as e:
        logger.warning(f"Permission denied for user {request.user.email}: {e}")
        messages.error(request, f"You do not have permission to access this page. (User: {request.user.email})")
        return redirect('school:dashboard')
    
    if request.method != 'POST':
        return redirect('school:smartid-list')
    
    smartid = get_object_or_404(SmartID, pk=pk, school=school)
    form = SmartIDForm(request.POST, instance=smartid, school=school)
    if form.is_valid():
        form.save()
        messages.success(request, f'Smart ID "{smartid.card_id}" updated successfully.')
        logger.info(f"Updated Smart ID {smartid.card_id} for school {school.name} by {request.user.email}.")
        return redirect('school:smartid-list')
    else:
        # Add form errors to messages
        for field, error_list in form.errors.items():
            if field == '__all__':
                for error in error_list:
                    messages.error(request, error)
            else:
                label = form.fields[field].label
                for error in error_list:
                    messages.error(request, f"{label}: {error}")
        return redirect('school:smartid-list')

@login_required
def smartid_delete(request, pk):
    try:
        school = request.user.school_admin_profile
    except AttributeError as e:
        logger.warning(f"Permission denied for user {request.user.email}: {e}")
        messages.error(request, f"You do not have permission to access this page. (User: {request.user.email})")
        return redirect('school:dashboard')
    
    if request.method != 'POST':
        messages.warning(request, "Use the delete button in the list to confirm.")
        return redirect('school:smartid-list')
    
    smartid = get_object_or_404(SmartID, pk=pk, school=school)
    smartid.is_active = False  # Soft delete
    smartid.save()
    messages.success(request, f'Smart ID "{smartid.card_id}" deactivated.')
    logger.info(f"Deactivated Smart ID {smartid.card_id} for school {school.name} by {request.user.email}.")
    return redirect('school:smartid-list')

# -------------------------------SCAN LOGS VIEW-------------------------------
@login_required
def scan_logs_view(request):
    """
    Display all scan logs with pagination and simple search filters.
    """
    search = request.GET.get('q', '')
    school = getattr(request.user, 'school', None)

    logs = ScanLog.objects.all()
    print((logs))
    # Optional: limit logs by user's school
    if school:
        logs = logs.filter(school=school)

    if search:
        logs = logs.filter(school=school)

    paginator = Paginator(logs, 25)  # Show 25 logs per page
    page = request.GET.get('page')
    logs_page = paginator.get_page(page)

    context = {
        'logs': logs_page,
        'search': search,
    }
    return render(request, 'school/scan_logs.html', context)

@login_required
def grade_create(request):
    try:
        school = request.user.school_admin_profile
    except AttributeError as e:
        logger.warning(f"Permission denied for user {request.user.email}: {e}")
        messages.error(request, f"You do not have permission to access this page. (User: {request.user.email})")
        return redirect('school:dashboard')

    if request.method != 'POST':
        return redirect('school:school-grades')

    form = GradeForm(request.POST, school=school)
    if form.is_valid():
        grade = form.save(commit=False)
        grade.school = school
        grade.save()
        messages.success(request, f'Grade "{grade.name}" created successfully.')
        logger.info(f"Created grade {grade.name} for school {school.name} by {request.user.email}.")
        return redirect('school:school-grades')
    else:
        # Add form errors to messages
        for field, error_list in form.errors.items():
            if field == '__all__':
                for error in error_list:
                    messages.error(request, error)
            else:
                label = form.fields[field].label
                for error in error_list:
                    messages.error(request, f"{label}: {error}")
        return redirect('school:school-grades')


@login_required
def grade_edit(request, pk):
    try:
        school = request.user.school_admin_profile
    except AttributeError as e:
        logger.warning(f"Permission denied for user {request.user.email}: {e}")
        messages.error(request, f"You do not have permission to access this page. (User: {request.user.email})")
        return redirect('school:dashboard')

    if request.method != 'POST':
        return redirect('school:school-grades')

    grade = get_object_or_404(Grade, pk=pk, school=school)
    form = GradeForm(request.POST, instance=grade, school=school)
    if form.is_valid():
        form.save()
        messages.success(request, f'Grade "{grade.name}" updated successfully.')
        logger.info(f"Updated grade {grade.name} for school {school.name} by {request.user.email}.")
        return redirect('school:school-grades')
    else:
        # Add form errors to messages
        for field, error_list in form.errors.items():
            if field == '__all__':
                for error in error_list:
                    messages.error(request, error)
            else:
                label = form.fields[field].label
                for error in error_list:
                    messages.error(request, f"{label}: {error}")
        return redirect('school:school-grades')


@login_required
def grade_delete(request, pk):
    try:
        school = request.user.school_admin_profile
    except AttributeError as e:
        logger.warning(f"Permission denied for user {request.user.email}: {e}")
        messages.error(request, f"You do not have permission to access this page. (User: {request.user.email})")
        return redirect('school:dashboard')

    if request.method != 'POST':
        messages.warning(request, "Use the delete button in the list to confirm.")
        return redirect('school:school-grades')

    grade = get_object_or_404(Grade, pk=pk, school=school)
    grade.is_active = False  # Soft delete
    grade.save()
    messages.success(request, f'Grade "{grade.name}" deactivated.')
    logger.info(f"Deactivated grade {grade.name} for school {school.name} by {request.user.email}.")
    return redirect('school:school-grades')



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
            Q(user__phone_number__icontains=query) |
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




def school_exams(request):
    return render(request, "school/exam.html", {})


def school_subscriptions(request):
    return render(request, "school/subscription.html", {})


def school_notifications(request):
    return render(request, "school/notification.html", {})


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

def school_certificates(request):
    return render(request, "school/certificate.html", {})

def scholarships(request):
    return render(request, "school/scholarship.html", {})


@login_required
def school_subjects(request):
    try:
        school = request.user.school_admin_profile
        print(school)
    except AttributeError:
        messages.error(request, "Access denied: Admin privileges required.")
        return redirect('school:dashboard')
    
    query = request.GET.get('q', '')
    subjects = Subject.objects.filter(school=school).select_related('teacher', 'grade')
    if query:
        subjects = subjects.filter(
            Q(name__icontains=query) | Q(code__icontains=query) | Q(teacher__user__first_name__icontains=query)
        )
    
    form = SubjectForm(school=school)
    context = {
        'subjects': subjects,
        'form': form,
        'school': school,
        'query': query,
    }
    return render(request, 'school/subject.html', context)

@login_required
def subject_create(request):
    try:
        school = request.user.school_admin_profile
    except AttributeError:
        messages.error(request, "Access denied: Admin privileges required.")
        return redirect('school:school-subjects')
    
    if request.method == 'POST':
        form = SubjectForm(request.POST, school=school)
        if form.is_valid():
            subject = form.save(commit=False)
            subject.school = school
            subject.save()
            messages.success(request, f'Subject "{subject.name}" created successfully.')
            logger.info(f"Created subject {subject.name} for school {school.name}.")
            return redirect('school:school-subjects')
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f"{form.fields[field].label}: {error}")
    return redirect('school:school-subjects')

@login_required
def subject_edit(request, pk):
    try:
        school = request.user.school_admin_profile
    except AttributeError:
        messages.error(request, "Access denied: Admin privileges required.")
        return redirect('school:school-subjects')
    
    subject = get_object_or_404(Subject, pk=pk, school=school)
    if request.method == 'POST':
        form = SubjectForm(request.POST, instance=subject, school=school)
        if form.is_valid():
            form.save()
            messages.success(request, f'Subject "{subject.name}" updated successfully.')
            return redirect('school:school-subjects')
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f"{form.fields[field].label}: {error}")
    return redirect('school:school-subjects')

@login_required
def subject_delete(request, pk):
    try:
        school = request.user.school_admin_profile
    except AttributeError:
        messages.error(request, "Access denied: Admin privileges required.")
        return redirect('school:school-subjects')
    
    subject = get_object_or_404(Subject, pk=pk, school=school)
    if request.method == 'POST':
        subject.is_active = False  # Soft delete
        subject.save()
        messages.success(request, f'Subject "{subject.name}" deactivated.')
        return redirect('school:school-subjects')
    return redirect('school:school-subjects')

@login_required
def school_enrollment(request):
    try:
        school = request.user.school_admin_profile
    except AttributeError:
        messages.error(request, "Access denied: Admin privileges required.")
        return redirect('school:dashboard')
    
    query = request.GET.get('q', '')
    enrollments = Enrollment.objects.filter(school=school).select_related('student', 'subject')
    if query:
        enrollments = enrollments.filter(
            Q(student__user__first_name__icontains=query) | Q(subject__name__icontains=query)
        )
    
    form = EnrollmentForm(school=school)
    context = {
        'enrollments': enrollments,
        'form': form,
        'school': school,
        'query': query,
    }
    return render(request, 'school/enrollment.html', context)

@login_required
def enrollment_create(request):
    try:
        school = request.user.school_admin_profile
    except AttributeError:
        messages.error(request, "Access denied: Admin privileges required.")
        return redirect('school:school-enrollment')
    
    if request.method == 'POST':
        form = EnrollmentForm(request.POST, school=school)
        if form.is_valid():
            enrollment = form.save(commit=False)
            enrollment.school = school
            enrollment.save()
            messages.success(request, f'Enrollment for {enrollment.student} in {enrollment.subject} created.')
            return redirect('school:school-enrollment')
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f"{form.fields[field].label}: {error}")
    return redirect('school:school-enrollment')


@login_required
def enrollment_edit(request, pk):
    """
    Edit existing enrollment (e.g., change subject).
    """
    try:
        school = request.user.school_admin_profile
    except AttributeError:
        messages.error(request, "Access denied: Admin privileges required.")
        return redirect('school:school-enrollment')
    
    enrollment = get_object_or_404(Enrollment, pk=pk, school=school)
    if request.method == 'POST':
        form = EnrollmentForm(request.POST, instance=enrollment, school=school)
        if form.is_valid():
            form.save()
            messages.success(request, f'Enrollment for {enrollment.student} updated successfully.')
            return redirect('school:school-enrollment')
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f"{form.fields[field].label}: {error}")
    return redirect('school:school-enrollment')

@login_required
def enrollment_delete(request, pk):
    """
    Soft-delete enrollment (set inactive or remove).
    """
    try:
        school = request.user.school_admin_profile
    except AttributeError:
        messages.error(request, "Access denied: Admin privileges required.")
        return redirect('school:school-enrollment')
    
    enrollment = get_object_or_404(Enrollment, pk=pk, school=school)
    if request.method == 'POST':
        # Soft delete: Mark inactive or cascade to lessons if needed
        enrollment.is_active = False
        enrollment.save()
        messages.success(request, f'Enrollment for {enrollment.student} in {enrollment.subject} deactivated.')
        return redirect('school:school-enrollment')
    return redirect('school:school-enrollment')

@login_required
def school_timetable(request):
    """
    List all timetables with search/filter by grade, term, year.
    Displays lessons/sessions under each timetable.
    """
    try:
        school = request.user.school_admin_profile  # Adjust based on your User extension
    except AttributeError:
        messages.error(request, "Access denied: Admin privileges required.")
        return redirect('school:dashboard')
    
    query = request.GET.get('q', '')
    timetables = Timetable.objects.filter(school=school).select_related('grade').order_by('-year', 'term')
    if query:
        timetables = timetables.filter(
            Q(grade__name__icontains=query) | Q(term__icontains=query) | Q(year__icontains=query)
        )
    
    # Pagination
    paginator = Paginator(timetables, 10)
    page_number = request.GET.get('page')
    timetables_page = paginator.get_page(page_number)
    
    # For each timetable, fetch sample lessons (limit to avoid overload)
    timetables_with_lessons = []
    for tt in timetables_page:
        lessons_qs = Lesson.objects.filter(timetable=tt).select_related('subject', 'teacher').order_by('date', 'start_time')[:20]
        lessons_count = Lesson.objects.filter(timetable=tt).count()
        timetables_with_lessons.append({
            'timetable': tt,
            'lessons': lessons_qs,
            'lessons_count': lessons_count,
            'active': timezone.now().date() >= tt.start_date and timezone.now().date() <= tt.end_date,
        })

    
    form = TimetableForm(school=school)
    context = {
        'timetables': timetables_with_lessons,
        'form': form,
        'school': school,
        'query': query,
    }
    return render(request, 'school/timetable.html', context)

@login_required
def timetable_create(request):
    """
    Create a new timetable for a grade/term/year.
    Validates unique_together and date range.
    """
    try:
        school = request.user.school_admin_profile
    except AttributeError:
        messages.error(request, "Access denied: Admin privileges required.")
        return redirect('school:school-timetable')
    
    if request.method == 'POST':
        form = TimetableForm(request.POST, school=school)
        if form.is_valid():
            timetable = form.save(commit=False)
            timetable.school = school
            timetable.save()
            messages.success(request, f'Timetable for {timetable.grade.name} - Term {timetable.term} {timetable.year} created successfully.')
            logger.info(f"Created timetable {timetable.id} for {school.name}.")
            return redirect('school:school-timetable')
        else:
            # Render errors in messages
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f"{form.fields[field].label if field != '__all__' else 'Form'}: {error}")
    else:
        form = TimetableForm(school=school)
    
    # On GET error or initial, redirect to list
    return redirect('school:school-timetable')
# Similar edit/delete...


@login_required
def timetable_edit(request, pk):
    """
    Edit existing timetable (e.g., adjust dates).
    """
    try:
        school = request.user.school_admin_profile
    except AttributeError:
        messages.error(request, "Access denied: Admin privileges required.")
        return redirect('school:school-timetable')
    
    timetable = get_object_or_404(Timetable, pk=pk, school=school)
    if request.method == 'POST':
        form = TimetableForm(request.POST, instance=timetable, school=school)
        if form.is_valid():
            form.save()
            messages.success(request, f'Timetable for {timetable.grade.name} updated successfully.')
            return redirect('school:school-timetable')
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f"{form.fields[field].label if field != '__all__' else 'Form'}: {error}")
    else:
        form = TimetableForm(instance=timetable, school=school)
    
    context = {'form': form, 'timetable': timetable}
    return render(request, 'school/timetable_form.html', context)  # Or modal-redirect


@login_required
def timetable_delete(request, pk):
    """
    Soft-delete timetable (set inactive or remove).
    """
    try:
        school = request.user.school_admin_profile
    except AttributeError:
        messages.error(request, "Access denied: Admin privileges required.")
        return redirect('school:school-timetable')
    
    timetable = get_object_or_404(Timetable, pk=pk, school=school)
    if request.method == 'POST':
        # Soft delete: Mark inactive or cascade to lessons if needed
        timetable.delete()  # Or timetable.is_active = False; timetable.save()
        messages.success(request, f'Timetable for {timetable.grade.name} deleted.')
        return redirect('school:school-timetable')
    messages.warning(request, "Confirm deletion.")
    return redirect('school:school-timetable')


# List lessons via @login_required
def lesson_list(request, timetable_id):
    """
    List all lessons for a specific timetable
    """
    try:
        school = request.user.school_admin_profile
    except AttributeError:
        messages.error(request, "Access denied: Admin privileges required.")
        return redirect('school:school-timetable')
    
    timetable = get_object_or_404(Timetable, id=timetable_id, school=school)
    lessons = timetable.lessons.select_related('subject', 'teacher').order_by('date', 'start_time')
    
    query = request.GET.get('q', '')
    if query:
        lessons = lessons.filter(
            Q(subject__name__icontains=query) |
            Q(teacher__user__first_name__icontains=query) |
            Q(teacher__user__last_name__icontains=query) |
            Q(room__icontains=query)
        )
    
    paginator = Paginator(lessons, 10)
    page_number = request.GET.get('page')
    lessons_page = paginator.get_page(page_number)
    
    form = LessonForm(school=school, initial={'timetable': timetable})
    context = {
        'timetable': timetable,
        'lessons': lessons_page,
        'form': form,
        'query': query,
        'school': school,
    }
    return render(request, 'school/lessons.html', context)


@login_required
def lesson_create(request):
    try:
        school = request.user.school_admin_profile
    except AttributeError:
        messages.error(request, "Access denied: Admin privileges required.")
        return redirect('school:school-timetable')
    
    if request.method == 'POST':
        form = LessonForm(request.POST, school=school)
        if form.is_valid():
            lesson = form.save(commit=False)
            lesson.save()
            messages.success(request, f'Lesson for {lesson.subject} on {lesson.date} created.')
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f"{form.fields[field].label}: {error}")
    return redirect('school:lesson-list', timetable_id=request.POST.get('timetable'))


@login_required
def lesson_edit(request, lesson_id):
    try:
        school = request.user.school_admin_profile
    except AttributeError:
        messages.error(request, "Access denied: Admin privileges required.")
        return redirect('school:school-timetable')
    
    lesson = get_object_or_404(Lesson, id=lesson_id, timetable__school=school)
    
    if request.method == 'POST':
        form = LessonForm(request.POST, instance=lesson, school=school)
        if form.is_valid():
            form.save()
            messages.success(request, f'Lesson for {lesson.subject} on {lesson.date} updated.')
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f"{form.fields[field].label}: {error}")
    return redirect('school:lesson-list', timetable_id=lesson.timetable.id)


@login_required
def lesson_delete(request, lesson_id):
    try:
        school = request.user.school_admin_profile
    except AttributeError:
        messages.error(request, "Access denied: Admin privileges required.")
        return redirect('school:school-timetable')
    
    lesson = get_object_or_404(Lesson, id=lesson_id, timetable__school=school)
    timetable_id = lesson.timetable.id
    lesson.delete()
    messages.success(request, "Lesson deleted successfully.")
    return redirect('school:lesson-list', timetable_id=timetable_id)

@login_required
def school_virtual_classes(request):
    try:
        school = request.user.school_admin_profile
    except AttributeError:
        messages.error(request, "Access denied: Admin privileges required.")
        return redirect('school:dashboard')
    
    query = request.GET.get('q', '')
    sessions = Session.objects.filter(school=school).select_related('subject', 'teacher')
    if query:
        sessions = sessions.filter(Q(title__icontains=query) | Q(subject__name__icontains=query))
    
    form = SessionForm(school=school)
    context = {
        'sessions': sessions,
        'form': form,
        'school': school,
        'query': query,
    }
    return render(request, 'school/session.html', context)


@login_required
def session_create(request):
    try:
        school = request.user.school_admin_profile
    except AttributeError:
        messages.error(request, "Access denied: Admin privileges required.")
        return redirect('school:dashboard')

    if request.method == 'POST':
        form = SessionForm(request.POST, school=school)
        if form.is_valid():
            session = form.save(commit=False)
            session.school = school
            session.teacher = request.user.staffprofile
            session.save()
            messages.success(request, f"Session '{session.title}' created successfully.")
        else:
            messages.error(request, "Error creating session. Check the form.")
    return redirect('school:school-sessions')


@login_required
def session_edit(request, session_id):
    session = get_object_or_404(Session, id=session_id)
    try:
        school = request.user.school_admin_profile
    except AttributeError:
        messages.error(request, "Access denied: Admin privileges required.")
        return redirect('school:dashboard')

    if request.method == 'POST':
        form = SessionForm(request.POST, instance=session, school=school)
        if form.is_valid():
            form.save()
            messages.success(request, f"Session '{session.title}' updated successfully.")
        else:
            messages.error(request, "Error updating session. Check the form.")
    return redirect('school:school-sessions')


@login_required
def session_delete(request, session_id):
    session = get_object_or_404(Session, id=session_id)
    try:
        school = request.user.school_admin_profile
    except AttributeError:
        messages.error(request, "Access denied: Admin privileges required.")
        return redirect('school:dashboard')

    if request.method == 'POST':
        session.delete()
        messages.success(request, f"Session '{session.title}' deleted successfully.")
    return redirect('school:school-sessions')


# Create/edit similar to above...

@login_required
def school_attendance(request):
    try:
        school = request.user.school_admin_profile
    except AttributeError:
        messages.error(request, "Access denied: Admin privileges required.")
        return redirect('school:dashboard')
    
    # Filter by date/lesson if provided
    date_filter = request.GET.get('date')
    lesson_id = request.GET.get('lesson')
    attendances = Attendance.objects.select_related('enrollment__student', 'lesson', 'marked_by')
    if date_filter:
        attendances = attendances.filter(lesson__date=date_filter)
    if lesson_id:
        attendances = attendances.filter(lesson_id=lesson_id)
    
    paginator = Paginator(attendances, 50)
    page = request.GET.get('page')
    attendances_page = paginator.get_page(page)
    
    context = {
        'attendances': attendances_page,
        'school': school,
    }
    return render(request, 'school/attendance.html', context)

@login_required
def attendance_mark(request, lesson_id):
    lesson = get_object_or_404(Lesson, id=lesson_id, teacher=request.user.staffprofile)
    if request.method == 'POST':
        # Bulk mark or individual; assume formset or bulk logic
        enrollments = Enrollment.objects.filter(subject=lesson.subject, status='active')
        for enrollment in enrollments:
            status = request.POST.get(f'status_{enrollment.id}', 'P')
            Attendance.objects.update_or_create(
                enrollment=enrollment,
                lesson=lesson,
                defaults={'status': status, 'marked_by': request.user.staffprofile}
            )
        messages.success(request, f'Attendance marked for {lesson.subject} on {lesson.date}.')
        return redirect('school:school-attendance')
    return redirect('school:school-attendance')

@login_required
def attendance_edit(request, attendance_id):
    attendance = get_object_or_404(Attendance, id=attendance_id, lesson__teacher=request.user.staffprofile)
    if request.method == 'POST':
        form = AttendanceForm(request.POST, instance=attendance)
        if form.is_valid():
            form.save()
            messages.success(request, f'Attendance for {attendance.enrollment.student} updated successfully.')
        else:
            messages.error(request, "Error updating attendance. Check the form.")
    return redirect('school:school-attendance')

@login_required
def attendance_delete(request, attendance_id):
    attendance = get_object_or_404(Attendance, id=attendance_id, lesson__teacher=request.user.staffprofile)
    if request.method == 'POST':
        attendance.delete()
        messages.success(request, f'Attendance for {attendance.enrollment.student} deleted successfully.')
    return redirect('school:school-attendance')
# Summary view
@login_required
def attendance_summary(request):
    try:
        school = request.user.school_admin_profile
    except AttributeError:
        messages.error(request, "Access denied: Admin privileges required.")
        return redirect('school:dashboard')
    
    # Generate summary data
    period_start = request.GET.get('start')
    period_end = request.GET.get('end')
    if not period_start or not period_end:
        period_start = timezone.now().date().replace(day=1)
        period_end = timezone.now().date()
    
    lessons = Lesson.objects.filter(date__range=[period_start, period_end], school=school)
    attendances = Attendance.objects.filter(lesson__in=lessons)
    
    summary = attendances.values('status').annotate(count=Count('status'))
    total_sessions = lessons.count()
    present_pct = (summary.get('P', {'count': 0})['count'] / (len(enrollments) * total_sessions)) * 100 if total_sessions else 0
    
    context = {
        'summary': summary,
        'period_start': period_start,
        'period_end': period_end,
        'present_pct': round(present_pct, 2),
        'school': school,
    }
    return render(request, 'school/attendance_summary.html', context)

@login_required
def school_discipline(request):
    try:
        school = request.user.school_admin_profile
    except AttributeError:
        messages.error(request, "Access denied: Admin privileges required.")
        return redirect('school:dashboard')
    
    query = request.GET.get('q', '')
    records = DisciplineRecord.objects.filter(school=school).select_related('student', 'teacher')
    if query:
        records = records.filter(
            Q(student__user__first_name__icontains=query) | Q(description__icontains=query)
        )
    
    form = DisciplineRecordForm(school=school)
    context = {
        'records': records,
        'form': form,
        'school': school,
        'query': query,
    }
    return render(request, 'school/discipline.html', context)

@login_required
def discipline_create(request):
    try:
        school = request.user.school_admin_profile
    except AttributeError:
        messages.error(request, "Access denied: Admin privileges required.")
        return redirect('school:school-discipline')
    
    if request.method == 'POST':
        form = DisciplineRecordForm(request.POST, school=school)
        if form.is_valid():
            record = form.save(commit=False)
            record.school = school
            record.teacher = request.user.staffprofile
            record.reported_by = request.user
            record.save()
            # Trigger notification
            Notification.objects.create(
                recipient=record.student.parent.user,
                title="Discipline Incident Logged",
                message=f"An incident of {record.incident_type} has been recorded.",
                related_discipline=record,
                school=school
            )
            messages.success(request, f'Discipline record for {record.student} created.')
            return redirect('school:school-discipline')
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f"{form.fields[field].label}: {error}")
    return redirect('school:school-discipline')

# Similar edit/delete, with validation for severity/frequency...

@login_required
def discipline_edit(request, pk):
    try:
        school = request.user.school_admin_profile
    except AttributeError:
        messages.error(request, "Access denied: Admin privileges required.")
        return redirect('school:school-discipline')
    
    record = get_object_or_404(DisciplineRecord, id=pk, school=school)
    if request.method == 'POST':
        form = DisciplineRecordForm(request.POST, instance=record, school=school)
        if form.is_valid():
            form.save()
            messages.success(request, f'Discipline record for {record.student} updated.')
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f"{form.fields[field].label}: {error}")
    return redirect('school:school-discipline')


@login_required
def discipline_delete(request, pk):
    try:
        school = request.user.school_admin_profile
    except AttributeError:
        messages.error(request, "Access denied: Admin privileges required.")
        return redirect('school:school-discipline')
    
    record = get_object_or_404(DisciplineRecord, id=pk, school=school)
    if request.method == 'POST':
        record.delete()
        messages.success(request, f'Discipline record for {record.student} deleted.')
    return redirect('school:school-discipline')


@login_required
def school_notifications(request):
    try:
        school = request.user.school_admin_profile
    except AttributeError:
        messages.error(request, "Access denied: Admin privileges required.")
        return redirect('school:dashboard')
    
    notifications = Notification.objects.filter(school=school).order_by('-sent_at')
    # Mark as read for current user if applicable
    if request.user.is_authenticated:
        notifications.filter(recipient=request.user, is_read=False).update(is_read=True)
    
    form = NotificationForm(school=school)
    context = {
        'notifications': notifications,
        'form': form,
        'school': school,
    }
    return render(request, 'school/notification.html', context)

@login_required
def notification_send(request):
    try:
        school = request.user.school_admin_profile
    except AttributeError:
        messages.error(request, "Access denied: Admin privileges required.")
        return redirect('school:school-notifications')
    
    if request.method == 'POST':
        form = NotificationForm(request.POST, school=school)
        if form.is_valid():
            notification = form.save(commit=False)
            notification.school = school
            notification.save()
            # Actual send via email/SMS (integrate with external service)
            if notification.recipient.email:
                send_mail(
                    notification.title,
                    notification.message,
                    settings.DEFAULT_FROM_EMAIL,
                    [notification.recipient.email],
                )
            messages.success(request, 'Notification sent successfully.')
            return redirect('school:school-notifications')
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f"{form.fields[field].label}: {error}")
    return redirect('school:school-notifications')

@login_required
def school_reports(request):
    try:
        school = request.user.school_admin_profile
    except AttributeError:
        messages.error(request, "Access denied: Admin privileges required.")
        return redirect('school:dashboard')
    
    # Generate on-the-fly or from SummaryReport
    report_type = request.GET.get('type', 'school')
    period_start = request.GET.get('start', timezone.now().date().replace(day=1))
    period_end = request.GET.get('end', timezone.now().date())
    
    # Example: Attendance report
    if report_type == 'attendance':
        lessons = Lesson.objects.filter(date__range=[period_start, period_end], school=school)
        data = Attendance.objects.filter(lesson__in=lessons).values('status').annotate(count=Count('status'))
        # Save as SummaryReport
        SummaryReport.objects.update_or_create(
            school=school, report_type='school', period_start=period_start, period_end=period_end,
            defaults={'data': dict(data), 'generated_by': request.user.staffprofile}
        )
    
    context = {
        'report_type': report_type,
        'period_start': period_start,
        'period_end': period_end,
        'school': school,
        # Pass data...
    }
    return render(request, 'school/report.html', context)

@login_required
def export_report(request):
    # CSV export example
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="report.csv"'
    writer = csv.writer(response)
    writer.writerow(['Status', 'Count'])
    # Add data...
    return response

@login_required
def export_pdf_report(request):
    # PDF export using reportlab
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = 'attachment; filename="report.pdf"'
    doc = SimpleDocTemplate(response, pagesize=letter)
    story = []
    styles = getSampleStyleSheet()
    story.append(Paragraph("Attendance Report", styles['Title']))
    # Add table...
    data = [['Status', 'Count']]  # Populate
    t = Table(data)
    t.setStyle(TableStyle([('BACKGROUND', (0, 0), (-1, 0), colors.grey)]))
    story.append(t)
    doc.build(story)
    return response

@login_required
def school_student_assignments(request):
    try:
        school = request.user.school_admin_profile
    except AttributeError:
        messages.error(request, "Access denied: Admin privileges required.")
        return redirect('school:dashboard')
    
    query = request.GET.get('q', '')
    assignments = Assignment.objects.filter(school=school).select_related('subject')
    if query:
        assignments = assignments.filter(Q(title__icontains=query) | Q(subject__name__icontains=query))
    
    form = AssignmentForm(school=school)
    context = {
        'assignments': assignments,
        'form': form,
        'school': school,
        'query': query,
    }
    return render(request, 'school/assignment.html', context)

# Create/edit assignment similar...
@login_required
def assignment_create(request):
    try:
        school = request.user.school_admin_profile
    except AttributeError:
        messages.error(request, "Access denied: Admin privileges required.")
        return redirect('school:school-student-assignments')
    
    if request.method == 'POST':
        form = AssignmentForm(request.POST, school=school)
        if form.is_valid():
            assignment = form.save(commit=False)
            assignment.school = school
            assignment.teacher = request.user.staffprofile
            assignment.save()
            messages.success(request, f'Assignment "{assignment.title}" created successfully.')
            return redirect('school:school-student-assignments')
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f"{form.fields[field].label}: {error}")
    return redirect('school:school-student-assignments')
@login_required
def assignment_edit(request, pk):
    try:
        school = request.user.school_admin_profile
    except AttributeError:
        messages.error(request, "Access denied: Admin privileges required.")
        return redirect('school:school-student-assignments')
    
    assignment = get_object_or_404(Assignment, pk=pk, school=school)
    if request.method == 'POST':
        form = AssignmentForm(request.POST, instance=assignment, school=school)
        if form.is_valid():
            form.save()
            messages.success(request, f'Assignment "{assignment.title}" updated successfully.')
            return redirect('school:school-student-assignments')
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f"{form.fields[field].label}: {error}")
    return redirect('school:school-student-assignments')

@login_required
def assignment_delete(request, pk):
    try:
        school = request.user.school_admin_profile
    except AttributeError:
        messages.error(request, "Access denied: Admin privileges required.")
        return redirect('school:school-student-assignments')
    
    assignment = get_object_or_404(Assignment, pk=pk, school=school)
    assignment.delete()
    messages.success(request, f'Assignment "{assignment.title}" deleted successfully.')
    return redirect('school:school-student-assignments')
# Delete assignment


@login_required
def school_students_submissions(request):
    try:
        school = request.user.school_admin_profile
    except AttributeError:
        messages.error(request, "Access denied: Admin privileges required.")
        return redirect('school:dashboard')
    
    query = request.GET.get('q', '')
    submissions = Submission.objects.filter(school=school).select_related('enrollment__student', 'assignment')
    if query:
        submissions = submissions.filter(Q(enrollment__student__user__first_name__icontains=query))
    
    context = {
        'submissions': submissions,
        'school': school,
        'query': query,
    }
    return render(request, 'school/submission.html', context)

# Grade submission (update score/feedback)
@login_required
def submission_grade(request, pk):
    submission = get_object_or_404(Submission, pk=pk)
    if request.method == 'POST':
        submission.score = request.POST.get('score')
        submission.feedback = request.POST.get('feedback')
        submission.save()
        messages.success(request, 'Submission graded successfully.')
        return redirect('school:school-students-submissions')
    return redirect('school:school-students-submissions')


#student submission

@login_required
def submission_create(request):
    try:
        student = request.user.student
    except AttributeError:
        messages.error(request, "Access denied: Student privileges required.")
        return redirect('school:dashboard')
    
    query = request.GET.get('q', '')
    submissions = Submission.objects.filter(enrollment__student=student).select_related('assignment')
    if query:
        submissions = submissions.filter(Q(assignment__title__icontains=query))
    
    context = {
        'submissions': submissions,
        'query': query,
    }
    return render(request, 'school/student_submissions.html', context)

@login_required
def submission_edit(request, pk):
    try:
        student = request.user.student
    except AttributeError:
        messages.error(request, "Access denied: Student privileges required.")
        return redirect('school:dashboard')
    
    submission = get_object_or_404(Submission, pk=pk, enrollment__student=student)
    if request.method == 'POST':
        submission.file = request.FILES.get('file', submission.file)
        submission.save()
        messages.success(request, 'Submission updated successfully.')
        return redirect('school:student-submissions')
    return redirect('school:student-submissions')


@login_required
def submission_delete(request, pk):
    try:
        student = request.user.student
    except AttributeError:
        messages.error(request, "Access denied: Student privileges required.")
        return redirect('school:dashboard')
    
    submission = get_object_or_404(Submission, pk=pk, enrollment__student=student)
    if request.method == 'POST':
        submission.delete()
        messages.success(request, 'Submission deleted successfully.')
    return redirect('school:student-submissions')


@login_required
def student_submissions(request):
    try:
        student = request.user.student
    except AttributeError:
        messages.error(request, "Access denied: Student privileges required.")
        return redirect('school:dashboard')
    
    query = request.GET.get('q', '')
    submissions = Submission.objects.filter(enrollment__student=student).select_related('assignment')
    if query:
        submissions = submissions.filter(Q(assignment__title__icontains=query))
    
    context = {
        'submissions': submissions,
        'query': query,
    }
    return render(request, 'school/student_submissions.html', context)
@login_required
def school_fees(request):
    try:
        school = request.user.school_admin_profile
    except AttributeError:
        messages.error(request, "Access denied: Admin privileges required.")
        return redirect('school:dashboard')
    
    query = request.GET.get('q', '')
    payments = Payment.objects.filter(school=school).select_related('student')
    if query:
        payments = payments.filter(Q(student__user__first_name__icontains=query) | Q(payment_type__icontains=query))
    
    form = PaymentForm(school=school)
    context = {
        'payments': payments,
        'form': form,
        'school': school,
        'query': query,
    }
    return render(request, 'school/fee.html', context)

# Integrate M-Pesa for payments...
@login_required
def process_mpesa_payment(request):
    # Example: Trigger STK push
    # Use Daraja API (assume configured)
    # For now, placeholder
    messages.success(request, 'Payment processed via M-Pesa.')
    return redirect('school:school-fees')

@login_required
def school_finance(request):
    try:
        school = request.user.school_admin_profile
    except AttributeError:
        messages.error(request, "Access denied: Admin privileges required.")
        return redirect('school:dashboard')
    
    subscriptions = SchoolSubscription.objects.filter(school=school)
    invoices = Invoice.objects.filter(school=school)
    
    context = {
        'subscriptions': subscriptions,
        'invoices': invoices,
        'school': school,
    }
    return render(request, 'school/finance.html', context)

@login_required
def school_subscriptions(request):
    try:
        school = request.user.school_admin_profile
    except AttributeError:
        messages.error(request, "Access denied: Admin privileges required.")
        return redirect('school:dashboard')
    
    subscription = school.platform_subscription
    form = SchoolSubscriptionForm(instance=subscription)
    
    if request.method == 'POST':
        form = SchoolSubscriptionForm(request.POST, instance=subscription)
        if form.is_valid():
            form.save()
            messages.success(request, 'Subscription updated.')
            return redirect('school:school-subscriptions')
    
    context = {
        'subscription': subscription,
        'form': form,
        'plans': SubscriptionPlan.objects.filter(is_active=True),
        'school': school,
    }
    return render(request, 'school/subscription.html', context)

# Generate invoice
@login_required
def generate_invoice(request):
    school = request.user.school_admin_profile
    subscription = school.platform_subscription
    if subscription:
        cost = subscription.calculate_current_cost()
        invoice = Invoice.objects.create(
            school=school,
            subscription=subscription,
            amount_due=cost,
            line_items=[{'description': 'Subscription', 'total': cost}]  # Simplify
        )
        messages.success(request, f'Invoice {invoice.invoice_id} generated.')
    return redirect('school:school-finance')

@login_required
def school_calendar(request):
    # Integrate with fullcalendar.js or similar in template
    try:
        school = request.user.school_admin_profile
    except AttributeError:
        messages.error(request, "Access denied: Admin privileges required.")
        return redirect('school:dashboard')
    
    # Fetch events (use Session, Lesson, etc. as events)
    events = []  # JSON for JS
    context = {
        'events': mark_safe(json.dumps(events)),
        'school': school,
    }
    return render(request, 'school/calendar.html', context)

@login_required
def school_events(request):
    try:
        school = request.user.school_admin_profile
    except AttributeError:
        messages.error(request, "Access denied: Admin privileges required.")
        return redirect('school:dashboard')
    
    # Events could be a new model or use existing (e.g., Sessions)
    # Placeholder: List sessions as events
    events = Session.objects.filter(school=school)
    context = {'events': events, 'school': school}
    return render(request, 'school/event.html', context)

# ------------------------------- SETTINGS & PERMISSIONS -------------------------------
@login_required
def school_settings(request):
    try:
        school = request.user.school_admin_profile
    except AttributeError:
        messages.error(request, "Access denied: Admin privileges required.")
        return redirect('school:dashboard')
    
    if request.method == 'POST':
        school.name = request.POST.get('name')
        school.contact_email = request.POST.get('email')
        school.save()
        messages.success(request, 'School settings updated.')
        return redirect('school:school-settings')
    
    context = {'school': school}
    return render(request, 'school/settings.html', context)

@login_required
def permissions_logs(request):
    try:
        school = request.user.school_admin_profile
    except AttributeError:
        messages.error(request, "Access denied: Admin privileges required.")
        return redirect('school:dashboard')
    
    # Log actions via middleware or signals; placeholder query
    logs = []  # From audit log model if added
    context = {'logs': logs, 'school': school}
    return render(request, 'school/permissions.html', context)  # Assume template

@login_required
def contact_messages(request):
    try:
        school = request.user.school_admin_profile
    except AttributeError:
        messages.error(request, "Access denied: Admin privileges required.")
        return redirect('school:dashboard')
    
    messages_list = ContactMessage.objects.all().order_by('-created_at')
    context = {'messages': messages_list}
    return render(request, 'school/contact.html', context)

# Callbacks for M-Pesa (STK push response, payment confirmation)
def mpesa_stk_callback(request):
    # Parse XML/JSON from M-Pesa
    # Update MpesaStkPushRequestResponse
    return JsonResponse({'ResultCode': 0, 'ResultDesc': 'Success'})

def mpesa_payment_callback(request):
    # Update MpesaPayment and link to Invoice/Payment
    body = request.POST.get('Body')
    # Parse and save
    payment = MpesaPayment.objects.create(
        merchant_request_id=body.get('MerchantRequestID'),
        # ... other fields
    )
    # Update related Payment/Invoice status to 'paid'
    return JsonResponse({'ResultCode': 0, 'ResultDesc': 'Success'})


