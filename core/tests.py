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
