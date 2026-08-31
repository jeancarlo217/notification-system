from django.urls import path

from core import views

urlpatterns = [
    path("", views.service_list, name="service-list"),
    path("novo/", views.service_create, name="service-create"),
    path("<int:pk>/vencimento/", views.service_due_date, name="service-due-date"),
    path("<int:pk>/concluir/", views.service_complete, name="service-complete"),
]
