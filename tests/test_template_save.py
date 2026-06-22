import cv2
import numpy as np
from ievr_bot.template_extractor import save_template


def test_save_template_writes_cropped_region(tmp_path):
    frame = np.zeros((100, 200, 3), np.uint8)
    frame[40:60, 50:90] = 200  # a bright patch we will crop to
    dest = tmp_path / "goal.png"
    save_template(frame, (50, 40, 40, 20), dest)
    out = cv2.imread(str(dest))
    assert out.shape[:2] == (20, 40)
    assert int(out.mean()) == 200


def test_save_template_writes_full_frame_when_crop_none(tmp_path):
    frame = np.full((30, 50, 3), 7, np.uint8)
    dest = tmp_path / "loading.png"
    save_template(frame, None, dest)
    out = cv2.imread(str(dest))
    assert out.shape[:2] == (30, 50)


def test_save_template_creates_parent_dir(tmp_path):
    frame = np.zeros((10, 10, 3), np.uint8)
    dest = tmp_path / "pve" / "goal.png"
    save_template(frame, None, dest)
    assert dest.exists()
