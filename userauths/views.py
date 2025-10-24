from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout,update_session_auth_hash
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import PasswordChangeForm

from userauths.models import User


def index(request):
    return render(request, "landing/index.html",{})


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
                return redirect("school:dashboard")
            else:
                messages.warning(request, "Username or password does not exist")
                return redirect("userauths:sign-in")

        except User.DoesNotExist:
            messages.warning(request, "User does not exist")
            return redirect("userauths:sign-in")

    # if request.user.is_authenticated:
    #     messages.warning(request, "You are already logged In")
    #     return redirect("wallet:dashboard")

    return render(request, "landing/login.html",{})

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
