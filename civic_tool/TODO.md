# TODO: Add Image and Video Upload to Report Issue Page

- [ ] Update IssueReport model in civilian/models.py to add image and video fields
- [ ] Update settings.py to add MEDIA_URL and MEDIA_ROOT
- [ ] Update urls.py to serve media files during development
- [ ] Update report_issue view in civilian/views.py to handle file uploads and validate video length (max 6 seconds)
- [ ] Update report_issue.html template to add file input fields and set enctype="multipart/form-data"
- [ ] Run makemigrations and migrate for the new model fields
- [ ] Test the upload functionality
