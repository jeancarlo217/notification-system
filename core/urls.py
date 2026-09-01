from django.urls import path

from core import views

urlpatterns = [
    path("", views.service_list, name="service-list"),
    path("novo/", views.service_create, name="service-create"),
    path("exportar/", views.service_export, name="service-export"),
    path("<int:pk>/editar/", views.service_edit, name="service-edit"),
    path("<int:pk>/concluir/", views.service_complete, name="service-complete"),
]
