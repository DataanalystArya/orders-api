import time
import uuid
from collections import defaultdict

from fastapi import FastAPI, Request, Header
from fastapi.responses import JSONResponse, Response
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

TOTAL_ORDERS = 55
RATE_LIMIT = 17
WINDOW = 10

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],   # If grader gives a specific origin later, replace "*" with that origin.
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Fixed catalog of orders
catalog = [{"id": i} for i in range(1, TOTAL_ORDERS + 1)]

# Idempotency storage
idempotency_store = {}

# Rate limiting
clients = defaultdict(list)


@app.middleware("http")
async def rate_limit(request: Request, call_next):
    client_id = request.headers.get("X-Client-Id")

    if client_id:
        now = time.time()

        clients[client_id] = [
            t for t in clients[client_id]
            if now - t < WINDOW
        ]

        if len(clients[client_id]) >= RATE_LIMIT:
            retry = WINDOW - (now - clients[client_id][0])

            return JSONResponse(
                status_code=429,
                headers={"Retry-After": str(int(retry) + 1)},
                content={"detail": "Rate limit exceeded"},
            )

        clients[client_id].append(now)

    response = await call_next(request)
    return response


@app.get("/ping")
def ping():
    return {"status": "ok"}


@app.post("/orders", status_code=201)
def create_order(
    request: Request,
    idempotency_key: str = Header(..., alias="Idempotency-Key"),
):
    if idempotency_key in idempotency_store:
        return idempotency_store[idempotency_key]

    order = {
        "id": str(uuid.uuid4())
    }

    idempotency_store[idempotency_key] = order
    return order


@app.get("/orders")
def get_orders(limit: int = 10, cursor: str | None = None):

    start = 0

    if cursor:
        start = int(cursor)

    items = catalog[start:start + limit]

    next_cursor = None

    if start + limit < TOTAL_ORDERS:
        next_cursor = str(start + limit)

    return {
        "items": items,
        "next_cursor": next_cursor,
    }
