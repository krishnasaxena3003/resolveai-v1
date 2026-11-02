import io
import os
import stat
import pytest
from PIL import Image
from attachments import MAX_FILES, AttachmentError, list_attachments, read_attachment, save_image
from auth_service import register_student
from ai_service import fallback_analysis
from conftest import staff_for
import ticket_service as ts

PW = "correct-horse-1"
T = "No electricity in Hostel Block B since morning"


@pytest.fixture
def env(db, tmp_path):
    stu = register_student("Asha", "a@c.edu", PW, db_path=db)
    t = ts.create_ticket(fallback_analysis(T), T, None, "fallback", reporter_id=stu.id, db_path=db).ticket
    return db, str(tmp_path / "up"), stu, t


def img(fmt="JPEG", size=(300, 200), mode="RGB", **kw):
    b = io.BytesIO()
    Image.new(mode, size, (200, 30, 30) if mode == "RGB" else (200, 30, 30, 80)).save(b, fmt, **kw)
    return b.getvalue()


def save(env, data, name="photo.jpg", kind="report"):
    db, up, stu, t = env
    return save_image(t.ticket_id, data, name, kind=kind, uploader_id=stu.id, db_path=db, upload_dir=up)


def test_valid_photos_are_saved_as_jpeg_and_listed(env):
    db, up, stu, t = env
    for data, name in ((img("JPEG"), "a.jpg"), (img("PNG", mode="RGBA"), "b.png"), (img("WEBP"), "c.webp")):
        save(env, data, name)
    assert [a["original_name"] for a in list_attachments(t.ticket_id, db)] == ["a.jpg", "b.png", "c.webp"]
    assert Image.open(os.path.join(up, os.listdir(up)[0])).format == "JPEG"


def test_exif_metadata_including_camera_and_location_tags_is_stripped(env):
    db, up, *_ = env
    ex = Image.Exif(); ex[0x010F] = "SecretCam"; ex[0x8825] = {1: "N", 2: (12.0, 5.0, 3.0), 3: "E", 4: (77.0, 1.0, 1.0)}
    data = img("JPEG", exif=ex)
    assert Image.open(io.BytesIO(data)).getexif().get(0x010F) == "SecretCam"  # the upload really had metadata
    save(env, data)
    saved = Image.open(os.path.join(up, os.listdir(up)[0]))
    assert dict(saved.getexif()) == {} and "exif" not in saved.info


def test_large_photos_are_downscaled(env):
    _, up, *_ = env
    save(env, img("JPEG", size=(4000, 3000)))
    assert max(Image.open(os.path.join(up, os.listdir(up)[0])).size) == 1600


@pytest.mark.parametrize("data,why", [(b"not an image at all", "could not be read"), (b"", "smaller than 5 MB"), (img("GIF"), "JPEG, PNG or WebP"),
                                      (img("JPEG")[:60], "could not be read"), (b"<?php system($_GET['c']); ?>", "could not be read"),
                                      (b"\x00" * (5 * 1024 * 1024 + 1), "smaller than 5 MB")])
def test_non_images_and_bad_files_are_rejected_even_with_a_jpg_name(env, data, why):
    with pytest.raises(AttachmentError, match=why):
        save(env, data, "evidence.jpg")


def test_pixel_bombs_are_rejected(env):
    with pytest.raises(AttachmentError, match="too large in pixels"):
        save(env, img("PNG", size=(5200, 5200)))


def test_at_most_three_photos_per_kind(env):
    for _ in range(MAX_FILES):
        save(env, img())
    with pytest.raises(AttachmentError, match="up to 3"):
        save(env, img())
    save(env, img(), kind="resolution")  # evidence from staff has its own allowance
    assert len(os.listdir(env[1])) == MAX_FILES + 1  # the rejected one left no file behind


def test_file_names_are_sanitised_and_stored_under_random_names(env):
    _, up, *_ = env
    save(env, img(), "../../etc/passwd<script>.jpg")
    row = list_attachments(env[3].ticket_id, env[0])[0]
    assert "/" not in row["original_name"] and "<" not in row["original_name"] and os.listdir(up)[0].endswith(".jpg") and "passwd" not in os.listdir(up)[0]
    if os.name == "posix":
        assert stat.S_IMODE(os.stat(os.path.join(up, os.listdir(up)[0])).st_mode) == 0o600


def test_only_the_owner_and_staff_can_read_a_photo(env):
    db, up, stu, t = env
    aid = save(env, img())
    other = register_student("Ben", "b@c.edu", PW, db_path=db)
    assert read_attachment(aid, viewer=stu, db_path=db, upload_dir=up)[:2] == b"\xff\xd8"  # JPEG signature
    assert read_attachment(aid, viewer=staff_for(db), db_path=db, upload_dir=up)
    for viewer in (other, None):
        with pytest.raises(AttachmentError):
            read_attachment(aid, viewer=viewer, db_path=db, upload_dir=up)
    with pytest.raises(AttachmentError):
        read_attachment(9999, viewer=stu, db_path=db, upload_dir=up)
