from django.shortcuts import render
from django.db.models import Sum, F, Q
from django.core.paginator import Paginator
from users.models import User


def customers(request):
    customers = User.objects.filter(role=User.CUSTOMER).annotate(
        total_debt=Sum(
            F("customer_debts__amount_owed") - F("customer_debts__amount_paid")
        )
    )

    search_query = request.GET.get("search", "").strip()
    if search_query:
        customers = customers.filter(
            Q(first_name__icontains=search_query)
            | Q(last_name__icontains=search_query)
            | Q(phone_number__icontains=search_query)
            | Q(email__icontains=search_query)
        )

    sort_by = request.GET.get("sort", "first_name")

    valid_sort_fields = [
        "first_name",
        "-first_name",
        "last_name",
        "-last_name",
        "phone_number",
        "-phone_number",
        "email",
        "-email",
        "total_debt",
        "-total_debt",
    ]

    if sort_by not in valid_sort_fields:
        sort_by = "first_name"

    customers = customers.order_by(sort_by)

    paginator = Paginator(customers, 15)
    page_number = request.GET.get("page", 1)
    try:
        page_number = int(page_number)
        if page_number < 1:
            page_number = 1
    except ValueError:
        page_number = 1
    page_obj = paginator.get_page(page_number)

    context = {
        "page_obj": page_obj,
        "show_pagination": paginator.num_pages > 1,
        "current_sort": sort_by,
        "search_query": search_query,
    }
    return render(request, "customers/customers.html", context)
