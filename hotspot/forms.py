# hotspot/forms.py
from django import forms
from .models import HotspotLocation

class HotspotLocationForm(forms.ModelForm):
    """Form for vendors to add new locations"""
    
    class Meta:
        model = HotspotLocation
        fields = ['site_name', 'location_type', 'address', 'town_city']
        widgets = {
            'address': forms.Textarea(attrs={'rows': 3, 'placeholder': 'Full physical address'}),
            'site_name': forms.TextInput(attrs={'placeholder': 'e.g., Tech Cafe Westlands'}),
            'town_city': forms.TextInput(attrs={'placeholder': 'e.g., Nairobi'}),
        }
    
    def save(self, commit=True, vendor=None):
        """Save with vendor and pending status"""
        location = super().save(commit=False)
        if vendor:
            location.vendor = vendor
            location.status = 'PENDING'  # Always start as pending
        
        if commit:
            location.save()
        
        return location