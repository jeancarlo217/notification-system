from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from core.forms import DueDateForm, ServiceRegistrationForm
from core.models import Service


def service_list(request: HttpRequest) -> HttpResponse:
    services = Service.objects.order_by("due_date", "pk")
    return render(request, "core/service_list.html", {"services": services})


def service_create(request: HttpRequest) -> HttpResponse:
    form = ServiceRegistrationForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        form.save()
        return redirect("service-list")
    context = {"form": form, "title": "Cadastrar serviço", "action": "Cadastrar"}
    return render(request, "core/service_form.html", context)


def service_due_date(request: HttpRequest, pk: int) -> HttpResponse:
    service = get_object_or_404(Service, pk=pk)
    form = DueDateForm(request.POST or None, instance=service)
    if request.method == "POST" and form.is_valid():
        form.save()
        return redirect("service-list")
    context = {"form": form, "title": "Editar vencimento", "action": "Salvar", "service": service}
    return render(request, "core/service_form.html", context)


@require_POST
def service_complete(request: HttpRequest, pk: int) -> HttpResponse:
    service = get_object_or_404(Service, pk=pk)
    service.status = Service.Status.COMPLETED
    service.save(update_fields=["status"])
    return redirect("service-list")


def health(request: HttpRequest) -> HttpResponse:
    """Liveness for the container runtime: the process answered, and nothing else is claimed.

    It is the single route outside the secret path segment, so it touches no dependency and
    reveals no data (foundation section 6).
    """
    return HttpResponse("ok", content_type="text/plain; charset=utf-8")
