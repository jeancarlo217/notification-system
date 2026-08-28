from django.urls import path

from core import views

urlpatterns = [
    path("", views.service_list, name="service-list"),
    path("servicos/novo/", views.service_create, name="service-create"),
    path("servicos/<int:pk>/vencimento/", views.service_due_date, name="service-due-date"),
    path("servicos/<int:pk>/concluir/", views.service_complete, name="service-complete"),
]
