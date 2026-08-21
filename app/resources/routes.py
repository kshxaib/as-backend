from typing import Literal

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.resources.schemas import ResourceListResponse, ResourceResponse
from app.resources.service import create_resource, delete_resource, get_resource, get_resources



router = APIRouter(
    prefix="/api/resources",
    tags=["Resources"],
)

# Upload a PDF resource.
# Steps:
#         1. Validate the uploaded file.
#         2. Send PDF to Cloudinary.
#         3. Store Cloudinary references in PostgreSQL.
#         4. Return resource metadata.
@router.post("", response_model=ResourceResponse)
def create_resource_endpoint(
    user_id: int = Form(...),
    name: str = Form(...),
    subject: str = Form(...),
    chapters: str | None = Form(None),
    description: str | None = Form(None),
    visibility: Literal["private", "community"] = Form("private"),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):

    # Validate file extension.
    if not file.filename:
        raise HTTPException(
            status_code=400,
            detail="A file is required.",
        )

    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(
            status_code=400,
            detail="Only PDF files are allowed.",
        )

    resource = create_resource(
        db=db,
        user_id=user_id,
        name=name,
        subject=subject,
        chapters=chapters,
        description=description,
        visibility=visibility,
        file=file,
    )

    return resource



# Fetch all resources.
@router.get("", response_model=ResourceListResponse)
def list_resources_endpoint(user_id: int | None = None, db: Session = Depends(get_db)):

    resources = get_resources(db=db, user_id=user_id)

    return {
        "resources": resources,
    }



# Fetch a single resource.
@router.get("/{resource_id}", response_model=ResourceResponse)
def get_resource_endpoint( resource_id: int, db: Session = Depends(get_db),):

    resource = get_resource(db=db, resource_id=resource_id)

    if resource is None:
        raise HTTPException(
            status_code=404,
            detail="Resource not found",
        )

    return resource


# Delete a resource.
@router.delete("/{resource_id}")
def delete_resource_endpoint(resource_id: int, db: Session = Depends(get_db)):

    resource = get_resource(db=db, resource_id=resource_id)

    if resource is None:
        raise HTTPException(
            status_code=404,
            detail="Resource not found",
        )

    delete_resource(db=db,resource=resource)

    return {
        "message": "Resource deleted successfully",
        "resource_id": resource_id,
    }