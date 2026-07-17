# views.py (CRUD for School)
import logging
import secrets
from django.shortcuts import render, redirect, get_object_or_404
from django.views.decorators.csrf import csrf_exempt as csrf_exempt_view
from django.contrib.auth import login as auth_login, logout as auth_logout
from django.contrib.auth.decorators import login_required,permission_required
from django.contrib import messages
from django.contrib.messages.views import SuccessMessageMixin
from django.views.generic import ListView, CreateView, UpdateView, DeleteView
from django.urls import reverse_lazy
from django.http import JsonResponse
from django.utils import timezone
from django.db.models import Q, Count, F
from django.db import models
from decimal import Decimal
from django.urls import reverse
from django.conf import settings
from school.models import School,Scholarship,SubscriptionPlan,ContactMessage, SchoolSubscription, StaffProfile, Student, Parent, Scholarship, County, City,Constituency,SubCounty,Ward, SubjectCatalog, Complaint
from userauths.models import User
from .forms import SchoolCreationForm, SchoolEditForm,AdminEditForm,ScholarshipForm,SubscriptionPlanForm, SchoolSubscriptionForm
from django.contrib.auth.hashers import make_password
from django.db import IntegrityError
from django.core.paginator import Paginator
from django.views.decorators.http import require_POST


from .models import (
    School, UserProfile, Guardian, Subject, Program, Enrollment,
    VirtualClass, ClassAttendance, Lesson, Assignment, AssignmentSubmission,
    Assessment, Question, Choice, StudentAssessmentAttempt, StudentAnswer,
    NotificationTemplate, NotificationLog, TuitionPayment,
    PAYMENT_STATUS_CHOICES, PAYMENT_METHOD_CHOICES,
)
from .forms import (
    StudentRegistrationForm, TeacherRegistrationForm,
    StudentProfileOnlyForm, TeacherProfileOnlyForm,
    GuardianForm,
    VettingForm, EnrollmentForm,
    VirtualClassForm, RecordingUploadForm, AttendanceManualForm,
    LessonForm, AssignmentForm, SubmissionForm, GradeSubmissionForm,
    AssessmentForm, QuestionForm, ChoiceForm, ChoiceFormSet, PublishResultsForm,
    NotificationTemplateForm, BulkNotificationForm,
    TuitionProgramForm, TuitionPaymentForm, SubjectForm, SubjectCatalogForm, PrincipalTuitionEnrollForm,
)
from .utils import (
    auto_grade_attempt, record_join_attendance, get_attendance_summary,
    get_program_performance_report, get_teacher_activity_report,
    get_school_utilization_report, send_notification, notify_class_reminder,
    notify_assignment_due,
)
 


logger = logging.getLogger(__name__)

@login_required
def school_list(request):
    """
    List schools with search/filter.
    Handles creation via POST (from add modal).
    """
    if not (request.user.is_superuser or request.user.is_admin or request.user.is_kiswate_admin or request.user.is_kiswate_user):
        messages.error(request, "Access denied: Superuser privileges required.")
        return redirect('kiswate_digital_app:kiswate_admin_dashboard')
    if request.method == 'POST':
        form = SchoolCreationForm(request.POST)
        if form.is_valid():
            school, password = form.save()
            messages.success(
                request,
                f'Successfully created school "{school.name}" ({school.code}). '
                f'Admin: {school.school_admin.get_full_name()}. '
                f'Temporary password: <strong>{password}</strong>. '
                f'Email sent: {"Yes" if form.cleaned_data["send_email"] else "No"}.'
            )
            logger.info(f"Created school {school.code} by superuser {request.user.email}.")
            return redirect('kiswate_digital_app:school_list')
        else:
            messages.error(request, "Please correct the form errors below.")
    else:
        form = SchoolCreationForm()

    # List schools
    counties = County.objects.all().order_by('name')
    cities = City.objects.all().order_by('name')
    constituencies = Constituency.objects.all().order_by('name')
    sub_counties = SubCounty.objects.all().order_by('name')
    wards = Ward.objects.all().order_by('name')

    query = request.GET.get('q', '')
    schools = School.objects.all().order_by('-created_at')
    if query:
        schools = schools.filter(
            Q(name__icontains=query) |
            Q(code__icontains=query) |
            Q(contact_email__icontains=query) |
            Q(school_admin__email__icontains=query)
        )

    context = {
        'schools': schools,
        'counties': counties,
        'cities': cities,
        'constituencies': constituencies,
        'sub_counties': sub_counties,
        'wards': wards,
        'form': form,
        'query': query,
    }
    return render(request, "Dashboard/school_list.html", context)


@login_required
def edit_school(request, pk):
    """
    Edit via modal form POST.
    Redirects back to list on success/error.
    """
    if not (request.user.is_superuser or request.user.is_admin or request.user.is_kiswate_admin or request.user.is_kiswate_user):
        messages.error(request, "Access denied: Superuser privileges required.")
        return redirect('kiswate_digital_app:school_list')

    school = get_object_or_404(School, pk=pk, is_active=True)

    if request.method == 'POST':
        form = SchoolEditForm(request.POST, instance=school)
        if form.is_valid():
            form.save()
            messages.success(
                request,
                f'Successfully updated school "{school.name}". '
                f'Email sent: {"Yes" if form.cleaned_data["send_email"] else "No"}. '
                f'Password reset: {"Yes" if form.cleaned_data["reset_password"] else "No"}.'
            )
            logger.info(f"Updated school {school.code} by superuser {request.user.email}.")
            return redirect('kiswate_digital_app:school_list')
        else:
            messages.error(request, "Please correct the form errors.")
    # For GET: Redirect to list (modal-driven)
    messages.info(request, "Use the edit button in the list to modify.")
    return redirect('kiswate_digital_app:school_list')


@login_required
def delete_school(request, pk):
    """
    Soft-delete via modal form POST.
    Redirects back to list on success.
    """
    if not request.user.is_superuser:
        messages.error(request, "Access denied: Superuser privileges required.")
        return redirect('kiswate_digital_app:school_list')

    school = get_object_or_404(School, pk=pk)

    if request.method == 'POST':
        school.is_active = False
        school.save()
        messages.success(request, f'School "{school.name}" ({school.code}) has been deactivated.')
        logger.info(f"Deactivated school {school.code} by superuser {request.user.email}.")
        return redirect('kiswate_digital_app:school_list')
    
    # For GET: Redirect to list
    messages.warning(request, "Use the delete button in the list to confirm.")
    return redirect('kiswate_digital_app:school_list')


@login_required
def new_school(request):
    """
    Direct create page (optional; modal preferred).
    """
    if not (request.user.is_superuser or request.user.is_admin or request.user.is_kiswate_admin or request.user.is_kiswate_user):
        messages.error(request, "Access denied: Superuser privileges required.")
        return redirect('kiswate_digital_app:school_list')

    if request.method == 'POST':
        form = SchoolCreationForm(request.POST)
        if form.is_valid():
            school, password = form.save()
            messages.success(
                request,
                f'Successfully created school "{school.name}". '
                f'Admin password: <strong>{password}</strong>.'
            )
            return redirect('kiswate_digital_app:school_list')
    else:
        form = SchoolCreationForm()

    context = {'form': form}
    return render(request, "Dashboard/new_school.html", context)
@login_required
def kiswate_dashboard(request):
    if not (request.user.is_superuser or request.user.is_admin or request.user.is_kiswate_admin or request.user.is_kiswate_user):
        messages.error(request, "Access denied: Superuser privileges required.")
        return redirect('userauths:sign-in')

    from django.db.models import Count, Q

    total_schools = School.objects.count()
    active_schools = School.objects.filter(is_active=True).count()
    total_teachers = StaffProfile.objects.filter(position='teacher').count()
    total_students = Student.objects.count()
    active_students = Student.objects.filter(is_active=True).count()
    suspended_students = Student.objects.filter(suspended=True).count()
    total_parents = Parent.objects.count()
    total_scholarships = Scholarship.objects.count()
    total_demo_requests = ContactMessage.objects.count()
    new_demos = ContactMessage.objects.filter(lead_status='new').count()

    # School subscriptions breakdown
    active_subs = SchoolSubscription.objects.filter(status='active').count()
    trial_subs = SchoolSubscription.objects.filter(status='trial').count()
    expired_subs = SchoolSubscription.objects.filter(status='expired').count()

    # Schools by classification
    schools_by_class = School.objects.values('school_classification').annotate(n=Count('id')).order_by('-n')

    # Schools by county (top 10)
    schools_by_county = School.objects.values(
        county_name=models.F('county__name')
    ).annotate(n=Count('id')).order_by('-n')[:10]

    # Recent schools
    recent_schools = School.objects.select_related('school_admin').order_by('-created_at')[:8]

    # Recent demo requests
    recent_demos = ContactMessage.objects.order_by('-created_at')[:5]

    return render(request, "Dashboard/kiswate_admin_dashboard.html", {
        "total_schools": total_schools,
        "active_schools": active_schools,
        "total_teachers": total_teachers,
        "total_students": total_students,
        "active_students": active_students,
        "suspended_students": suspended_students,
        "total_parents": total_parents,
        "total_scholarships": total_scholarships,
        "total_demo_requests": total_demo_requests,
        "new_demos": new_demos,
        "active_subs": active_subs,
        "trial_subs": trial_subs,
        "expired_subs": expired_subs,
        "schools_by_class": list(schools_by_class),
        "schools_by_county": list(schools_by_county),
        "recent_schools": recent_schools,
        "recent_demos": recent_demos,
    })


# ── IMPERSONATION ─────────────────────────────────────────────────────────────

_IMPERSONATOR_KEY = 'kiswate_impersonator_pk'
_IMPERSONATOR_EMAIL_KEY = 'kiswate_impersonator_email'


@login_required
def impersonate_school(request, school_pk, role):
    """
    Kiswate admin temporarily logs in as a school's admin, principal, or deputy principal.
    role must be one of: 'admin', 'principal', 'deputy'
    The original Kiswate admin pk is stored in the session; a banner in the school
    base template lets them return at any time.
    """
    if not (request.user.is_superuser or request.user.is_kiswate_admin or request.user.is_kiswate_user):
        messages.error(request, "Only Kiswate admins can impersonate school users.")
        return redirect('kiswate_digital_app:kiswate_admin_dashboard')

    school = get_object_or_404(School, pk=school_pk)
    target_user = None

    if role == 'admin':
        target_user = school.school_admin
    elif role == 'principal':
        from school.models import StaffProfile as SP
        sp = SP.objects.filter(school=school, user__is_principal=True).select_related('user').first()
        target_user = sp.user if sp else None
    elif role == 'deputy':
        from school.models import StaffProfile as SP
        sp = SP.objects.filter(school=school, user__is_deputy_principal=True).select_related('user').first()
        target_user = sp.user if sp else None

    if not target_user:
        role_labels = {'admin': 'School Admin', 'principal': 'Principal', 'deputy': 'Deputy Principal'}
        messages.warning(request, f"No {role_labels.get(role, role)} found for {school.name}.")
        return redirect('kiswate_digital_app:school_list')

    # Stash the original Kiswate admin in the session
    original_pk = request.user.pk
    original_email = request.user.email

    # Switch the session to the target user (Django's login() rotates the session key)
    target_user.backend = 'userauths.backends.EmailBackend'
    auth_login(request, target_user)

    # Write impersonator info AFTER login() because login() flushes and migrates session data
    request.session[_IMPERSONATOR_KEY] = original_pk
    request.session[_IMPERSONATOR_EMAIL_KEY] = original_email

    role_labels = {'admin': 'School Admin', 'principal': 'Principal', 'deputy': 'Deputy Principal'}
    messages.info(
        request,
        f"You are now logged in as {target_user.get_full_name()} ({role_labels.get(role, role)}) "
        f"at {school.name}. Use the banner to return to your Kiswate Admin account."
    )
    return redirect('school:dashboard')


@login_required
def stop_impersonating(request):
    """Return the Kiswate admin to their own session."""
    original_pk = request.session.get(_IMPERSONATOR_KEY)
    if not original_pk:
        messages.warning(request, "No active impersonation session.")
        return redirect('userauths:sign-in')

    from userauths.models import User as AuthUser
    try:
        original_user = AuthUser.objects.get(pk=original_pk)
    except AuthUser.DoesNotExist:
        messages.error(request, "Original admin account not found. Please log in again.")
        auth_logout(request)
        return redirect('userauths:sign-in')

    original_user.backend = 'userauths.backends.EmailBackend'
    auth_login(request, original_user)
    # Session is fresh after login() — no stale impersonation key
    messages.success(request, "Returned to your Kiswate Admin account.")
    return redirect('kiswate_digital_app:school_list')


@login_required
def school_admin_list(request):
    # Superuser check
    if not (request.user.is_superuser or request.user.is_admin or request.user.is_kiswate_admin or request.user.is_kiswate_user):
        messages.error(request, "Access denied: Superuser privileges required.")
        return redirect('kiswate_digital_app:kiswate_admin_dashboard')

    query = request.GET.get('q', '')
    schools = School.objects.select_related('school_admin').order_by('-created_at')
    if query:
        schools = schools.filter(
            Q(school_admin__first_name__icontains=query) |
            Q(school_admin__last_name__icontains=query) |
            Q(school_admin__email__icontains=query) |
            Q(name__icontains=query)
        )

    # Determine which school had form errors (from query param)
    edit_pk = request.GET.get('school_pk')
    error = request.GET.get('error') == '1'

    # Prepare a form for each school
    forms_dict = {}
    for school in schools:
        if edit_pk and str(school.pk) == str(edit_pk) and error:
            # Keep POST data with errors in form
            forms_dict[school.pk] = AdminEditForm(request.POST or None, instance=school.school_admin)
            messages.error(request, "Please correct the form errors below.")
        else:
            # Normal form
            forms_dict[school.pk] = AdminEditForm(instance=school.school_admin)

        # Attach form to school for easier template access
        school.form = forms_dict[school.pk]

    context = {
        'schools': schools,
        'query': query,
        'edit_pk': edit_pk,
    }
    return render(request, "Dashboard/school_admin_list.html", context)


@login_required
def edit_school_admin(request, school_pk):
    if not (request.user.is_superuser or request.user.is_admin or request.user.is_kiswate_admin or request.user.is_kiswate_user):
        messages.error(request, "Access denied: Superuser privileges required.")
        return redirect('kiswate_digital_app:school_admin_list')

    school = get_object_or_404(School, pk=school_pk)
    admin = school.school_admin

    if request.method == 'POST':
        form = AdminEditForm(request.POST, instance=admin)
        logger.info(f"POST data for admin {admin.email}: {request.POST}")
        if form.is_valid():
            form.save()
            messages.success(
                request,
                f'Successfully updated admin "{admin.get_full_name()}" for {school.name}. '
                f'Email sent: {"Yes" if form.cleaned_data.get("send_email") else "No"}. '
                f'Password reset: {"Yes" if form.cleaned_data.get("reset_password") else "No"}.'
            )
            logger.info(f"Updated admin {admin.email} for school {school.name}.")
            return redirect('kiswate_digital_app:school_admin_list')
        else:
            logger.warning(f"Form errors for admin {admin.email}: {form.errors}")
            messages.error(request, "Please correct the form errors.")
            # Redirect with query params to re-open modal if needed
            return redirect(f'/school-admins/?edit_pk={school_pk}&error=1')

    messages.info(request, "Use the edit button in the list to modify this admin.")
    return redirect('kiswate_digital_app:school_admin_list')

@login_required
def delete_school_admin(request, school_pk):
    if not (request.user.is_superuser or request.user.is_admin or request.user.is_kiswate_admin or request.user.is_kiswate_user):
        messages.error(request, "Access denied: Superuser privileges required.")
        return redirect('kiswate_digital_app:kiswate_admin_dashboard')
    """
    Deactivate school admin via modal POST.
    """
    if not request.user.is_superuser or  not request.user.is_kiswate_user:
        messages.error(request, "Access denied: Superuser privileges required.")
        return redirect('kiswate_digital_app:school_admin_list')

    school = get_object_or_404(School, pk=school_pk)
    admin = school.school_admin

    if request.method == 'POST':
        admin.is_active = False
        admin.save()
        messages.success(request, f'Admin "{admin.get_full_name()}" for {school.name} has been deactivated.')
        logger.info(f"Deactivated admin {admin.email} for school {school.name}.")
        return redirect('kiswate_digital_app:school_admin_list')
    
    # For GET: Redirect
    messages.warning(request, "Use the delete button in the list to confirm.")
    return redirect('kiswate_digital_app:school_admin_list')

def kiswate_settings(request):
    return render(request, "Dashboard/kiswate_settings.html", {})


@login_required
def invoice_list(request):
    if not (request.user.is_superuser or request.user.is_admin or request.user.is_kiswate_admin or request.user.is_kiswate_user):
        return redirect('kiswate_digital_app:kiswate_admin_dashboard')
    from school.models import SchoolSubscription
    q = request.GET.get('q', '').strip()
    status = request.GET.get('status', '')
    subs = SchoolSubscription.objects.select_related('school', 'plan', 'managed_by').order_by('-created_at')
    if q:
        subs = subs.filter(Q(school__name__icontains=q) | Q(school__code__icontains=q))
    if status:
        subs = subs.filter(status=status)
    from django.core.paginator import Paginator
    page = Paginator(subs, 20).get_page(request.GET.get('page'))
    return render(request, "Dashboard/invoice_list.html", {'subscriptions': page, 'q': q, 'status': status})


@login_required
def create_invoice(request):
    if not (request.user.is_superuser or request.user.is_admin or request.user.is_kiswate_admin or request.user.is_kiswate_user):
        return redirect('kiswate_digital_app:kiswate_admin_dashboard')
    return redirect('kiswate_digital_app:invoice_list')


@login_required
def payment_history(request):
    if not (request.user.is_superuser or request.user.is_admin or request.user.is_kiswate_admin or request.user.is_kiswate_user):
        return redirect('kiswate_digital_app:kiswate_admin_dashboard')
    from school.models import Payment
    q = request.GET.get('q', '').strip()
    payments = Payment.objects.select_related('student__user', 'school').order_by('-paid_at', '-id')
    if q:
        payments = payments.filter(
            Q(student__user__first_name__icontains=q) |
            Q(student__user__last_name__icontains=q) |
            Q(transaction_id__icontains=q) |
            Q(school__name__icontains=q)
        )
    from django.core.paginator import Paginator
    page = Paginator(payments, 25).get_page(request.GET.get('page'))
    return render(request, "Dashboard/payment_history.html", {'payments': page, 'q': q})


@login_required
def reports(request):
    if not (request.user.is_superuser or request.user.is_admin or request.user.is_kiswate_admin or request.user.is_kiswate_user):
        return redirect('kiswate_digital_app:kiswate_admin_dashboard')
    return redirect('kiswate_digital_app:reports_dashboard')


@login_required
def support(request):
    if not (request.user.is_superuser or request.user.is_admin or request.user.is_kiswate_admin or request.user.is_kiswate_user):
        return redirect('kiswate_digital_app:kiswate_admin_dashboard')
    from school.models import ContactMessage
    messages_qs = ContactMessage.objects.order_by('-created_at')
    from django.core.paginator import Paginator
    page = Paginator(messages_qs, 20).get_page(request.GET.get('page'))
    return render(request, "Dashboard/support.html", {'contact_messages': page})


@login_required
def kiswate_escalations(request):
    """Kiswate admins view and respond to principal escalation complaints."""
    user = request.user
    if not (user.is_superuser or user.is_kiswate_admin or user.is_kiswate_user):
        messages.error(request, "Access denied.")
        return redirect('kiswate_digital_app:kiswate_admin_dashboard')

    status_filter = request.GET.get('status', '')
    qs = Complaint.objects.filter(target='kiswate_admin').select_related(
        'school', 'teacher_complainant__user', 'responded_by__user'
    ).order_by('-created_at')
    if status_filter:
        qs = qs.filter(status=status_filter)

    if request.method == 'POST':
        complaint_id = request.POST.get('complaint_id')
        response_text = request.POST.get('response', '').strip()
        new_status = request.POST.get('status', 'resolved')
        complaint = get_object_or_404(Complaint, pk=complaint_id, target='kiswate_admin')
        if response_text:
            try:
                staff = user.staffprofile
            except Exception:
                staff = None
            complaint.response = response_text
            complaint.status = new_status
            complaint.responded_by = staff
            from django.utils import timezone
            complaint.responded_at = timezone.now()
            complaint.save()
            messages.success(request, "Response saved.")
        return redirect('kiswate_digital_app:kiswate_escalations')

    page = Paginator(qs, 20).get_page(request.GET.get('page'))
    return render(request, 'dim/escalations.html', {
        'complaints': page,
        'status_filter': status_filter,
        'status_choices': Complaint.STATUS_CHOICES,
    })


@login_required
def scholarship_list_create(request):
    if not (request.user.is_superuser or  request.user.is_kiswate_user):
        messages.error(request, "Access denied: Superuser privileges required.")
        return redirect('kiswate_digital_app:kiswate_admin_dashboard')

    """
    List scholarships with search/filter.
    Handles creation via POST from modal.
    """
    if request.method == 'POST':
        form = ScholarshipForm(request.POST, user=request.user)
        if form.is_valid():
            scholarship = form.save()
            messages.success(request, f'Scholarship "{scholarship.title}" created successfully.')
            logger.info(f"Created scholarship '{scholarship.title}' by {request.user.email}.")
            return redirect('kiswate_digital_app:scholarship_list_create')
        else:
            messages.error(request, 'Please correct the form errors below.')
    else:
        form = ScholarshipForm(user=request.user)

    # List with search
    query = request.GET.get('q', '')
    scholarships = Scholarship.objects.filter(created_by=request.user, is_active=True).order_by('-created_at')
    if query:
        scholarships = scholarships.filter(
            Q(title__icontains=query) | Q(description__icontains=query) | Q(eligibility_criteria__icontains=query)
        )

    context = {
        'scholarships': scholarships,
        'form': form,  # For create modal
        'query': query,
    }
    return render(request, 'Dashboard/scholarship_list.html', context)


@login_required
def scholarship_edit(request, pk):
    if not request.user.is_superuser or  not request.user.is_kiswate_user:
        messages.error(request, "Access denied: Superuser privileges required.")
        return redirect('kiswate_digital_app:kiswate_admin_dashboard')
    """
    Edit scholarship via modal POST.
    On error, re-render list with bound form to show errors.
    """
    scholarship = get_object_or_404(Scholarship, pk=pk, created_by=request.user)

    if request.method == 'POST':
        form = ScholarshipForm(request.POST, instance=scholarship, user=request.user)
        if form.is_valid():
            scholarship = form.save()
            messages.success(request, f'Scholarship "{scholarship.title}" updated successfully.')
            logger.info(f"Updated scholarship '{scholarship.title}' by {request.user.email}.")
            return redirect('kiswate_digital_app:scholarship_list_create')
        else:
            messages.error(request, 'Please correct the form errors below.')
            logger.warning(f"Invalid scholarship edit form for {pk} by {request.user.email}: {form.errors}")
            # Re-render list with bound form
            scholarships = Scholarship.objects.filter(created_by=request.user).order_by('-created_at')  # Match list view query
            return render(request, 'Dashboard/scholarship_list.html', {
                'scholarships': scholarships,
                'form': form,  # Bound form for error display
            })
    # For direct GET: Redirect to list
    messages.info(request, "Use the edit button in the list.")
    return redirect('kiswate_digital_app:scholarship_list_create')


@login_required
def scholarship_delete(request, pk):
    if not request.user.is_superuser:
        messages.error(request, "Access denied: Superuser privileges required.")
        return redirect('kiswate_digital_app:kiswate_admin_dashboard')
    """
    Soft-delete scholarship via modal POST.
    """
    scholarship = get_object_or_404(Scholarship, pk=pk, created_by=request.user)

    if request.method == 'POST':
        scholarship.is_active = False
        scholarship.save()
        messages.success(request, f'Scholarship "{scholarship.title}" deactivated successfully.')
        logger.info(f"Deactivated scholarship '{scholarship.title}' by {request.user.email}.")
        return redirect('kiswate_digital_app:scholarship_list_create')

    # For GET: Redirect (modal-driven)
    messages.warning(request, "Use the delete button in the list to confirm.")
    return redirect('kiswate_digital_app:scholarship_list_create')


@login_required
def subscription_plan_list(request):
    if not (request.user.is_superuser or request.user.is_admin or request.user.is_kiswate_admin or request.user.is_kiswate_user):
        messages.error(request, "Access denied: Admin privileges required.")
        return redirect('kiswate_digital_app:kiswate_admin_dashboard')

    plans = SubscriptionPlan.objects.all().order_by('name')
    can_edit = request.user.is_superuser or request.user.is_kiswate_admin
    if request.method == 'POST' and not can_edit:
        messages.error(request, "Access denied: You can only view subscription plans.")
        return redirect('kiswate_digital_app:subscription_plan_list')

    if request.method == 'POST':
        form = SubscriptionPlanForm(request.POST)
        if form.is_valid():
            plan = form.save()
            messages.success(request, f'Subscription plan "{plan.name}" created successfully.')
            logger.info(f"Created subscription plan {plan.name} by {request.user.email}.")
            return redirect('kiswate_digital_app:subscription_plan_list')
    else:
        form = SubscriptionPlanForm()
    return render(request, 'Dashboard/subscription_plan_list.html', {
        'plans': plans,
        'can_edit': can_edit,
        'form': form,
        'title': 'Create Subscription Plan',
    })


@login_required
def subscription_plan_create(request):
    if not request.user.is_superuser:
        messages.error(request, "Access denied: Superuser privileges required.")
        return redirect('kiswate_digital_app:subscription_plan_list')

    if request.method == 'POST':
        form = SubscriptionPlanForm(request.POST)
        if form.is_valid():
            plan = form.save()
            messages.success(request, f'Subscription plan "{plan.name}" created successfully.')
            logger.info(f"Created subscription plan {plan.name} by {request.user.email}.")
            return redirect('kiswate_digital_app:subscription_plan_list')
        else:
            # Explicitly handle invalid form: log errors, add message
            logger.warning(f"Invalid subscription plan form from {request.user.email}: {form.errors}")
            messages.error(request, "Please correct the errors in the form.")
            # Fall through to render with bound form
    else:
        form = SubscriptionPlanForm()

    # Re-render list template with form (for modal errors)
    plans = SubscriptionPlan.objects.all().order_by('name')
    return render(request, 'Dashboard/subscription_plan_list.html', {
        'plans': plans,
        'form': form,
    })

@login_required
def subscription_plan_update(request, pk):
    """
    Update an existing subscription plan (superuser only).
    """
    if not request.user.is_superuser:
        messages.error(request, "Access denied: Superuser privileges required.")
        return redirect('kiswate_digital_app:subscription_plan_list')

    plan = get_object_or_404(SubscriptionPlan, pk=pk)
    if request.method == 'POST':
        form = SubscriptionPlanForm(request.POST, instance=plan)
        if form.is_valid():
            form.save()
            messages.success(request, f'Subscription plan "{plan.name}" updated successfully.')
            logger.info(f"Updated subscription plan {plan.name} by {request.user.email}.")
            return redirect('kiswate_digital_app:subscription_plan_list')
    else:
        form = SubscriptionPlanForm(instance=plan)
    return render(request, 'Dashboard/subscription_plan_list.html', {
        'form': form,
        'title': f'Update Subscription Plan: {plan.name}',
    })


@login_required
def subscription_plan_delete(request, pk):
    """
    Deactivate subscription plan via modal POST (superuser only).
    """
    if not request.user.is_superuser:
        messages.error(request, "Access denied: Superuser privileges required.")
        return redirect('kiswate_digital_app:subscription_plan_list')

    plan = get_object_or_404(SubscriptionPlan, pk=pk)

    if request.method == 'POST':
        plan.is_active = False
        plan.save()
        messages.success(request, f'Subscription plan "{plan.name}" has been deactivated.')
        logger.info(f"Deactivated subscription plan {plan.name} by {request.user.email}.")
        return redirect('kiswate_digital_app:subscription_plan_list')
    
    # For GET: Redirect
    messages.warning(request, "Use the delete button in the list to confirm.")
    return redirect('kiswate_digital_app:subscription_plan_list')



@login_required
def announcements(request):
    if not (request.user.is_superuser or request.user.is_admin or request.user.is_kiswate_admin or request.user.is_kiswate_user):
        return redirect('kiswate_digital_app:kiswate_admin_dashboard')
    return redirect('kiswate_digital_app:kiswate_admin_dashboard')


@login_required
def new_announcement(request):
    return redirect('kiswate_digital_app:kiswate_admin_dashboard')


@login_required
def edit_announcement(request):
    return redirect('kiswate_digital_app:kiswate_admin_dashboard')


@login_required
def delete_announcement(request):
    return redirect('kiswate_digital_app:kiswate_admin_dashboard')


@login_required
def demo_request_list(request):
    if not (request.user.is_superuser or request.user.is_admin or request.user.is_kiswate_admin or request.user.is_kiswate_user):
        messages.error(request, "Access denied: Admin privileges required.")
        return redirect('kiswate_digital_app:kiswate_admin_dashboard')
    
    demo_requests = ContactMessage.objects.all().order_by('-created_at')

    return render(request, "Dashboard/demo_request_list.html", {'demo_requests': demo_requests})



# Mark Verified
@login_required
def mark_verified(request, lead_id):
    if not (request.user.is_superuser or request.user.is_admin or request.user.is_kiswate_admin or request.user.is_kiswate_user):
        messages.error(request, "Access denied: Admin privileges required.")
        return redirect('kiswate_digital_app:kiswate_admin_dashboard')
    lead = get_object_or_404(ContactMessage, id=lead_id)
    lead.is_verified = True
    lead.save()
    messages.success(request, "Lead has been verified successfully.")
    return redirect('kiswate_digital_app:demo_request_list')

# Convert to School

@login_required
def convert_to_school(request, lead_id):
    if not (request.user.is_superuser or request.user.is_admin or request.user.is_kiswate_admin or request.user.is_kiswate_user):
        messages.error(request, "Access denied: Admin privileges required.")
        return redirect('kiswate_digital_app:kiswate_admin_dashboard')

    try:
        lead = get_object_or_404(ContactMessage, id=lead_id)

        if not lead.is_verified:
            messages.warning(request, "Verify the lead first.")
            return redirect('kiswate_digital_app:demo_request_list')

        # Lookup related location instances safely
        county = County.objects.filter(name__iexact=lead.county).first() if lead.county else None
        sub_county = SubCounty.objects.filter(name__iexact=lead.sub_county).first() if lead.sub_county else None
        constituency = Constituency.objects.filter(name__iexact=lead.constituency).first() if lead.constituency else None
        ward = Ward.objects.filter(name__iexact=lead.ward).first() if lead.ward else None
        city = City.objects.filter(name__iexact=lead.city).first() if lead.city else None

        # Generate a secure random password for the school admin
        random_password = secrets.token_urlsafe(12)

        # Create the school admin user
        school_admin = User.objects.create(
            first_name=lead.first_name,
            last_name=lead.last_name,
            email=lead.email_address,
            phone_number=lead.contact_phone,
            is_active=True,
            is_admin=True,      # mark as school admin
            is_principal=True,    # mark as principal
            password=make_password(random_password)
        )

        # Create the School object
        school = School.objects.create(
            name=lead.school_name,
            school_classification=lead.school_category,
            school_admin=school_admin,
            contact_email=lead.email_address,
            contact_phone=lead.contact_phone,
            address=lead.address,
            county=county,
            sub_county=sub_county,
            constituency=constituency,
            ward=ward,
            city=city,
        )

        staff_profile = StaffProfile.objects.create(
            user=school_admin,
            position='teacher',
            school=school,
        )
        # Mark the lead as converted
        lead.status = "converted"
        lead.save()

        messages.success(
            request,
            f"{school.name} has been converted to a School object. Admin password: {random_password}"
        )

    except IntegrityError as e:
        messages.error(request, f"Integrity error occurred during conversion. This may be due to duplicate email or phone number.")
    except Exception as e:
        messages.error(request, f"An unexpected error occurred: {str(e)}")

    return redirect('kiswate_digital_app:demo_request_list')

@login_required
def staff_members(request):
    staff = User.objects.filter(is_kiswate_user=True).order_by('-created_at')
    return render(request, "Dashboard/staff_members.html", {"staff": staff})


# Create new staff (from modal)
@login_required
def new_staff_members(request):
    if request.method == "POST":
        first_name = request.POST.get("first_name")
        last_name = request.POST.get("last_name")
        email = request.POST.get("email")
        phone_number = request.POST.get("phone_number")
        country = request.POST.get("country")
        password = request.POST.get("password")

        # Validation
        if not phone_number:
            messages.error(request, "Phone number is required.")
            return redirect("kiswate_digital_app:staff-members")
        if User.objects.filter(email=email).exists():
            messages.error(request, "Email already exists.")
            return redirect("kiswate_digital_app:staff-members")
        if User.objects.filter(phone_number=phone_number).exists():
            messages.error(request, "Phone number already exists.")
            return redirect("kiswate_digital_app:staff-members")

        user = User.objects.create(
            first_name=first_name,
            last_name=last_name,
            email=email,
            phone_number=phone_number,
            country=country,
            is_staff=True,
            # is_superuser=True,
            is_kiswate_user=True,
            is_active=True,
            password=make_password(password),
        )

        messages.success(request, f"{user.get_full_name()} has been created successfully.")
        return redirect("kiswate_digital_app:staff-members")

    return redirect("kiswate_digital_app:staff-members")


# Edit staff (modal)
@login_required
def edit_staff_member(request, pk):
    staff = get_object_or_404(User, pk=pk, is_kiswate_user=True)
    if request.method == "POST":
        staff.first_name = request.POST.get("first_name")
        staff.last_name = request.POST.get("last_name")
        staff.email = request.POST.get("email")
        staff.phone_number = request.POST.get("phone_number")
        staff.country = request.POST.get("country")
        password = request.POST.get("password")
        if password:
            staff.password = make_password(password)
        staff.save()
        messages.success(request, f"{staff.get_full_name()} updated successfully.")
        return redirect("kiswate_digital_app:staff-members")
    return redirect("kiswate_digital_app:staff-members")


# Delete staff (modal)
@login_required
def delete_staff_member(request, pk):
    staff = get_object_or_404(User, pk=pk, is_kiswate_user=True)
    staff_name = staff.get_full_name()
    staff.delete()
    messages.success(request, f"{staff_name} deleted successfully.")
    return redirect("kiswate_digital_app:staff-members")


 
def _get_profile(request):
    """Returns the UserProfile for the logged-in user, or None."""
    try:
        return request.user.profile
    except (UserProfile.DoesNotExist, AttributeError):
        return None


def _tuition_base_template(request):
    """Return the correct base template for DIL pages — DIL is a module integrated into each role's portal."""
    user = request.user
    if not user.is_authenticated:
        return 'dim/tuition/portal_base.html'
    if getattr(user, 'is_kiswate_admin', False) or getattr(user, 'is_kiswate_user', False):
        return 'Dashboard/base.html'
    # An approved DIL teacher always gets the DIL teacher portal regardless of school role.
    # This prevents school admins/principals who also teach on DIL from seeing the admin sidebar.
    profile = _get_profile(request)
    if profile and profile.role == 'teacher' and profile.vetting_status == 'approved':
        return 'dim/tuition/portal_base.html'
    # School role hierarchy for non-DIL users
    if getattr(user, 'is_principal', False) or getattr(user, 'is_deputy_principal', False) or getattr(user, 'is_admin', False):
        return 'school/base.html'
    if getattr(user, 'is_teacher', False):
        return 'school/teacher/base.html'
    if getattr(user, 'is_parent', False):
        return 'school/parent/base.html'
    if getattr(user, 'is_student', False):
        return 'school/student/base.html'
    return 'dim/tuition/portal_base.html'


def _learning_ctx(request):
    """Return base_template and portal_role for DIL content views (lessons/assignments/classes)."""
    profile = _get_profile(request)
    base = _tuition_base_template(request)
    if profile and profile.role == 'teacher':
        return {'base_template': base, 'portal_role': 'teacher', 'profile': profile}
    if profile and profile.role == 'student':
        return {'base_template': base, 'portal_role': 'student', 'profile': profile}
    return {'base_template': base, 'portal_role': None, 'profile': profile}


def _is_kiswate_or_admin(user):
    return user.is_kiswate_admin or user.is_kiswate_user or user.is_admin


def _is_notification_admin(user):
    return user.is_kiswate_admin or user.is_admin or user.is_principal or user.is_deputy_principal


# ═══════════════════════════════════════════════════════════════════════════════
# MODULE 1: USER MANAGEMENT
# ═══════════════════════════════════════════════════════════════════════════════
 
def student_register(request):
    """Registration for tuition students. Auto-sets up profile if user is already in the system."""
    if request.user.is_authenticated:
        existing = _get_profile(request)
        if existing and existing.role == 'student':
            return redirect('kiswate_digital_app:student_tuition_dashboard')

        # School student — auto-create approved tuition profile from existing data
        if getattr(request.user, 'is_student', False):
            UserProfile.objects.get_or_create(
                user=request.user,
                defaults={
                    'role': 'student',
                    'phone': getattr(request.user, 'phone_number', '') or '',
                    'vetting_status': 'approved',
                },
            )
            messages.success(request, "Your tuition profile has been set up. Welcome!")
            return redirect('kiswate_digital_app:student_tuition_dashboard')

        # Logged in but no school-student flag — show profile-only form (no password needed)
        if request.method == 'POST':
            form = StudentProfileOnlyForm(request.POST)
            if form.is_valid():
                profile = form.save(commit=False)
                profile.user = request.user
                profile.role = 'student'
                profile.phone = profile.phone or getattr(request.user, 'phone_number', '') or ''
                profile.save()
                messages.success(request, "Registration submitted. Awaiting approval.")
                return redirect('kiswate_digital_app:student_register_done')
        else:
            form = StudentProfileOnlyForm(initial={
                'phone': getattr(request.user, 'phone_number', '') or '',
            })
        return render(request, 'dim/users/student_register.html', {'form': form, 'logged_in_flow': True})

    # Anonymous user — full registration form
    if request.method == 'POST':
        form = StudentRegistrationForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Registration submitted. Awaiting approval.")
            return redirect('kiswate_digital_app:student_register_done')
    else:
        form = StudentRegistrationForm()
    return render(request, 'dim/users/student_register.html', {'form': form})
 
 
def teacher_register(request):
    """Registration for tuition teachers. Pre-fills data if user is already in the system."""
    user = request.user
    # Always use teacher base on this registration page
    if user.is_authenticated:
        if getattr(user, 'is_kiswate_admin', False) or getattr(user, 'is_kiswate_user', False):
            base_tpl = 'Dashboard/base.html'
        elif getattr(user, 'is_teacher', False):
            base_tpl = 'school/teacher/base.html'
        else:
            base_tpl = _tuition_base_template(request)
    else:
        base_tpl = 'dim/tuition/portal_base.html'

    if user.is_authenticated:
        existing = _get_profile(request)
        if existing and existing.role == 'teacher':
            return redirect('kiswate_digital_app:teacher_tuition_dashboard')

        # Logged-in user — show profile-only form (no password needed)
        if request.method == 'POST':
            form = TeacherProfileOnlyForm(request.POST)
            if form.is_valid():
                profile = form.save(commit=False)
                profile.user = user
                profile.role = 'teacher'
                profile.phone = profile.phone or getattr(user, 'phone_number', '') or ''
                profile.save()
                messages.success(request, "Registration submitted. Your profile will be vetted.")
                return redirect('kiswate_digital_app:teacher_register_done')
        else:
            form = TeacherProfileOnlyForm(initial={
                'phone': getattr(user, 'phone_number', '') or '',
            })
        return render(request, 'dim/users/teacher_register.html', {
            'form': form, 'logged_in_flow': True, 'portal_role': 'teacher',
            'base_template': base_tpl,
        })

    # Anonymous user — full registration form
    if request.method == 'POST':
        form = TeacherRegistrationForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Registration submitted. Your profile will be vetted.")
            return redirect('kiswate_digital_app:teacher_register_done')
    else:
        form = TeacherRegistrationForm()
    return render(request, 'dim/users/teacher_register.html', {
        'form': form, 'portal_role': 'teacher',
        'base_template': base_tpl,
    })
 
 
def register_done(request):
    is_teacher_done = request.resolver_match.url_name == 'teacher_register_done'
    base_template = 'school/teacher/base.html' if is_teacher_done else 'dim/base.html'
    return render(request, 'dim/users/register_done.html', {'base_template': base_template})
 
 
@login_required
def user_list(request):
    """Admin: list all users with filter by role/vetting status."""
    if not _is_kiswate_or_admin(request.user):
        messages.error(request, "Access denied.")
        return redirect('userauths:sign-in')
    role = request.GET.get('role', '')
    status = request.GET.get('status', '')
    search = request.GET.get('q', '')

    profiles = UserProfile.objects.select_related('user', 'school').order_by('-created_at')
    if role:
        profiles = profiles.filter(role=role)
    if status:
        profiles = profiles.filter(vetting_status=status)
    if search:
        profiles = profiles.filter(
            Q(user__first_name__icontains=search) |
            Q(user__last_name__icontains=search) |
            Q(user__email__icontains=search)
        )

    paginator = Paginator(profiles, 25)
    page_obj = paginator.get_page(request.GET.get('page'))
    return render(request, 'dim/users/user_list.html', {
        'profiles': page_obj, 'page_obj': page_obj, 'role': role, 'status': status, 'search': search,
    })
 
 
@login_required
def user_detail(request, pk):
    if not _is_kiswate_or_admin(request.user):
        messages.error(request, "Access denied.")
        return redirect('userauths:sign-in')
    profile = get_object_or_404(UserProfile, pk=pk)
    guardians = profile.guardians.all() if profile.role == 'student' else []
    enrollments = profile.enrollments.select_related('program') if profile.role == 'student' else []
    return render(request, 'dim/users/user_detail.html', {
        'profile': profile, 'guardians': guardians, 'enrollments': enrollments,
    })
 
 
@login_required
def vet_user(request, pk):
    """Admin: approve or reject a user profile."""
    if not _is_kiswate_or_admin(request.user):
        messages.error(request, "Access denied.")
        return redirect('userauths:sign-in')
    profile = get_object_or_404(UserProfile, pk=pk)
    if request.method == 'POST':
        form = VettingForm(request.POST, instance=profile)
        if form.is_valid():
            p = form.save(commit=False)
            p.vetted_by = request.user
            p.vetted_at = timezone.now()
            p.save()
            messages.success(request, f"Profile {p.get_vetting_status_display()} successfully.")
            return redirect('kiswate_digital_app:user_detail', pk=pk)
    else:
        form = VettingForm(instance=profile)
    return render(request, 'dim/users/vet_user.html', {'form': form, 'profile': profile})


@login_required
def assign_lessons_to_teacher(request, pk):
    """Admin: assign / un-assign lessons to an approved DIL teacher."""
    if not _is_kiswate_or_admin(request.user):
        messages.error(request, "Access denied.")
        return redirect('userauths:sign-in')
    teacher_profile = get_object_or_404(UserProfile, pk=pk, role='teacher', vetting_status='approved')
    all_lessons = Lesson.objects.select_related('program__subject').order_by('program__name', 'order', 'title')

    if request.method == 'POST':
        selected_ids = request.POST.getlist('lesson_ids')
        # Remove this teacher from lessons that were de-selected
        Lesson.objects.filter(teacher=teacher_profile).exclude(pk__in=selected_ids).update(teacher=None)
        # Assign selected lessons to this teacher
        if selected_ids:
            Lesson.objects.filter(pk__in=selected_ids).update(teacher=teacher_profile)
        count = len(selected_ids)
        messages.success(request, f"{count} lesson{'s' if count != 1 else ''} assigned to {teacher_profile.full_name}.")
        return redirect('kiswate_digital_app:user_detail', pk=pk)

    assigned_ids = set(Lesson.objects.filter(teacher=teacher_profile).values_list('pk', flat=True))
    # Group lessons by program for easier display
    programs_map = {}
    for lesson in all_lessons:
        prog = lesson.program
        programs_map.setdefault(prog, []).append(lesson)

    return render(request, 'dim/users/assign_lessons.html', {
        'teacher_profile': teacher_profile,
        'programs_map': programs_map,
        'assigned_ids': assigned_ids,
    })


@login_required
def add_guardian(request, student_pk):
    if not _is_kiswate_or_admin(request.user):
        messages.error(request, "Access denied.")
        return redirect('userauths:sign-in')
    student = get_object_or_404(UserProfile, pk=student_pk, role='student')
    if request.method == 'POST':
        form = GuardianForm(request.POST)
        if form.is_valid():
            g = form.save(commit=False)
            g.student = student
            g.save()
            messages.success(request, "Guardian added.")
            return redirect('kiswate_digital_app:user_detail', pk=student_pk)
    else:
        form = GuardianForm()
    return render(request, 'dim/users/guardian_form.html',
                  {'form': form, 'student': student})
 
 
@login_required
def enrollment_list(request):
    if not _is_kiswate_or_admin(request.user):
        messages.error(request, "Access denied.")
        return redirect('userauths:sign-in')
    enrollments = Enrollment.objects.select_related('student__user', 'program').order_by('-enrolled_at')
    paginator = Paginator(enrollments, 25)
    page_obj = paginator.get_page(request.GET.get('page'))
    return render(request, 'dim/users/enrollment_list.html', {'enrollments': page_obj, 'page_obj': page_obj})
 
 
@login_required
def enroll_student(request):
    if not _is_kiswate_or_admin(request.user):
        messages.error(request, "Access denied.")
        return redirect('userauths:sign-in')
    profile = _get_profile(request)
    school = profile.school if profile else None
    if request.method == 'POST':
        form = EnrollmentForm(request.POST, school=school)
        if form.is_valid():
            form.save()
            messages.success(request, "Student enrolled successfully.")
            return redirect('kiswate_digital_app:enrollment_list')
    else:
        form = EnrollmentForm(school=school)
    return render(request, 'dim/users/enroll_student.html', {'form': form})
 
 
# ═══════════════════════════════════════════════════════════════════════════════
# MODULE 2: VIRTUAL LEARNING
# ═══════════════════════════════════════════════════════════════════════════════
 
@login_required
def virtual_class_list(request):
    profile = _get_profile(request)
    upcoming_qs = VirtualClass.objects.filter(
        is_cancelled=False, scheduled_at__gte=timezone.now()
    ).select_related('program', 'teacher__user')
    past_qs = VirtualClass.objects.filter(
        is_cancelled=False, scheduled_at__lt=timezone.now()
    ).select_related('program', 'teacher__user')
 
    if profile and profile.role == 'teacher':
        upcoming_qs = upcoming_qs.filter(teacher=profile)
        past_qs = past_qs.filter(teacher=profile)
    elif profile and profile.role == 'student':
        enrolled_programs = profile.enrollments.filter(is_active=True).values_list('program_id', flat=True)
        upcoming_qs = upcoming_qs.filter(program_id__in=enrolled_programs)
        past_qs = past_qs.filter(program_id__in=enrolled_programs)
 
    ctx = _learning_ctx(request)
    ctx.update({'upcoming_classes': upcoming_qs[:20], 'past_classes': past_qs[:20]})
    return render(request, 'dim/virtual_learning/class_list.html', ctx)
 
 
@login_required
def virtual_class_create(request):
    profile = _get_profile(request)
    if not _is_kiswate_or_admin(request.user):
        messages.error(request, "Only administrators can schedule DIL classes.")
        if profile and profile.role == 'teacher':
            return redirect('kiswate_digital_app:teacher_tuition_dashboard')
        return redirect('userauths:sign-in')
    ctx = _learning_ctx(request)
    if request.method == 'POST':
        form = VirtualClassForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Class scheduled successfully.")
            return redirect('kiswate_digital_app:virtual_class_detail', pk=form.instance.pk)
    else:
        form = VirtualClassForm()
    ctx.update({'form': form, 'action': 'Schedule'})
    return render(request, 'dim/virtual_learning/class_form.html', ctx)
 
 
@login_required
def virtual_class_detail(request, pk):
    vc = get_object_or_404(VirtualClass, pk=pk)
    profile = _get_profile(request)
    attendance_summary = get_attendance_summary(vc)
    my_attendance = None
    if profile and profile.role == 'student':
        my_attendance = ClassAttendance.objects.filter(
            virtual_class=vc, student=profile).first()
 
    attendance_records = vc.attendance_records.select_related('student__user').filter(is_present=True)
 
    ctx = _learning_ctx(request)
    ctx.update({'vc': vc, 'attendance_summary': attendance_summary,
                'my_attendance': my_attendance, 'attendance_records': attendance_records})
    return render(request, 'dim/virtual_learning/class_detail.html', ctx)
 
 
@login_required
def virtual_class_edit(request, pk):
    profile = _get_profile(request)
    if not _is_kiswate_or_admin(request.user):
        messages.error(request, "Only administrators can edit DIL classes.")
        if profile and profile.role == 'teacher':
            return redirect('kiswate_digital_app:teacher_tuition_dashboard')
        return redirect('userauths:sign-in')
    vc = get_object_or_404(VirtualClass, pk=pk)
    ctx = _learning_ctx(request)
    if request.method == 'POST':
        form = VirtualClassForm(request.POST, instance=vc)
        if form.is_valid():
            form.save()
            messages.success(request, "Class updated.")
            return redirect('kiswate_digital_app:virtual_class_detail', pk=pk)
    else:
        form = VirtualClassForm(instance=vc)
    ctx.update({'form': form, 'action': 'Edit', 'vc': vc})
    return render(request, 'dim/virtual_learning/class_form.html', ctx)
 
 
@login_required
def virtual_class_cancel(request, pk):
    if not _is_kiswate_or_admin(request.user):
        messages.error(request, "Access denied.")
        return redirect('userauths:sign-in')
    vc = get_object_or_404(VirtualClass, pk=pk)
    if request.method == 'POST':
        vc.is_cancelled = True
        vc.save(update_fields=['is_cancelled'])
        messages.warning(request, "Class cancelled.")
    return redirect('kiswate_digital_app:virtual_class_list')
 
 
@login_required
def join_class(request, pk):
    """
    Student clicks 'Join' — records attendance then redirects to the meeting link.
    This is the core attendance tracking mechanism.
    """
    vc = get_object_or_404(VirtualClass, pk=pk)
    profile = _get_profile(request)
 
    if profile and profile.role == 'student':
        record, created = record_join_attendance(vc, profile)
        if created:
            messages.info(request, "Your attendance has been recorded.")

    if not vc.meeting_link:
        messages.error(request, "No meeting link has been set for this class.")
        return redirect('kiswate_digital_app:virtual_class_detail', pk=pk)
    return redirect(vc.meeting_link)
 
 
@login_required
def mark_attendance_manual(request, pk):
    """Teacher manually marks attendance for a class."""
    profile = _get_profile(request)
    is_tuition_teacher = profile and profile.role == 'teacher' and profile.vetting_status == 'approved'
    if not _is_kiswate_or_admin(request.user) and not is_tuition_teacher:
        messages.error(request, "Access denied.")
        return redirect('userauths:sign-in')
    vc = get_object_or_404(VirtualClass, pk=pk)
    if request.method == 'POST':
        form = AttendanceManualForm(request.POST, virtual_class=vc)
        if form.is_valid():
            present_students = form.cleaned_data['present_students']
            ClassAttendance.objects.filter(virtual_class=vc, marked_by_teacher=True).delete()
            for student in present_students:
                ClassAttendance.objects.update_or_create(
                    virtual_class=vc, student=student,
                    defaults={'is_present': True, 'marked_by_teacher': True, 'joined_at': timezone.now()}
                )
            messages.success(request, "Attendance saved.")
            return redirect('kiswate_digital_app:virtual_class_detail', pk=pk)
    else:
        form = AttendanceManualForm(virtual_class=vc)
    ctx = _learning_ctx(request)
    ctx.update({'form': form, 'vc': vc})
    return render(request, 'dim/virtual_learning/mark_attendance.html', ctx)
 
 
@login_required
@require_POST
def mark_nil_attendance(request, pk):
    """Teacher marks a class session as NIL — class ran but no attendance is recorded.
    Clears any existing teacher-marked records and flags the class with a NIL note."""
    profile = _get_profile(request)
    is_tuition_teacher = profile and profile.role == 'teacher' and profile.vetting_status == 'approved'
    if not _is_kiswate_or_admin(request.user) and not is_tuition_teacher:
        messages.error(request, "Access denied.")
        return redirect('userauths:sign-in')
    vc = get_object_or_404(VirtualClass, pk=pk)
    # Remove any existing teacher-marked attendance to avoid partial records
    ClassAttendance.objects.filter(virtual_class=vc, marked_by_teacher=True).delete()
    # Record NIL in the class notes so it's auditable
    nil_stamp = f"\n[NIL] Attendance submitted as NIL by {request.user.get_full_name() or request.user.email} on {timezone.now().strftime('%d %b %Y %H:%M')}."
    VirtualClass.objects.filter(pk=pk).update(notes=vc.notes + nil_stamp)
    messages.success(request, "NIL attendance recorded — no students marked present for this class.")
    return redirect('kiswate_digital_app:virtual_class_detail', pk=pk)


@login_required
def upload_recording(request, pk):
    profile = _get_profile(request)
    is_tuition_teacher = profile and profile.role == 'teacher' and profile.vetting_status == 'approved'
    if not _is_kiswate_or_admin(request.user) and not is_tuition_teacher:
        messages.error(request, "Access denied.")
        return redirect('userauths:sign-in')
    vc = get_object_or_404(VirtualClass, pk=pk)
    if request.method == 'POST':
        form = RecordingUploadForm(request.POST, instance=vc)
        if form.is_valid():
            form.save()
            messages.success(request, "Recording link saved.")
            return redirect('kiswate_digital_app:virtual_class_detail', pk=pk)
    else:
        form = RecordingUploadForm(instance=vc)
    ctx = _learning_ctx(request)
    ctx.update({'form': form, 'vc': vc})
    return render(request, 'dim/virtual_learning/upload_recording.html', ctx)
 
 
@login_required
def lesson_list(request):
    profile = _get_profile(request)
    lessons = Lesson.objects.select_related('program', 'teacher__user')
    if profile and profile.role == 'teacher':
        lessons = lessons.filter(teacher=profile)
    elif profile and profile.role == 'student':
        enrolled = profile.enrollments.filter(is_active=True).values_list('program_id', flat=True)
        lessons = lessons.filter(program_id__in=enrolled, is_published=True)
    paginator = Paginator(lessons, 20)
    page_obj = paginator.get_page(request.GET.get('page'))
    ctx = _learning_ctx(request)
    ctx.update({'lessons': page_obj, 'page_obj': page_obj})
    return render(request, 'dim/virtual_learning/lesson_list.html', ctx)
 
 
@login_required
def lesson_create(request):
    profile = _get_profile(request)
    is_tuition_teacher = profile and profile.role == 'teacher' and profile.vetting_status == 'approved'
    if not _is_kiswate_or_admin(request.user) and not is_tuition_teacher:
        messages.error(request, "Access denied.")
        return redirect('userauths:sign-in')
    ctx = _learning_ctx(request)
    if request.method == 'POST':
        form = LessonForm(request.POST, request.FILES, teacher_profile=profile if is_tuition_teacher else None)
        if form.is_valid():
            lesson = form.save(commit=False)
            if is_tuition_teacher:
                lesson.teacher = profile
            lesson.save()
            messages.success(request, "Lesson created.")
            if is_tuition_teacher:
                return redirect('kiswate_digital_app:teacher_tuition_dashboard')
            return redirect('kiswate_digital_app:lesson_list')
    else:
        form = LessonForm(teacher_profile=profile if is_tuition_teacher else None)
    ctx.update({'form': form, 'action': 'Create'})
    return render(request, 'dim/virtual_learning/lesson_form.html', ctx)
 
 
@login_required
def lesson_detail(request, pk):
    lesson = get_object_or_404(Lesson, pk=pk)
    assignments = lesson.assignments.filter(is_published=True)
    # Upcoming virtual classes for this lesson's program so the teacher can see/share meeting links
    upcoming_classes = VirtualClass.objects.filter(
        program=lesson.program, is_cancelled=False
    ).order_by('scheduled_at')[:5]
    ctx = _learning_ctx(request)
    ctx.update({'lesson': lesson, 'assignments': assignments, 'upcoming_classes': upcoming_classes})
    return render(request, 'dim/virtual_learning/lesson_detail.html', ctx)
 
 
@login_required
def lesson_edit(request, pk):
    profile = _get_profile(request)
    is_tuition_teacher = profile and profile.role == 'teacher' and profile.vetting_status == 'approved'
    if not _is_kiswate_or_admin(request.user) and not is_tuition_teacher:
        messages.error(request, "Access denied.")
        return redirect('userauths:sign-in')
    lesson = get_object_or_404(Lesson, pk=pk)
    ctx = _learning_ctx(request)
    if request.method == 'POST':
        form = LessonForm(request.POST, request.FILES, instance=lesson,
                          teacher_profile=profile if is_tuition_teacher else None)
        if form.is_valid():
            form.save()
            messages.success(request, "Lesson updated.")
            return redirect('kiswate_digital_app:lesson_detail', pk=pk)
    else:
        form = LessonForm(instance=lesson, teacher_profile=profile if is_tuition_teacher else None)
    ctx.update({'form': form, 'action': 'Edit', 'lesson': lesson})
    return render(request, 'dim/virtual_learning/lesson_form.html', ctx)
 
 
@login_required
def assignment_list(request):
    profile = _get_profile(request)
    assignments = Assignment.objects.select_related('program', 'lesson').order_by('-due_date')
    if profile and profile.role == 'teacher':
        teacher_programs = profile.teaching_programs.filter(is_tuition=True)
        assignments = assignments.filter(program__in=teacher_programs)
    elif profile and profile.role == 'student':
        enrolled = profile.enrollments.filter(is_active=True).values_list('program_id', flat=True)
        assignments = assignments.filter(program_id__in=enrolled, is_published=True)
    paginator = Paginator(assignments, 20)
    page_obj = paginator.get_page(request.GET.get('page'))
    ctx = _learning_ctx(request)
    ctx.update({'assignments': page_obj, 'page_obj': page_obj})
    return render(request, 'dim/virtual_learning/assignment_list.html', ctx)
 
 
@login_required
def assignment_create(request):
    profile = _get_profile(request)
    is_tuition_teacher = profile and profile.role == 'teacher' and profile.vetting_status == 'approved'
    if not _is_kiswate_or_admin(request.user) and not is_tuition_teacher:
        messages.error(request, "Access denied.")
        return redirect('userauths:sign-in')
    if request.method == 'POST':
        form = AssignmentForm(request.POST, request.FILES,
                              teacher_profile=profile if is_tuition_teacher else None)
        if form.is_valid():
            form.save()
            asgn = form.instance
            notify_assignment_due(asgn)
            messages.success(request, "Assignment created and students notified.")
            redirect_to = 'kiswate_digital_app:teacher_tuition_dashboard' if is_tuition_teacher else 'kiswate_digital_app:assignment_list'
            return redirect(redirect_to)
    else:
        form = AssignmentForm(teacher_profile=profile if is_tuition_teacher else None)
    ctx = _learning_ctx(request)
    ctx.update({'form': form, 'action': 'Create'})
    return render(request, 'dim/virtual_learning/assignment_form.html', ctx)


@login_required
def assignment_detail(request, pk):
    assignment = get_object_or_404(Assignment, pk=pk)
    profile = _get_profile(request)
    my_submission = None
    submissions = []
    if profile and profile.role == 'student':
        my_submission = AssignmentSubmission.objects.filter(
            assignment=assignment, student=profile).first()
    elif profile and profile.role in ('teacher', 'school_admin', 'super_admin'):
        submissions = assignment.submissions.select_related('student__user').order_by('-submitted_at')
    elif not profile:
        submissions = assignment.submissions.select_related('student__user').order_by('-submitted_at')
    ctx = _learning_ctx(request)
    ctx.update({'assignment': assignment, 'my_submission': my_submission, 'submissions': submissions})
    return render(request, 'dim/virtual_learning/assignment_detail.html', ctx)
 
 
@login_required
def submit_assignment(request, pk):
    assignment = get_object_or_404(Assignment, pk=pk)
    profile = _get_profile(request)
    if not profile:
        messages.error(request, "No profile found.")
        return redirect('userauths:sign-in')
    existing = AssignmentSubmission.objects.filter(assignment=assignment, student=profile).first()
    if existing:
        messages.warning(request, "You have already submitted this assignment.")
        return redirect('kiswate_digital_app:assignment_detail', pk=pk)
 
    if request.method == 'POST':
        form = SubmissionForm(request.POST, request.FILES)
        if form.is_valid():
            sub = form.save(commit=False)
            sub.assignment = assignment
            sub.student = profile
            sub.save()
            messages.success(request, "Submission received.")
            return redirect('kiswate_digital_app:assignment_detail', pk=pk)
    else:
        form = SubmissionForm()
    ctx = _learning_ctx(request)
    ctx.update({'form': form, 'assignment': assignment})
    return render(request, 'dim/virtual_learning/submit_assignment.html', ctx)
 
 
@login_required
def grade_submission(request, pk):
    profile = _get_profile(request)
    is_tuition_teacher = profile and profile.role == 'teacher' and profile.vetting_status == 'approved'
    if not _is_kiswate_or_admin(request.user) and not is_tuition_teacher:
        messages.error(request, "Access denied.")
        return redirect('userauths:sign-in')
    submission = get_object_or_404(AssignmentSubmission, pk=pk)
    if request.method == 'POST':
        form = GradeSubmissionForm(request.POST, instance=submission)
        if form.is_valid():
            s = form.save(commit=False)
            s.graded_at = timezone.now()
            s.graded_by = profile
            s.save()
            messages.success(request, "Submission graded.")
            return redirect('kiswate_digital_app:assignment_detail', pk=submission.assignment.pk)
    else:
        form = GradeSubmissionForm(instance=submission)
    ctx = _learning_ctx(request)
    ctx.update({'form': form, 'submission': submission})
    return render(request, 'dim/virtual_learning/grade_submission.html', ctx)
 
 
# ═══════════════════════════════════════════════════════════════════════════════
# MODULE 3: ASSESSMENT
# ═══════════════════════════════════════════════════════════════════════════════
 
@login_required
def assessment_list(request):
    profile = _get_profile(request)
    assessments = Assessment.objects.select_related('program').order_by('-created_at')
    if profile and profile.role == 'student':
        enrolled = profile.enrollments.filter(is_active=True).values_list('program_id', flat=True)
        assessments = assessments.filter(program_id__in=enrolled, is_published=True)
    paginator = Paginator(assessments, 20)
    page_obj = paginator.get_page(request.GET.get('page'))
    ctx = _learning_ctx(request)
    ctx.update({'assessments': page_obj, 'page_obj': page_obj})
    return render(request, 'dim/assessments/assessment_list.html', ctx)
 
 
@login_required
def assessment_create(request):
    profile = _get_profile(request)
    is_tuition_teacher = profile and profile.role == 'teacher' and profile.vetting_status == 'approved'
    if not _is_kiswate_or_admin(request.user) and not is_tuition_teacher:
        messages.error(request, "Access denied.")
        return redirect('userauths:sign-in')
    if request.method == 'POST':
        form = AssessmentForm(request.POST, teacher_profile=profile if is_tuition_teacher else None)
        if form.is_valid():
            a = form.save(commit=False)
            if profile:
                a.created_by = profile
            a.save()
            messages.success(request, "Assessment created. Now add questions.")
            return redirect('kiswate_digital_app:assessment_questions', pk=a.pk)
    else:
        form = AssessmentForm(teacher_profile=profile if is_tuition_teacher else None)
    ctx = _learning_ctx(request)
    ctx.update({'form': form, 'action': 'Create'})
    return render(request, 'dim/assessments/assessment_form.html', ctx)
 
 
@login_required
def assessment_detail(request, pk):
    assessment = get_object_or_404(Assessment, pk=pk)
    profile = _get_profile(request)
    questions = assessment.questions.prefetch_related('choices')
    my_attempt = None
    if profile and profile.role == 'student':
        my_attempt = StudentAssessmentAttempt.objects.filter(
            assessment=assessment, student=profile).first()
    results = None
    if assessment.results_published:
        results = assessment.attempts.filter(is_graded=True).select_related('student__user')
    ctx = _learning_ctx(request)
    ctx.update({'assessment': assessment, 'questions': questions,
                'my_attempt': my_attempt, 'results': results})
    return render(request, 'dim/assessments/assessment_detail.html', ctx)
 
 
@login_required
def assessment_questions(request, pk):
    """Add/manage questions for an assessment."""
    assessment = get_object_or_404(Assessment, pk=pk)
    questions = assessment.questions.prefetch_related('choices').all()
    return render(request, 'dim/assessments/assessment_questions.html',
                  {'assessment': assessment, 'questions': questions})
 
 
@login_required
def question_create(request, assessment_pk):
    if not _is_kiswate_or_admin(request.user):
        messages.error(request, "Access denied.")
        return redirect('userauths:sign-in')
    assessment = get_object_or_404(Assessment, pk=assessment_pk)
    if request.method == 'POST':
        form = QuestionForm(request.POST)
        formset = ChoiceFormSet(request.POST)
        if form.is_valid() and formset.is_valid():
            question = form.save(commit=False)
            question.assessment = assessment
            question.save()
            formset.instance = question
            formset.save()
            messages.success(request, "Question added.")
            return redirect('kiswate_digital_app:assessment_questions', pk=assessment_pk)
    else:
        form = QuestionForm()
        formset = ChoiceFormSet()
    return render(request, 'dim/assessments/question_form.html',
                  {'form': form, 'formset': formset, 'assessment': assessment})
 
 
@login_required
def question_edit(request, pk):
    if not _is_kiswate_or_admin(request.user):
        messages.error(request, "Access denied.")
        return redirect('userauths:sign-in')
    question = get_object_or_404(Question, pk=pk)
    if request.method == 'POST':
        form = QuestionForm(request.POST, instance=question)
        formset = ChoiceFormSet(request.POST, instance=question)
        if form.is_valid() and formset.is_valid():
            form.save()
            formset.save()
            messages.success(request, "Question updated.")
            return redirect('kiswate_digital_app:assessment_questions', pk=question.assessment.pk)
    else:
        form = QuestionForm(instance=question)
        formset = ChoiceFormSet(instance=question)
    return render(request, 'dim/assessments/question_form.html',
                  {'form': form, 'formset': formset, 'assessment': question.assessment, 'question': question})
 
 
@login_required
def take_assessment(request, pk):
    """Student takes an assessment."""
    assessment = get_object_or_404(Assessment, pk=pk)
    profile = _get_profile(request)
    if not profile:
        messages.error(request, "No student profile found.")
        return redirect('userauths:sign-in')

    # Check time window
    now = timezone.now()
    if assessment.start_time and now < assessment.start_time:
        messages.warning(request, "This assessment has not started yet.")
        return redirect('kiswate_digital_app:assessment_detail', pk=pk)
    if assessment.end_time and now > assessment.end_time:
        messages.warning(request, "This assessment has closed.")
        return redirect('kiswate_digital_app:assessment_detail', pk=pk)
 
    attempt, created = StudentAssessmentAttempt.objects.get_or_create(
        assessment=assessment, student=profile,
        defaults={'started_at': now}
    )
    if attempt.submitted_at:
        messages.info(request, "You have already submitted this assessment.")
        return redirect('kiswate_digital_app:assessment_result', pk=attempt.pk)
 
    questions = assessment.questions.prefetch_related('choices').all()
 
    if request.method == 'POST':
        # Save answers
        for question in questions:
            field_name = f"q_{question.pk}"
            if question.question_type in ('mcq', 'true_false'):
                choice_id = request.POST.get(field_name)
                choice = Choice.objects.filter(pk=choice_id).first() if choice_id else None
                StudentAnswer.objects.update_or_create(
                    attempt=attempt, question=question,
                    defaults={'selected_choice': choice}
                )
            else:
                text = request.POST.get(field_name, '')
                StudentAnswer.objects.update_or_create(
                    attempt=attempt, question=question,
                    defaults={'text_answer': text}
                )
        attempt.submitted_at = timezone.now()
        attempt.save(update_fields=['submitted_at'])
        auto_grade_attempt(attempt)
        messages.success(request, "Assessment submitted.")
        return redirect('kiswate_digital_app:assessment_result', pk=attempt.pk)
 
    ctx = _learning_ctx(request)
    ctx.update({'assessment': assessment, 'questions': questions, 'attempt': attempt})
    return render(request, 'dim/assessments/take_assessment.html', ctx)
 
 
@login_required
def assessment_result(request, pk):
    attempt = get_object_or_404(StudentAssessmentAttempt, pk=pk)
    profile = _get_profile(request)
    if profile and attempt.student != profile and not _is_kiswate_or_admin(request.user):
        messages.error(request, "You can only view your own results.")
        return redirect('kiswate_digital_app:assessment_list')
    answers = attempt.answers.select_related('question', 'selected_choice').all()
    ctx = _learning_ctx(request)
    ctx.update({'attempt': attempt, 'answers': answers})
    return render(request, 'dim/assessments/result.html', ctx)
 
 
@login_required
def publish_results(request, pk):
    if not _is_kiswate_or_admin(request.user):
        messages.error(request, "Access denied.")
        return redirect('userauths:sign-in')
    assessment = get_object_or_404(Assessment, pk=pk)
    if request.method == 'POST':
        assessment.results_published = True
        assessment.save(update_fields=['results_published'])
        messages.success(request, "Results published to students.")
    return redirect('kiswate_digital_app:assessment_detail', pk=pk)
 
 
# ═══════════════════════════════════════════════════════════════════════════════
# MODULE 4: COMMUNICATION & NOTIFICATIONS
# ═══════════════════════════════════════════════════════════════════════════════
 
@login_required
def notification_list(request):
    profile = _get_profile(request)
    is_tuition_teacher = profile and profile.role == 'teacher' and profile.vetting_status == 'approved'
    if not _is_notification_admin(request.user) and not is_tuition_teacher:
        messages.error(request, "Access denied.")
        return redirect('userauths:sign-in')
    if is_tuition_teacher:
        teacher_programs = profile.teaching_programs.filter(is_tuition=True)
        enrolled_students = UserProfile.objects.filter(
            enrollments__program__in=teacher_programs, enrollments__is_active=True)
        logs = NotificationLog.objects.filter(
            recipient__in=enrolled_students).select_related('recipient__user').order_by('-created_at')
    else:
        logs = NotificationLog.objects.select_related('recipient__user').order_by('-created_at')
    paginator = Paginator(logs, 20)
    page_obj = paginator.get_page(request.GET.get('page'))
    ctx = _learning_ctx(request)
    ctx.update({'logs': page_obj, 'page_obj': page_obj, 'is_admin': _is_kiswate_or_admin(request.user)})
    return render(request, 'dim/communication/notification_list.html', ctx)
 
 
@login_required
def notification_template_list(request):
    if not _is_kiswate_or_admin(request.user):
        messages.error(request, "Access denied.")
        return redirect('userauths:sign-in')
    templates = NotificationTemplate.objects.all()
    return render(request, 'dim/communication/template_list.html', {'templates': templates})
 
 
@login_required
def notification_template_create(request):
    if not _is_kiswate_or_admin(request.user):
        messages.error(request, "Access denied.")
        return redirect('userauths:sign-in')
    if request.method == 'POST':
        form = NotificationTemplateForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Template saved.")
            return redirect('kiswate_digital_app:notification_template_list')
    else:
        form = NotificationTemplateForm()
    return render(request, 'dim/communication/template_form.html',
                  {'form': form, 'action': 'Create'})
 
 
@login_required
def notification_template_edit(request, pk):
    if not _is_kiswate_or_admin(request.user):
        messages.error(request, "Access denied.")
        return redirect('userauths:sign-in')
    template = get_object_or_404(NotificationTemplate, pk=pk)
    if request.method == 'POST':
        form = NotificationTemplateForm(request.POST, instance=template)
        if form.is_valid():
            form.save()
            messages.success(request, "Template updated.")
            return redirect('kiswate_digital_app:notification_template_list')
    else:
        form = NotificationTemplateForm(instance=template)
    return render(request, 'dim/communication/template_form.html',
                  {'form': form, 'action': 'Edit', 'template': template})
 
 
@login_required
def send_bulk_notification(request):
    if not _is_notification_admin(request.user):
        messages.error(request, "Access denied.")
        return redirect('userauths:sign-in')
    if request.method == 'POST':
        form = BulkNotificationForm(request.POST)
        if form.is_valid():
            data = form.cleaned_data
            recipients = []
            if data['recipients'] == 'all_students':
                recipients = UserProfile.objects.filter(role='student', vetting_status='approved')
            elif data['recipients'] == 'all_teachers':
                recipients = UserProfile.objects.filter(role='teacher', vetting_status='approved')
            elif data['recipients'] == 'program' and data.get('program'):
                recipients = UserProfile.objects.filter(
                    enrollments__program=data['program'], enrollments__is_active=True)
            elif data['recipients'] == 'school' and data.get('school'):
                recipients = UserProfile.objects.filter(school=data['school'])
 
            sent = 0
            for r in recipients:
                send_notification(r, data['message'], data.get('subject', ''), data['notification_type'])
                sent += 1
            messages.success(request, f"Notification queued for {sent} recipients.")
            return redirect('kiswate_digital_app:notification_list')
    else:
        form = BulkNotificationForm()
    return render(request, 'dim/communication/bulk_notify.html', {'form': form})
 
 
@login_required
def send_class_reminder(request, pk):
    """Quick action: send reminder for an upcoming class."""
    if not _is_kiswate_or_admin(request.user):
        messages.error(request, "Access denied.")
        return redirect('userauths:sign-in')
    vc = get_object_or_404(VirtualClass, pk=pk)
    if request.method == 'POST':
        notify_class_reminder(vc)
        messages.success(request, "Reminder sent to all enrolled students.")
    return redirect('kiswate_digital_app:virtual_class_detail', pk=pk)
 
 
# ═══════════════════════════════════════════════════════════════════════════════
# MODULE 5: REPORTS & ANALYTICS
# ═══════════════════════════════════════════════════════════════════════════════
 
@login_required
def reports_dashboard(request):
    """Main reports landing page with summary tiles."""
    if not _is_kiswate_or_admin(request.user):
        messages.error(request, "Access denied.")
        return redirect('userauths:sign-in')
    from .models import School, Program
    schools = School.objects.filter(is_active=True)
    programs = Program.objects.filter(is_active=True)
    return render(request, 'dim/reports/dashboard.html',
                  {'schools': schools, 'programs': programs})
 
 
@login_required
def student_performance_report(request):
    if not _is_kiswate_or_admin(request.user):
        messages.error(request, "Access denied.")
        return redirect('userauths:sign-in')
    program_id = request.GET.get('program')
    school_id = request.GET.get('school')
    program = None
    report = []
 
    if program_id:
        program = get_object_or_404(Program, pk=program_id)
        report = get_program_performance_report(program)
    elif school_id:
        school = get_object_or_404(School, pk=school_id)
        for prog in Program.objects.filter(school=school, is_active=True):
            report.extend(get_program_performance_report(prog))
 
    return render(request, 'dim/reports/student_performance.html', {
        'report': report, 'program': program,
    })
 
 
@login_required
def attendance_report(request):
    """
    Attendance report built from ClassAttendance records.
    Shows per-class and per-student attendance derived from join-click and teacher-marked data.
    """
    if not _is_kiswate_or_admin(request.user):
        messages.error(request, "Access denied.")
        return redirect('userauths:sign-in')
    program_id = request.GET.get('program')
    program = None
    classes_data = []
 
    if program_id:
        program = get_object_or_404(Program, pk=program_id)
        virtual_classes = VirtualClass.objects.filter(
            program=program, is_cancelled=False
        ).order_by('scheduled_at')
 
        for vc in virtual_classes:
            summary = get_attendance_summary(vc)
            classes_data.append({'vc': vc, **summary})
 
    return render(request, 'dim/reports/attendance.html', {
        'program': program, 'classes_data': classes_data,
    })
 
 
@login_required
def teacher_activity_report(request):
    if not _is_kiswate_or_admin(request.user):
        messages.error(request, "Access denied.")
        return redirect('userauths:sign-in')
    teachers = UserProfile.objects.filter(role='teacher', vetting_status='approved')
    report = [get_teacher_activity_report(t) for t in teachers]
    return render(request, 'dim/reports/teacher_activity.html', {'report': report})
 
 
@login_required
def school_utilization_report(request):
    if not _is_kiswate_or_admin(request.user):
        messages.error(request, "Access denied.")
        return redirect('userauths:sign-in')
    schools = School.objects.filter(is_active=True)
    report = [get_school_utilization_report(s) for s in schools]
    return render(request, 'dim/reports/school_utilization.html', {'report': report})
 
 
@login_required
def my_performance(request):
    """Student's personal performance view."""
    profile = _get_profile(request)
    if not profile:
        messages.error(request, "No profile found.")
        return redirect('userauths:sign-in')
    attempts = StudentAssessmentAttempt.objects.filter(
        student=profile, is_graded=True
    ).select_related('assessment__program').order_by('-submitted_at')
    enrollments = profile.enrollments.filter(is_active=True).select_related('program')
 
    attendance_by_program = {}
    for enr in enrollments:
        from .utils import get_student_attendance_rate
        attendance_by_program[enr.program] = get_student_attendance_rate(profile, enr.program)
 
    ctx = _learning_ctx(request)
    ctx.update({
        'profile': profile, 'attempts': attempts,
        'attendance_by_program': attendance_by_program,
    })
    return render(request, 'dim/reports/my_performance.html', ctx)


# ═══════════════════════════════════════════════════════════════════════════════
# TUITION MODULE — ADMIN MANAGEMENT
# ═══════════════════════════════════════════════════════════════════════════════

@login_required
def tuition_program_list(request):
    user = request.user
    is_school_admin = (user.is_principal or user.is_deputy_principal or user.is_admin) and not (
        user.is_kiswate_admin or user.is_kiswate_user or user.is_superuser
    )
    if not (_is_kiswate_or_admin(user) or user.is_principal or user.is_deputy_principal):
        messages.error(request, "Access denied.")
        return redirect('userauths:sign-in')
    q = request.GET.get('q', '')
    programs = Program.objects.filter(is_tuition=True).select_related('subject', 'teacher__user').order_by('-created_at')
    if q:
        programs = programs.filter(Q(name__icontains=q) | Q(subject__name__icontains=q) | Q(teacher__user__first_name__icontains=q))
    paginator = Paginator(programs, 20)
    page_obj = paginator.get_page(request.GET.get('page'))
    teachers = UserProfile.objects.filter(role='teacher', vetting_status='approved')
    form = TuitionProgramForm()
    if is_school_admin:
        base_tpl = 'school/base.html'
    elif user.is_kiswate_admin or user.is_kiswate_user:
        base_tpl = 'Dashboard/base.html'
    else:
        base_tpl = _tuition_base_template(request)
    return render(request, 'dim/tuition/program_list.html', {
        'programs': page_obj, 'page_obj': page_obj, 'q': q,
        'form': form, 'teachers': teachers,
        'base_template': base_tpl,
        'is_school_admin': is_school_admin,
    })


@login_required
def tuition_program_create(request):
    if not _is_kiswate_or_admin(request.user):
        messages.error(request, "Access denied.")
        return redirect('userauths:sign-in')
    if request.method == 'POST':
        form = TuitionProgramForm(request.POST)
        if form.is_valid():
            program = form.save(commit=False)
            program.is_tuition = True
            program.school = None
            program.save()
            messages.success(request, f"Tuition program '{program.name}' created.")
            return redirect('kiswate_digital_app:tuition_program_list')
        messages.error(request, "Please correct the errors below.")
    return redirect('kiswate_digital_app:tuition_program_list')


@login_required
def tuition_program_edit(request, pk):
    if not _is_kiswate_or_admin(request.user):
        messages.error(request, "Access denied.")
        return redirect('userauths:sign-in')
    program = get_object_or_404(Program, pk=pk, is_tuition=True)
    if request.method == 'POST':
        form = TuitionProgramForm(request.POST, instance=program)
        if form.is_valid():
            form.save()
            messages.success(request, f"Program '{program.name}' updated.")
            return redirect('kiswate_digital_app:tuition_program_list')
        messages.error(request, "Please correct the errors.")
    return redirect('kiswate_digital_app:tuition_program_list')


@login_required
def tuition_program_delete(request, pk):
    if not _is_kiswate_or_admin(request.user):
        messages.error(request, "Access denied.")
        return redirect('userauths:sign-in')
    program = get_object_or_404(Program, pk=pk, is_tuition=True)
    if request.method == 'POST':
        program.is_active = False
        program.save(update_fields=['is_active'])
        messages.success(request, f"Program '{program.name}' deactivated.")
    return redirect('kiswate_digital_app:tuition_program_list')


@login_required
def tuition_assign_teacher(request, pk):
    """Admin assigns a teacher to a tuition program."""
    if not _is_kiswate_or_admin(request.user):
        messages.error(request, "Access denied.")
        return redirect('userauths:sign-in')
    program = get_object_or_404(Program, pk=pk, is_tuition=True)
    if request.method == 'POST':
        teacher_pk = request.POST.get('teacher')
        teacher = get_object_or_404(UserProfile, pk=teacher_pk, role='teacher', vetting_status='approved')
        program.teacher = teacher
        program.save(update_fields=['teacher'])
        messages.success(request, f"Teacher assigned to '{program.name}'.")
    return redirect('kiswate_digital_app:tuition_program_list')


# ═══════════════════════════════════════════════════════════════════════════════
# TUITION MODULE — PUBLIC BROWSE
# ═══════════════════════════════════════════════════════════════════════════════

def tuition_browse(request):
    """Public/student browse of available tuition programs."""
    q = request.GET.get('q', '')
    category = request.GET.get('category', '')
    level = request.GET.get('level', '')

    programs = Program.objects.filter(is_tuition=True, is_active=True).select_related('subject', 'teacher__user')
    if q:
        programs = programs.filter(
            Q(name__icontains=q) | Q(subject__name__icontains=q) | Q(description__icontains=q)
        )
    if category:
        programs = programs.filter(category=category)
    if level:
        programs = programs.filter(level=level)

    categories = Program.objects.filter(is_tuition=True, is_active=True).values_list('category', flat=True).distinct()
    levels = Program.objects.filter(is_tuition=True, is_active=True).values_list('level', flat=True).distinct()

    paginator = Paginator(programs, 12)
    page_obj = paginator.get_page(request.GET.get('page'))
    profile = _get_profile(request)
    portal_role = profile.role if profile and profile.role in ('teacher', 'student') else None
    # Give teacher priority over admin on this browse page
    buser = request.user
    if getattr(buser, 'is_kiswate_admin', False) or getattr(buser, 'is_kiswate_user', False):
        browse_base = 'Dashboard/base.html'
    elif getattr(buser, 'is_teacher', False):
        browse_base = 'school/teacher/base.html'
    else:
        browse_base = _tuition_base_template(request)
    return render(request, 'dim/tuition/browse.html', {
        'programs': page_obj, 'page_obj': page_obj,
        'q': q, 'category': category, 'level': level,
        'categories': [c for c in categories if c],
        'levels': [lv for lv in levels if lv],
        'portal_role': portal_role,
        'base_template': browse_base,
    })


def tuition_program_detail(request, pk):
    program = get_object_or_404(Program, pk=pk, is_tuition=True)
    profile = _get_profile(request)
    enrollment = None
    lessons = []
    upcoming_classes = []
    pending_assignments = []

    if profile and profile.role == 'student':
        enrollment = Enrollment.objects.filter(student=profile, program=program).first()
        if enrollment and enrollment.is_active:
            lessons = program.lessons.filter(is_published=True)
            upcoming_classes = VirtualClass.objects.filter(
                program=program, is_cancelled=False, scheduled_at__gte=timezone.now()
            ).order_by('scheduled_at')[:5]
            pending_assignments = Assignment.objects.filter(
                program=program, is_published=True, due_date__gte=timezone.now()
            ).order_by('due_date')[:5]

    # Teacher-first base template: teachers get teacher base even if also marked as admin
    user = request.user
    if getattr(user, 'is_kiswate_admin', False) or getattr(user, 'is_kiswate_user', False):
        base_tpl = 'Dashboard/base.html'
    elif getattr(user, 'is_teacher', False):
        base_tpl = 'school/teacher/base.html'
    elif getattr(user, 'is_principal', False) or getattr(user, 'is_deputy_principal', False) or getattr(user, 'is_admin', False):
        base_tpl = 'school/base.html'
    elif getattr(user, 'is_parent', False):
        base_tpl = 'school/parent/base.html'
    elif getattr(user, 'is_student', False):
        base_tpl = 'school/student/base.html'
    else:
        base_tpl = _tuition_base_template(request)

    portal_role = profile.role if profile and profile.role in ('teacher', 'student') else None
    return render(request, 'dim/tuition/program_detail.html', {
        'program': program, 'profile': profile,
        'enrollment': enrollment, 'lessons': lessons,
        'upcoming_classes': upcoming_classes, 'pending_assignments': pending_assignments,
        'portal_role': portal_role,
        'base_template': base_tpl,
    })


@login_required
def tuition_enroll(request, pk):
    """Enroll in a tuition program. Parents select a child; students enroll themselves."""
    program = get_object_or_404(Program, pk=pk, is_tuition=True, is_active=True)
    user = request.user

    # ── PARENT FLOW ──────────────────────────────────────────────────────────
    if getattr(user, 'is_parent', False):
        from school.models import Parent as SchoolParent
        try:
            parent_obj = SchoolParent.objects.get(user=user)
            school_students = list(parent_obj.children.select_related('user').all())
        except SchoolParent.DoesNotExist:
            parent_obj = None
            school_students = []

        child_emails = [s.user.email for s in school_students]
        tuition_profiles = list(
            UserProfile.objects.filter(user__email__in=child_emails, role='student', vetting_status='approved')
        )

        if request.method == 'POST':
            student_pk = request.POST.get('student_pk')
            child_profile = get_object_or_404(UserProfile, pk=student_pk, role='student')
            allowed = parent_obj and parent_obj.children.filter(user=child_profile.user).exists()
            if not allowed:
                messages.error(request, "You are not authorised to enroll this student.")
            elif Enrollment.objects.filter(student=child_profile, program=program).exists():
                messages.info(request, f"{child_profile.full_name} is already enrolled in {program.name}.")
            else:
                Enrollment.objects.create(student=child_profile, program=program, is_active=True)
                messages.success(request, f"Enrolled {child_profile.full_name} in {program.name}.")
            return redirect('kiswate_digital_app:parent_tuition_view')

        return render(request, 'dim/tuition/program_detail.html', {
            'program': program,
            'enrolling': True,
            'parent_enroll': True,
            'tuition_profiles': tuition_profiles,
            'portal_role': 'parent',
            'base_template': _tuition_base_template(request),
        })

    # ── STUDENT FLOW ─────────────────────────────────────────────────────────
    profile = _get_profile(request)

    if not profile or profile.role != 'student':
        messages.warning(request, "Register as a tuition student first to enroll in programs.")
        return redirect('kiswate_digital_app:student_register')

    if profile.vetting_status != 'approved':
        messages.warning(request, "Your profile is pending approval. Enroll once approved.")
        return redirect('kiswate_digital_app:student_tuition_dashboard')

    if Enrollment.objects.filter(student=profile, program=program).exists():
        messages.info(request, "You are already enrolled in this program.")
        return redirect('kiswate_digital_app:tuition_program_detail', pk=pk)

    if request.method == 'POST':
        enrollment = Enrollment.objects.create(student=profile, program=program)
        if program.price > 0:
            pay_form = TuitionPaymentForm(request.POST)
            if pay_form.is_valid():
                payment = pay_form.save(commit=False)
                payment.enrollment = enrollment
                payment.amount = program.price
                payment.save()
        messages.success(request, f"Enrolled in '{program.name}'! Check your tuition dashboard.")
        return redirect('kiswate_digital_app:student_tuition_dashboard')

    pay_form = TuitionPaymentForm() if program.price > 0 else None
    return render(request, 'dim/tuition/program_detail.html', {
        'program': program, 'profile': profile,
        'enrolling': True, 'pay_form': pay_form,
        'portal_role': 'student',
        'base_template': _tuition_base_template(request),
    })


# ═══════════════════════════════════════════════════════════════════════════════
# TUITION MODULE — TEACHER PORTAL
# ═══════════════════════════════════════════════════════════════════════════════

@login_required
def teacher_tuition_dashboard(request):
    profile = _get_profile(request)
    # Always use teacher base for this page regardless of admin flags
    user = request.user
    if getattr(user, 'is_kiswate_admin', False) or getattr(user, 'is_kiswate_user', False):
        base_tpl = 'Dashboard/base.html'
    elif getattr(user, 'is_teacher', False):
        base_tpl = 'school/teacher/base.html'
    else:
        base_tpl = _tuition_base_template(request)

    if not profile or profile.role != 'teacher':
        return render(request, 'dim/tuition/teacher_dashboard.html', {
            'not_registered': True, 'portal_role': 'teacher',
            'base_template': base_tpl,
        })

    programs = Program.objects.filter(teacher=profile, is_tuition=True, is_active=True)
    # Lessons assigned to this teacher by admin (via Lesson.teacher FK)
    my_lessons = Lesson.objects.filter(teacher=profile).select_related('program__subject').order_by('program__name', 'order', 'title')
    upcoming_classes = VirtualClass.objects.filter(
        program__in=programs, is_cancelled=False, scheduled_at__gte=timezone.now()
    ).select_related('program').order_by('scheduled_at')[:5]
    pending_grading = AssignmentSubmission.objects.filter(
        assignment__program__in=programs, marks_obtained__isnull=True
    ).count()
    total_students = Enrollment.objects.filter(program__in=programs, is_active=True).count()
    recent_submissions = AssignmentSubmission.objects.filter(
        assignment__program__in=programs
    ).select_related('student__user', 'assignment').order_by('-submitted_at')[:5]

    return render(request, 'dim/tuition/teacher_dashboard.html', {
        'profile': profile,
        'programs': programs,
        'my_lessons': my_lessons,
        'upcoming_classes': upcoming_classes,
        'pending_grading': pending_grading,
        'total_students': total_students,
        'recent_submissions': recent_submissions,
        'portal_role': 'teacher',
        'base_template': base_tpl,
    })


@login_required
def teacher_program_create(request):
    """Create a tuition program. Accessible by principals, deputies, school admins, and kiswate admins."""
    user = request.user
    is_school_admin = (
        getattr(user, 'is_kiswate_admin', False) or getattr(user, 'is_kiswate_user', False) or
        getattr(user, 'is_principal', False) or getattr(user, 'is_deputy_principal', False) or
        getattr(user, 'is_admin', False)
    )
    if not is_school_admin:
        messages.error(request, "Access denied. Only school administrators can create DIL programs.")
        return redirect('kiswate_digital_app:tuition_browse')

    if request.method == 'POST':
        form = TuitionProgramForm(request.POST)
        if form.is_valid():
            program = form.save(commit=False)
            program.is_tuition = True
            program.school = None
            program.save()
            messages.success(request, f"Program '{program.name}' created successfully.")
            return redirect('kiswate_digital_app:tuition_program_list')
    else:
        form = TuitionProgramForm()

    if getattr(user, 'is_kiswate_admin', False) or getattr(user, 'is_kiswate_user', False):
        base_tpl = 'Dashboard/base.html'
    else:
        base_tpl = 'school/base.html'

    return render(request, 'dim/tuition/program_form.html', {
        'form': form, 'action': 'Create', 'for_teacher': False,
        'base_template': base_tpl,
    })


@login_required
def teacher_program_edit(request, pk):
    profile = _get_profile(request)
    if not profile or profile.role != 'teacher':
        messages.error(request, "Access denied.")
        return redirect('kiswate_digital_app:teacher_tuition_dashboard')
    program = get_object_or_404(Program, pk=pk, teacher=profile, is_tuition=True)
    if request.method == 'POST':
        form = TuitionProgramForm(request.POST, instance=program, teacher_locked=profile)
        if form.is_valid():
            form.save()
            messages.success(request, "Program updated.")
            return redirect('kiswate_digital_app:teacher_tuition_dashboard')
    else:
        form = TuitionProgramForm(instance=program, teacher_locked=profile)
    return render(request, 'dim/tuition/program_form.html', {
        'form': form, 'action': 'Edit', 'program': program, 'for_teacher': True, 'portal_role': 'teacher',
        'base_template': _tuition_base_template(request),
    })


# ═══════════════════════════════════════════════════════════════════════════════
# TUITION MODULE — STUDENT PORTAL
# ═══════════════════════════════════════════════════════════════════════════════

@login_required
def student_tuition_dashboard(request):
    profile = _get_profile(request)
    if not profile or profile.role != 'student':
        # Auto-create an approved tuition profile for school students
        if getattr(request.user, 'is_student', False):
            profile, _ = UserProfile.objects.get_or_create(
                user=request.user,
                defaults={
                    'role': 'student',
                    'phone': getattr(request.user, 'phone_number', '') or '',
                    'vetting_status': 'approved',
                },
            )
        else:
            return render(request, 'dim/tuition/student_dashboard.html', {
                'not_registered': True, 'portal_role': 'student',
                'base_template': _tuition_base_template(request),
            })

    enrollments = profile.enrollments.filter(
        is_active=True, program__is_tuition=True
    ).select_related('program__subject', 'program__teacher__user')

    enrolled_pks = enrollments.values_list('program_id', flat=True)
    pending_assignments = Assignment.objects.filter(
        program_id__in=enrolled_pks, is_published=True, due_date__gte=timezone.now()
    ).order_by('due_date')[:5]
    upcoming_classes = VirtualClass.objects.filter(
        program_id__in=enrolled_pks, is_cancelled=False, scheduled_at__gte=timezone.now()
    ).order_by('scheduled_at')[:5]
    open_assessments = Assessment.objects.filter(
        program_id__in=enrolled_pks, is_published=True
    ).exclude(attempts__student=profile).order_by('-created_at')[:5]
    guardians = profile.guardians.all()
    notifications = profile.notifications.order_by('-created_at')[:5]

    return render(request, 'dim/tuition/student_dashboard.html', {
        'profile': profile,
        'enrollments': enrollments,
        'pending_assignments': pending_assignments,
        'upcoming_classes': upcoming_classes,
        'open_assessments': open_assessments,
        'guardians': guardians,
        'notifications': notifications,
        'portal_role': 'student',
        'base_template': _tuition_base_template(request),
    })


@login_required
def student_add_guardian_self(request):
    """Student adds their own guardian/payment contact."""
    profile = _get_profile(request)
    if not profile or profile.role != 'student':
        messages.error(request, "Student profile required.")
        return redirect('kiswate_digital_app:student_tuition_dashboard')
    if request.method == 'POST':
        form = GuardianForm(request.POST)
        if form.is_valid():
            g = form.save(commit=False)
            g.student = profile
            g.save()
            messages.success(request, "Guardian/contact added successfully.")
            return redirect('kiswate_digital_app:student_tuition_dashboard')
    else:
        form = GuardianForm()
    return render(request, 'dim/tuition/guardian_form.html', {
        'form': form, 'student': profile, 'portal_role': 'student',
        'base_template': _tuition_base_template(request),
    })


# ═══════════════════════════════════════════════════════════════════════════════
# TUITION MODULE — PARENT PORTAL
# ═══════════════════════════════════════════════════════════════════════════════

@login_required
@login_required
def parent_tuition_view(request):
    """Parent DIL dashboard — overview of children's programs, payments, assignments, assessments, notifications."""
    from school.models import Parent
    try:
        parent_obj = Parent.objects.get(user=request.user)
        school_students = list(parent_obj.children.select_related('user').all())
    except Parent.DoesNotExist:
        parent_obj = None
        school_students = []

    # Find DIL profiles for school children (match by email)
    student_emails = [s.user.email for s in school_students]
    tuition_profiles = list(
        UserProfile.objects.filter(user__email__in=student_emails, role='student')
        .prefetch_related(
            'enrollments__program__subject',
            'enrollments__program__teacher__user',
            'enrollments__payment',
            'guardians',
        )
    ) if student_emails else []

    # Guardian-based links (parent's own email/phone is listed as guardian)
    guardian_links = list(
        Guardian.objects.filter(
            Q(email=request.user.email) | Q(phone=getattr(request.user, 'phone_number', ''))
        ).select_related('student__user')
    ) if request.user.email else []

    # Collect enrolled program PKs across all children
    all_student_profiles = list(tuition_profiles) + [g.student for g in guardian_links]
    enrolled_program_pks = []
    for tp in all_student_profiles:
        enrolled_program_pks += list(tp.enrollments.values_list('program_id', flat=True))
    enrolled_program_pks = list(set(enrolled_program_pks))

    # Assignments across enrolled programs (upcoming, not yet due)
    upcoming_assignments = (
        Assignment.objects.filter(
            program_id__in=enrolled_program_pks, is_published=True
        ).select_related('program').order_by('due_date')[:10]
    )

    # Assessments across enrolled programs
    open_assessments = (
        Assessment.objects.filter(
            program_id__in=enrolled_program_pks, is_published=True
        ).select_related('program').order_by('-created_at')[:10]
    )

    # Upcoming live classes
    upcoming_classes = (
        VirtualClass.objects.filter(
            program_id__in=enrolled_program_pks,
            is_cancelled=False,
            scheduled_at__gte=timezone.now(),
        ).select_related('program', 'teacher__user').order_by('scheduled_at')[:8]
    )

    # Notifications for children's DIL profiles
    child_profile_pks = [tp.pk for tp in all_student_profiles]
    notifications = (
        NotificationLog.objects.filter(recipient_id__in=child_profile_pks)
        .select_related('recipient').order_by('-created_at')[:10]
    )

    # KPIs
    total_enrolled = sum(
        tp.enrollments.filter(is_active=True, program__is_tuition=True).count()
        for tp in tuition_profiles
    )
    unpaid_count = 0
    for tp in tuition_profiles:
        for enr in tp.enrollments.filter(is_active=True, program__is_tuition=True):
            if enr.program.price and enr.program.price > 0:
                try:
                    if enr.payment.status != 'paid':
                        unpaid_count += 1
                except TuitionPayment.DoesNotExist:
                    unpaid_count += 1

    # Available programs to enroll children into (not already enrolled)
    available_programs = Program.objects.filter(is_tuition=True, is_active=True).select_related('subject', 'teacher__user').order_by('name')

    return render(request, 'dim/tuition/parent_view.html', {
        'tuition_profiles': tuition_profiles,
        'parent_obj': parent_obj,
        'guardian_links': guardian_links,
        'school_students': school_students,
        'upcoming_assignments': upcoming_assignments,
        'open_assessments': open_assessments,
        'upcoming_classes': upcoming_classes,
        'notifications': notifications,
        'available_programs': available_programs,
        'total_enrolled': total_enrolled,
        'unpaid_count': unpaid_count,
        'upcoming_class_count': upcoming_classes.count(),
        'assignment_count': upcoming_assignments.count(),
        'now': timezone.now(),
        'portal_role': 'parent',
        'base_template': _tuition_base_template(request),
    })


@login_required
def parent_enroll_child(request):
    """Parent enrolls one of their children into a DIL program."""
    if request.method != 'POST':
        return redirect('kiswate_digital_app:parent_tuition_view')

    program_pk = request.POST.get('program_pk')
    student_pk = request.POST.get('student_pk')

    program = get_object_or_404(Program, pk=program_pk, is_tuition=True, is_active=True)

    # Verify the student belongs to this parent
    from school.models import Parent
    try:
        parent_obj = Parent.objects.get(user=request.user)
    except Parent.DoesNotExist:
        parent_obj = None

    # Resolve the DIL UserProfile
    profile = get_object_or_404(UserProfile, pk=student_pk, role='student')

    # Ensure the parent is linked (school children or guardian link)
    allowed = False
    if parent_obj:
        allowed = parent_obj.children.filter(user=profile.user).exists()
    if not allowed:
        allowed = Guardian.objects.filter(
            student=profile,
            email=request.user.email,
        ).exists()
    if not allowed:
        messages.error(request, "You are not authorized to enroll this student.")
        return redirect('kiswate_digital_app:parent_tuition_view')

    if Enrollment.objects.filter(student=profile, program=program).exists():
        messages.info(request, f"{profile.full_name} is already enrolled in {program.name}.")
    else:
        Enrollment.objects.create(student=profile, program=program, is_active=True)
        messages.success(request, f"Enrolled {profile.full_name} in {program.name} successfully.")

    return redirect('kiswate_digital_app:parent_tuition_view')


@login_required
def parent_stk_push(request, enrollment_pk):
    """Parent pays for a child's DIL enrollment via M-Pesa STK push."""
    from .mpesa import initiate_stk_push

    if request.method != 'POST':
        return redirect('kiswate_digital_app:parent_tuition_view')

    enrollment = get_object_or_404(Enrollment, pk=enrollment_pk)

    # Verify parent link
    from school.models import Parent
    allowed = False
    try:
        parent_obj = Parent.objects.get(user=request.user)
        allowed = parent_obj.children.filter(user=enrollment.student.user).exists()
    except Parent.DoesNotExist:
        pass
    if not allowed:
        allowed = Guardian.objects.filter(
            student=enrollment.student, email=request.user.email
        ).exists()
    if not allowed:
        messages.error(request, "Access denied.")
        return redirect('kiswate_digital_app:parent_tuition_view')

    phone = request.POST.get('phone', '').strip() or getattr(request.user, 'phone_number', '') or ''
    if not phone:
        messages.error(request, "Please provide a phone number for the STK push.")
        return redirect('kiswate_digital_app:parent_tuition_view')

    amount = int(enrollment.program.price)
    if amount <= 0:
        messages.info(request, "This program is free.")
        return redirect('kiswate_digital_app:parent_tuition_view')

    result = initiate_stk_push(
        phone=phone,
        amount=amount,
        account_ref=f"DIL{enrollment.pk}",
        description="DIL Fee",
    )

    payment, _ = TuitionPayment.objects.get_or_create(
        enrollment=enrollment,
        defaults={
            'amount': enrollment.program.price,
            'payment_method': 'mpesa',
            'status': 'pending',
            'payer_phone': phone,
        },
    )
    payment.payer_phone = phone
    payment.payment_method = 'mpesa'

    if result['success']:
        payment.transaction_id = result.get('checkout_request_id', '')
        payment.status = 'pending'
        payment.save(update_fields=['payer_phone', 'payment_method', 'transaction_id', 'status'])
        if result.get('test_mode'):
            messages.info(request, f"TEST MODE: STK push simulated for {phone}. Ref: {payment.transaction_id}")
        else:
            messages.success(request, f"STK push sent to {phone}. Approve the prompt on your phone.")
    else:
        payment.save(update_fields=['payer_phone', 'payment_method'])
        messages.error(request, f"STK push failed: {result.get('message', 'Please try again.')}")

    return redirect('kiswate_digital_app:parent_tuition_view')


def _is_kiswate_admin_only(user):
    return user.is_superuser or getattr(user, 'is_kiswate_admin', False) or getattr(user, 'is_kiswate_user', False)


# ═══════════════════════════════════════════════════════════════════════════════
# GLOBAL SUBJECT MANAGEMENT (Kiswate Admin only)
# ═══════════════════════════════════════════════════════════════════════════════

@login_required
def subject_list(request):
    """Kiswate admin: view, create, and manage global subject catalog."""
    if not _is_kiswate_admin_only(request.user):
        messages.error(request, "Access denied. This area is restricted to Kiswate administrators.")
        return redirect('userauths:sign-in')

    q = request.GET.get('q', '')
    subjects = SubjectCatalog.objects.filter(is_active=True).order_by('name')
    if q:
        subjects = subjects.filter(Q(name__icontains=q) | Q(code__icontains=q))

    total = subjects.count()
    paginator = Paginator(subjects, 25)
    page_obj = paginator.get_page(request.GET.get('page'))
    form = SubjectCatalogForm()
    return render(request, 'dim/subjects/subject_list.html', {
        'subjects': page_obj, 'page_obj': page_obj, 'q': q, 'form': form, 'total': total,
    })


@login_required
def subject_create(request):
    if not _is_kiswate_admin_only(request.user):
        messages.error(request, "Access denied.")
        return redirect('userauths:sign-in')
    if request.method == 'POST':
        form = SubjectCatalogForm(request.POST)
        if form.is_valid():
            s = form.save()
            messages.success(request, f"Subject '{s.name}' created.")
        else:
            messages.error(request, f"Error: {form.errors.as_text()}")
    return redirect('kiswate_digital_app:subject_list')


@login_required
def subject_edit(request, pk):
    if not _is_kiswate_admin_only(request.user):
        messages.error(request, "Access denied.")
        return redirect('userauths:sign-in')
    subj = get_object_or_404(SubjectCatalog, pk=pk)
    if request.method == 'POST':
        form = SubjectCatalogForm(request.POST, instance=subj)
        if form.is_valid():
            form.save()
            messages.success(request, f"Subject '{subj.name}' updated.")
        else:
            messages.error(request, f"Error: {form.errors.as_text()}")
    return redirect('kiswate_digital_app:subject_list')


@login_required
def subject_delete(request, pk):
    if not _is_kiswate_admin_only(request.user):
        messages.error(request, "Access denied.")
        return redirect('userauths:sign-in')
    subj = get_object_or_404(SubjectCatalog, pk=pk)
    if request.method == 'POST':
        name = subj.name
        subj.is_active = False
        subj.save(update_fields=['is_active'])
        messages.success(request, f"Subject '{name}' deactivated from catalog.")
    return redirect('kiswate_digital_app:subject_list')


@login_required
def subject_bulk_upload(request):
    """Bulk upload subjects from CSV or Excel. Required columns: name, code. Optional: description."""
    if not _is_kiswate_admin_only(request.user):
        messages.error(request, "Access denied.")
        return redirect('userauths:sign-in')

    if request.method != 'POST':
        return redirect('kiswate_digital_app:subject_list')

    file = request.FILES.get('file')
    if not file:
        messages.error(request, "No file uploaded.")
        return redirect('kiswate_digital_app:subject_list')

    if file.size > 10 * 1024 * 1024:
        messages.error(request, "File too large (max 10 MB).")
        return redirect('kiswate_digital_app:subject_list')

    try:
        import pandas as pd
        fname = file.name.lower()
        if fname.endswith('.csv'):
            df = pd.read_csv(file)
        elif fname.endswith(('.xlsx', '.xls')):
            df = pd.read_excel(file)
        else:
            messages.error(request, "Unsupported format. Upload a .csv or .xlsx file.")
            return redirect('kiswate_digital_app:subject_list')

        df.columns = [c.lower().strip() for c in df.columns]
        if not {'name', 'code'}.issubset(set(df.columns)):
            messages.error(request, "File must have 'name' and 'code' columns.")
            return redirect('kiswate_digital_app:subject_list')

        created = updated = skipped = 0
        row_errors = []

        for i, row in df.iterrows():
            name = str(row.get('name', '')).strip()
            code = str(row.get('code', '')).strip().upper()
            desc_val = row.get('description')
            description = str(desc_val).strip() if 'description' in df.columns and pd.notna(desc_val) else ''

            if not name or not code or code == 'NAN':
                row_errors.append(f"Row {i + 2}: 'name' and 'code' required — skipped.")
                skipped += 1
                continue

            obj, is_new = SubjectCatalog.objects.update_or_create(
                code=code,
                defaults={'name': name, 'description': description, 'is_active': True},
            )
            if is_new:
                created += 1
            else:
                updated += 1

        messages.success(request, f"Upload complete: {created} created, {updated} updated, {skipped} skipped.")
        if row_errors:
            messages.warning(request, " · ".join(row_errors[:10]))

    except Exception as exc:
        messages.error(request, f"Upload failed: {exc}")

    return redirect('kiswate_digital_app:subject_list')


# ═══════════════════════════════════════════════════════════════════════════════
# PRINCIPAL / DEPUTY — TUITION ENROLLMENT
# ═══════════════════════════════════════════════════════════════════════════════

@login_required
def principal_enroll_tuition(request):
    """Principal or deputy principal enrolls school students in tuition programs."""
    if not (request.user.is_principal or request.user.is_deputy_principal or request.user.is_admin):
        messages.error(request, "Access denied. Principal or Deputy Principal role required.")
        return redirect('school:dashboard')

    try:
        school = request.user.staffprofile.school
    except Exception:
        messages.error(request, "Staff profile not found. Contact your administrator.")
        return redirect('school:dashboard')

    from school.models import Student as SchoolStudent

    from school.models import Grade as SchoolGrade, Streams as SchoolStream

    def _enroll_students(students_qs, program, school):
        enrolled_count = 0
        skipped_count = 0
        for school_student in students_qs:
            profile, created = UserProfile.objects.get_or_create(
                user=school_student.user,
                defaults={
                    'role': 'student',
                    'phone': getattr(school_student.user, 'phone_number', '') or '',
                    'vetting_status': 'approved',
                    'vetted_by': request.user,
                    'vetted_at': timezone.now(),
                    'school': school,
                },
            )
            # Always ensure school FK is set (may be missing on pre-existing profiles)
            update_fields = []
            if profile.school_id != school.pk:
                profile.school = school
                update_fields.append('school')
            if not created and profile.role == 'student' and profile.vetting_status == 'pending':
                profile.vetting_status = 'approved'
                profile.vetted_by = request.user
                profile.vetted_at = timezone.now()
                update_fields += ['vetting_status', 'vetted_by', 'vetted_at']
            if update_fields:
                profile.save(update_fields=update_fields)
            if not created and profile.role != 'student':
                skipped_count += 1
                continue
            if Enrollment.objects.filter(student=profile, program=program).exists():
                skipped_count += 1
                continue
            enrollment = Enrollment.objects.create(student=profile, program=program)
            if program.price > 0:
                TuitionPayment.objects.create(
                    enrollment=enrollment,
                    amount=program.price,
                    payment_method='school',
                    status='paid',
                    paid_at=timezone.now(),
                    notes=f"Enrolled and paid by {school.name} on behalf of student.",
                )
            enrolled_count += 1
        return enrolled_count, skipped_count

    if request.method == 'POST':
        form = PrincipalTuitionEnrollForm(request.POST, school=school)
        if form.is_valid():
            mode = form.cleaned_data['enroll_mode']
            program = form.cleaned_data['program']

            if mode == 'grade':
                grade = form.cleaned_data['grade']
                students_qs = SchoolStudent.objects.filter(school=school, is_active=True, grade_level=grade).select_related('user')
                label = f"grade {grade.name}"
            elif mode == 'stream':
                stream = form.cleaned_data['stream']
                students_qs = SchoolStudent.objects.filter(school=school, is_active=True, stream=stream).select_related('user')
                label = f"stream {stream.name}"
            else:
                students_qs = form.cleaned_data['students']
                label = "selected students"

            enrolled_count, skipped_count = _enroll_students(students_qs, program, school)

            if enrolled_count:
                messages.success(request, f"{enrolled_count} student(s) from {label} enrolled in '{program.name}'."
                                 + (f" {skipped_count} skipped (already enrolled or profile conflict)." if skipped_count else ""))
            else:
                messages.warning(request, f"No new enrollments from {label}. All students may already be enrolled or have profile conflicts.")
            return redirect('kiswate_digital_app:principal_enroll_tuition')
    else:
        form = PrincipalTuitionEnrollForm(school=school)

    school_student_users = SchoolStudent.objects.filter(school=school).values_list('user_id', flat=True)
    recent_enrollments = Enrollment.objects.filter(
        student__user_id__in=school_student_users,
        program__is_tuition=True,
    ).select_related('student__user', 'program__subject', 'payment').order_by('-enrolled_at')[:20]

    programs = Program.objects.filter(is_tuition=True, is_active=True).select_related('subject', 'teacher__user')
    grades = SchoolGrade.objects.filter(school=school, is_active=True).order_by('name')
    streams = SchoolStream.objects.filter(school=school, is_active=True).select_related('grade').order_by('grade__name', 'name')

    return render(request, 'school/tuition_enroll.html', {
        'form': form,
        'school': school,
        'programs': programs,
        'recent_enrollments': recent_enrollments,
        'grades': grades,
        'streams': streams,
    })


# ═══════════════════════════════════════════════════════════════════════════════
# SYSTEM USERS MANAGEMENT (Kiswate Admin)
# ═══════════════════════════════════════════════════════════════════════════════

@login_required
def system_users(request):
    """Kiswate admin: list and manage all system users."""
    if not _is_kiswate_admin_only(request.user):
        messages.error(request, "Access denied.")
        return redirect('userauths:sign-in')

    q = request.GET.get('q', '')
    role_filter = request.GET.get('role', '')
    active_filter = request.GET.get('active', '')

    users = User.objects.order_by('-date_joined')
    if q:
        users = users.filter(
            Q(first_name__icontains=q) | Q(last_name__icontains=q) |
            Q(email__icontains=q) | Q(phone_number__icontains=q)
        )
    role_map = {
        'kiswate_admin': 'is_kiswate_admin',
        'kiswate_user': 'is_kiswate_user',
        'admin': 'is_admin',
        'teacher': 'is_teacher',
        'student': 'is_student',
        'parent': 'is_parent',
        'principal': 'is_principal',
        'deputy': 'is_deputy_principal',
    }
    if role_filter and role_filter in role_map:
        users = users.filter(**{role_map[role_filter]: True})
    if active_filter == '1':
        users = users.filter(is_active=True)
    elif active_filter == '0':
        users = users.filter(is_active=False)

    paginator = Paginator(users, 25)
    page_obj = paginator.get_page(request.GET.get('page'))
    return render(request, 'Dashboard/system_users.html', {
        'users': page_obj, 'page_obj': page_obj,
        'q': q, 'role_filter': role_filter, 'active_filter': active_filter,
    })


@login_required
def system_user_edit(request, pk):
    """Kiswate admin: edit a system user and optionally change their password."""
    if not _is_kiswate_admin_only(request.user):
        messages.error(request, "Access denied.")
        return redirect('userauths:sign-in')
    target_user = get_object_or_404(User, pk=pk)

    if request.method == 'POST':
        action = request.POST.get('action', 'update')
        if action == 'change_password':
            new_pw = request.POST.get('new_password', '').strip()
            if len(new_pw) < 6:
                messages.error(request, "Password must be at least 6 characters.")
            else:
                target_user.set_password(new_pw)
                target_user.save(update_fields=['password'])
                messages.success(request, f"Password updated for {target_user.email}.")
        elif action == 'toggle_active':
            target_user.is_active = not target_user.is_active
            target_user.save(update_fields=['is_active'])
            status = 'activated' if target_user.is_active else 'deactivated'
            messages.success(request, f"User {status}.")
        else:
            target_user.first_name = request.POST.get('first_name', target_user.first_name)
            target_user.last_name = request.POST.get('last_name', target_user.last_name)
            target_user.phone_number = request.POST.get('phone_number', target_user.phone_number)
            target_user.is_kiswate_admin = 'is_kiswate_admin' in request.POST
            target_user.is_kiswate_user = 'is_kiswate_user' in request.POST
            target_user.is_admin = 'is_admin' in request.POST
            target_user.is_active = 'is_active' in request.POST
            target_user.save()
            messages.success(request, "User updated.")
        return redirect('kiswate_digital_app:system_user_edit', pk=pk)

    return render(request, 'Dashboard/system_user_edit.html', {'target_user': target_user})


# ─── TUITION PAYMENTS ────────────────────────────────────────────────────────

@login_required
def tuition_payment_list(request):
    """DIL payment list. Kiswate admins see all; school admins see their school's sponsored students."""
    user = request.user
    is_kiswate = _is_kiswate_admin_only(user)
    is_school_admin = (user.is_principal or user.is_deputy_principal or user.is_admin) and not is_kiswate

    if not (is_kiswate or is_school_admin):
        messages.error(request, "Access denied.")
        return redirect('school:dashboard')

    school = None
    if is_school_admin:
        try:
            school = user.staffprofile.school
        except Exception:
            messages.error(request, "Staff profile not found.")
            return redirect('school:dashboard')

    status_filter = request.GET.get('status', '')
    method_filter = request.GET.get('method', '')

    # ── School admin: query Enrollments (not Payments) so free-program enrollments
    #    also appear. Filter via SchoolStudent user IDs — reliable even if
    #    UserProfile.school was not set on older records.
    if is_school_admin:
        from school.models import Student as SchoolStudent
        from django.db.models import Sum, Count, OuterRef, Subquery

        school_user_ids = SchoolStudent.objects.filter(school=school).values_list('user_id', flat=True)

        enroll_qs = Enrollment.objects.filter(
            student__user_id__in=school_user_ids,
        ).select_related(
            'student__user', 'program__subject', 'payment',
        ).order_by('-enrolled_at')

        if status_filter:
            enroll_qs = enroll_qs.filter(payment__status=status_filter)
        if method_filter:
            enroll_qs = enroll_qs.filter(payment__payment_method=method_filter)

        # Summary stats over all school enrollments (unfiltered)
        all_payments = TuitionPayment.objects.filter(enrollment__student__user_id__in=school_user_ids)
        school_summary = all_payments.aggregate(
            total_sponsored=Sum('amount', filter=models.Q(payment_method='school')),
            count_sponsored=Count('pk', filter=models.Q(payment_method='school')),
            count_paid=Count('pk', filter=models.Q(status='paid')),
            count_pending=Count('pk', filter=models.Q(status='pending')),
        )
        school_summary['total_enrollments'] = school_user_ids.count()

        paginator = Paginator(enroll_qs, 25)
        page_obj = paginator.get_page(request.GET.get('page'))
        return render(request, 'dim/tuition/payment_list.html', {
            'page_obj': page_obj,
            'enrollments': page_obj,           # school admin uses this
            'status_filter': status_filter,
            'method_filter': method_filter,
            'status_choices': PAYMENT_STATUS_CHOICES,
            'method_choices': PAYMENT_METHOD_CHOICES,
            'base_template': 'school/base.html',
            'is_school_admin': True,
            'is_kiswate': False,
            'school': school,
            'school_summary': school_summary,
        })

    # ── Kiswate admin: all TuitionPayments ────────────────────────────────────
    qs = TuitionPayment.objects.select_related(
        'enrollment__student__user',
        'enrollment__student__school',
        'enrollment__program__subject',
    ).order_by('-created_at')

    if status_filter:
        qs = qs.filter(status=status_filter)
    if method_filter:
        qs = qs.filter(payment_method=method_filter)

    paginator = Paginator(qs, 25)
    page_obj = paginator.get_page(request.GET.get('page'))
    return render(request, 'dim/tuition/payment_list.html', {
        'page_obj': page_obj,
        'payments': page_obj,
        'status_filter': status_filter,
        'method_filter': method_filter,
        'status_choices': PAYMENT_STATUS_CHOICES,
        'method_choices': PAYMENT_METHOD_CHOICES,
        'base_template': _tuition_base_template(request),
        'is_school_admin': False,
        'is_kiswate': True,
        'school': None,
        'school_summary': None,
    })


@login_required
def tuition_payment_detail(request, pk):
    """Kiswate admin: view a single payment."""
    if not _is_kiswate_admin_only(request.user):
        messages.error(request, "Access denied.")
        return redirect('userauths:sign-in')
    payment = get_object_or_404(
        TuitionPayment.objects.select_related(
            'enrollment__student__user', 'enrollment__program__teacher__user'
        ), pk=pk
    )
    return render(request, 'dim/tuition/payment_detail.html', {'payment': payment})


@login_required
def tuition_payment_update(request, pk):
    """Kiswate admin: update payment status / details."""
    if not _is_kiswate_admin_only(request.user):
        messages.error(request, "Access denied.")
        return redirect('userauths:sign-in')
    if request.method != 'POST':
        return redirect('kiswate_digital_app:tuition_payment_detail', pk=pk)

    payment = get_object_or_404(TuitionPayment, pk=pk)
    payment.status = request.POST.get('status', payment.status)
    payment.payment_method = request.POST.get('payment_method', payment.payment_method)
    payment.transaction_id = request.POST.get('transaction_id', payment.transaction_id)
    payment.payer_phone = request.POST.get('payer_phone', payment.payer_phone)
    payment.notes = request.POST.get('notes', payment.notes)
    if payment.status == 'paid' and not payment.paid_at:
        payment.paid_at = timezone.now()
    payment.save()
    messages.success(request, "Payment record updated.")
    return redirect('kiswate_digital_app:tuition_payment_detail', pk=pk)


@login_required
def guardian_list(request):
    """Kiswate admin: list and manage all DIL guardians."""
    if not _is_kiswate_or_admin(request.user):
        messages.error(request, "Access denied.")
        return redirect('userauths:sign-in')

    q = request.GET.get('q', '')
    guardians = Guardian.objects.select_related('student__user').order_by('name')
    if q:
        guardians = guardians.filter(
            Q(name__icontains=q) | Q(email__icontains=q) |
            Q(phone__icontains=q) | Q(student__user__first_name__icontains=q) |
            Q(student__user__last_name__icontains=q)
        )

    paginator = Paginator(guardians, 25)
    page_obj = paginator.get_page(request.GET.get('page'))
    return render(request, 'dim/users/guardian_list.html', {
        'guardians': page_obj, 'page_obj': page_obj, 'q': q,
    })


@login_required
def guardian_edit(request, pk):
    """Kiswate admin: edit a guardian record."""
    if not _is_kiswate_or_admin(request.user):
        messages.error(request, "Access denied.")
        return redirect('userauths:sign-in')
    guardian = get_object_or_404(Guardian, pk=pk)
    if request.method == 'POST':
        form = GuardianForm(request.POST, instance=guardian)
        if form.is_valid():
            form.save()
            messages.success(request, "Guardian updated.")
            return redirect('kiswate_digital_app:guardian_list')
        messages.error(request, "Please correct the errors.")
    return redirect('kiswate_digital_app:guardian_list')


@login_required
def guardian_delete(request, pk):
    """Kiswate admin: delete a guardian record."""
    if not _is_kiswate_or_admin(request.user):
        messages.error(request, "Access denied.")
        return redirect('userauths:sign-in')
    guardian = get_object_or_404(Guardian, pk=pk)
    if request.method == 'POST':
        student_pk = guardian.student.pk
        guardian.delete()
        messages.success(request, "Guardian removed.")
        return redirect('kiswate_digital_app:guardian_list')
    return redirect('kiswate_digital_app:guardian_list')


@login_required
def tuition_stk_push(request, enrollment_pk):
    """
    Student initiates M-Pesa STK push for a DIL enrollment payment.
    POST params: phone (optional — falls back to user's phone).
    """
    from .mpesa import initiate_stk_push
    profile = _get_profile(request)
    if not profile or profile.role != 'student':
        messages.error(request, "Student profile required.")
        return redirect('kiswate_digital_app:student_payment_view')

    enrollment = get_object_or_404(Enrollment, pk=enrollment_pk, student=profile)

    if request.method != 'POST':
        return redirect('kiswate_digital_app:student_payment_view')

    phone = request.POST.get('phone', '').strip() or getattr(request.user, 'phone_number', '') or ''
    if not phone:
        messages.error(request, "Please provide a phone number to receive the STK push.")
        return redirect('kiswate_digital_app:student_payment_view')

    amount = int(enrollment.program.price)
    if amount <= 0:
        messages.info(request, "This program is free — no payment needed.")
        return redirect('kiswate_digital_app:student_payment_view')

    result = initiate_stk_push(
        phone=phone,
        amount=amount,
        account_ref=f"DIL{enrollment.pk}",
        description=f"DIL Fee",
    )

    # Upsert the payment record
    payment, _ = TuitionPayment.objects.get_or_create(
        enrollment=enrollment,
        defaults={
            'amount': enrollment.program.price,
            'payment_method': 'mpesa',
            'status': 'pending',
            'payer_phone': phone,
        },
    )
    payment.payer_phone = phone
    payment.payment_method = 'mpesa'

    if result['success']:
        payment.transaction_id = result.get('checkout_request_id', '')
        payment.status = 'pending'
        payment.save(update_fields=['payer_phone', 'payment_method', 'transaction_id', 'status'])
        if result.get('test_mode'):
            messages.info(request, f"TEST MODE: STK push simulated for {phone}. No real charge made. Transaction ref: {payment.transaction_id}")
        else:
            messages.success(request, f"STK push sent to {phone}. Approve the payment prompt on your phone. Ref: {payment.transaction_id}")
    else:
        payment.save(update_fields=['payer_phone', 'payment_method'])
        messages.error(request, f"STK push failed: {result.get('message', 'Please try again.')}")

    return redirect('kiswate_digital_app:student_payment_view')


@csrf_exempt_view
def tuition_mpesa_callback(request):
    """
    Safaricom Daraja STK push callback (must be publicly accessible).
    Set MPESA_CALLBACK_URL to point here.
    """
    import json as _json

    # ── Safaricom IP whitelist ────────────────────────────────────────────────
    # Safaricom production Daraja IPs. Update if Safaricom publishes new ranges.
    SAFARICOM_IPS = {
        '196.201.214.200', '196.201.214.206', '196.201.213.114',
        '196.201.214.207', '196.201.214.208', '196.201.213.44',
        '196.201.212.127', '196.201.212.138', '196.201.212.129',
        '196.201.212.136', '196.201.212.74',  '196.201.212.69',
    }
    # In sandbox mode allow all (useful for testing). In production enforce IP.
    from django.conf import settings as _s
    if not getattr(_s, 'DEBUG', True):
        forwarded = request.META.get('HTTP_X_FORWARDED_FOR', '')
        caller_ip = (forwarded.split(',')[0].strip()
                     if forwarded else request.META.get('REMOTE_ADDR', ''))
        if caller_ip not in SAFARICOM_IPS:
            logger.warning("M-Pesa callback rejected from IP: %s", caller_ip)
            return JsonResponse({'ResultCode': 1, 'ResultDesc': 'Rejected'}, status=403)

    try:
        data = _json.loads(request.body)
        stk = data.get('Body', {}).get('stkCallback', {})
        result_code = stk.get('ResultCode')
        checkout_id = stk.get('CheckoutRequestID', '').strip()

        if not checkout_id:
            return JsonResponse({'ResultCode': 0, 'ResultDesc': 'Accepted'})

        # Only update payments that are still PENDING — prevents replay attacks
        payment = TuitionPayment.objects.filter(
            transaction_id=checkout_id, status='pending'
        ).select_for_update().first()

        if not payment:
            # Log but always return 200 so Safaricom does not retry
            logger.info("M-Pesa callback: no pending payment for CheckoutRequestID %s", checkout_id)
            return JsonResponse({'ResultCode': 0, 'ResultDesc': 'Accepted'})

        if result_code == 0:
            items = stk.get('CallbackMetadata', {}).get('Item', [])
            receipt = next((i['Value'] for i in items if i.get('Name') == 'MpesaReceiptNumber'), '')
            # Use server-side expected amount — never trust callback amount for auth
            payment.status = 'paid'
            payment.paid_at = timezone.now()
            if receipt:
                payment.transaction_id = receipt
            payment.save(update_fields=['status', 'paid_at', 'transaction_id'])
        else:
            payment.status = 'failed'
            payment.notes = stk.get('ResultDesc', 'Payment declined or timed out.')
            payment.save(update_fields=['status', 'notes'])

    except Exception as exc:
        logger.error("M-Pesa callback error: %s", exc)

    return JsonResponse({'ResultCode': 0, 'ResultDesc': 'Accepted'})


@login_required
def student_payment_view(request):
    """Student: view their own enrolled programs and payment status."""
    profile = _get_profile(request)
    if not profile or profile.role != 'student':
        messages.error(request, "Student profile required.")
        return redirect('kiswate_digital_app:student_register')

    enrollments = Enrollment.objects.filter(
        student=profile, is_active=True
    ).select_related('program', 'program__teacher__user').prefetch_related('payment')

    # Attach payment to each enrollment (or None)
    enr_data = []
    for enr in enrollments:
        try:
            payment = enr.payment
        except TuitionPayment.DoesNotExist:
            payment = None
        enr_data.append({'enrollment': enr, 'payment': payment})

    return render(request, 'dim/tuition/student_payments.html', {
        'enr_data': enr_data,
        'portal_role': 'student',
        'base_template': _tuition_base_template(request),
        'profile': profile,
    })


# ── SCHOOL SUBSCRIPTIONS (Kiswate admin) ────────────────────────────────────

def _is_sub_admin(user):
    return user.is_superuser or user.is_admin or user.is_kiswate_admin or user.is_kiswate_user


@login_required
def school_subscription_list(request):
    if not _is_sub_admin(request.user):
        return redirect('kiswate_digital_app:kiswate_admin_dashboard')
    q = request.GET.get('q', '').strip()
    status = request.GET.get('status', '')
    subs = SchoolSubscription.objects.select_related('school', 'plan', 'managed_by').order_by('-created_at')
    if q:
        subs = subs.filter(Q(school__name__icontains=q) | Q(school__code__icontains=q))
    if status:
        subs = subs.filter(status=status)
    page = Paginator(subs, 20).get_page(request.GET.get('page'))
    form = SchoolSubscriptionForm()
    return render(request, 'Dashboard/school_subscription_list.html', {
        'subscriptions': page, 'q': q, 'status': status, 'form': form,
    })


@login_required
def school_subscription_update(request, pk):
    if not _is_sub_admin(request.user):
        return redirect('kiswate_digital_app:kiswate_admin_dashboard')
    sub = get_object_or_404(SchoolSubscription, pk=pk)
    if request.method == 'POST':
        form = SchoolSubscriptionForm(request.POST, instance=sub)
        if form.is_valid():
            form.save()
            messages.success(request, f'Subscription for {sub.school.name} updated.')
        else:
            messages.error(request, 'Please correct the form errors.')
    return redirect('kiswate_digital_app:school_subscription_list')


@login_required
def school_subscription_delete(request, pk):
    if not _is_sub_admin(request.user):
        return redirect('kiswate_digital_app:kiswate_admin_dashboard')
    sub = get_object_or_404(SchoolSubscription, pk=pk)
    if request.method == 'POST':
        sub.status = 'cancelled'
        sub.save(update_fields=['status'])
        messages.success(request, f'Subscription for {sub.school.name} cancelled.')
    return redirect('kiswate_digital_app:school_subscription_list')
