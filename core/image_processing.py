import os
import io
from PIL import Image, ImageOps
from django.core.files.base import ContentFile

def process_and_convert_to_webp(image_field_file, max_dimension=1920, quality=88):
    """
    Image Processing Pipeline:
    1. Auto-orients image based on camera EXIF tags (fixes iPhone/Android rotation).
    2. Resizes large images maintaining exact aspect ratio using LANCZOS filter.
    3. Converts image to WebP format.
    4. Compresses with high visual quality (quality=88-90, optimize=True, method=6).
    5. Returns a ContentFile ready for Django model saving / Cloudflare R2 upload.
    """
    if not image_field_file:
        return image_field_file

    # If it's already a WebP image, skip or process if unoptimized
    try:
        # Open image with Pillow
        img = Image.open(image_field_file)

        # 1. EXIF Auto-orientation (Fixes rotated mobile uploads)
        try:
            img = ImageOps.exif_transpose(img)
        except Exception:
            pass

        # 2. Color mode handling
        if img.mode in ('RGBA', 'LA') or (img.mode == 'P' and 'transparency' in img.info):
            img = img.convert('RGBA')
        else:
            img = img.convert('RGB')

        # 3. High Quality Aspect Ratio Resizing (LANCZOS Filter)
        width, height = img.size
        if width > max_dimension or height > max_dimension:
            if width > height:
                new_width = max_dimension
                new_height = int(height * (max_dimension / width))
            else:
                new_height = max_dimension
                new_width = int(width * (max_dimension / height))
            img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)

        # 4. WebP Encoding & Compression (Lossless quality preservation)
        output_buffer = io.BytesIO()
        img.save(
            output_buffer,
            format='WEBP',
            quality=quality,
            optimize=True,
            method=6
        )
        output_buffer.seek(0)

        # 5. Extract original filename and replace extension with .webp
        original_name = os.path.basename(image_field_file.name)
        base_name = os.path.splitext(original_name)[0]
        new_filename = f"{base_name}.webp"

        return ContentFile(output_buffer.getvalue(), name=new_filename)

    except Exception as e:
        # Fallback to original image if processing encounters unexpected format
        return image_field_file
