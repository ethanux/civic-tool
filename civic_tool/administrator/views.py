from django.shortcuts import render, get_object_or_404, redirect
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.db.models import Q, Count
from django.utils import timezone
from datetime import datetime, timedelta
from civilian.models import IssueReport

# Create your views here.

@login_required
def home(request):
    return redirect('admin_dashboard')

@login_required
def dashboard(request):
    """Admin dashboard with comprehensive analytics"""
    
    # Get all reports for analytics
    all_reports = IssueReport.objects.all()
    
    # Basic statistics
    total_reports = all_reports.count()
    
    # Reports by status
    status_stats = {}
    for choice in IssueReport.STATUS_CHOICES:
        status_stats[choice[0]] = {
            'name': choice[1],
            'count': all_reports.filter(status=choice[0]).count(),
            'percentage': 0
        }
    
    # Calculate percentages
    if total_reports > 0:
        for status in status_stats:
            status_stats[status]['percentage'] = round(
                (status_stats[status]['count'] / total_reports) * 100, 1
            )
    
    # Reports by category
    category_stats = {}
    for choice in IssueReport.CATEGORY_CHOICES:
        category_stats[choice[0]] = {
            'name': choice[1],
            'count': all_reports.filter(category=choice[0]).count(),
            'percentage': 0
        }
    
    # Calculate category percentages
    if total_reports > 0:
        for category in category_stats:
            category_stats[category]['percentage'] = round(
                (category_stats[category]['count'] / total_reports) * 100, 1
            )
    
    # Time-based analytics
    now = timezone.now()
    
    # Today's reports
    today_reports = all_reports.filter(created_at__date=now.date()).count()
    
    # This week's reports
    week_ago = now - timedelta(days=7)
    week_reports = all_reports.filter(created_at__gte=week_ago).count()
    
    # This month's reports
    month_ago = now - timedelta(days=30)
    month_reports = all_reports.filter(created_at__gte=month_ago).count()
    
    # Reports with media
    reports_with_media = all_reports.filter(
        Q(image__isnull=False) | Q(video__isnull=False)
    ).count()
    
    # Recent reports (last 10)
    recent_reports = all_reports.order_by('-created_at')[:10]
    
    # Reports by day (last 7 days) for chart
    daily_reports = []
    for i in range(7):
        date = (now - timedelta(days=i)).date()
        count = all_reports.filter(created_at__date=date).count()
        daily_reports.append({
            'date': date.strftime('%Y-%m-%d'),
            'day': date.strftime('%a'),
            'count': count
        })
    daily_reports.reverse()
    
    # Top reporters
    top_reporters = User.objects.filter(
        issue_reports__isnull=False
    ).annotate(
        report_count=Count('issue_reports')
    ).order_by('-report_count')[:5]
    
    context = {
        'total_reports': total_reports,
        'status_stats': status_stats,
        'category_stats': category_stats,
        'today_reports': today_reports,
        'week_reports': week_reports,
        'month_reports': month_reports,
        'reports_with_media': reports_with_media,
        'recent_reports': recent_reports,
        'daily_reports': daily_reports,
        'top_reporters': top_reporters,
    }
    
    return render(request, "administrator/dashboard.html", context)

@login_required
def view_reported_issues(request):
    """View all reported issues with filtering and search"""
    
    # Get filter parameters
    status_filter = request.GET.get('status', '')
    category_filter = request.GET.get('category', '')
    search_query = request.GET.get('search', '')
    date_from = request.GET.get('date_from', '')
    date_to = request.GET.get('date_to', '')
    
    # Start with all reports
    reports = IssueReport.objects.all().order_by('-created_at')
    
    # Apply filters
    if status_filter:
        reports = reports.filter(status=status_filter)
    
    if category_filter:
        reports = reports.filter(category=category_filter)
    
    if search_query:
        reports = reports.filter(
            Q(title__icontains=search_query) |
            Q(description__icontains=search_query) |
            Q(location__icontains=search_query) |
            Q(reporter__username__icontains=search_query) |
            Q(reporter__email__icontains=search_query)
        )
    
    if date_from:
        try:
            from_date = datetime.strptime(date_from, '%Y-%m-%d').date()
            reports = reports.filter(created_at__date__gte=from_date)
        except ValueError:
            pass
    
    if date_to:
        try:
            to_date = datetime.strptime(date_to, '%Y-%m-%d').date()
            reports = reports.filter(created_at__date__lte=to_date)
        except ValueError:
            pass
    
    # Pagination (simple version)
    page = int(request.GET.get('page', 1))
    per_page = 20
    start = (page - 1) * per_page
    end = start + per_page
    
    reports_page = reports[start:end]
    total_reports = reports.count()
    total_pages = (total_reports + per_page - 1) // per_page
    
    context = {
        'reports': reports_page,
        'status_choices': IssueReport.STATUS_CHOICES,
        'category_choices': IssueReport.CATEGORY_CHOICES,
        'severity_choices': IssueReport.SEVERITY_CHOICES,
        'current_status': status_filter,
        'current_category': category_filter,
        'current_search': search_query,
        'current_date_from': date_from,
        'current_date_to': date_to,
        'current_page': page,
        'total_pages': total_pages,
        'total_reports': total_reports,
        'has_previous': page > 1,
        'has_next': page < total_pages,
        'previous_page': page - 1 if page > 1 else None,
        'next_page': page + 1 if page < total_pages else None,
    }
    
    return render(request, "administrator/view_reported_issues.html", context)

@login_required
def manage_reports(request):
    """Manage reports - update status and view details"""
    
    if request.method == 'POST':
        report_id = request.POST.get('report_id')
        new_status = request.POST.get('status')
        
        if report_id and new_status:
            try:
                report = get_object_or_404(IssueReport, id=report_id)
                old_status = report.status
                report.status = new_status
                report.save()
                
                return JsonResponse({
                    'success': True,
                    'message': f'Status updated from {report.get_status_display()} to {report.get_status_display()}',
                    'new_status': new_status,
                    'new_status_display': report.get_status_display()
                })
            except Exception as e:
                return JsonResponse({
                    'success': False,
                    'message': f'Error updating status: {str(e)}'
                })
    
    # Get reports for management
    reports = IssueReport.objects.all().order_by('-created_at')
    
    # Apply filters if provided
    status_filter = request.GET.get('status', '')
    if status_filter:
        reports = reports.filter(status=status_filter)
    
    context = {
        'reports': reports,
        'status_choices': IssueReport.STATUS_CHOICES,
        'severity_choices': IssueReport.SEVERITY_CHOICES,
        'current_status': status_filter,
    }
    
    return render(request, "administrator/manage_reports.html", context)

@login_required
def manage_account(request):
    """Manage administrator account"""
    
    if request.method == 'POST':
        # Handle account updates
        first_name = request.POST.get('first_name', '').strip()
        last_name = request.POST.get('last_name', '').strip()
        email = request.POST.get('email', '').strip()
        
        if first_name:
            request.user.first_name = first_name
        if last_name:
            request.user.last_name = last_name
        if email:
            request.user.email = email
        
        request.user.save()
        
        return render(request, "administrator/manage_account.html", {
            'success_message': 'Account updated successfully!'
        })
    
    return render(request, "administrator/manage_account.html")

@login_required
def report_detail(request, report_id):
    """View detailed information about a specific report"""
    
    report = get_object_or_404(IssueReport, id=report_id)
    
    context = {
        'report': report,
        'status_choices': IssueReport.STATUS_CHOICES,
        'severity_choices': IssueReport.SEVERITY_CHOICES,
    }
    
    return render(request, "administrator/report_detail.html", context)