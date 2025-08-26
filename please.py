import gradio as gr
import qrcode
import io
import base64
import os
import uuid
from datetime import datetime
from pymongo import MongoClient
import certifi
# ---------------- Helper to get BASE URL ----------------
def get_base_url():
    return os.getenv("BASE_URL", "https://onetime-qr.vercel.app")  # <- use your Vercel domain

# ---------------- MongoDB Setup ----------------
MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017/")
DB_NAME = os.getenv("DB_NAME", "Onetimeqr")
COLLECTION_NAME = "qr_codes"

client = MongoClient(MONGO_URI, tlsCAFile=certifi.where())
db = client[DB_NAME]
collection = db["qr_codes"]

# ---------------- DB Functions ----------------
def list_codes():
    codes = collection.find().sort("claimed_at", -1)
    status = ""
    for c in codes:
        if c.get("is_used", False):
            status += f"❌ {c['id']} used by {c.get('claimed_by')} at {c.get('claimed_at')}\n"
        else:
            status += f"✅ {c['id']} available\n"
    return status if status else "No codes yet!"

def generate_single_qr():
    qr_id = str(uuid.uuid4())[:8].upper()
    collection.insert_one({
        "id": qr_id,
        "is_used": False,
        "claimed_by": None,
        "claimed_at": None
    })

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

    if not os.path.exists('qr_codes'):
        os.makedirs('qr_codes')

    for i in range(10):
        qr_id = str(uuid.uuid4())[:8].upper()
        qr_ids.append(qr_id)
        collection.insert_one({
            "id": qr_id,
            "is_used": False,
            "claimed_by": None,
            "claimed_at": None
        })

        qr_url = f"{base_url}/claim/{qr_id}"
        qr = qrcode.QRCode(version=1, box_size=10, border=5)
        qr.add_data(qr_url)
        qr.make(fit=True)

        img = qr.make_image(fill_color="black", back_color="white")
        img_path = f'qr_codes/qr_{qr_id}.png'
        img.save(img_path)

        img_buffer = io.BytesIO()
        img.save(img_buffer, format="PNG")
        img_str = base64.b64encode(img_buffer.getvalue()).decode()
        qr_images.append(f"<div style='display:inline-block; margin:10px; padding:15px; border:1px solid #ddd; border-radius:8px; background:white; text-align:center;'><img src='data:image/png;base64,{img_str}' width='150'><br><small style='font-weight:bold; color:#007bff;'>{qr_id}</small></div>")

    zip_path = 'qr_codes_bulk.zip'
    import zipfile
    with zipfile.ZipFile(zip_path, 'w') as zipf:
        for qr_id in qr_ids:
            img_path = f'qr_codes/qr_{qr_id}.png'
            zipf.write(img_path, f'qr_{qr_id}.png')

    gallery_html = f"<div style='background:#f8f9fa; padding:20px; border-radius:10px;'><h3 style='color:#28a745; margin-bottom:15px;'>✅ Generated 10 QR Codes Successfully!</h3><div style='max-height:400px; overflow-y:auto;'>{''.join(qr_images)}</div><p style='margin-top:15px; color:#666;'><b>IDs:</b> {', '.join(qr_ids)}</p></div>"

    return gallery_html, list_codes(), zip_path

def reset_all():
    collection.update_many({}, {"$set": {"is_used": False, "claimed_by": None, "claimed_at": None}})
    return "🔄 All QR codes reset!", list_codes()

# ---------------- Gradio UI ----------------
with gr.Blocks() as demo:
    gr.Markdown("# 🎁 QR Code One-Time System")
    gr.Markdown("*Generate secure QR codes that can only be claimed once*")

    with gr.Row():
        with gr.Column(scale=1):
            gen_single_btn = gr.Button("➕ Generate Single QR Code")
        with gr.Column(scale=1):
            gen_bulk_btn = gr.Button("📦 Generate 10 QR Codes")
        with gr.Column(scale=1):
            reset_btn = gr.Button("🔄 Reset All")

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
            claim_id = gr.Textbox(label="Enter QR ID to Claim")
        with gr.Column(scale=1):
            claim_btn = gr.Button("✅ Claim")

    claim_output = gr.Textbox(label="Claim Result", interactive=False)

    gen_single_btn.click(fn=generate_single_qr, outputs=[qr_output, db_output])

    def handle_bulk_generation():
        gallery, status, zip_path = generate_bulk_qrs()
        return gallery, status, gr.update(value=zip_path, visible=True)

    gen_bulk_btn.click(fn=handle_bulk_generation, outputs=[qr_output, db_output, download_file])
    claim_btn.click(fn=lambda x: ("Use the Vercel endpoint to claim", list_codes()), inputs=claim_id, outputs=[claim_output, db_output])
    reset_btn.click(fn=reset_all, outputs=[claim_output, db_output])

    demo.load(fn=list_codes, outputs=db_output)

if __name__ == "__main__":
    demo.launch(server_name="0.0.0.0", share=True)
