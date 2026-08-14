"""Persistent/local upload storage abstraction for Ri Burom."""
import io
import os
import re
import uuid
from urllib.parse import urlparse

from PIL import Image, UnidentifiedImageError

MAX_IMAGE_DIMENSION = 1600
ALLOWED_IMAGE_EXTENSIONS = {'png', 'jpg', 'jpeg', 'webp'}
ALLOWED_PDF_EXTENSIONS = {'pdf'}
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
DEFAULT_UPLOAD_FOLDER = os.path.join(BASE_DIR, 'static', 'uploads')
PROTECTED_STATIC_FILES = {'default.jpg', 'logo.png', 'manifest.json', 'robots.txt', 'sw.js'}


def _meaningful(value):
    return bool(value and value.strip() and not value.strip().lower().startswith('your-') and value.strip().lower() not in {'replace-me', 'change-me'})


def _cloudinary_configured():
    explicit = os.environ.get('USE_CLOUDINARY', '').strip().lower() in {'1', 'true', 'yes', 'on'}
    app_env = os.environ.get('APP_ENV', 'production').strip().lower()
    has_url = _meaningful(os.environ.get('CLOUDINARY_URL'))
    has_fields = all(_meaningful(os.environ.get(key)) for key in ('CLOUDINARY_CLOUD_NAME', 'CLOUDINARY_API_KEY', 'CLOUDINARY_API_SECRET'))
    if app_env in {'development', 'dev', 'testing', 'test'}:
        return explicit and (has_url or has_fields)
    return has_url or has_fields


USING_CLOUDINARY = _cloudinary_configured()

if USING_CLOUDINARY:
    import cloudinary
    import cloudinary.uploader

    if not os.environ.get('CLOUDINARY_URL'):
        cloudinary.config(
            cloud_name=os.environ['CLOUDINARY_CLOUD_NAME'],
            api_key=os.environ['CLOUDINARY_API_KEY'],
            api_secret=os.environ['CLOUDINARY_API_SECRET'],
            secure=True,
        )
    else:
        cloudinary.config(secure=True)

STORAGE_BACKEND = 'Cloudinary' if USING_CLOUDINARY else 'Local disk (development)'


def allowed_file(filename, allowed_set):
    return bool(filename and '.' in filename and filename.rsplit('.', 1)[1].lower() in allowed_set)


def _compress_image(file_storage, ext):
    try:
        image = Image.open(file_storage.stream)
        image.verify()
        file_storage.stream.seek(0)
        image = Image.open(file_storage.stream)
    except (UnidentifiedImageError, OSError) as exc:
        raise ValueError('The uploaded file is not a valid image.') from exc

    try:
        image = Image.exif_transpose(image)
    except Exception:
        pass

    if ext in ('jpg', 'jpeg'):
        image = image.convert('RGB')
    elif image.mode not in ('RGB', 'RGBA'):
        image = image.convert('RGBA')

    if max(image.size) > MAX_IMAGE_DIMENSION:
        image.thumbnail((MAX_IMAGE_DIMENSION, MAX_IMAGE_DIMENSION), Image.LANCZOS)

    save_kwargs = (
        {'quality': 85, 'optimize': True}
        if ext in ('jpg', 'jpeg', 'webp') else {'optimize': True}
    )
    pillow_format = 'JPEG' if ext in ('jpg', 'jpeg') else ext.upper()
    return image, save_kwargs, pillow_format


def save_image(file_storage, upload_folder=DEFAULT_UPLOAD_FOLDER):
    if not file_storage or not file_storage.filename:
        return None
    if not allowed_file(file_storage.filename, ALLOWED_IMAGE_EXTENSIONS):
        raise ValueError('Supported image types are jpg, png, and webp.')

    ext = file_storage.filename.rsplit('.', 1)[1].lower()
    image, save_kwargs, pillow_format = _compress_image(file_storage, ext)

    if USING_CLOUDINARY:
        buf = io.BytesIO()
        image.save(buf, format=pillow_format, **save_kwargs)
        buf.seek(0)
        result = cloudinary.uploader.upload(buf, resource_type='image', folder='riburom')
        return result['secure_url']

    os.makedirs(upload_folder, exist_ok=True)
    safe_name = f"{uuid.uuid4().hex}.{ext}"
    image.save(os.path.join(upload_folder, safe_name), format=pillow_format, **save_kwargs)
    return f'uploads/{safe_name}'



def save_generated_png(png_bytes, upload_folder=DEFAULT_UPLOAD_FOLDER):
    """Persist a generated PNG (such as an Instagram QR code)."""
    if not png_bytes:
        return None
    if USING_CLOUDINARY:
        buf = io.BytesIO(png_bytes)
        result = cloudinary.uploader.upload(buf, resource_type='image', folder='riburom/generated')
        return result['secure_url']
    os.makedirs(upload_folder, exist_ok=True)
    safe_name = f"{uuid.uuid4().hex}.png"
    with open(os.path.join(upload_folder, safe_name), 'wb') as fh:
        fh.write(png_bytes)
    return f'uploads/{safe_name}'

def save_pdf(file_storage, upload_folder=DEFAULT_UPLOAD_FOLDER):
    if not file_storage or not file_storage.filename:
        return None
    if not allowed_file(file_storage.filename, ALLOWED_PDF_EXTENSIONS):
        raise ValueError('Only PDF documents are supported.')

    header = file_storage.stream.read(5)
    file_storage.stream.seek(0)
    if header != b'%PDF-':
        raise ValueError('The uploaded file does not appear to be a valid PDF.')

    if USING_CLOUDINARY:
        result = cloudinary.uploader.upload(
            file_storage, resource_type='raw', folder='riburom', format='pdf'
        )
        return result['secure_url']

    os.makedirs(upload_folder, exist_ok=True)
    safe_name = f"{uuid.uuid4().hex}.pdf"
    file_storage.save(os.path.join(upload_folder, safe_name))
    return f'uploads/{safe_name}'


def _cloudinary_public_id(value):
    """Extract the Cloudinary public id from image/raw secure URLs."""
    parsed = urlparse(value)
    path = parsed.path
    match = re.search(r'/upload/(?:v\d+/)?(.+)$', path)
    if not match:
        return None
    public_id = match.group(1)
    public_id = public_id.rsplit('.', 1)[0]
    return public_id


def delete_media(value):
    """Delete a stored media object; safe to call with blank/missing values."""
    if not value or os.path.basename(str(value)) in PROTECTED_STATIC_FILES:
        return

    try:
        if value.startswith('http://') or value.startswith('https://'):
            if not USING_CLOUDINARY:
                return
            public_id = _cloudinary_public_id(value)
            if not public_id:
                return
            resource_type = 'raw' if '/raw/upload/' in value else 'image'
            cloudinary.uploader.destroy(
                public_id,
                resource_type=resource_type,
                invalidate=True,
            )
            return

        relative = value.replace('\\', '/').lstrip('/')
        static_root = os.path.realpath(os.path.join(BASE_DIR, 'static'))
        local_path = os.path.realpath(os.path.join(static_root, relative))
        if os.path.commonpath([static_root, local_path]) != static_root:
            return
        if os.path.exists(local_path):
            os.remove(local_path)
        else:
            legacy_path = os.path.realpath(os.path.join(static_root, os.path.basename(relative)))
            if os.path.commonpath([static_root, legacy_path]) == static_root and os.path.exists(legacy_path) and os.path.basename(relative) not in PROTECTED_STATIC_FILES:
                os.remove(legacy_path)
    except Exception:
        # Media cleanup should never prevent a database update/delete from completing.
        return


def imgsrc(value, default='default.jpg'):
    if not value:
        value = default
    if value.startswith('http://') or value.startswith('https://'):
        return value
    return f'/static/{value}'
