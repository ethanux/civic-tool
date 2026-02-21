from django.urls import path, include
from . import views
urlpatterns = [
    path("", views.home, name="home"),
    path("login/", views.login_view, name="login"),
    path("register/", views.register_view, name="register"),
    path("logout/", views.logout_view, name="logout"),
    path("dashboard/", views.dashboard, name="civilian_dashboard"),
    path("report-issue/", views.report_issue, name="civilian_report_issue"),
    path("view-reports/", views.view_reports, name="civilian_view_reports"),
    path("area-risk-heatmap/", views.area_risk_heatmap, name="civilian_area_risk_heatmap"),
    path("api/hazard-alerts/", views.hazard_alerts_api, name="civilian_hazard_alerts_api"),
    path("manage-account/", views.manage_account, name="civilian_manage_account"),
]