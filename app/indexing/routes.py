from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.indexing.service import index_resource
from app.resources.service import get_resource


router = APIRouter(
    prefix="/api/resources",
    tags=["Indexing"],
)


# Index a resource into the Qdrant vector store.
@router.post("/{resource_id}/index")
def index_resource_endpoint(resource_id: int, db: Session = Depends(get_db)):
    resource = get_resource(db=db, resource_id=resource_id)

    if resource is None:
        raise HTTPException(status_code=404, detail="Resource not found")

    if resource.status == "indexed":
        return {
            "message": "Resource is already indexed.",
            "resource_id": resource.id,
            "status": resource.status,
        }

    try:
        chunk_count = index_resource(
            db=db,
            resource=resource,
        )

        return {
            "message": "Resource indexed successfully.",
            "resource_id": resource.id,
            "status": resource.status,
            "chunks_indexed": chunk_count,
        }

    except HTTPException:
        raise
    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail=f"Indexing failed: {str(error)}",
        )