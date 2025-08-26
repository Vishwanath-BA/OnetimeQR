from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from datetime import datetime
import uuid
import os
from pymongo import MongoClient
import certifi

# ---------------- MongoDB Connection ----------------
MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017/")
DB_NAME = os.getenv("DB_NAME", "Onetimeqr")
COLLECTION_NAME = "qr_codes"

client = MongoClient(MONGO_URI, tlsCAFile=certifi.where())
db = client[DB_NAME]
collection = db[COLLECTION_NAME]

# ---------------- FastAPI App ----------------
app = FastAPI()

def claim_qr_logic(qr_id: str):
    qr_doc = collection.find_one({"id": qr_id})

    if not qr_doc:
        return False, f"❌ QR Code {qr_id} not found!"

    if not qr_doc.get("is_used", False):
        user_id = f"User_{uuid.uuid4().hex[:6]}"
        current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        result = collection.update_one(
            {"id": qr_id, "is_used": False},
            {"$set": {
                "is_used": True,
                "claimed_by": user_id,
                "claimed_at": current_time
            }}
        )

        if result.modified_count > 0:
            return True, f"🎉 {qr_id} claimed at {current_time} by {user_id}.<br><b>Reward: WINNER50</b>"
        else:
            return claim_qr_logic(qr_id)  # retry in case of race
    else:
        return False, f"⚠️ {qr_id} already claimed by {qr_doc['claimed_by']} at {qr_doc['claimed_at']}"

@app.get("/claim/{qr_id}", response_class=HTMLResponse)
def claim_api(qr_id: str):
    success, msg = claim_qr_logic(qr_id)

    return f"""
    <html>
      <head><title>QR Claim</title></head>
      <body style="font-family: sans-serif; text-align:center; padding:40px">
        <h1>{"✅" if success else "❌"} Claim Result</h1>
        <p>{msg}</p>
        <p><i>{datetime.now().strftime('%B %d, %Y %I:%M %p')}</i></p>
      </body>
    </html>
    """
