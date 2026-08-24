import uuid
from sqlalchemy.orm import Session

from app.db.models import Resource
from app.storage.cloudinary import delete_pdf, upload_pdf
from app.vector_store.qdrant import delete_resource_vectors


def create_resource(
    db: Session, user_id: int, name: str, subject: str, chapters: str | None,
    description: str | None, visibility: str, file,
) -> Resource:

    safe_name = (
        name.strip()
        .lower()
        .replace(" ", "_")
    )

    unique_id = uuid.uuid4().hex[:12]
    public_id = f"user_{user_id}_{safe_name}_{unique_id}"

    upload_result = upload_pdf(
        file=file,
        public_id=public_id,
    )

    cloudinary_url = upload_result["secure_url"]
    cloudinary_public_id = upload_result["public_id"]

    resource = Resource(
        user_id=user_id,
        name=name,
        subject=subject,
        chapters=chapters,
        description=description,
        cloudinary_url=cloudinary_url,
        cloudinary_public_id=cloudinary_public_id,
        visibility=visibility,
        status="uploaded",
    )

    db.add(resource)
    db.commit()
    db.refresh(resource)

    return resource


def get_resource(db: Session, resource_id: int) -> Resource | None:

    return (
        db.query(Resource)
        .filter(Resource.id == resource_id)
        .first()
    )


def get_resources(db: Session, user_id: int | None = None) -> list[Resource]:

    query = db.query(Resource)

    if user_id is not None:
        query = query.filter(Resource.user_id == user_id)

    return (
        query
        .order_by(Resource.created_at.desc())
        .all()
    )


# Delete a resource from all storage layers.
def delete_resource(db: Session, resource: Resource) -> None:
    # 1. Safely remove indexed vectors from Qdrant.
    try:
        delete_resource_vectors(resource_id=resource.id)
    except Exception as exc:
        print(f"[WARN] Failed to delete Qdrant vectors for resource {resource.id}: {exc}")

    # 2. Safely remove PDF from Cloudinary.
    try:
        delete_pdf(public_id=resource.cloudinary_public_id)
    except Exception as exc:
        print(f"[WARN] Failed to delete Cloudinary PDF for resource {resource.id}: {exc}")

    # 3. Always remove PostgreSQL record.
    db.delete(resource)
    db.commit()