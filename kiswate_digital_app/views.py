# views.py (CRUD for School)
import logging
import secrets
from django.shortcuts import render, redirect, get_object_or_404
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
from school.models import School,Scholarship,SubscriptionPlan,ContactMessage, SchoolSubscription, StaffProfile, Student, Parent, Scholarship, County, City,Constituency,SubCounty,Ward
from userauths.models import User
from .forms import SchoolCreationForm, SchoolEditForm,AdminEditForm,ScholarshipForm,SubscriptionPlanForm, SchoolSubscriptionForm
from django.contrib.auth.hashers import make_password
from django.db import IntegrityError
from django.core.paginator import Paginator


from .models import (
    School, UserProfile, Guardian, Program, Enrollment,
    VirtualClass, ClassAttendance, Lesson, Assignment, AssignmentSubmission,
    Assessment, Question, Choice, StudentAssessmentAttempt, StudentAnswer,
    NotificationTemplate, NotificationLog,
)
from .forms import (
    StudentRegistrationForm, TeacherRegistrationForm, GuardianForm,
    VettingForm, EnrollmentForm,
    VirtualClassForm, RecordingUploadForm, AttendanceManualForm,
    LessonForm, AssignmentForm, SubmissionForm, GradeSubmissionForm,
    AssessmentForm, QuestionForm, ChoiceForm, ChoiceFormSet, PublishResultsForm,
    NotificationTemplateForm, BulkNotificationForm,
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
    if not (request.user.is_superuser or request.user.is_kiswate_user):
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
    if not (request.user.is_superuser or request.user.is_kiswate_user):
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
    if not (request.user.is_superuser or request.user.is_kiswate_user):
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
    if not (request.user.is_superuser or request.user.is_kiswate_user):
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


@login_required
def school_admin_list(request):
    # Superuser check
    if not (request.user.is_superuser or request.user.is_kiswate_user):
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
    if not (request.user.is_superuser or request.user.is_kiswate_user):
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
    if not (request.user.is_superuser or request.user.is_kiswate_user):
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
    if not (request.user.is_superuser or request.user.is_kiswate_user):
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
    if not (request.user.is_superuser or request.user.is_kiswate_user):
        return redirect('kiswate_digital_app:kiswate_admin_dashboard')
    return redirect('kiswate_digital_app:invoice_list')


@login_required
def payment_history(request):
    if not (request.user.is_superuser or request.user.is_kiswate_user):
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
    if not (request.user.is_superuser or request.user.is_kiswate_user):
        return redirect('kiswate_digital_app:kiswate_admin_dashboard')
    return redirect('kiswate_digital_app:reports_dashboard')


@login_required
def support(request):
    if not (request.user.is_superuser or request.user.is_kiswate_user):
        return redirect('kiswate_digital_app:kiswate_admin_dashboard')
    from school.models import ContactMessage
    messages_qs = ContactMessage.objects.order_by('-created_at')
    from django.core.paginator import Paginator
    page = Paginator(messages_qs, 20).get_page(request.GET.get('page'))
    return render(request, "Dashboard/support.html", {'contact_messages': page})


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
            return render(request, 'scholarship_list.html', {
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
    if not request.user.is_superuser:
        messages.error(request, "Access denied: Superuser privileges required.")
        return redirect('kiswate_digital_app:kiswate_admin_dashboard')

    """
    List all subscription plans.
    """
    plans = SubscriptionPlan.objects.all().order_by('name')
    can_edit = request.user.is_superuser
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
    if not (request.user.is_superuser or request.user.is_kiswate_user):
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
    if not (request.user.is_superuser or request.user.is_kiswate_user):
        messages.error(request, "Access denied: Admin privileges required.")
        return redirect('kiswate_digital_app:kiswate_admin_dashboard')
    
    demo_requests = ContactMessage.objects.all().order_by('-created_at')

    return render(request, "Dashboard/demo_request_list.html", {'demo_requests': demo_requests})



# Mark Verified
@login_required
def mark_verified(request, lead_id):
    if not (request.user.is_superuser or request.user.is_kiswate_user):
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
    if not (request.user.is_superuser or getattr(request.user, "is_kiswate_user", False)):
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
            is_kiswate_user=True,  # optional: if you want them to have Kiswate privileges
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
    except UserProfile.DoesNotExist:
        return None


def _is_kiswate_or_admin(user):
    return user.is_kiswate_admin or user.is_kiswate_user or user.is_admin


def _is_notification_admin(user):
    return user.is_kiswate_admin or user.is_admin or user.is_principal or user.is_deputy_principal


# ═══════════════════════════════════════════════════════════════════════════════
# MODULE 1: USER MANAGEMENT
# ═══════════════════════════════════════════════════════════════════════════════
 
def student_register(request):
    """Public registration for students."""
    if request.method == 'POST':
        form = StudentRegistrationForm(request.POST)
        if form.is_valid():
            profile = form.save()
            messages.success(request, "Registration submitted. Awaiting approval.")
            return redirect('kiswate_digital_app:student_register_done')
    else:
        form = StudentRegistrationForm()
    return render(request, 'dim/users/student_register.html', {'form': form})
 
 
def teacher_register(request):
    """Public registration for teachers."""
    if request.method == 'POST':
        form = TeacherRegistrationForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Registration submitted. Your profile will be vetted.")
            return redirect('kiswate_digital_app:teacher_register_done')
    else:
        form = TeacherRegistrationForm()
    return render(request, 'dim/users/teacher_register.html', {'form': form})
 
 
def register_done(request):
    return render(request, 'dim/users/register_done.html')
 
 
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
 
    return render(request, 'dim/virtual_learning/class_list.html', {
        'upcoming_classes': upcoming_qs[:20],
        'past_classes': past_qs[:20],
        'profile': profile,
    })
 
 
@login_required
def virtual_class_create(request):
    if not _is_kiswate_or_admin(request.user):
        messages.error(request, "Access denied.")
        return redirect('userauths:sign-in')
    profile = _get_profile(request)
    if request.method == 'POST':
        form = VirtualClassForm(request.POST, teacher_profile=profile)
        if form.is_valid():
            vc = form.save(commit=False)
            vc.teacher = profile
            vc.save()
            messages.success(request, "Class scheduled successfully.")
            return redirect('kiswate_digital_app:virtual_class_detail', pk=vc.pk)
    else:
        form = VirtualClassForm(teacher_profile=profile)
    return render(request, 'dim/virtual_learning/class_form.html',
                  {'form': form, 'action': 'Schedule'})
 
 
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
 
    return render(request, 'dim/virtual_learning/class_detail.html', {
        'vc': vc,
        'profile': profile,
        'attendance_summary': attendance_summary,
        'my_attendance': my_attendance,
        'attendance_records': attendance_records,
    })
 
 
@login_required
def virtual_class_edit(request, pk):
    if not _is_kiswate_or_admin(request.user):
        messages.error(request, "Access denied.")
        return redirect('userauths:sign-in')
    vc = get_object_or_404(VirtualClass, pk=pk)
    profile = _get_profile(request)
    if request.method == 'POST':
        form = VirtualClassForm(request.POST, instance=vc, teacher_profile=profile)
        if form.is_valid():
            form.save()
            messages.success(request, "Class updated.")
            return redirect('kiswate_digital_app:virtual_class_detail', pk=pk)
    else:
        form = VirtualClassForm(instance=vc, teacher_profile=profile)
    return render(request, 'dim/virtual_learning/class_form.html',
                  {'form': form, 'action': 'Edit', 'vc': vc})
 
 
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
    if not _is_kiswate_or_admin(request.user):
        messages.error(request, "Access denied.")
        return redirect('userauths:sign-in')
    vc = get_object_or_404(VirtualClass, pk=pk)
    if request.method == 'POST':
        form = AttendanceManualForm(request.POST, virtual_class=vc)
        if form.is_valid():
            present_students = form.cleaned_data['present_students']
            # Clear existing teacher-marked records, re-set
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
    return render(request, 'dim/virtual_learning/mark_attendance.html',
                  {'form': form, 'vc': vc})
 
 
@login_required
def upload_recording(request, pk):
    if not _is_kiswate_or_admin(request.user):
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
    return render(request, 'dim/virtual_learning/upload_recording.html',
                  {'form': form, 'vc': vc})
 
 
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
    return render(request, 'dim/virtual_learning/lesson_list.html', {'lessons': page_obj, 'page_obj': page_obj})
 
 
@login_required
def lesson_create(request):
    if not _is_kiswate_or_admin(request.user):
        messages.error(request, "Access denied.")
        return redirect('userauths:sign-in')
    profile = _get_profile(request)
    if request.method == 'POST':
        form = LessonForm(request.POST, request.FILES)
        if form.is_valid():
            lesson = form.save(commit=False)
            lesson.teacher = profile
            lesson.save()
            messages.success(request, "Lesson created.")
            return redirect('kiswate_digital_app:lesson_list')
    else:
        form = LessonForm()
    return render(request, 'dim/virtual_learning/lesson_form.html',
                  {'form': form, 'action': 'Create'})
 
 
@login_required
def lesson_detail(request, pk):
    lesson = get_object_or_404(Lesson, pk=pk)
    assignments = lesson.assignments.filter(is_published=True)
    return render(request, 'dim/virtual_learning/lesson_detail.html',
                  {'lesson': lesson, 'assignments': assignments})
 
 
@login_required
def lesson_edit(request, pk):
    if not _is_kiswate_or_admin(request.user):
        messages.error(request, "Access denied.")
        return redirect('userauths:sign-in')
    lesson = get_object_or_404(Lesson, pk=pk)
    if request.method == 'POST':
        form = LessonForm(request.POST, request.FILES, instance=lesson)
        if form.is_valid():
            form.save()
            messages.success(request, "Lesson updated.")
            return redirect('kiswate_digital_app:lesson_detail', pk=pk)
    else:
        form = LessonForm(instance=lesson)
    return render(request, 'dim/virtual_learning/lesson_form.html',
                  {'form': form, 'action': 'Edit', 'lesson': lesson})
 
 
@login_required
def assignment_list(request):
    profile = _get_profile(request)
    assignments = Assignment.objects.select_related('program', 'lesson').order_by('-due_date')
    if profile and profile.role == 'student':
        enrolled = profile.enrollments.filter(is_active=True).values_list('program_id', flat=True)
        assignments = assignments.filter(program_id__in=enrolled, is_published=True)
    paginator = Paginator(assignments, 20)
    page_obj = paginator.get_page(request.GET.get('page'))
    return render(request, 'dim/virtual_learning/assignment_list.html',
                  {'assignments': page_obj, 'page_obj': page_obj, 'profile': profile})
 
 
@login_required
def assignment_create(request):
    if not _is_kiswate_or_admin(request.user):
        messages.error(request, "Access denied.")
        return redirect('userauths:sign-in')
    if request.method == 'POST':
        form = AssignmentForm(request.POST, request.FILES)
        if form.is_valid():
            form.save()
            asgn = form.instance
            notify_assignment_due(asgn)
            messages.success(request, "Assignment created and students notified.")
            return redirect('kiswate_digital_app:assignment_list')
    else:
        form = AssignmentForm()
    return render(request, 'dim/virtual_learning/assignment_form.html',
                  {'form': form, 'action': 'Create'})
 
 
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
    return render(request, 'dim/virtual_learning/assignment_detail.html', {
        'assignment': assignment, 'profile': profile,
        'my_submission': my_submission, 'submissions': submissions,
    })
 
 
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
    return render(request, 'dim/virtual_learning/submit_assignment.html',
                  {'form': form, 'assignment': assignment})
 
 
@login_required
def grade_submission(request, pk):
    if not _is_kiswate_or_admin(request.user):
        messages.error(request, "Access denied.")
        return redirect('userauths:sign-in')
    submission = get_object_or_404(AssignmentSubmission, pk=pk)
    if request.method == 'POST':
        form = GradeSubmissionForm(request.POST, instance=submission)
        if form.is_valid():
            s = form.save(commit=False)
            s.graded_at = timezone.now()
            s.graded_by = _get_profile(request)
            s.save()
            messages.success(request, "Submission graded.")
            return redirect('kiswate_digital_app:assignment_detail', pk=submission.assignment.pk)
    else:
        form = GradeSubmissionForm(instance=submission)
    return render(request, 'dim/virtual_learning/grade_submission.html',
                  {'form': form, 'submission': submission})
 
 
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
    return render(request, 'dim/assessments/assessment_list.html',
                  {'assessments': page_obj, 'page_obj': page_obj, 'profile': profile})
 
 
@login_required
def assessment_create(request):
    if not _is_kiswate_or_admin(request.user):
        messages.error(request, "Access denied.")
        return redirect('userauths:sign-in')
    profile = _get_profile(request)
    if request.method == 'POST':
        form = AssessmentForm(request.POST)
        if form.is_valid():
            a = form.save(commit=False)
            a.created_by = profile
            a.save()
            messages.success(request, "Assessment created. Now add questions.")
            return redirect('kiswate_digital_app:assessment_questions', pk=a.pk)
    else:
        form = AssessmentForm()
    return render(request, 'dim/assessments/assessment_form.html',
                  {'form': form, 'action': 'Create'})
 
 
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
    return render(request, 'dim/assessments/assessment_detail.html', {
        'assessment': assessment, 'questions': questions,
        'my_attempt': my_attempt, 'results': results, 'profile': profile,
    })
 
 
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
 
    return render(request, 'dim/assessments/take_assessment.html',
                  {'assessment': assessment, 'questions': questions, 'attempt': attempt})
 
 
@login_required
def assessment_result(request, pk):
    attempt = get_object_or_404(StudentAssessmentAttempt, pk=pk)
    profile = _get_profile(request)
    if profile and attempt.student != profile and not _is_kiswate_or_admin(request.user):
        messages.error(request, "You can only view your own results.")
        return redirect('kiswate_digital_app:assessment_list')
    answers = attempt.answers.select_related('question', 'selected_choice').all()
    return render(request, 'dim/assessments/result.html',
                  {'attempt': attempt, 'answers': answers})
 
 
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
    if not _is_kiswate_or_admin(request.user):
        messages.error(request, "Access denied.")
        return redirect('userauths:sign-in')
    logs = NotificationLog.objects.select_related('recipient__user').order_by('-created_at')
    paginator = Paginator(logs, 20)
    page_obj = paginator.get_page(request.GET.get('page'))
    return render(request, 'dim/communication/notification_list.html', {'logs': page_obj, 'page_obj': page_obj})
 
 
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
 
    return render(request, 'dim/reports/my_performance.html', {
        'profile': profile, 'attempts': attempts,
        'attendance_by_program': attendance_by_program,
    })
 
