from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from datetime import datetime
import sqlite3
import uuid

app = FastAPI()

def claim_qr_logic(qr_id):
    conn = sqlite3.connect('qr_codes.db')
    cursor = conn.cursor()
    cursor.execute('SELECT is_used, claimed_by, claimed_at FROM qr_codes WHERE id = ?', (qr_id,))
    result = cursor.fetchone()

    if not result:
        conn.close()
        return False, f"❌ QR Code {qr_id} not found!"

    is_used, claimed_by, claimed_at = result

    if not is_used:
        user_id = f"User_{uuid.uuid4().hex[:6]}"
        current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        cursor.execute('''
            UPDATE qr_codes 
            SET is_used = ?, claimed_by = ?, claimed_at = ?
            WHERE id = ? AND is_used = ?
        ''', (True, user_id, current_time, qr_id, False))
        if cursor.rowcount > 0:
            conn.commit()
            conn.close()
            return True, f"🎉 {qr_id} claimed at {current_time} by {user_id}.<br><b>Reward: WINNER50</b>"
    conn.close()
    return False, f"⚠️ {qr_id} already claimed!"

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

# ✅ Export as Vercel handler
# This tells Vercel how to serve FastAPI
from mangum import Mangum
handler = Mangum(app)
