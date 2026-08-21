import os
import cloudinary
import cloudinary.uploader
from dotenv import load_dotenv


load_dotenv()


CLOUDINARY_CLOUD_NAME = os.getenv("CLOUDINARY_CLOUD_NAME")
CLOUDINARY_API_KEY = os.getenv("CLOUDINARY_API_KEY")
CLOUDINARY_API_SECRET = os.getenv("CLOUDINARY_API_SECRET")


if not CLOUDINARY_CLOUD_NAME:
    raise RuntimeError(
        "CLOUDINARY_CLOUD_NAME is not configured."
    )

if not CLOUDINARY_API_KEY:
    raise RuntimeError(
        "CLOUDINARY_API_KEY is not configured."
    )

if not CLOUDINARY_API_SECRET:
    raise RuntimeError(
        "CLOUDINARY_API_SECRET is not configured."
    )


cloudinary.config(
    cloud_name=CLOUDINARY_CLOUD_NAME,
    api_key=CLOUDINARY_API_KEY,
    api_secret=CLOUDINARY_API_SECRET,
    secure=True,
)


def upload_pdf(file, public_id: str, folder: str = "academicstack/resources"):
    result = cloudinary.uploader.upload(
        file.file,
        resource_type="raw",
        folder=folder,
        public_id=public_id,
        overwrite=False,
    )

    return result


def delete_pdf(public_id: str):
    result = cloudinary.uploader.destroy(
        public_id,
        resource_type="image",
        invalidate=True,
    )

    return result