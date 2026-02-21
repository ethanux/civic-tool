from django.urls import path, include
from . import views
urlpatterns = [
    path("", views.dashboard, name="admin_home"),
    path("dashboard/", views.dashboard, name="admin_dashboard"),
    path("view-reported-issues/", views.view_reported_issues, name="admin_view_reported_issues"),
    path("manage-reports/", views.manage_reports, name="admin_manage_reports"),
    path("manage-account/", views.manage_account, name="admin_manage_account"),
    path("report/<int:report_id>/", views.report_detail, name="admin_report_detail"),
]
    