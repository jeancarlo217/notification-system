import datetime
from collections.abc import Iterator, Sequence
from dataclasses import dataclass

from django.core.paginator import Page, Paginator
from django.db.models import Q, QuerySet
from django.http import HttpRequest, HttpResponse, StreamingHttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from core import clock
from core.audit import log_service_submission
from core.engine import RETRY_INTERVAL
from core.export import (
    BYTE_ORDER_MARK,
    EXPORT_HEADER,
    ExportedService,
    csv_line,
    export_filename,
    export_row,
)
from core.forms import ServiceEditForm, ServiceRegistrationForm
from core.models import Dispatch, Service
from deadliner.config import get_config

SERVICES_PER_PAGE = 20

DISPATCH_NOT_ATTEMPTED = "none"


@dataclass(frozen=True, slots=True)
class DispatchNotice:
    """What the list screen says about today's list, in Portuguese (I2, foundation section 12).

    ``earlier`` names the latest earlier day whose list was never delivered, and it is blank once
    a later list has been.
    """

    state: str
    text: str
    earlier: str


def dispatch_notice(
    today: datetime.date, recent: Sequence[Dispatch], timezone: datetime.tzinfo
) -> DispatchNotice:
    """The notice for ``today``, from the dispatch rows up to it, newest first.

    A pure decision: the rows and the zone in, the words out.
    """
    current = next((row for row in recent if row.local_date == today), None)
    previous = next((row for row in recent if row.local_date < today), None)

    delivered_today = current is not None and current.state == Dispatch.State.SENT
    earlier = ""
    if previous is not None and previous.state != Dispatch.State.SENT and not delivered_today:
        earlier = f"A lista de {previous.local_date:%d/%m/%Y} não foi entregue."

    if current is None:
        return DispatchNotice(
            state=DISPATCH_NOT_ATTEMPTED,
            text="A lista de hoje ainda não foi enviada.",
            earlier=earlier,
        )

    attempted = current.last_attempt_at.astimezone(timezone)
    at = f"{attempted:%H:%M}"
    retry = f"{attempted + RETRY_INTERVAL:%H:%M}"
    if current.state == Dispatch.State.SENT:
        text = f"Lista de hoje enviada às {at}."
    elif current.state == Dispatch.State.FAILED:
        text = f"O envio da lista de hoje falhou às {at}. Nova tentativa às {retry}."
    else:
        text = (
            f"O envio da lista de hoje começou às {at} e não foi confirmado. "
            f"Nova tentativa às {retry}."
        )
    return DispatchNotice(state=current.state, text=text, earlier=earlier)


def service_list(request: HttpRequest) -> HttpResponse:
    """The records, each with who registered it, under what became of today's list."""
    term = request.GET.get("q", "").strip()
    page = _page_of_services(_matching(term), request.GET.get("page"))
    context = {
        "rows": page.object_list,
        "page": page,
        "term": term,
        "dispatch": _todays_notice(),
    }
    return render(request, "core/service_list.html", context)


def _todays_notice() -> DispatchNotice:
    """Today's notice, read in one query whatever the table holds (foundation section 8)."""
    timezone = get_config().timezone
    today = clock.now().astimezone(timezone).date()
    recent = list(Dispatch.objects.filter(local_date__lte=today).order_by("-local_date")[:2])
    return dispatch_notice(today, recent, timezone)


def _matching(term: str) -> QuerySet[Service]:
    """The listing, narrowed to ``term`` when there is one.

    The catalogue name is reached through the join the listing already selects, so filtering on it
    costs no extra query (foundation section 8).
    """
    services = Service.objects.select_related("catalog_service", "submitter").order_by(
        "due_date", "pk"
    )
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


def service_edit(request: HttpRequest, pk: int) -> HttpResponse:
    """One screen for the whole record (B23): every field it holds, edited together.

    The audit entry carries the record's own submitter and never one asked for here, because
    attribution is per record and not per edit (ADR 0006, I6).
    """
    # The head names the catalogue entry, so it rides in on the record's own query.
    service = get_object_or_404(Service.objects.select_related("catalog_service"), pk=pk)
    form = ServiceEditForm(request.POST or None, instance=service)
    if request.method == "POST" and form.is_valid():
        form.save()
        log_service_submission(service.pk, service.submitter_id)
        return redirect("service-list")
    context = {"form": form, "title": "Editar serviço", "action": "Salvar", "service": service}
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
    taken_on = clock.now().astimezone(timezone).date()
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
