import csv
import itertools
from collections.abc import Iterator

from django.http import HttpRequest, HttpResponse, StreamingHttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.timezone import localtime
from django.views.decorators.http import require_POST

from core.audit import log_service_submission
from core.export import BYTE_ORDER_MARK, CSV_DELIMITER, ExportRecord, export_rows
from core.forms import DueDateForm, ServiceRegistrationForm
from core.models import Service


def service_list(request: HttpRequest) -> HttpResponse:
    services = Service.objects.order_by("due_date", "pk")
    return render(request, "core/service_list.html", {"services": services})


def service_create(request: HttpRequest) -> HttpResponse:
    form = ServiceRegistrationForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        service = form.save()
        log_service_submission(service.pk)
        return redirect("service-list")
    context = {"form": form, "title": "Cadastrar serviço", "action": "Cadastrar"}
    return render(request, "core/service_form.html", context)


def service_due_date(request: HttpRequest, pk: int) -> HttpResponse:
    service = get_object_or_404(Service, pk=pk)
    form = DueDateForm(request.POST or None, instance=service)
    if request.method == "POST" and form.is_valid():
        form.save()
        log_service_submission(service.pk)
        return redirect("service-list")
    context = {"form": form, "title": "Editar vencimento", "action": "Salvar", "service": service}
    return render(request, "core/service_form.html", context)


@require_POST
def service_complete(request: HttpRequest, pk: int) -> HttpResponse:
    service = get_object_or_404(Service, pk=pk)
    service.status = Service.Status.COMPLETED
    service.save(update_fields=["status"])
    log_service_submission(service.pk)
    return redirect("service-list")


def health(request: HttpRequest) -> HttpResponse:
    """Liveness for the container runtime: the process answered, and nothing else is claimed.

    It is the single route outside the secret path segment, so it touches no dependency and
    reveals no data (foundation section 6).
    """
    return HttpResponse("ok", content_type="text/plain; charset=utf-8")


class _Echo:
    """A file-like object whose write returns the line instead of storing it.

    Django's own way of streaming CSV: it is what turns the writer into a generator of lines
    rather than a buffer the whole file has to fit in.
    """

    def write(self, value: str) -> str:
        return value


def service_export(request: HttpRequest) -> StreamingHttpResponse:
    """The whole dataset as one spreadsheet row per record, streamed (foundation section 7)."""
    writer = csv.writer(_Echo(), delimiter=CSV_DELIMITER)
    lines = (str(writer.writerow(row)) for row in export_rows(_export_records()))
    response = StreamingHttpResponse(
        itertools.chain([BYTE_ORDER_MARK], lines),
        content_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="servicos.csv"'},
    )
    return response


def _export_records() -> Iterator[ExportRecord]:
    # One query for the whole file, streamed in chunks, never one per row (foundation section 8).
    for service in Service.objects.order_by("due_date", "pk").iterator():
        yield ExportRecord(
            client=service.client,
            description=service.description,
            due_date=service.due_date,
            status_label=service.get_status_display(),
            created_at=localtime(service.created_at),
        )
