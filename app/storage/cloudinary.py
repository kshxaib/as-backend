import os
import cloudinary
import cloudinary.uploader
import cloudinary.utils
import requests
from dotenv import load_dotenv

load_dotenv()

CLOUDINARY_CLOUD_NAME = os.getenv("CLOUDINARY_CLOUD_NAME")
CLOUDINARY_API_KEY = os.getenv("CLOUDINARY_API_KEY")
CLOUDINARY_API_SECRET = os.getenv("CLOUDINARY_API_SECRET")

if not CLOUDINARY_CLOUD_NAME:
    raise RuntimeError("CLOUDINARY_CLOUD_NAME is not configured.")

if not CLOUDINARY_API_KEY:
    raise RuntimeError("CLOUDINARY_API_KEY is not configured.")

if not CLOUDINARY_API_SECRET:
    raise RuntimeError("CLOUDINARY_API_SECRET is not configured.")

cloudinary.config(
    cloud_name=CLOUDINARY_CLOUD_NAME,
    api_key=CLOUDINARY_API_KEY,
    api_secret=CLOUDINARY_API_SECRET,
    secure=True,
)


def upload_pdf(file, public_id: str, folder: str = "academicstack/resources"):
    clean_id = public_id if public_id.endswith(".pdf") else f"{public_id}.pdf"

    result = cloudinary.uploader.upload(
        file.file,
        resource_type="raw",
        access_mode="public",
        type="upload",
        folder=folder,
        public_id=clean_id,
        overwrite=True,
    )

    return result


def delete_pdf(public_id: str):
    result = cloudinary.uploader.destroy(
        public_id,
        resource_type="raw",
        invalidate=True,
    )

    return result


def get_download_url(public_id: str, resource_type: str = "raw") -> str:
    """Generate signed download URL for restricted Cloudinary delivery."""
    url = cloudinary.utils.private_download_url(
        public_id=public_id,
        format="",
        resource_type=resource_type,
        type="upload",
    )
    return url


def download_file_bytes(public_id: str, direct_url: str | None = None, resource_type: str = "raw") -> bytes:
    """Safely fetch file bytes using signed download URL or fallback direct URL."""
    try:
        signed_url = get_download_url(public_id=public_id, resource_type=resource_type)
        r = requests.get(signed_url, timeout=60)
        if r.status_code == 200 and len(r.content) > 0:
            return r.content
    except Exception:
        pass

    if direct_url:
        r = requests.get(direct_url, timeout=60)
        r.raise_for_status()
        return r.content

    raise ValueError("Could not download file from storage.")