from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List, Optional
from prometheus_client import Counter, Histogram, generate_latest
from fastapi.responses import PlainTextResponse
import sqlite3
import uvicorn

app = FastAPI(title="SwiggyOps Notification Service")

# Prometheus metrics
request_counter = Counter("notification_requests_total", "Total requests", ["method", "endpoint"])
request_latency = Histogram("notification_request_latency_seconds", "Request latency")

# Database setup
def get_db():
    conn = sqlite3.connect("notifications.db")
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS notifications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            customer_id INTEGER NOT NULL,
            order_id INTEGER,
            type TEXT NOT NULL,
            message TEXT NOT NULL,
            channel TEXT NOT NULL,
            status TEXT DEFAULT 'sent',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    # Sample data
    conn.execute("INSERT OR IGNORE INTO notifications (id, customer_id, order_id, type, message, channel, status) VALUES (1, 101, 1, 'order_confirmed', 'Your order has been confirmed!', 'SMS', 'sent')")
    conn.execute("INSERT OR IGNORE INTO notifications (id, customer_id, order_id, type, message, channel, status) VALUES (2, 101, 1, 'order_delivered', 'Your order has been delivered!', 'Email', 'sent')")
    conn.commit()
    conn.close()

init_db()

# Models
class Notification(BaseModel):
    customer_id: int
    order_id: Optional[int] = None
    type: str
    message: str
    channel: str

# Notification Routes
@app.get("/notifications")
def get_notifications():
    request_counter.labels(method="GET", endpoint="/notifications").inc()
    conn = get_db()
    notifications = conn.execute("SELECT * FROM notifications").fetchall()
    conn.close()
    return [dict(n) for n in notifications]

@app.get("/notifications/{notification_id}")
def get_notification(notification_id: int):
    request_counter.labels(method="GET", endpoint="/notifications/id").inc()
    conn = get_db()
    notification = conn.execute("SELECT * FROM notifications WHERE id=?", (notification_id,)).fetchone()
    conn.close()
    if not notification:
        raise HTTPException(status_code=404, detail="Notification not found")
    return dict(notification)

@app.post("/notifications")
def send_notification(notification: Notification):
    request_counter.labels(method="POST", endpoint="/notifications").inc()
    conn = get_db()
    cursor = conn.execute(
        "INSERT INTO notifications (customer_id, order_id, type, message, channel, status) VALUES (?, ?, ?, ?, ?, ?)",
        (notification.customer_id, notification.order_id, notification.type, notification.message, notification.channel, "sent")
    )
    conn.commit()
    conn.close()
    return {"id": cursor.lastrowid, "message": "Notification sent!", "status": "sent"}

@app.get("/notifications/customer/{customer_id}")
def get_customer_notifications(customer_id: int):
    request_counter.labels(method="GET", endpoint="/notifications/customer").inc()
    conn = get_db()
    notifications = conn.execute("SELECT * FROM notifications WHERE customer_id=?", (customer_id,)).fetchall()
    conn.close()
    return [dict(n) for n in notifications]

@app.post("/notifications/order-confirmed")
def order_confirmed(order_id: int, customer_id: int):
    request_counter.labels(method="POST", endpoint="/notifications/order-confirmed").inc()
    conn = get_db()
    cursor = conn.execute(
        "INSERT INTO notifications (customer_id, order_id, type, message, channel, status) VALUES (?, ?, ?, ?, ?, ?)",
        (customer_id, order_id, "order_confirmed", f"Order #{order_id} confirmed!", "SMS", "sent")
    )
    conn.commit()
    conn.close()
    return {"message": "Order confirmation notification sent!"}

@app.post("/notifications/order-delivered")
def order_delivered(order_id: int, customer_id: int):
    request_counter.labels(method="POST", endpoint="/notifications/order-delivered").inc()
    conn = get_db()
    cursor = conn.execute(
        "INSERT INTO notifications (customer_id, order_id, type, message, channel, status) VALUES (?, ?, ?, ?, ?, ?)",
        (customer_id, order_id, "order_delivered", f"Order #{order_id} delivered!", "Email", "sent")
    )
    conn.commit()
    conn.close()
    return {"message": "Order delivery notification sent!"}

@app.get("/health")
def health():
    return {"status": "healthy", "service": "notification-service"}

@app.get("/metrics", response_class=PlainTextResponse)
def metrics():
    return generate_latest()

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8006)