from django.shortcuts import render, redirect
from django.http import HttpRequest, HttpResponse
from tempfile import NamedTemporaryFile
from typing import Optional
from django.contrib.auth.models import User
from django.contrib.auth import authenticate, login, logout
from django.db import models
from administrator.views import home as administrator_home
from .models import IssueReport
import os
from ai.utils.detect import detect_pothole_severity

def _get_video_duration_seconds(uploaded_file) -> Optional[float]:
    """Return duration in seconds for a video upload, or None if unknown/unreadable."""
    try:
        # Reset file pointer to beginning
        uploaded_file.seek(0)
        
        # Try multiple approaches for video duration detection
        duration = None
        
        # Determine file extension based on content type
        file_extension = ".webm"  # default
        if uploaded_file.content_type:
            if "mp4" in uploaded_file.content_type:
                file_extension = ".mp4"
            elif "webm" in uploaded_file.content_type:
                file_extension = ".webm"
            elif "avi" in uploaded_file.content_type:
                file_extension = ".avi"
        
        print(f"Attempting to detect duration for {uploaded_file.name} (type: {uploaded_file.content_type}, ext: {file_extension})")
        
        # Method 1: Try with moviepy (most reliable)
        try:
            from moviepy.editor import VideoFileClip
            with NamedTemporaryFile(delete=True, suffix=file_extension) as tmp:
                for chunk in uploaded_file.chunks():
                    tmp.write(chunk)
                tmp.flush()
                uploaded_file.seek(0)  # Reset for potential retry
                
                print(f"Trying MoviePy with temp file: {tmp.name}")
                with VideoFileClip(tmp.name) as clip:
                    if clip.duration is not None and clip.duration > 0:
                        duration = float(clip.duration)
                        print(f"MoviePy success: {duration} seconds")
        except Exception as e:
            print(f"MoviePy failed: {e}")
        
        # Method 2: Try with ffmpeg-python if moviepy fails
        if duration is None:
            try:
                import ffmpeg
                with NamedTemporaryFile(delete=True, suffix=file_extension) as tmp:
                    for chunk in uploaded_file.chunks():
                        tmp.write(chunk)
                    tmp.flush()
                    uploaded_file.seek(0)  # Reset for potential retry
                    
                    print(f"Trying FFmpeg with temp file: {tmp.name}")
                    probe = ffmpeg.probe(tmp.name)
                    duration_info = next((stream for stream in probe['streams'] if stream['codec_type'] == 'video'), None)
                    if duration_info and 'duration' in duration_info:
                        duration = float(duration_info['duration'])
                        print(f"FFmpeg success: {duration} seconds")
            except Exception as e:
                print(f"FFmpeg failed: {e}")
        
        # Method 3: Try with opencv if available
        if duration is None:
            try:
                import cv2
                with NamedTemporaryFile(delete=True, suffix=file_extension) as tmp:
                    for chunk in uploaded_file.chunks():
                        tmp.write(chunk)
                    tmp.flush()
                    uploaded_file.seek(0)  # Reset for potential retry
                    
                    print(f"Trying OpenCV with temp file: {tmp.name}")
                    cap = cv2.VideoCapture(tmp.name)
                    if cap.isOpened():
                        frame_count = cap.get(cv2.CAP_PROP_FRAME_COUNT)
                        fps = cap.get(cv2.CAP_PROP_FPS)
                        print(f"OpenCV: frame_count={frame_count}, fps={fps}")
                        if fps > 0 and frame_count > 0:
                            duration = frame_count / fps
                            print(f"OpenCV success: {duration} seconds")
                        cap.release()
            except Exception as e:
                print(f"OpenCV failed: {e}")
        
        # Method 4: Simple file size estimation (very rough fallback)
        if duration is None:
            try:
                # This is a very rough estimation - not reliable but better than nothing
                file_size_mb = uploaded_file.size / (1024 * 1024)
                # Rough estimate: 1MB per second for compressed video
                estimated_duration = file_size_mb
                if estimated_duration > 0 and estimated_duration <= 10:  # Reasonable range
                    duration = estimated_duration
                    print(f"File size estimation: {duration} seconds (rough estimate)")
            except Exception as e:
                print(f"File size estimation failed: {e}")
        
        print(f"Final duration result: {duration}")
        return duration
        
    except Exception as e:
        print(f"Video duration detection failed: {e}")
        return None
# Create your views here.

def home(request):
    return render(request, "civilian/base.html")


def login_view(request: HttpRequest) -> HttpResponse:
    if request.user.is_authenticated:
        return redirect("home")
    if request.method == "POST":
        email = request.POST.get("email", "").strip()
        password = request.POST.get("password", "")
        if not (email and password):
            return render(request, "civilian/login.html", {"error": "Email and password are required."})

        # Authenticate using email by resolving to username
        try:
            user_obj = User.objects.get(email=email)
            username = user_obj.username
        except User.DoesNotExist:
            return render(request, "civilian/login.html", {"error": "Invalid credentials."})

        user = authenticate(request, username=username, password=password)
        if user is None:
            return render(request, "civilian/login.html", {"error": "Invalid credentials."})

        login(request, user)
        if user.is_staff:
            return redirect("admin_home")
        return redirect("civilian_dashboard")

    return render(request, "civilian/login.html")


def register_view(request: HttpRequest) -> HttpResponse:
    if request.user.is_authenticated:
        return redirect("home")
    if request.method == "POST":
        email = request.POST.get("email", "").strip()
        username = request.POST.get("username", "").strip()
        password = request.POST.get("password", "")
        confirm_password = request.POST.get("confirm_password", "")

        if not (email and username and password and confirm_password):
            return render(request, "civilian/register.html", {"error": "All fields are required."})
        if password != confirm_password:
            return render(request, "civilian/register.html", {"error": "Passwords do not match."})

        if User.objects.filter(username=username).exists():
            return render(request, "civilian/register.html", {"error": "Username already taken."})
        if User.objects.filter(email=email).exists():
            return render(request, "civilian/register.html", {"error": "Email already registered."})

        user = User.objects.create_user(username=username, email=email, password=password)
        # Auto-login after registration
        login(request, user)
        return redirect("home")

    return render(request, "civilian/register.html")


def logout_view(request: HttpRequest) -> HttpResponse:
    logout(request)
    return redirect("login")


def dashboard(request: HttpRequest) -> HttpResponse:
    if request.user.is_authenticated:
        # Get user's reports for analytics
        user_reports = IssueReport.objects.filter(reporter=request.user)
        
        # Calculate statistics
        total_reports = user_reports.count()
        
        # Reports by category
        category_stats = {}
        for choice in IssueReport.CATEGORY_CHOICES:
            category_stats[choice[0]] = {
                'name': choice[1],
                'count': user_reports.filter(category=choice[0]).count()
            }
        
        # Recent reports (last 7 days)
        from datetime import datetime, timedelta
        from django.utils import timezone
        week_ago = timezone.now() - timedelta(days=7)
        recent_reports = user_reports.filter(created_at__gte=week_ago).count()
        
        # Reports with media
        reports_with_media = user_reports.filter(
            models.Q(image__isnull=False) | models.Q(video__isnull=False)
        ).count()
        
        # Status statistics
        status_stats = {}
        for choice in IssueReport.STATUS_CHOICES:
            status_stats[choice[0]] = {
                'name': choice[1],
                'count': user_reports.filter(status=choice[0]).count()
            }
        
        # Latest reports for activity feed
        latest_reports = user_reports.order_by('-created_at')[:5]
        
        context = {
            'total_reports': total_reports,
            'category_stats': category_stats,
            'status_stats': status_stats,
            'recent_reports': recent_reports,
            'reports_with_media': reports_with_media,
            'latest_reports': latest_reports,
        }
    else:
        context = {
            'total_reports': 0,
            'category_stats': {},
            'status_stats': {},
            'recent_reports': 0,
            'reports_with_media': 0,
            'latest_reports': [],
        }
    
    return render(request, "civilian/dashboard.html", context)



# Create your views here.


# Join a file path inside the app
import tempfile
import os
APP_ROOTs = os.path.dirname(os.path.abspath(__file__))
def save_uploaded_file_temp(uploaded_file):
    """Save a Django InMemoryUploadedFile or TemporaryUploadedFile to a temp file and return its path."""
    original_name = uploaded_file.name
    extension = os.path.splitext(original_name)[1] or '.tmp'

    with tempfile.NamedTemporaryFile(delete=False, suffix=extension, mode='wb') as temp_file:
        for chunk in uploaded_file.chunks():
            temp_file.write(chunk)
        temp_path = temp_file.name

    print(f"Saved temp file to: {temp_path}")
    return temp_path

def report_issue(request: HttpRequest) -> HttpResponse:
    if request.method == "POST":
        title = request.POST.get("title", "").strip()
        category = request.POST.get("category", "").strip()
        description = request.POST.get("description", "").strip()
        location = request.POST.get("location", "").strip()
        image_file = request.FILES.get("image")
        video_file = request.FILES.get("video")

        if not (title and category and description and location):
            return render(request, "civilian/report_issue.html", {"error": "All fields are required."})

        if image_file:
            temp_image_path = save_uploaded_file_temp(image_file)
            result = detect_pothole_severity(
                file_path=temp_image_path,  # or video.mp4
                model_path= os.path.join(APP_ROOTs, '..','ai', 'utils','best.pt'),
                output_folder=os.path.join(APP_ROOTs, '..','media', 'issues','ann_images'),
                
                conf_threshold=0.5
            )

            print(result)
            if result['boxes'] == 0 :
                return redirect("civilian_view_reports")

        elif video_file:
            temp_video_path = save_uploaded_file_temp(video_file)
            result = detect_pothole_severity(
            file_path=temp_video_path,  # or video.mp4
            model_path= os.path.join(APP_ROOTs, '..', 'ai', 'utils','best.pt'),
            output_folder=os.path.join(APP_ROOTs, '..', 'media', 'issues','ann_videos'),
            conf_threshold=0.5
            )
            if result['boxes'] == 0 :
                return redirect("civilian_view_reports")
        else:
            return redirect("civilian_view_reports")

        
        # Media is optional but recommended
        # if not image_file and not video_file:
        #     return render(request, "civilian/report_issue.html", {"error": "Please capture and include an image or a short video (max 6s)."})

        # Allow both image and video to be uploaded
        # if image_file and video_file:
        #     return render(request, "civilian/report_issue.html", {"error": "Please upload either an image or a video, not both."})

        # Validate video duration if provided (max 6 seconds)
        if video_file:

            print(f"Validating video file: {video_file.name}, size: {video_file.size}, type: {video_file.content_type}")
            duration = _get_video_duration_seconds(video_file)
            if duration is None:
                # If we can't read the video duration, we'll still accept it but warn the user
                # This is more user-friendly than rejecting the upload
                print(f"Warning: Could not determine duration for video file: {video_file.name}")
                print("Proceeding with upload despite unknown duration - client-side validation should have caught this")
                # Continue with the upload - the client-side validation should have caught this
            elif duration > 6.0:
                print(f"Video duration validation failed: {duration:.1f} seconds (max 6 seconds)")
                return render(request, "civilian/report_issue.html", {"error": f"Video must be 6 seconds or less. Your video is {duration:.1f} seconds long."})
            else:
                print(f"Video duration validation passed: {duration:.1f} seconds")

        try:

            
            issue = IssueReport.objects.create(
                reporter=request.user if request.user.is_authenticated else None,
                title=title,
                category=category,
                description=description,
                location=location,
                severity=result['severity'],
            )

            # Validate and save image file
            if image_file:
                print(f"Saving image file: {image_file.name}, size: {image_file.size}, type: {image_file.content_type}")
                # Validate that it's actually an image
                if not image_file.content_type.startswith('image/'):
                    print(f"ERROR: File {image_file.name} is not an image (type: {image_file.content_type})")
                    return render(request, "civilian/report_issue.html", {"error": "Invalid image file type. Please upload a valid image."})
                issue.image = image_file
                issue.annotated_image = result['annotated_output']
                issue.save(update_fields=["image"])
                print(f"Image saved successfully to issue {issue.id}")
                
            # Validate and save video file
            if video_file:
                print(f"Saving video file: {video_file.name}, size: {video_file.size}, type: {video_file.content_type}")
                # Validate that it's actually a video
                if not video_file.content_type.startswith('video/'):
                    print(f"ERROR: File {video_file.name} is not a video (type: {video_file.content_type})")
                    return render(request, "civilian/report_issue.html", {"error": "Invalid video file type. Please upload a valid video."})
                issue.video = video_file
                issue.annotated_video = result['annotated_output']
                issue.save(update_fields=["video"])
                print(f"Video saved successfully to issue {issue.id}")
                
            print(f"Issue created successfully: {issue.id}")
            return redirect("civilian_view_reports")
            
        except Exception as e:
            print(f"Error creating issue: {e}")
            return render(request, "civilian/report_issue.html", {"error": f"Failed to create issue report: {str(e)}"})

    return render(request, "civilian/report_issue.html")



def view_reports(request: HttpRequest) -> HttpResponse:
    if request.user.is_authenticated:
        reports = IssueReport.objects.filter(reporter=request.user).order_by("-created_at")
    else:
        reports = IssueReport.objects.none()
    return render(request, "civilian/view_reports.html", {"reports": reports})


def manage_account(request: HttpRequest) -> HttpResponse:
    return render(request, "civilian/manage_account.html")


def area_risk_heatmap(request: HttpRequest) -> HttpResponse:
    """Display a heatmap of reported issues with filtering capabilities."""
    from django.db.models import Count
    from django.http import JsonResponse
    import json
    from datetime import datetime, timedelta
    from django.utils import timezone
    
    # Handle AJAX requests for filtered data
    if request.method == 'GET' and request.GET.get('format') == 'json':
        # Get filter parameters
        area_filter = request.GET.get('area', '').strip()
        category_filter = request.GET.get('category', '').strip()
        severity_filter = request.GET.get('severity', '').strip()
        
        # Base queryset - get all public reports (not just user's own)
        reports = IssueReport.objects.all()
        
        # Apply filters
        if area_filter:
            reports = reports.filter(location__icontains=area_filter)
        if category_filter:
            reports = reports.filter(category=category_filter)
        if severity_filter:
            reports = reports.filter(severity=severity_filter)
        
        # Convert to JSON format for the map
        map_data = []
        for report in reports:
            # Try to extract coordinates from location if possible
            # For now, we'll use a simple approach and generate mock coordinates
            # In a real implementation, you'd want to geocode the location
            
            # Generate mock coordinates based on location hash for consistency
            import hashlib
            location_hash = hashlib.md5(report.location.encode()).hexdigest()
            # Convert hash to coordinates (mock approach) - South Africa area
            lat = -26.2041 + (int(location_hash[:8], 16) / 0xffffffff - 0.5) * 2.0  # South Africa area
            lng = 28.0473 + (int(location_hash[8:16], 16) / 0xffffffff - 0.5) * 2.0
            
            map_data.append({
                'id': report.id,
                'title': report.title,
                'category': report.get_category_display(),
                'severity': report.get_severity_display(),
                'status': report.get_status_display(),
                'location': report.location,
                'description': report.description[:100] + '...' if len(report.description) > 100 else report.description,
                'created_at': report.created_at.strftime('%Y-%m-%d %H:%M'),
                'lat': lat,
                'lng': lng,
                'has_image': bool(report.image),
                'has_video': bool(report.video),
            })
        
        return JsonResponse({'reports': map_data})
    
    # Regular page request - get filter options
    # South African provinces
    sa_provinces = [
        'Western Cape', 'Eastern Cape', 'Northern Cape', 'Free State', 
        'KwaZulu-Natal', 'North West', 'Gauteng', 'Mpumalanga', 'Limpopo'
    ]
    
    # Get unique areas from locations (first part before comma)
    areas = IssueReport.objects.exclude(location='').values_list('location', flat=True).distinct()
    area_list = []
    for area in areas:
        # Extract area name (first part before comma or first word)
        area_name = area.split(',')[0].strip()
        if area_name and area_name not in area_list:
            area_list.append(area_name)
    
    # Add South African provinces to the area list
    area_list.extend(sa_provinces)
    area_list = sorted(list(set(area_list)))  # Remove duplicates and sort
    
    # Get category and severity choices
    categories = IssueReport.CATEGORY_CHOICES
    severities = IssueReport.SEVERITY_CHOICES
    
    # Create sample data if no reports exist
    if IssueReport.objects.count() == 0:
        create_sample_data()
    
    # Get some statistics for the page
    total_reports = IssueReport.objects.count()
    reports_by_category = {}
    for category_key, category_name in categories:
        count = IssueReport.objects.filter(category=category_key).count()
        reports_by_category[category_key] = {
            'name': category_name,
            'count': count
        }
    
    context = {
        'areas': sorted(area_list),
        'categories': categories,
        'severities': severities,
        'total_reports': total_reports,
        'reports_by_category': reports_by_category,
    }
    
    return render(request, "civilian/area_risk_heatmap.html", context)


def create_sample_data():
    """Create sample data for demonstration purposes."""
    from django.contrib.auth.models import User
    from datetime import datetime, timedelta
    from django.utils import timezone
    import random
    
    # Sample data for South African provinces
    sample_reports = [
        # Western Cape
        {"title": "Large pothole on N1 highway", "category": "pothole", "severity": "high", "location": "Cape Town, Western Cape", "description": "Deep pothole causing traffic delays and vehicle damage"},
        {"title": "Broken streetlight on Long Street", "category": "streetlight", "severity": "medium", "location": "Cape Town, Western Cape", "description": "Streetlight not working for 3 days, safety concern"},
        {"title": "Garbage collection missed", "category": "waste", "severity": "medium", "location": "Stellenbosch, Western Cape", "description": "Residential area garbage not collected for 2 weeks"},
        
        # Gauteng
        {"title": "Water leak on main road", "category": "water", "severity": "critical", "location": "Johannesburg, Gauteng", "description": "Major water leak causing flooding and traffic disruption"},
        {"title": "Multiple potholes on M1", "category": "pothole", "severity": "high", "location": "Johannesburg, Gauteng", "description": "Several large potholes on M1 highway causing accidents"},
        {"title": "Sewage overflow", "category": "water", "severity": "critical", "location": "Pretoria, Gauteng", "description": "Sewage overflow in residential area, health hazard"},
        
        # KwaZulu-Natal
        {"title": "Faulty traffic lights", "category": "other", "severity": "high", "location": "Durban, KwaZulu-Natal", "description": "Traffic lights not working at busy intersection"},
        {"title": "Waste dumping site", "category": "waste", "severity": "high", "location": "Pietermaritzburg, KwaZulu-Natal", "description": "Illegal waste dumping in public park"},
        
        # Eastern Cape
        {"title": "Road surface damage", "category": "pothole", "severity": "medium", "location": "Port Elizabeth, Eastern Cape", "description": "Road surface severely damaged after heavy rains"},
        {"title": "Water supply interruption", "category": "water", "severity": "critical", "location": "East London, Eastern Cape", "description": "No water supply for 3 days in residential area"},
        
        # Free State
        {"title": "Streetlight maintenance needed", "category": "streetlight", "severity": "low", "location": "Bloemfontein, Free State", "description": "Several streetlights need maintenance"},
        
        # North West
        {"title": "Garbage collection issue", "category": "waste", "severity": "medium", "location": "Rustenburg, North West", "description": "Inconsistent garbage collection service"},
        
        # Mpumalanga
        {"title": "Road repair needed", "category": "pothole", "severity": "medium", "location": "Nelspruit, Mpumalanga", "description": "Road needs repair after storm damage"},
        
        # Limpopo
        {"title": "Water quality concern", "category": "water", "severity": "high", "location": "Polokwane, Limpopo", "description": "Residents reporting brown water from taps"},
        
        # Northern Cape
        {"title": "Street maintenance", "category": "other", "severity": "low", "location": "Kimberley, Northern Cape", "description": "Street cleaning and maintenance needed"},
    ]
    
    # Get or create a sample user
    user, created = User.objects.get_or_create(
        username='sample_user',
        defaults={'email': 'sample@example.com'}
    )
    
    # Create sample reports
    for report_data in sample_reports:
        # Add some random time variation
        days_ago = random.randint(1, 30)
        created_at = timezone.now() - timedelta(days=days_ago)
        
        IssueReport.objects.create(
            reporter=user,
            title=report_data['title'],
            category=report_data['category'],
            description=report_data['description'],
            location=report_data['location'],
            severity=report_data['severity'],
            status=random.choice(['pending', 'in_progress', 'resolved']),
            created_at=created_at
        )


def hazard_alerts_api(request: HttpRequest) -> HttpResponse:
    """API endpoint for real-time GPS hazard alerts."""
    from django.http import JsonResponse
    import math
    
    # Get user's current location from request
    lat = request.GET.get('lat')
    lng = request.GET.get('lng')
    radius = float(request.GET.get('radius', 1000))  # Default 1km radius
    
    if not lat or not lng:
        return JsonResponse({'error': 'Latitude and longitude are required'}, status=400)
    
    try:
        user_lat = float(lat)
        user_lng = float(lng)
    except ValueError:
        return JsonResponse({'error': 'Invalid coordinates'}, status=400)
    
    # Haversine formula for distance calculation
    def haversine_distance(lat1, lng1, lat2, lng2):
        """Calculate distance between two points in meters using Haversine formula."""
        R = 6371000  # Earth's radius in meters
        
        lat1_rad = math.radians(lat1)
        lat2_rad = math.radians(lat2)
        delta_lat = math.radians(lat2 - lat1)
        delta_lng = math.radians(lng2 - lng1)
        
        a = (math.sin(delta_lat / 2) ** 2 + 
             math.cos(lat1_rad) * math.cos(lat2_rad) * 
             math.sin(delta_lng / 2) ** 2)
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
        
        return R * c
    
    # Get all active issues (not resolved/closed)
    active_issues = IssueReport.objects.exclude(
        status__in=['resolved', 'closed']
    ).filter(
        severity__in=['high', 'critical']  # Only alert for high/critical issues
    )
    
    nearby_hazards = []
    
    for issue in active_issues:
        # Generate coordinates for the issue (same logic as heatmap)
        import hashlib
        location_hash = hashlib.md5(issue.location.encode()).hexdigest()
        issue_lat = -26.2041 + (int(location_hash[:8], 16) / 0xffffffff - 0.5) * 2.0
        issue_lng = 28.0473 + (int(location_hash[8:16], 16) / 0xffffffff - 0.5) * 2.0
        
        # Calculate distance
        distance = haversine_distance(user_lat, user_lng, issue_lat, issue_lng)
        
        # Only include hazards within the specified radius
        if distance <= radius:
            # Determine alert level based on distance and severity
            if distance <= 50:  # Within 50 meters
                alert_level = 'immediate'
            elif distance <= 200:  # Within 200 meters
                alert_level = 'warning'
            else:  # Within radius but further away
                alert_level = 'info'
            
            nearby_hazards.append({
                'id': issue.id,
                'title': issue.title,
                'category': issue.get_category_display(),
                'severity': issue.get_severity_display(),
                'description': issue.description[:100] + '...' if len(issue.description) > 100 else issue.description,
                'location': issue.location,
                'distance': round(distance),
                'alert_level': alert_level,
                'lat': issue_lat,
                'lng': issue_lng,
                'created_at': issue.created_at.strftime('%Y-%m-%d %H:%M'),
            })
    
    # Sort by distance (closest first)
    nearby_hazards.sort(key=lambda x: x['distance'])
    
    return JsonResponse({
        'hazards': nearby_hazards,
        'user_location': {
            'lat': user_lat,
            'lng': user_lng
        },
        'radius': radius,
        'timestamp': timezone.now().isoformat()
    })