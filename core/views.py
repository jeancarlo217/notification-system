from django.core.paginator import Page, Paginator
from django.db.models import Q, QuerySet
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from core.audit import log_service_submission
from core.forms import DueDateForm, ServiceRegistrationForm
from core.models import Service

SERVICES_PER_PAGE = 20


def service_list(request: HttpRequest) -> HttpResponse:
    term = request.GET.get("q", "").strip()
    page = _page_of_services(_matching(term), request.GET.get("page"))
    context = {"services": page.object_list, "page": page, "term": term}
    return render(request, "core/service_list.html", context)


def _matching(term: str) -> QuerySet[Service]:
    """The listing, narrowed to ``term`` when there is one.

    The catalogue name is reached through the join the listing already selects, so filtering on it
    costs no extra query (foundation section 8).
    """
    services = Service.objects.select_related("catalog_service").order_by("due_date", "pk")
    if not term:
        return services
    return services.filter(Q(client__icontains=term) | Q(catalog_service__name__icontains=term))


def _page_of_services(services: QuerySet[Service], number: str | None) -> Page[Service]:
    """The requested page, or the nearest one that exists.

    ``get_page`` is what turns a hand edited or stale ``?page=`` into the first or the last page
    instead of an error screen, which is the only behaviour an employee following a link can use.
    """
    return Paginator(services, SERVICES_PER_PAGE).get_page(number)


def service_create(request: HttpRequest) -> HttpResponse:
    form = ServiceRegistrationForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        service = form.save()
        log_service_submission(service.pk, service.submitter_id)
        return redirect("service-list")
    context = {"form": form, "title": "Cadastrar serviço", "action": "Cadastrar"}
    return render(request, "core/service_form.html", context)


def service_due_date(request: HttpRequest, pk: int) -> HttpResponse:
    service = get_object_or_404(Service, pk=pk)
    form = DueDateForm(request.POST or None, instance=service)
    if request.method == "POST" and form.is_valid():
        form.save()
        log_service_submission(service.pk, service.submitter_id)
        return redirect("service-list")
    context = {"form": form, "title": "Editar vencimento", "action": "Salvar", "service": service}
    return render(request, "core/service_form.html", context)


@require_POST
def service_complete(request: HttpRequest, pk: int) -> HttpResponse:
    service = get_object_or_404(Service, pk=pk)
    service.status = Service.Status.COMPLETED
    service.save(update_fields=["status"])
    log_service_submission(service.pk, service.submitter_id)
    return redirect("service-list")


def health(request: HttpRequest) -> HttpResponse:
    """Liveness for the container runtime: the process answered, and nothing else is claimed.

    It is the single route outside the secret path segment, so it touches no dependency and
    reveals no data (foundation section 6).
    """
    return HttpResponse("ok", content_type="text/plain; charset=utf-8")
