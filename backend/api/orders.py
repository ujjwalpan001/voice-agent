"""
Orders API – order listing, detail, and status updates.
"""
from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from backend.api.auth import get_current_admin
from backend.database.mongodb import get_orders_col
from backend.models.admin import AdminResponse
from backend.models.order import OrderStatusUpdate

router = APIRouter(prefix="/orders", tags=["Orders"])


@router.get("")
async def list_orders(
    status: Optional[str] = Query(None),
    customer_phone: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    _: AdminResponse = Depends(get_current_admin),
):
    col = get_orders_col()
    filter_doc = {}
    if status:
        filter_doc["status"] = status
    if customer_phone:
        filter_doc["customer_phone"] = customer_phone
    skip = (page - 1) * limit
    total = await col.count_documents(filter_doc)
    cursor = col.find(filter_doc, {"_id": 0}).sort("created_at", -1).skip(skip).limit(limit)
    items = await cursor.to_list(length=limit)
    return {"orders": items, "total": total, "page": page, "limit": limit}


@router.get("/{order_id}")
async def get_order(
    order_id: str,
    _: AdminResponse = Depends(get_current_admin),
):
    col = get_orders_col()
    order = await col.find_one({"id": order_id}, {"_id": 0})
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    return order


@router.patch("/{order_id}/status")
async def update_order_status(
    order_id: str,
    body: OrderStatusUpdate,
    _: AdminResponse = Depends(get_current_admin),
):
    col = get_orders_col()
    result = await col.update_one(
        {"id": order_id},
        {"$set": {"status": body.status, "updated_at": datetime.utcnow()}},
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Order not found")
    return {"success": True, "order_id": order_id, "status": body.status}


@router.get("/stats/summary")
async def order_stats(_: AdminResponse = Depends(get_current_admin)):
    col = get_orders_col()
    pipeline = [
        {
            "$group": {
                "_id": "$status",
                "count": {"$sum": 1},
                "revenue": {"$sum": "$grand_total"},
            }
        }
    ]
    result = await col.aggregate(pipeline).to_list(length=20)
    stats = {r["_id"]: {"count": r["count"], "revenue": r["revenue"]} for r in result}
    total_orders = sum(v["count"] for v in stats.values())
    total_revenue = sum(v["revenue"] for v in stats.values())
    return {
        "total_orders": total_orders,
        "total_revenue": round(total_revenue, 2),
        "by_status": stats,
    }
