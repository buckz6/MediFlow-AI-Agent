import os

import numpy as np
from PIL import Image, ImageDraw


def _create_xray_image(size=224, infiltrate=False):
    width = height = size
    base = np.full((height, width), 20, dtype=np.float32)

    yy, xx = np.mgrid[:height, :width]

    lungs = [
        {"center": (int(width * 0.35), int(height * 0.5)), "radius": (50, 80)},
        {"center": (int(width * 0.65), int(height * 0.5)), "radius": (50, 80)},
    ]

    for lung in lungs:
        cx, cy = lung["center"]
        rx, ry = lung["radius"]
        norm = ((xx - cx) / rx) ** 2 + ((yy - cy) / ry) ** 2
        mask = norm <= 1.0
        gradient = 1.0 - np.sqrt(norm[mask])
        values = 100 + gradient * 60
        base[mask] = np.maximum(base[mask], values)

    heart_cx, heart_cy = int(width * 0.45), int(height * 0.62)
    heart_rx, heart_ry = 28, 35
    heart_mask = (((xx - heart_cx) / heart_rx) ** 2 + ((yy - heart_cy) / heart_ry) ** 2) <= 1.0
    base[heart_mask] = np.minimum(base[heart_mask], 60)

    image = Image.fromarray(np.clip(base, 0, 255).astype(np.uint8), mode="L")
    draw = ImageDraw.Draw(image)

    left_box = [lungs[0]["center"][0] - lungs[0]["radius"][0], lungs[0]["center"][1] - lungs[0]["radius"][1], lungs[0]["center"][0] + lungs[0]["radius"][0], lungs[0]["center"][1] + lungs[0]["radius"][1]]
    right_box = [lungs[1]["center"][0] - lungs[1]["radius"][0], lungs[1]["center"][1] - lungs[1]["radius"][1], lungs[1]["center"][0] + lungs[1]["radius"][0], lungs[1]["center"][1] + lungs[1]["radius"][1]]

    for index, box in enumerate((left_box, right_box)):
        for offset in range(8):
            top = 70 + offset * 12
            bottom = 180 + offset * 3
            start_angle = 200 if index == 0 else 340
            end_angle = 340 if index == 0 else 520
            draw.arc(box, start=start_angle, end=end_angle, fill=180, width=2)
            box = [box[0] + 1, box[1] + 1, box[2] - 1, box[3] - 1]

    if infiltrate:
        patch_cx, patch_cy = int(width * 0.68), int(height * 0.35)
        patch_rx, patch_ry = 18, 14
        patch_norm = (((xx - patch_cx) / patch_rx) ** 2 + ((yy - patch_cy) / patch_ry) ** 2)
        patch_mask = patch_norm <= 1.0
        patch_strength = np.exp(-patch_norm[patch_mask] * 2.2)
        base = np.array(image, dtype=np.float32)
        base[patch_mask] = np.maximum(base[patch_mask], 220 * patch_strength + 20)
        image = Image.fromarray(np.clip(base, 0, 255).astype(np.uint8), mode="L")

    noise = np.random.normal(loc=0, scale=8, size=(height, width))
    noisy = np.array(image, dtype=np.float32) + noise
    noisy = np.clip(noisy, 0, 255).astype(np.uint8)
    return Image.fromarray(noisy, mode="L")


def _ensure_output_dir(path):
    os.makedirs(path, exist_ok=True)
    return path


def save_samples():
    fixture_dir = _ensure_output_dir(os.path.join(os.path.dirname(__file__)))

    normal_path = os.path.join(fixture_dir, "sample_xray_normal.png")
    abnormal_path = os.path.join(fixture_dir, "sample_xray_abnormal.png")
    lab_path = os.path.join(fixture_dir, "sample_lab.txt")

    _create_xray_image(infiltrate=False).save(normal_path)
    _create_xray_image(infiltrate=True).save(abnormal_path)

    lab_text = (
        "Hasil Pemeriksaan Laboratorium\n"
        "Nama: Budi Santoso | Tanggal: 18 Mei 2026\n"
        "BTA Sputum: Positif (+2)\n"
        "LED: 45 mm/jam (Tinggi)\n"
        "Leukosit: 11.200/µL (Tinggi)\n"
        "Kesimpulan: Mendukung diagnosis TBC aktif"
    )
    with open(lab_path, "w", encoding="utf-8") as f:
        f.write(lab_text)

    print("✅ Sample files generated")


if __name__ == "__main__":
    save_samples()
