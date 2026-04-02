from django.db import models

class PortalTemplate(models.Model):
    name = models.CharField(max_length=100, default="Default Portal")
    zip_file = models.FileField(upload_to="portal_templates/")
    uploaded_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.name
