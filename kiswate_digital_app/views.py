# views.py (CRUD for School)
import logging
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Q
from django.conf import settings
from school.models import School
from userauths.models import User
from .forms import SchoolCreationForm, SchoolEditForm,AdminEditForm

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
    return render(request, "Dashboard/kiswate_admin_dashboard.html", {})


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

def subscription_plans(request):
    return render(request, "Dashboard/subscription_plans.html", {})
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


def scholarships(request):
    return render(request, "Dashboard/scholarships.html", {})

def new_scholarship(request):
    return render(request, "Dashboard/new_scholarship.html", {})

def edit_scholarship(request):
    return render(request, "Dashboard/edit_scholarship.html", {})

def delete_scholarship(request):
    return render(request, "Dashboard/delete_scholarship.html", {})

def announcements(request):
    return render(request, "Dashboard/announcements.html", {})
def new_announcement(request):
    return render(request, "Dashboard/new_announcement.html", {})

def edit_announcement(request):
    return render(request, "Dashboard/edit_announcement.html", {})

def delete_announcement(request):
    return render(request, "Dashboard/delete_announcement.html", {})

