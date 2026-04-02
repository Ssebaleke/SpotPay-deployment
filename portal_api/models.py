from django.db import models

class PortalTemplate(models.Model):
    LOGIN_TYPES = (
        ('PLAIN', 'Plain (username = password)'),
        ('NONE', 'None (username only, blank password)'),
        ('CHAP', 'CHAP MD5 (username ≠ password)'),
        ('SEPARATE', 'Separate username & password'),
    )

    name = models.CharField(max_length=100, default="Default Portal")
    login_type = models.CharField(max_length=10, choices=LOGIN_TYPES, default='PLAIN')
    zip_file = models.FileField(upload_to="portal_templates/")
    uploaded_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.name} ({self.get_login_type_display()})"
