from decimal import Decimal
from rest_framework import serializers
from urllib.parse import urlparse

class CoordinateField(serializers.Field):
    """
    A versatile GPS coordinate serializer field that accepts integers, floats,
    decimals, or strings on input, and returns normalized numeric float values
    without trailing zeros on output.
    """
    def to_internal_value(self, data):
        if data is None or data == '':
            return None
        try:
            val = Decimal(str(data).strip())
            return val
        except Exception:
            raise serializers.ValidationError("Enter a valid coordinate number.")

    def to_representation(self, value):
        if value is None:
            return None
        try:
            d = Decimal(str(value))
            formatted_str = f"{d.normalize():f}"
            if '.' in formatted_str:
                formatted_str = formatted_str.rstrip('0').rstrip('.')
            return float(formatted_str)
        except Exception:
            try:
                return float(value)
            except Exception:
                return value


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
