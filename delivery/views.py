from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from .models import Delivery
from users.models import User
from django.db.models import Count, Q


@login_required
def delivery_home(request):
    if not (request.user.is_admin() or request.user.is_supervisor()):
        raise PermissionDenied("You do not have permission to manage deliveries.")

    delivery_guys = User.objects.filter(role="delivery_guy", is_active=True).order_by('first_name', 'last_name')

    delivery_guys_with_status = []
    for guy in delivery_guys:
        active_delivery = Delivery.objects.filter(
            delivery_guy=guy,
            status__in=['assigned', 'in_transit']
        ).select_related('sale').first()

        delivery_guys_with_status.append({
            'user': guy,
            'active_delivery': active_delivery,
            'is_available': active_delivery is None
        })

    recent_deliveries = Delivery.objects.select_related(
        'sale', 'delivery_guy', 'responsible_cashier'
    ).order_by('-created_at')[:20]

    total_deliveries = Delivery.objects.count()
    pending_deliveries = Delivery.objects.filter(status='pending').count()
    assigned_deliveries = Delivery.objects.filter(status='assigned').count()
    in_transit_deliveries = Delivery.objects.filter(status='in_transit').count()
    delivered_deliveries = Delivery.objects.filter(status='delivered').count()
    cancelled_deliveries = Delivery.objects.filter(status='cancelled').count()

    context = {
        'delivery_guys': delivery_guys_with_status,
        'recent_deliveries': recent_deliveries,
        'stats': {
            'total': total_deliveries,
            'pending': pending_deliveries,
            'assigned': assigned_deliveries,
            'in_transit': in_transit_deliveries,
            'delivered': delivered_deliveries,
            'cancelled': cancelled_deliveries,
        }
    }

    return render(request, 'delivery/delivery_home.html', context)


@login_required
def delivery_history(request):
    if not request.user.is_delivery_guy():
        raise PermissionDenied("Access denied")

    completed_deliveries = (
        Delivery.objects.filter(
            delivery_guy=request.user, status="delivered"
        )
        .select_related("sale")
        .order_by("-delivered_at")
    )

    context = {
        "user": request.user,
        "completed_deliveries": completed_deliveries,
    }
    return render(request, "delivery/delivery_history.html", context)


@login_required
def delivery_detail(request, delivery_id):
    if not request.user.is_delivery_guy():
        raise PermissionDenied("Access denied")

    delivery = get_object_or_404(
        Delivery,
        id=delivery_id,
        delivery_guy=request.user
    )

    sale_items = delivery.sale.items.select_related("product").all()

    context = {
        "user": request.user,
        "delivery": delivery,
        "sale_items": sale_items,
    }
    return render(request, "delivery/delivery_detail.html", context)
