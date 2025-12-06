from django.shortcuts import render, redirect, get_object_or_404
from users.models import User
from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.forms import SetPasswordForm
from django.http import JsonResponse
from .forms import CustomUserCreationForm, CustomUserChangeForm
import subprocess
import sys
import os


def can_manage_users(user):
    return user.can_manage_users()


@login_required
@user_passes_test(can_manage_users)
def settings_home(request):
    return render(request, "settings/home.html")


@login_required
@user_passes_test(can_manage_users)
def printer_settings(request):
    import json
    config_path = os.path.join(os.path.dirname(__file__), "../hardware/printer_config.json")
    printer_configured = os.path.exists(config_path)
    printer_config = None
    if printer_configured:
        try:
            with open(config_path, 'r') as f:
                printer_config = json.load(f)
        except:
            pass
    return render(request, "settings/printer.html", {
        "printer_configured": printer_configured,
        "printer_config": printer_config
    })


@login_required
@user_passes_test(can_manage_users)
def setup_printer(request):
    if request.method == "POST":
        try:
            setup_script = os.path.join(os.path.dirname(__file__), "../hardware/setup_printer.py")
            result = subprocess.run([sys.executable, setup_script],
                                  capture_output=True, text=True, timeout=60)

            if result.returncode == 0:
                return JsonResponse({
                    "success": True,
                    "message": "Printer setup completed successfully!"
                })
            else:
                return JsonResponse({
                    "success": False,
                    "error": result.stderr or "Setup failed"
                })

        except subprocess.TimeoutExpired:
            return JsonResponse({
                "success": False,
                "error": "Setup timed out. Please try again."
            })
        except Exception as e:
            return JsonResponse({
                "success": False,
                "error": f"Setup failed: {str(e)}"
            })

    return JsonResponse({
        "success": False,
        "error": "Invalid request method"
    })


@login_required
@user_passes_test(can_manage_users)
def user_list(request):
    users = User.objects.exclude(role=User.CUSTOMER).order_by("username")
    return render(request, "settings/user_list.html", {"users": users})


@login_required
@user_passes_test(can_manage_users)
def create_user(request):
    if request.method == "POST":
        form = CustomUserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            messages.success(request, f"User {user.username} created successfully.")
            return redirect("settings:user_list")
    else:
        form = CustomUserCreationForm()
    return render(request, "settings/create_user.html", {"form": form})


@login_required
@user_passes_test(can_manage_users)
def update_user(request, user_id):
    user = get_object_or_404(User, id=user_id)
    if request.method == "POST":
        form = CustomUserChangeForm(request.POST, instance=user, current_user=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, f"User {user.username} updated successfully.")
            return redirect("settings:user_list")
    else:
        form = CustomUserChangeForm(instance=user, current_user=request.user)
    return render(request, "settings/update_user.html", {"form": form, "user": user})


@login_required
@user_passes_test(can_manage_users)
def delete_user(request, user_id):
    user = get_object_or_404(User, id=user_id)
    if request.method == "POST":
        username = user.username
        user.delete()
        messages.success(request, f"User {username} deleted successfully.")
        return redirect("settings:user_list")
    return render(request, "settings/delete_user.html", {"user": user})


@login_required
@user_passes_test(can_manage_users)
def change_password(request, user_id):
    user = get_object_or_404(User, id=user_id)
    if request.method == "POST":
        form = SetPasswordForm(user, request.POST)
        if form.is_valid():
            form.save()
            messages.success(
                request, f"Password for {user.username} changed successfully."
            )
            return redirect("settings:user_list")
    else:
        form = SetPasswordForm(user)
    return render(
        request, "settings/change_password.html", {"form": form, "user": user}
    )
