from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib import messages


def login_view(request):
    if request.user.is_authenticated:
        return redirect("dashboard")

    if request.method == "POST":
        username = request.POST.get("username")
        password = request.POST.get("password")

        user = authenticate(request, username=username, password=password)

        if user is not None:
            if user.is_customer():
                messages.error(
                    request, "Customer accounts cannot access the POS system"
                )
                return render(request, "users/login.html")

            login(request, user)
            messages.success(request, f"Logged in as {user.get_full_name()}")

            if user.is_admin():
                return redirect("admin_dashboard")
            elif user.is_cashier():
                return redirect("cashier_dashboard")
            elif user.is_supervisor():
                return redirect("supervisor_dashboard")
            elif user.is_delivery_guy():
                return redirect("delivery_dashboard")
            else:
                return redirect("customer_dashboard")
        else:
            messages.error(request, "Invalid username or password")
            return render(request, "users/login.html")

    return render(request, "users/login.html")


def logout_view(request):
    logout(request)
    messages.success(request, "You have been logged out successfully")
    return redirect("login_view")
