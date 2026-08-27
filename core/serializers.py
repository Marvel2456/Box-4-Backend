from rest_framework import serializers
from urllib.parse import urlparse

class FlexibleImageField(serializers.ImageField):
    """
    A versatile ImageField serializer field that accepts BOTH:
    1. A direct binary file upload (File / Image), AND
    2. A URL string / relative media path string from POST /api/v1/media/upload/.
    """
    def to_internal_value(self, data):
        if isinstance(data, str) and data.strip():
            clean_path = data.strip()
            if '/media/' in clean_path:
                clean_path = clean_path.split('/media/', 1)[1]
            elif clean_path.startswith('http://') or clean_path.startswith('https://'):
                clean_path = urlparse(clean_path).path.lstrip('/')
            return clean_path
        return super().to_internal_value(data)
