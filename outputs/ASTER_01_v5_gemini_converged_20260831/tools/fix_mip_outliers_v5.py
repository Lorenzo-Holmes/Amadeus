from __future__ import annotations

import argparse
import json
from pathlib import Path

import cv2
import numpy as np
from PIL import Image
from scipy import ndimage
from skimage.color import deltaE_ciede2000, rgb2lab

from apply_texture_tune_v3 import accessor_digests, sha256
from render_glb_numba import accessor_array, read_glb
from replace_glb_texture import replace_image


VIEWS = ("front", "front_right_3q", "right", "back_right_3q", "back", "back_left_3q", "left", "front_left_3q")


def remap(texture: np.ndarray, uv: np.ndarray, triangle: np.ndarray) -> np.ndarray:
    x = (uv[:, :, 0] * (texture.shape[1] - 1)).astype(np.float32)
    y = (uv[:, :, 1] * (texture.shape[0] - 1)).astype(np.float32)
    result = cv2.remap(texture, x, y, interpolation=cv2.INTER_LINEAR, borderMode=cv2.BORDER_WRAP)
    result[triangle < 0] = np.asarray([7, 9, 13], np.uint8)
    return result


def mip4(image: np.ndarray) -> np.ndarray:
    result = image
    for _ in range(4):
        result = cv2.resize(result, (result.shape[1] // 2, result.shape[0] // 2), interpolation=cv2.INTER_AREA)
    return result


def delta_map(first: np.ndarray, second: np.ndarray) -> np.ndarray:
    lab_first = rgb2lab(first.astype(np.float32) / 255.0)
    lab_second = rgb2lab(second.astype(np.float32) / 255.0)
    return deltaE_ciede2000(lab_first, lab_second)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", type=Path, required=True)
    parser.add_argument("--v3-texture", type=Path, required=True)
    parser.add_argument("--input-texture", type=Path, required=True)
    parser.add_argument("--original-texture", type=Path, required=True)
    parser.add_argument("--audit-dir", type=Path, required=True)
    parser.add_argument("--output-texture", type=Path, required=True)
    parser.add_argument("--output-model", type=Path, required=True)
    parser.add_argument("--report-dir", type=Path, required=True)
    args = parser.parse_args()

    document, binary = read_glb(args.model)
    primitive = document["meshes"][0]["primitives"][0]
    positions = accessor_array(document, binary, primitive["attributes"]["POSITION"]).astype(np.float32)
    indices = accessor_array(document, binary, primitive["indices"]).astype(np.int32).reshape(-1, 3)
    centroids_y = positions[indices].mean(axis=1)[:, 1]
    v3 = np.asarray(Image.open(args.v3_texture).convert("RGB"))
    current = np.asarray(Image.open(args.input_texture).convert("RGB"))
    input_texture_sha256 = sha256(args.input_texture)
    original = np.asarray(Image.open(args.original_texture).convert("RGB"))
    v3_mip4 = mip4(v3)
    current_mip4 = mip4(current)
    atlas_mask = np.zeros(current.shape[:2], np.uint8)
    view_counts = {}

    for view in VIEWS:
        buffers = np.load(args.audit_dir / f"ASTER_01_v5_audit_{view}_buffers.npz")
        uv = buffers["uv"]
        triangle = buffers["triangle"]
        valid = triangle >= 0
        v3_l0 = remap(v3, uv, triangle)
        original_l0 = remap(original, uv, triangle)
        v3_l4 = remap(v3_mip4, uv, triangle)
        current_l4 = remap(current_mip4, uv, triangle)
        red, green, blue = [v3_l0[:, :, channel].astype(np.int16) for channel in range(3)]
        maximum = np.maximum.reduce([red, green, blue])
        minimum = np.minimum.reduce([red, green, blue])
        visible_y = np.zeros(triangle.shape, np.float32)
        visible_y[valid] = centroids_y[triangle[valid]]
        hair = (red >= 55) & (red > green + 45) & (red > blue + 50) & (green < 105) & (blue < 100) & valid
        hair = ndimage.binary_erosion(hair, np.ones((7, 7), np.uint8), iterations=1)
        skin = (red > 225) & (green > 175) & (blue > 145) & (red > green + 10) & (green > blue + 8) & valid
        skin = ndimage.binary_erosion(skin, np.ones((5, 5), np.uint8), iterations=1)
        white = (red >= 215) & (green >= 210) & (blue >= 205) & ((maximum - minimum) < 25) & valid
        white = ndimage.binary_erosion(white, np.ones((9, 9), np.uint8), iterations=1)
        head = (visible_y > 1.36) & valid
        protected = hair | skin | white | head
        delta = delta_map(v3_l4, current_l4)
        outliers = protected & (delta > 0.85)
        view_counts[view] = {
            "outlier_pixels_over_0_85": int(outliers.sum()),
            "max_delta_e_before": float(delta[protected].max()) if np.any(protected) else 0.0,
        }
        for u, v in uv[outliers]:
            x = int(np.clip(round(float(u) * (current.shape[1] - 1)), 0, current.shape[1] - 1))
            y = int(np.clip(round(float(v) * (current.shape[0] - 1)), 0, current.shape[0] - 1))
            cv2.circle(atlas_mask, (x, y), 64, 255, thickness=-1)

    output = current.copy()
    output[atlas_mask > 0] = v3[atlas_mask > 0]
    Image.fromarray(output).save(args.output_texture, optimize=False, compress_level=6)
    Image.fromarray(atlas_mask).save(args.report_dir / "mip_outlier_lock_mask_v5.png")
    replacement = replace_image(args.model, args.output_texture, args.output_model, 0)
    report = {
        "schema": "aster01-mip-outlier-fix-v5",
        "status": "PASS" if accessor_digests(args.model) == accessor_digests(args.output_model) else "FAIL",
        "threshold_delta_e": 0.85,
        "atlas_lock_radius_px": 64,
        "view_counts": view_counts,
        "atlas_locked_texels": int((atlas_mask > 0).sum()),
        "input_texture_sha256": input_texture_sha256,
        "output_texture_sha256": sha256(args.output_texture),
        "output_model_sha256": sha256(args.output_model),
        "replacement": replacement,
    }
    (args.report_dir / "mip_outlier_fix_report_v5.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
