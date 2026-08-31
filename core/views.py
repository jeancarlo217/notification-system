import datetime
from collections.abc import Iterable, Iterator, Sequence
from dataclasses import dataclass

from django.core.paginator import Page, Paginator
from django.db.models import Q, QuerySet
from django.http import HttpRequest, HttpResponse, StreamingHttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from core.audit import log_service_submission
from core.export import (
    BYTE_ORDER_MARK,
    EXPORT_HEADER,
    ExportedService,
    csv_line,
    export_filename,
    export_row,
)
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


def service_export(request: HttpRequest) -> StreamingHttpResponse:
    """Every service record as one CSV row, streamed (foundation section 7).

    The whole dataset and never the page or the search on screen: B17 narrows how the list is
    read, never what the company owns.
    """
    timezone = get_config().timezone
    taken_on = datetime.datetime.now(tz=timezone).date()
    return StreamingHttpResponse(
        _export_lines(timezone),
        content_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{export_filename(taken_on)}"'},
    )


def _export_lines(timezone: datetime.tzinfo) -> Iterator[str]:
    """The file one line at a time, so no run of it ever holds the whole table in memory."""
    yield BYTE_ORDER_MARK + csv_line(EXPORT_HEADER)
    for service in _exportable():
        yield csv_line(export_row(_exported(service), timezone))


def _exportable() -> Iterator[Service]:
    """Every record with the two references it names, read in one query (foundation section 8).

    ``iterator`` is what keeps the rows off the heap: the query streams in chunks whatever the
    table holds, and the deadline order is the one the list already shows.
    """
    return (
        Service.objects.select_related("catalog_service__category", "submitter")
        .order_by("due_date", "pk")
        .iterator()
    )


def _exported(service: Service) -> ExportedService:
    """One persisted record as the plain data the row decision takes.

    The catalogue entry and the submitter resolve to columns here, which is what keeps the
    flatness promise of foundation section 3 true through two foreign keys.
    """
    return ExportedService(
        client=service.client,
        category=service.catalog_service.category.name,
        service=service.catalog_service.name,
        notes=service.notes,
        start_date=service.start_date,
        term_days=service.term_days,
        due_date=service.due_date,
        status=service.get_status_display(),
        submitter=service.submitter.display_name,
        created_at=service.created_at,
    )


def health(request: HttpRequest) -> HttpResponse:
    """Liveness for the container runtime: the process answered, and nothing else is claimed.

    It is the single route outside the secret path segment, so it touches no dependency and
    reveals no data (foundation section 6).
    """
    return HttpResponse("ok", content_type="text/plain; charset=utf-8")
