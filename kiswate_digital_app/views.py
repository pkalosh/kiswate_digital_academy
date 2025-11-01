# views.py (CRUD for School)
import logging
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required,permission_required
from django.contrib import messages
from django.contrib.messages.views import SuccessMessageMixin
from django.views.generic import ListView, CreateView, UpdateView, DeleteView
from django.urls import reverse_lazy
from django.http import JsonResponse
from django.utils import timezone
from django.db.models import Q
from decimal import Decimal
from django.urls import reverse
from django.conf import settings
from school.models import School,Scholarship,SubscriptionPlan, SchoolSubscription, StaffProfile, Student, Parent, Scholarship
from userauths.models import User
from .forms import SchoolCreationForm, SchoolEditForm,AdminEditForm,ScholarshipForm,SubscriptionPlanForm, SchoolSubscriptionForm

logger = logging.getLogger(__name__)

@login_required
def school_list(request):
    """
    List schools with search/filter.
    Handles creation via POST (from add modal).
    """
    if not request.user.is_superuser:
        messages.error(request, "Access denied: Superuser privileges required.")
        return redirect('dashboard')

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
    query = request.GET.get('q', '')
    schools = School.objects.filter(is_active=True).order_by('-created_at')
    if query:
        schools = schools.filter(
            Q(name__icontains=query) |
            Q(code__icontains=query) |
            Q(contact_email__icontains=query) |
            Q(school_admin__email__icontains=query)
        )

    context = {
        'schools': schools,
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
    if not request.user.is_superuser:
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
        return redirect('school:school_list')
    
    # For GET: Redirect to list
    messages.warning(request, "Use the delete button in the list to confirm.")
    return redirect('kiswate_digital_app:school_list')


@login_required
def new_school(request):
    """
    Direct create page (optional; modal preferred).
    """
    if not request.user.is_superuser:
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
def kiswate_dashboard(request):
    schools = School.objects.all().count()
    teachers = StaffProfile.objects.filter(position='teacher').count()
    students = Student.objects.all().count()
    parents = Parent.objects.all().count()
    scholarships = Scholarship.objects.all().count()
    
    return render(request, "Dashboard/kiswate_admin_dashboard.html", 
                  {
                      "schools":schools,
                      "teachers":teachers,
                      "students":students,
                      "parents":parents,
                      "scholarships":scholarships
                   }
                  )


@login_required
def school_admin_list(request):
    """
    List all school admins (via schools).
    Handles modal re-open on error via query param.
    """
    if not request.user.is_superuser:
        messages.error(request, "Access denied: Superuser privileges required.")
        return redirect('kiswate_digital_app:kiswate_admin_dashboard')

    # Check for error re-open
    edit_pk = request.GET.get('edit_pk')
    error = request.GET.get('error') == '1'

    query = request.GET.get('q', '')
    schools = School.objects.select_related('school_admin').order_by('-created_at')
    if query:
        schools = schools.filter(
            Q(school_admin__first_name__icontains=query) |
            Q(school_admin__last_name__icontains=query) |
            Q(school_admin__email__icontains=query) |
            Q(name__icontains=query)
        )

    # If error, fetch form for modal
    edit_form = None
    if edit_pk and error:
        school = get_object_or_404(School, pk=edit_pk)
        edit_form = AdminEditForm(instance=school.school_admin)
        messages.error(request, "Please correct the form errors below.")

    context = {
        'schools': schools,
        'query': query,
        'edit_pk': edit_pk,
        'edit_form': edit_form,  # Pass for modal errors
    }
    return render(request, "Dashboard/school_admin_list.html", context)


@login_required
def edit_school_admin(request, school_pk):
    """
    Edit school admin via modal POST.
    On error, redirect to list with params to re-open modal.
    """
    if not request.user.is_superuser:
        messages.error(request, "Access denied: Superuser privileges required.")
        return redirect('kiswate_digital_app:school_admin_list')

    school = get_object_or_404(School, pk=school_pk)
    admin = school.school_admin

    if request.method == 'POST':
        form = AdminEditForm(request.POST, instance=admin)
        logger.info(f"POST data for admin {admin.email}: {request.POST}")  # Debug log
        if form.is_valid():
            form.save()
            messages.success(
                request,
                f'Successfully updated admin "{admin.get_full_name()}" for {school.name}. '
                f'Email sent: {"Yes" if form.cleaned_data["send_email"] else "No"}. '
                f'Password reset: {"Yes" if form.cleaned_data["reset_password"] else "No"}.'
            )
            logger.info(f"Updated admin {admin.email} for school {school.name}.")
            return redirect('kiswate_digital_app:school_admin_list')
        else:
            logger.warning(f"Form errors for admin {admin.email}: {form.errors}")  # Debug log
            messages.error(request, "Please correct the form errors.")
            # Redirect to list with params to re-open modal
            return redirect(f'/school-admins/?edit_pk={school_pk}&error=1')
    # For GET: Redirect with message (avoid direct access)
    messages.info(request, "Use the edit button in the list to modify this admin.")
    return redirect('skiswate_digital_app:chool_admin_list')


@login_required
def delete_school_admin(request, school_pk):
    """
    Deactivate school admin via modal POST.
    """
    if not request.user.is_superuser:
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


def invoice_list(request):
    return render(request, "Dashboard/invoice_list.html", {})
def create_invoice(request):
    return render(request, "Dashboard/create_invoice.html", {})

def payment_history(request):
    return render(request, "Dashboard/payment_history.html", {})
def reports(request):
    return render(request, "Dashboard/reports.html", {})
def support(request):
    return render(request, "Dashboard/support.html", {})


@login_required
def scholarship_list_create(request):
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



def announcements(request):
    return render(request, "Dashboard/announcements.html", {})
def new_announcement(request):
    return render(request, "Dashboard/new_announcement.html", {})

def edit_announcement(request):
    return render(request, "Dashboard/edit_announcement.html", {})

def delete_announcement(request):
    return render(request, "Dashboard/delete_announcement.html", {})

