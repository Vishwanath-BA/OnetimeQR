import uuid
import zipfile
import io
import requests
import qrcode
from PIL import Image
import gradio as gr

# ---------------- Backend URL ----------------
BACKEND_URL = "https://onetime-qr.vercel.app"   # change if needed


def register_qr_in_db(qr_id: str):
    """Notify backend to insert QR code into MongoDB."""
    try:
        r = requests.post(f"{BACKEND_URL}/add_qr/{qr_id}")
        if r.status_code == 200:
            print(f"[DB] QR {qr_id} added →", r.json())
        else:
            print(f"[DB ERROR] {r.text}")
    except Exception as e:
        print("Error adding QR:", e)


# ---------------- Single QR Generator ----------------
def generate_single_qr():
    qr_id = uuid.uuid4().hex[:8].upper()
    qr_url = f"{BACKEND_URL}/claim/{qr_id}"

    # Register in DB
    register_qr_in_db(qr_id)

    # Generate QR code image
    qr = qrcode.make(qr_url)

    # ✅ Ensure it's a proper PIL.Image
    if hasattr(qr, "get_image"):
        qr = qr.get_image()

    return qr, qr_id, qr_url


# ---------------- Bulk QR Generator ----------------
def generate_bulk_qr(n=10):
    buffer = io.BytesIO()
    zipf = zipfile.ZipFile(buffer, "w")

    qr_list = []

    for _ in range(n):
        qr_id = uuid.uuid4().hex[:8].upper()
        qr_url = f"{BACKEND_URL}/claim/{qr_id}"

        # Register in DB
        register_qr_in_db(qr_id)

        # Generate QR code image
        qr = qrcode.make(qr_url)
        if hasattr(qr, "get_image"):
            qr = qr.get_image()

        img_bytes = io.BytesIO()
        qr.save(img_bytes, format="PNG")
        img_bytes.seek(0)

        # Add to ZIP
        zipf.writestr(f"{qr_id}.png", img_bytes.getvalue())
        qr_list.append(f"{qr_id} → {qr_url}")

    zipf.close()
    buffer.seek(0)

    return buffer, "\n".join(qr_list)


# ---------------- Gradio UI ----------------
with gr.Blocks(theme=gr.themes.Soft()) as demo:
    gr.Markdown("🎁 **QR Code One-Time System**\n\nGenerate secure QR codes that can only be claimed once")

    with gr.Row():
        btn_single = gr.Button("➕ Generate Single QR Code")
        btn_bulk = gr.Button("📦 Generate 10 QR Codes")
        btn_reset = gr.Button("🔄 Reset All")

    with gr.Row():
        qr_img = gr.Image(type="pil", label="Generated QR Code")
        db_status = gr.Textbox(label="Database Status (QRs)", interactive=False)

    qr_id_out = gr.Textbox(label="QR ID")
    qr_url_out = gr.Textbox(label="QR URL")

    zip_out = gr.File(label="Download Bulk ZIP")

    # Single QR callback
    def single_callback():
        img, qr_id, qr_url = generate_single_qr()
        return img, qr_id, qr_url, f"{qr_id} available"

    btn_single.click(single_callback, outputs=[qr_img, qr_id_out, qr_url_out, db_status])

    # Bulk QR callback
    def bulk_callback():
        zip_file, qr_list = generate_bulk_qr(10)
        return zip_file, qr_list

    btn_bulk.click(bulk_callback, outputs=[zip_out, db_status])

    # Reset DB button (calls backend directly)
    def reset_db():
        try:
            r = requests.post(f"{BACKEND_URL}/reset")
            return "✅ DB Reset Successful!" if r.status_code == 200 else f"❌ Reset failed: {r.text}"
        except Exception as e:
            return f"⚠️ Error resetting DB: {e}"

    btn_reset.click(reset_db, outputs=[db_status])


# ---------------- Run App ----------------
if __name__ == "__main__":
    demo.launch(server_name="0.0.0.0", server_port=7860)
