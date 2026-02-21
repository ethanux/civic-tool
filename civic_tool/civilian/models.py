from django.db import models
from django.contrib.auth.models import User

# No custom auth models; using Django's built-in auth User model.


class IssueReport(models.Model):
    CATEGORY_CHOICES = [
        ("pothole", "Pothole"),
        ("waste", "Waste management"),
        ("streetlight", "Faulty streetlight"),
        ("water", "Water and sanitation"),
        ("other", "Other"),
    ]
    
    STATUS_CHOICES = [
        ("pending", "Pending Review"),
        ("in_progress", "In Progress"),
        ("resolved", "Resolved"),
        ("closed", "Closed"),
    ]
    
    SEVERITY_CHOICES = [
        ("low", "Low"),
        ("medium", "Medium"),
        ("high", "High"),
        ("critical", "Critical"),
    ]

    reporter = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name="issue_reports")
    title = models.CharField(max_length=200)
    category = models.CharField(max_length=32, choices=CATEGORY_CHOICES)
    description = models.TextField()
    location = models.CharField(max_length=255, help_text="Street address or description of the location")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
    severity = models.CharField(max_length=20, choices=SEVERITY_CHOICES, default="medium")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    image = models.ImageField(upload_to="issues/images/", null=True, blank=True)
    video = models.FileField(upload_to="issues/videos/", null=True, blank=True)

    def __str__(self):
        return f"{self.title} ({self.get_category_display()})"
