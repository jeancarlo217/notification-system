from collections.abc import Iterable, Sequence
from dataclasses import dataclass

from django.core.paginator import Page, Paginator
from django.db.models import Q, QuerySet
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from core.audit import log_service_submission
from core.forms import DueDateForm, ServiceRegistrationForm
from core.models import Alert, Service
from deadliner.config import get_config

SERVICES_PER_PAGE = 20

WARNING_NOT_REACHED = "waiting"
WARNING_TEXT: dict[str, str] = {
    WARNING_NOT_REACHED: "aguardando",
    Alert.State.PENDING: "pendente",
    Alert.State.SENT: "enviado",
    Alert.State.FAILED: "falhou",
}
"""What each state of a warning is called on screen, in Portuguese (foundation section 12)."""


@dataclass(frozen=True, slots=True)
class ListedWarning:
    """One configured threshold beside what became of its warning (I2)."""

    label: str
    state: str
    text: str


@dataclass(frozen=True, slots=True)
class ListedService:
    """One row of the list: the record, and one warning per configured threshold."""

    service: Service
    warnings: tuple[ListedWarning, ...]


def service_list(request: HttpRequest) -> HttpResponse:
    """The records, each with who registered it and what became of every warning it is owed."""
    term = request.GET.get("q", "").strip()
    page = _page_of_services(_matching(term), request.GET.get("page"))
    context = {
        "rows": _listed(page.object_list, get_config().alert_thresholds),
        "page": page,
        "term": term,
    }
    return render(request, "core/service_list.html", context)


def _matching(term: str) -> QuerySet[Service]:
    """The listing, narrowed to ``term`` when there is one.

    The catalogue name is reached through the join the listing already selects, so filtering on it
    costs no extra query (foundation section 8). The alerts arrive in one further query for the
    whole page, never one per row.
    """
    services = (
        Service.objects.select_related("catalog_service", "submitter")
        .prefetch_related("alerts")
        .order_by("due_date", "pk")
    )
    if not term:
        return services
    return services.filter(Q(client__icontains=term) | Q(catalog_service__name__icontains=term))


def _listed(services: Iterable[Service], thresholds: Sequence[int]) -> list[ListedService]:
    """Each record beside one warning per configured threshold, in the configured order (I4)."""
    return [
        ListedService(
            service=service,
            warnings=tuple(_warning(service, threshold) for threshold in thresholds),
        )
        for service in services
    ]


def _warning(service: Service, threshold: int) -> ListedWarning:
    """What the screen says about one threshold of one record.

    No alert row means the threshold has not been reached, which is never the failed state (I2).
    ``alerts.all()`` reads the prefetch, so this loop adds no query.
    """
    state = next(
        (alert.state for alert in service.alerts.all() if alert.threshold == threshold),
        WARNING_NOT_REACHED,
    )
    return ListedWarning(label=f"{threshold}d", state=state, text=WARNING_TEXT[state])


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
