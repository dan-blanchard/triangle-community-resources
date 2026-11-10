# /// script
# dependencies = ["segno"]
# ///
"""Generate the site's QR code (static/qr.svg, static/qr.png). Re-run only if the URL changes."""
import segno

URL = "https://dan-blanchard.github.io/triangle-community-resources/"
qr = segno.make(URL, error="h")  # high error correction: still scans when printed small or scuffed
qr.save("static/qr.svg", scale=10, border=2, dark="#1f1d1a")
qr.save("static/qr.png", scale=20, border=2, dark="#1f1d1a")
print(f"QR version {qr.version}, {qr.error} error correction -> static/qr.svg, static/qr.png")
