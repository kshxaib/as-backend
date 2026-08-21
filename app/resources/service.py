import uuid
from sqlalchemy.orm import Session

from app.db.models import Resource
from app.storage.cloudinary import delete_pdf, upload_pdf


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


def delete_resource(db: Session, resource: Resource) -> None:

    delete_pdf(public_id=resource.cloudinary_public_id)

    db.delete(resource)
    db.commit()