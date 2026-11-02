"""Photo evidence. Uploads are decoded and re-encoded as JPEG, which removes EXIF (including GPS location) and anything that is not
really an image. Files live outside any public path and are only returned to the reporter or to staff."""
import hashlib
import io
import os
import re
import uuid
from datetime import datetime, timezone
from PIL import Image, ImageOps, UnidentifiedImageError
from auth_service import is_staff, is_worker
from config import get_settings
from database import connect, transaction
from schemas import User

MAX_BYTES, MAX_FILES, MAX_SIDE, MAX_PIXELS = 5 * 1024 * 1024, 3, 1600, 24_000_000
ALLOWED = {"JPEG", "PNG", "WEBP"}
Image.MAX_IMAGE_PIXELS = MAX_PIXELS


class AttachmentError(Exception):
    """Message is safe to show to the person."""


def _clean_name(name: str) -> str:
    base = os.path.basename((name or "photo").replace("\\", "/"))
    return re.sub(r"[^\w.\- ]", "", base)[:80] or "photo"


def validate_image(data: bytes) -> None:
    """Validate an uploaded image before the related ticket action is committed."""
    if not data or len(data) > MAX_BYTES:
        raise AttachmentError("Each photo must be smaller than 5 MB.")
    try:
        with Image.open(io.BytesIO(data)) as im:
            if im.format not in ALLOWED:
                raise AttachmentError("Please upload a JPEG, PNG or WebP photo.")
            if im.width * im.height > MAX_PIXELS:
                raise AttachmentError("That photo is too large in pixels. Please upload a smaller one.")
            im.verify()
    except AttachmentError:
        raise
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError, ValueError):
        raise AttachmentError("That file could not be read as a photo.") from None


def save_image(ticket_id: str, data: bytes, original_name: str, *, kind: str, uploader_id: int | None, db_path=None, upload_dir=None) -> int:
    if kind not in ("report", "resolution"):
        raise AttachmentError("Unknown attachment type.")
    validate_image(data)
    try:
        im = Image.open(io.BytesIO(data))
        im.load()
    except AttachmentError:
        raise
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError, ValueError):
        raise AttachmentError("That file could not be read as a photo.") from None
    im = ImageOps.exif_transpose(im)
    if im.mode in ("RGBA", "LA", "P"):
        im = im.convert("RGBA")
        bg = Image.new("RGB", im.size, "white")
        bg.paste(im, mask=im.split()[-1])
        im = bg
    else:
        im = im.convert("RGB")
    im.thumbnail((MAX_SIDE, MAX_SIDE))
    out = io.BytesIO()
    im.save(out, "JPEG", quality=85, optimize=True)  # no exif argument: metadata is dropped
    blob, stored = out.getvalue(), uuid.uuid4().hex + ".jpg"
    folder = upload_dir or get_settings().upload_dir
    os.makedirs(folder, exist_ok=True)
    with connect(db_path) as c, transaction(c):
        if c.execute("SELECT COUNT(*) FROM attachments WHERE ticket_id = ? AND kind = ?", (ticket_id, kind)).fetchone()[0] >= MAX_FILES:
            raise AttachmentError(f"You can attach up to {MAX_FILES} photos.")
        path = os.path.join(folder, stored)
        with open(path, "wb") as f:
            f.write(blob)
        os.chmod(path, 0o600)
        cur = c.execute("INSERT INTO attachments (ticket_id, kind, uploader_id, original_name, stored_name, content_type, size_bytes, width, height, sha256, created_at) "
                        "VALUES (?,?,?,?,?,?,?,?,?,?,?)", (ticket_id, kind, uploader_id, _clean_name(original_name), stored, "image/jpeg", len(blob), im.width, im.height,
                                                           hashlib.sha256(blob).hexdigest(), datetime.now(timezone.utc).isoformat(timespec="seconds")))
        return cur.lastrowid


def list_attachments(ticket_id: str, db_path=None) -> list[dict]:
    with connect(db_path) as c:
        return [dict(r) for r in c.execute("SELECT id, kind, original_name, size_bytes, width, height, created_at FROM attachments WHERE ticket_id = ? ORDER BY id", (ticket_id,))]


def read_attachment(att_id: int, *, viewer: User | None, db_path=None, upload_dir=None) -> bytes:
    """Only staff and the person who filed the ticket may read a photo."""
    if viewer is None:
        raise AttachmentError("Please sign in to view photos.")
    with connect(db_path) as c:
        row = c.execute("SELECT a.stored_name, t.reporter_id, t.assignee_id FROM attachments a JOIN tickets t ON t.ticket_id = a.ticket_id WHERE a.id = ?", (att_id,)).fetchone()
    if not row or not (is_staff(viewer.id, db_path) or row["reporter_id"] == viewer.id
                       or (is_worker(viewer.id, db_path) and row["assignee_id"] == viewer.id)):
        raise AttachmentError("You do not have access to this photo.")
    try:
        with open(os.path.join(upload_dir or get_settings().upload_dir, row["stored_name"]), "rb") as f:
            return f.read()
    except OSError:
        raise AttachmentError("This photo is no longer available.") from None
