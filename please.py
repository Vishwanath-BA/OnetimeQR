import gradio as gr
import qrcode
import io
import base64
import sqlite3
from datetime import datetime
import uuid
import socket
import threading
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
import uvicorn
import zipfile
import os

# ---------------- Helper to get BASE URL ----------------
def get_base_url():
    return os.getenv("BASE_URL", "http://localhost:8000")  # fallback for local dev

# ---------------- DB ----------------
def init_db():
    conn = sqlite3.connect('qr_codes.db')
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS qr_codes (
            id TEXT PRIMARY KEY,
            is_used BOOLEAN DEFAULT FALSE,
            claimed_by TEXT,
            claimed_at TIMESTAMP
        )
    ''')
    conn.commit()
    conn.close()


def list_codes():
    conn = sqlite3.connect('qr_codes.db')
    cursor = conn.cursor()
    cursor.execute('SELECT id, is_used, claimed_by, claimed_at FROM qr_codes ORDER BY claimed_at DESC')
    codes = cursor.fetchall()
    conn.close()
    status = ""
    for c in codes:
        if c[1]:
            status += f"❌ {c[0]} used by {c[2]} at {c[3]}\n"
        else:
            status += f"✅ {c[0]} available\n"
    return status if status else "No codes yet!"


def generate_single_qr():
    qr_id = str(uuid.uuid4())[:8].upper()

    conn = sqlite3.connect('qr_codes.db')
    cursor = conn.cursor()
    cursor.execute('INSERT INTO qr_codes (id, is_used) VALUES (?, ?)', (qr_id, False))
    conn.commit()
    conn.close()

    base_url = get_base_url()
    qr_url = f"{base_url}/claim/{qr_id}"

    qr = qrcode.QRCode(version=1, box_size=10, border=5)
    qr.add_data(qr_url)
    qr.make(fit=True)

    img = qr.make_image(fill_color="black", back_color="white")
    img_buffer = io.BytesIO()
    img.save(img_buffer, format="PNG")
    img_str = base64.b64encode(img_buffer.getvalue()).decode()
    img_html = f"<div style='text-align:center; padding:20px; border:2px solid #ddd; border-radius:10px; background:#f9f9f9;'><img src='data:image/png;base64,{img_str}' width='250'><br><b style='color:#333;'>ID:</b> <span style='color:#007bff; font-weight:bold;'>{qr_id}</span><br><b style='color:#333;'>URL:</b> <code style='background:#e9ecef; padding:2px 6px; border-radius:3px;'>{qr_url}</code></div>"

    return img_html, list_codes()


def generate_bulk_qrs():
    qr_ids = []
    qr_images = []
    base_url = get_base_url()
    
    # Create directory for QR codes if it doesn't exist
    if not os.path.exists('qr_codes'):
        os.makedirs('qr_codes')
    
    conn = sqlite3.connect('qr_codes.db')
    cursor = conn.cursor()
    
    for i in range(10):
        qr_id = str(uuid.uuid4())[:8].upper()
        qr_ids.append(qr_id)
        
        # Insert into database
        cursor.execute('INSERT INTO qr_codes (id, is_used) VALUES (?, ?)', (qr_id, False))
        
        # Generate QR code
        qr_url = f"{base_url}/claim/{qr_id}"
        qr = qrcode.QRCode(version=1, box_size=10, border=5)
        qr.add_data(qr_url)
        qr.make(fit=True)
        
        img = qr.make_image(fill_color="black", back_color="white")
        
        # Save individual QR code
        img_path = f'qr_codes/qr_{qr_id}.png'
        img.save(img_path)
        
        # Create base64 for display
        img_buffer = io.BytesIO()
        img.save(img_buffer, format="PNG")
        img_str = base64.b64encode(img_buffer.getvalue()).decode()
        qr_images.append(f"<div style='display:inline-block; margin:10px; padding:15px; border:1px solid #ddd; border-radius:8px; background:white; text-align:center;'><img src='data:image/png;base64,{img_str}' width='150'><br><small style='font-weight:bold; color:#007bff;'>{qr_id}</small></div>")
    
    conn.commit()
    conn.close()
    
    # Create ZIP file
    zip_path = 'qr_codes_bulk.zip'
    with zipfile.ZipFile(zip_path, 'w') as zipf:
        for qr_id in qr_ids:
            img_path = f'qr_codes/qr_{qr_id}.png'
            zipf.write(img_path, f'qr_{qr_id}.png')
    
    # Create HTML display
    gallery_html = f"<div style='background:#f8f9fa; padding:20px; border-radius:10px;'><h3 style='color:#28a745; margin-bottom:15px;'>✅ Generated 10 QR Codes Successfully!</h3><div style='max-height:400px; overflow-y:auto;'>{''.join(qr_images)}</div><p style='margin-top:15px; color:#666;'><b>IDs:</b> {', '.join(qr_ids)}</p></div>"
    
    return gallery_html, list_codes(), zip_path


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
        else:
            conn.close()
            return claim_qr_logic(qr_id)
    else:
        conn.close()
        return False, f"⚠ {qr_id} already claimed by {claimed_by} at {claimed_at}"


def claim_qr(qr_id):
    success, msg = claim_qr_logic(qr_id)
    return msg, list_codes()


def reset_all():
    conn = sqlite3.connect('qr_codes.db')
    cursor = conn.cursor()
    cursor.execute('UPDATE qr_codes SET is_used = ?, claimed_by = NULL, claimed_at = NULL', (False,))
    conn.commit()
    conn.close()
    return "🔄 All QR codes reset!", list_codes()


# ---------------- Gradio UI ----------------
with gr.Blocks(css="""
    .gradio-container {
        max-width: 1200px !important;
    }
    .generate-btn {
        background: linear-gradient(45deg, #28a745, #20c997) !important;
        border: none !important;
        color: white !important;
        font-weight: bold !important;
    }
    .bulk-btn {
        background: linear-gradient(45deg, #007bff, #6610f2) !important;
        border: none !important;
        color: white !important;
        font-weight: bold !important;
    }
    .reset-btn {
        background: linear-gradient(45deg, #dc3545, #fd7e14) !important;
        border: none !important;
        color: white !important;
        font-weight: bold !important;
    }
""") as demo:
    
    gr.Markdown("# 🎁 QR Code One-Time System")
    gr.Markdown("Generate secure QR codes that can only be claimed once")

    with gr.Row():
        with gr.Column(scale=1):
            gen_single_btn = gr.Button("➕ Generate Single QR Code", elem_classes=["generate-btn"], size="lg")
        with gr.Column(scale=1):
            gen_bulk_btn = gr.Button("📦 Generate 10 QR Codes", elem_classes=["bulk-btn"], size="lg")
        with gr.Column(scale=1):
            reset_btn = gr.Button("🔄 Reset All", elem_classes=["reset-btn"], size="lg")

    with gr.Row():
        with gr.Column(scale=2):
            qr_output = gr.HTML(label="Generated QR Code(s)")
            download_file = gr.File(label="Download ZIP (for bulk generation)", visible=False)
        with gr.Column(scale=1):
            db_output = gr.Textbox(label="📊 Database Status", interactive=False, lines=15, max_lines=20)

    gr.Markdown("---")
    gr.Markdown("### 🔧 Manual Testing")
    
    with gr.Row():
        with gr.Column(scale=3):
            claim_id = gr.Textbox(label="Enter QR ID to Claim", placeholder="e.g., ABC12DEF")
        with gr.Column(scale=1):
            claim_btn = gr.Button("✅ Claim", size="lg")
    
    claim_output = gr.Textbox(label="Claim Result", interactive=False)

    # Event handlers
    gen_single_btn.click(fn=generate_single_qr, outputs=[qr_output, db_output])
    
    def handle_bulk_generation():
        gallery, status, zip_path = generate_bulk_qrs()
        return gallery, status, gr.update(value=zip_path, visible=True)
    
    gen_bulk_btn.click(fn=handle_bulk_generation, outputs=[qr_output, db_output, download_file])
    
    claim_btn.click(fn=claim_qr, inputs=claim_id, outputs=[claim_output, db_output])
    reset_btn.click(fn=reset_all, outputs=[claim_output, db_output])

    demo.load(fn=list_codes, outputs=db_output)


# ---------------- FastAPI for /claim/<id> ----------------
app = FastAPI()

@app.get("/claim/{qr_id}", response_class=HTMLResponse)
def claim_api(qr_id: str):
    success, msg = claim_qr_logic(qr_id)
    base_url = get_base_url()
    
    # Enhanced HTML with beautiful UI
    if success:
        status_color = "#28a745"
        status_icon = "🎉"
        bg_gradient = "linear-gradient(135deg, #d4edda, #c3e6cb)"
        border_color = "#28a745"
    else:
        status_color = "#dc3545" 
        status_icon = "❌"
        bg_gradient = "linear-gradient(135deg, #f8d7da, #f5c6cb)"
        border_color = "#dc3545"
    
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>QR Code Claim Result</title>
        <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css" rel="stylesheet">
        <style>
            * {{
                margin: 0;
                padding: 0;
                box-sizing: border-box;
            }}
            
            body {{
                font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                min-height: 100vh;
                display: flex;
                align-items: center;
                justify-content: center;
                padding: 20px;
            }}
            
            .container {{
                background: white;
                border-radius: 20px;
                box-shadow: 0 20px 40px rgba(0,0,0,0.1);
                padding: 40px;
                max-width: 500px;
                width: 100%;
                text-align: center;
                position: relative;
                overflow: hidden;
            }}
            
            .container::before {{
                content: '';
                position: absolute;
                top: 0;
                left: 0;
                right: 0;
                height: 5px;
                background: {bg_gradient};
            }}
            
            .status-icon {{
                font-size: 4rem;
                margin-bottom: 20px;
                animation: bounce 0.6s ease-in-out;
            }}
            
            @keyframes bounce {{
                0%, 20%, 50%, 80%, 100% {{
                    transform: translateY(0);
                }}
                40% {{
                    transform: translateY(-10px);
                }}
                60% {{
                    transform: translateY(-5px);
                }}
            }}
            
            .status-message {{
                background: {bg_gradient};
                color: {status_color};
                padding: 20px;
                border-radius: 15px;
                border: 2px solid {border_color};
                margin-bottom: 30px;
                font-size: 1.1rem;
                font-weight: 500;
                line-height: 1.4;
            }}
            
            .qr-id {{
                background: #f8f9fa;
                color: #333;
                padding: 15px;
                border-radius: 10px;
                font-family: 'Courier New', monospace;
                font-size: 1.2rem;
                font-weight: bold;
                margin-bottom: 30px;
                border: 2px dashed #dee2e6;
            }}
            
            .back-button {{
                display: inline-block;
                background: linear-gradient(45deg, #007bff, #0056b3);
                color: white;
                text-decoration: none;
                padding: 15px 30px;
                border-radius: 50px;
                font-weight: bold;
                font-size: 1.1rem;
                transition: all 0.3s ease;
                box-shadow: 0 5px 15px rgba(0,123,255,0.3);
            }}
            
            .back-button:hover {{
                transform: translateY(-2px);
                box-shadow: 0 8px 25px rgba(0,123,255,0.4);
                text-decoration: none;
                color: white;
            }}
            
            .timestamp {{
                color: #6c757d;
                font-size: 0.9rem;
                margin-top: 20px;
                font-style: italic;
            }}
            
            @media (max-width: 600px) {{
                .container {{
                    padding: 30px 20px;
                }}
                .status-icon {{
                    font-size: 3rem;
                }}
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="status-icon">{status_icon}</div>
            
            <div class="qr-id">
                <i class="fas fa-qrcode"></i> QR ID: {qr_id}
            </div>
            
            <div class="status-message">
                {msg.replace('<br>', '<br>')}
            </div>
            
    
            
        </div>
        
    
    </body>
    </html>
    """
    return HTMLResponse(content=html)


# ---------------- Run both ----------------
def run_fastapi():
    uvicorn.run(app, host="0.0.0.0", port=8000)

if _name_ == "_main_":
    init_db()
    # Run FastAPI in background thread
    threading.Thread(target=run_fastapi, daemon=True).start()
    # Run Gradio dashboard
    demo.launch(server_name="0.0.0.0", share=True)
