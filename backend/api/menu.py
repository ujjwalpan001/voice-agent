"""
Menu management API.
Full CRUD for menu items and categories, plus bulk upload endpoint.
"""
import logging
import uuid
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File, Form
from backend.api.auth import get_current_admin
from backend.database.mongodb import get_menu_items_col, get_menu_categories_col
from backend.models.admin import AdminResponse
from backend.models.menu import MenuItem, MenuItemCreate, MenuItemUpdate, MenuCategory
from backend.rag.ingestion import ingest_document, ingest_menu_item_text

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/menu", tags=["Menu"])


# ─── Categories ───────────────────────────────────────────────────────────────

@router.get("/categories")
async def list_categories():
    col = get_menu_categories_col()
    cursor = col.find({}, {"_id": 0}).sort("display_order", 1)
    return await cursor.to_list(length=100)


@router.post("/categories", status_code=201)
async def create_category(
    category: MenuCategory,
    _: AdminResponse = Depends(get_current_admin),
):
    col = get_menu_categories_col()
    data = category.model_dump()
    await col.insert_one(data)
    return category


# ─── Menu Items ───────────────────────────────────────────────────────────────

@router.get("/items")
async def list_menu_items(
    category: Optional[str] = Query(None),
    available: Optional[bool] = Query(None),
    search: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
):
    col = get_menu_items_col()
    filter_doc = {}
    if category:
        filter_doc["category"] = {"$regex": category, "$options": "i"}
    if available is not None:
        filter_doc["available"] = available
    if search:
        filter_doc["$or"] = [
            {"name": {"$regex": search, "$options": "i"}},
            {"description": {"$regex": search, "$options": "i"}},
        ]
    skip = (page - 1) * limit
    total = await col.count_documents(filter_doc)
    cursor = col.find(filter_doc, {"_id": 0}).skip(skip).limit(limit)
    items = await cursor.to_list(length=limit)
    return {"items": items, "total": total, "page": page, "limit": limit}


@router.get("/items/{item_id}")
async def get_menu_item(item_id: str):
    col = get_menu_items_col()
    item = await col.find_one({"id": item_id}, {"_id": 0})
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    return item


@router.post("/items", status_code=201)
async def create_menu_item(
    item: MenuItemCreate,
    _: AdminResponse = Depends(get_current_admin),
):
    col = get_menu_items_col()
    new_item = MenuItem(**item.model_dump())
    await col.insert_one(new_item.model_dump())

    # Index in RAG
    try:
        await ingest_menu_item_text(
            item_id=new_item.id,
            name=new_item.name,
            description=new_item.description or "",
            category=new_item.category,
            ingredients=new_item.ingredients,
            dietary_tags=new_item.dietary_tags,
        )
    except Exception as e:
        logger.warning(f"RAG ingestion failed for {new_item.name}: {e}")

    return new_item


@router.put("/items/{item_id}")
async def update_menu_item(
    item_id: str,
    updates: MenuItemUpdate,
    _: AdminResponse = Depends(get_current_admin),
):
    col = get_menu_items_col()
    existing = await col.find_one({"id": item_id})
    if not existing:
        raise HTTPException(status_code=404, detail="Item not found")

    update_data = {k: v for k, v in updates.model_dump().items() if v is not None}
    update_data["updated_at"] = datetime.utcnow()
    await col.update_one({"id": item_id}, {"$set": update_data})

    updated = await col.find_one({"id": item_id}, {"_id": 0})

    # Re-index in RAG
    try:
        await ingest_menu_item_text(
            item_id=item_id,
            name=updated.get("name", ""),
            description=updated.get("description", ""),
            category=updated.get("category", ""),
            ingredients=updated.get("ingredients", []),
            dietary_tags=updated.get("dietary_tags", []),
        )
    except Exception as e:
        logger.warning(f"RAG re-index failed: {e}")

    return updated


@router.delete("/items/{item_id}", status_code=204)
async def delete_menu_item(
    item_id: str,
    _: AdminResponse = Depends(get_current_admin),
):
    col = get_menu_items_col()
    result = await col.delete_one({"id": item_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Item not found")

    # Remove from vector store
    from backend.rag.vector_store import vector_store
    try:
        vector_store.delete_by_ids([f"menu_item_{item_id}"])
    except Exception:
        pass


# ─── Bulk Upload ──────────────────────────────────────────────────────────────

@router.post("/upload")
async def upload_menu_document(
    file: UploadFile = File(...),
    source_type: str = Form("menu"),
    _: AdminResponse = Depends(get_current_admin),
):
    """
    Upload a PDF, image, CSV, Excel, or JSON menu document.
    Extracts text, chunks it, and stores it in the vector DB for RAG.
    """
    allowed_types = {
        "application/pdf", "image/png", "image/jpeg", "image/webp",
        "text/csv", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "application/json",
    }
    if file.content_type not in allowed_types and not file.filename.endswith(
        (".pdf", ".png", ".jpg", ".jpeg", ".csv", ".xlsx", ".json")
    ):
        raise HTTPException(status_code=400, detail="Unsupported file type")

    file_bytes = await file.read()
    try:
        chunk_count = await ingest_document(
            file_bytes=file_bytes,
            filename=file.filename,
            source_type=source_type,
        )
        return {
            "success": True,
            "filename": file.filename,
            "chunks_ingested": chunk_count,
        }
    except Exception as e:
        logger.error(f"Document ingestion error: {e}")
        raise HTTPException(status_code=500, detail=f"Ingestion failed: {str(e)}")
