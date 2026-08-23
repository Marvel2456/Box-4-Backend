import io
from PIL import Image
from django.test import TestCase
from django.core.files.uploadedfile import SimpleUploadedFile
from core.image_processing import process_and_convert_to_webp

class ImageProcessingTest(TestCase):
    def test_convert_png_to_webp_high_quality(self):
        # Create a 2000x2000 PNG image in memory
        image_io = io.BytesIO()
        img = Image.new('RGB', (2000, 2000), color='blue')
        img.save(image_io, format='PNG')
        image_io.seek(0)

        uploaded_file = SimpleUploadedFile(
            name="test_photo.png",
            content=image_io.getvalue(),
            content_type="image/png"
        )

        # Process image
        converted_file = process_and_convert_to_webp(uploaded_file, max_dimension=1000, quality=90)

        # Assertions
        self.assertTrue(converted_file.name.endswith('.webp'))
        
        # Verify output Pillow properties
        result_img = Image.open(converted_file)
        self.assertEqual(result_img.format, 'WEBP')
        self.assertLessEqual(result_img.width, 1000)
        self.assertLessEqual(result_img.height, 1000)


from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import RefreshToken

User = get_user_model()

class DirectMediaUploadAPITest(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="uploader@example.com",
            username="uploader@example.com",
            password="securepassword123",
            full_name="Media Uploader"
        )
        self.token = str(RefreshToken.for_user(self.user).access_token)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.token}')

    def test_direct_media_upload_view(self):
        image_io = io.BytesIO()
        img = Image.new('RGB', (800, 600), color='red')
        img.save(image_io, format='JPEG')
        image_io.seek(0)

        uploaded_file = SimpleUploadedFile(
            name="avatar.jpg",
            content=image_io.getvalue(),
            content_type="image/jpeg"
        )

        url = reverse('media-upload')
        response = self.client.post(url, {'file': uploaded_file, 'folder': 'profiles'}, format='multipart')

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn('url', response.data)
        self.assertIn('filename', response.data)
        self.assertTrue(response.data['filename'].endswith('.webp'))
        self.assertIn('/profiles/', response.data['url'])
