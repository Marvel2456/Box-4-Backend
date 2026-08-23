import os
import uuid
from django.core.files.storage import default_storage
from rest_framework import generics, permissions, status
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.response import Response
from rest_framework import serializers
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi

from core.image_processing import process_and_convert_to_webp


class DirectMediaUploadSerializer(serializers.Serializer):
    file = serializers.FileField(required=False, help_text="Media or image file to upload.")
    image = serializers.ImageField(required=False, help_text="Image file to upload.")
    media = serializers.FileField(required=False, help_text="Media file to upload.")
    folder = serializers.CharField(required=False, default="uploads", help_text="Optional destination subfolder under media/ (e.g. 'profiles', 'listings', 'categories').")


class DirectMediaUploadView(generics.GenericAPIView):
    permission_classes = [permissions.IsAuthenticated]
    parser_classes = (MultiPartParser, FormParser)
    serializer_class = DirectMediaUploadSerializer

    @swagger_auto_schema(
        operation_description="Direct media/image upload endpoint. Automatically processes images via image_processing pipeline (EXIF auto-orientation, aspect ratio resize, WebP conversion) and returns the public media file URL to use in JSON payloads.",
        manual_parameters=[
            openapi.Parameter(
                name='file',
                in_=openapi.IN_FORM,
                description='Media or image file to upload.',
                type=openapi.TYPE_FILE,
                required=False
            ),
            openapi.Parameter(
                name='image',
                in_=openapi.IN_FORM,
                description='Image file to upload.',
                type=openapi.TYPE_FILE,
                required=False
            ),
            openapi.Parameter(
                name='media',
                in_=openapi.IN_FORM,
                description='Media file to upload.',
                type=openapi.TYPE_FILE,
                required=False
            ),
            openapi.Parameter(
                name='folder',
                in_=openapi.IN_FORM,
                description="Optional subfolder path under media/ e.g. 'profiles', 'listings', 'categories' (default: 'uploads').",
                type=openapi.TYPE_STRING,
                required=False
            ),
        ],
        consumes=['multipart/form-data'],
        responses={
            201: openapi.Response(
                description="File uploaded and processed successfully.",
                examples={
                    "application/json": {
                        "message": "File uploaded and processed successfully.",
                        "url": "http://localhost:8000/media/uploads/unique_filename.webp",
                        "relative_url": "/media/uploads/unique_filename.webp",
                        "filename": "unique_filename.webp",
                        "size_bytes": 104520,
                        "content_type": "image/webp"
                    }
                }
            )
        }
    )
    def post(self, request, *args, **kwargs):
        uploaded_file = (
            request.FILES.get('file') or
            request.FILES.get('image') or
            request.FILES.get('media')
        )

        if not uploaded_file:
            return Response(
                {"error": "No file was uploaded. Please provide a file under parameter key 'file', 'image', or 'media'."},
                status=status.HTTP_400_BAD_REQUEST
            )

        folder = request.data.get('folder', 'uploads').strip('/\\')
        if not folder:
            folder = 'uploads'

        # Check if the uploaded file is an image
        filename = uploaded_file.name
        ext = os.path.splitext(filename)[1].lower()
        image_extensions = ['.jpg', '.jpeg', '.png', '.webp', '.heic', '.bmp', '.tiff', '.gif']

        # Process image using image_processing pipeline if it's an image
        if ext in image_extensions or (uploaded_file.content_type and uploaded_file.content_type.startswith('image/')):
            processed_file = process_and_convert_to_webp(uploaded_file)
        else:
            processed_file = uploaded_file

        # Generate a unique filename to prevent overwriting
        base_name, file_ext = os.path.splitext(os.path.basename(processed_file.name))
        unique_filename = f"{base_name}_{uuid.uuid4().hex[:8]}{file_ext}"
        storage_path = os.path.join(folder, unique_filename)

        # Save to storage (works with local disk or cloud bucket like S3 / R2)
        saved_path = default_storage.save(storage_path, processed_file)
        relative_url = default_storage.url(saved_path)
        if relative_url.startswith('http://') or relative_url.startswith('https://'):
            full_url = relative_url
        else:
            full_url = request.build_absolute_uri(relative_url)

        return Response({
            "message": "File uploaded and processed successfully.",
            "url": full_url,
            "relative_url": relative_url,
            "filename": os.path.basename(saved_path),
            "size_bytes": getattr(processed_file, 'size', 0),
            "content_type": getattr(processed_file, 'content_type', 'image/webp' if file_ext == '.webp' else 'application/octet-stream')
        }, status=status.HTTP_201_CREATED)
