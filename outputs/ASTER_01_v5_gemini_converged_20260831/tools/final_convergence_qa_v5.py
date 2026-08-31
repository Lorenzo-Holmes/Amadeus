from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw
from scipy import ndimage
from skimage.color import deltaE_ciede2000, rgb2lab

from render_glb_numba import accessor_array, read_glb


VIEWS = ("front", "front_right_3q", "right", "back_right_3q", "back", "back_left_3q", "left", "front_left_3q")


def remap_texture(texture: np.ndarray, uv: np.ndarray, triangle: np.ndarray) -> np.ndarray:
    map_x = (uv[:, :, 0] * (texture.shape[1] - 1)).astype(np.float32)
    map_y = (uv[:, :, 1] * (texture.shape[0] - 1)).astype(np.float32)
    output = cv2.remap(texture, map_x, map_y, interpolation=cv2.INTER_LINEAR, borderMode=cv2.BORDER_WRAP)
    output[triangle < 0] = np.asarray([7, 9, 13], np.uint8)
    return output


def color_delta_e(first: np.ndarray, second: np.ndarray, mask: np.ndarray) -> dict:
    count = int(mask.sum())
    if count == 0:
        return {"pixels": 0, "mean": 0.0, "max": 0.0, "p95": 0.0, "changed_pixels": 0, "max_rgb_delta": 0}
    a = first[mask].astype(np.float32) / 255.0
    b = second[mask].astype(np.float32) / 255.0
    delta = deltaE_ciede2000(rgb2lab(a.reshape(-1, 1, 3)).reshape(-1, 3), rgb2lab(b.reshape(-1, 1, 3)).reshape(-1, 3))
    rgb_delta = np.max(np.abs(first[mask].astype(np.int16) - second[mask].astype(np.int16)), axis=1)
    return {
        "pixels": count,
        "mean": float(delta.mean()),
        "max": float(delta.max()),
        "p95": float(np.percentile(delta, 95)),
        "changed_pixels": int((rgb_delta > 0).sum()),
        "max_rgb_delta": int(rgb_delta.max()),
    }


def semantic_masks(reference: np.ndarray, original: np.ndarray, triangle: np.ndarray, centroids_y: np.ndarray, band_visible: np.ndarray) -> dict[str, np.ndarray]:
    valid = triangle >= 0
    red, green, blue = [reference[:, :, channel].astype(np.int16) for channel in range(3)]
    maximum = np.maximum.reduce([red, green, blue])
    minimum = np.minimum.reduce([red, green, blue])
    hair = (red >= 55) & (red > green + 45) & (red > blue + 50) & (green < 105) & (blue < 100) & valid
    skin = (red > 225) & (green > 175) & (blue > 145) & (red > green + 10) & (green > blue + 8) & valid
    white = (red >= 215) & (green >= 210) & (blue >= 205) & ((maximum - minimum) < 25) & valid
    visible_y = np.zeros_like(red, dtype=np.float32)
    visible_y[valid] = centroids_y[triangle[valid]]
    head = (visible_y > 1.36) & valid
    o_red, o_green, o_blue = [original[:, :, channel].astype(np.int16) for channel in range(3)]
    original_luma = 0.2126 * o_red + 0.7152 * o_green + 0.0722 * o_blue
    lower_dark = (visible_y < 0.82) & (original_luma < 92) & valid
    return {
        "hair_core": ndimage.binary_erosion(hair, structure=np.ones((7, 7), np.uint8), iterations=1),
        "skin_core": ndimage.binary_erosion(skin, structure=np.ones((5, 5), np.uint8), iterations=1),
        "white_core": ndimage.binary_erosion(white, structure=np.ones((9, 9), np.uint8), iterations=1),
        "head_geometry": head,
        "lower_dark_core": ndimage.binary_erosion(lower_dark, structure=np.ones((5, 5), np.uint8), iterations=1),
        "back_band_exact": band_visible & valid,
    }


def mip_chain(image: np.ndarray) -> list[np.ndarray]:
    levels = [image]
    for _ in range(4):
        previous = levels[-1]
        levels.append(cv2.resize(previous, (previous.shape[1] // 2, previous.shape[0] // 2), interpolation=cv2.INTER_AREA))
    return levels


def sample_bilinear(texture: np.ndarray, uv: np.ndarray) -> np.ndarray:
    x = (uv[:, 0] % 1.0) * (texture.shape[1] - 1)
    y = (uv[:, 1] % 1.0) * (texture.shape[0] - 1)
    x0 = np.floor(x).astype(np.int64)
    y0 = np.floor(y).astype(np.int64)
    x1 = (x0 + 1) % texture.shape[1]
    y1 = (y0 + 1) % texture.shape[0]
    fx = (x - x0)[:, None]
    fy = (y - y0)[:, None]
    top = texture[y0, x0].astype(np.float32) * (1.0 - fx) + texture[y0, x1].astype(np.float32) * fx
    bottom = texture[y1, x0].astype(np.float32) * (1.0 - fx) + texture[y1, x1].astype(np.float32) * fx
    return top * (1.0 - fy) + bottom * fy


def seam_continuity(document: dict, binary: bytes, v3_texture: np.ndarray, v4_texture: np.ndarray) -> dict:
    primitive = document["meshes"][0]["primitives"][0]
    positions = accessor_array(document, binary, primitive["attributes"]["POSITION"]).astype(np.float64)
    uvs = accessor_array(document, binary, primitive["attributes"]["TEXCOORD_0"]).astype(np.float64)
    groups: dict[tuple[int, int, int], list[int]] = defaultdict(list)
    quantized = np.rint(positions * 100000.0).astype(np.int64)
    for index, value in enumerate(quantized):
        groups[(int(value[0]), int(value[1]), int(value[2]))].append(index)
    pairs = []
    for vertices in groups.values():
        if len(vertices) < 2:
            continue
        for offset, first in enumerate(vertices[:-1]):
            for second in vertices[offset + 1 :]:
                if np.linalg.norm(uvs[first] - uvs[second]) > 1e-5:
                    pairs.append((first, second))
    if not pairs:
        return {"candidate_pairs": 0, "baseline_continuous_pairs": 0, "v4_mean_delta_e": 0.0, "v4_max_delta_e": 0.0}
    pair_array = np.asarray(pairs, np.int64)
    first_v3 = sample_bilinear(v3_texture, uvs[pair_array[:, 0]]) / 255.0
    second_v3 = sample_bilinear(v3_texture, uvs[pair_array[:, 1]]) / 255.0
    first_v4 = sample_bilinear(v4_texture, uvs[pair_array[:, 0]]) / 255.0
    second_v4 = sample_bilinear(v4_texture, uvs[pair_array[:, 1]]) / 255.0
    baseline_delta = deltaE_ciede2000(rgb2lab(first_v3.reshape(-1, 1, 3)).reshape(-1, 3), rgb2lab(second_v3.reshape(-1, 1, 3)).reshape(-1, 3))
    v4_delta = deltaE_ciede2000(rgb2lab(first_v4.reshape(-1, 1, 3)).reshape(-1, 3), rgb2lab(second_v4.reshape(-1, 1, 3)).reshape(-1, 3))
    continuous = baseline_delta <= 2.5
    selected = v4_delta[continuous]
    return {
        "candidate_pairs": int(len(pairs)),
        "baseline_continuous_pairs": int(continuous.sum()),
        "baseline_mean_delta_e": float(baseline_delta[continuous].mean()) if selected.size else 0.0,
        "v4_mean_delta_e": float(selected.mean()) if selected.size else 0.0,
        "v4_max_delta_e": float(selected.max()) if selected.size else 0.0,
        "v4_p95_delta_e": float(np.percentile(selected, 95)) if selected.size else 0.0,
        "pairs_exceeding_2_5": int((selected > 2.5).sum()) if selected.size else 0,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", type=Path, required=True)
    parser.add_argument("--v3-texture", type=Path, required=True)
    parser.add_argument("--v4-texture", type=Path, required=True)
    parser.add_argument("--original-texture", type=Path, required=True)
    parser.add_argument("--audit-dir", type=Path, required=True)
    parser.add_argument("--band-mask", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    args.report.parent.mkdir(parents=True, exist_ok=True)

    document, binary = read_glb(args.model)
    primitive = document["meshes"][0]["primitives"][0]
    positions = accessor_array(document, binary, primitive["attributes"]["POSITION"]).astype(np.float32)
    indices = accessor_array(document, binary, primitive["indices"]).astype(np.int32).reshape(-1, 3)
    centroids_y = positions[indices].mean(axis=1)[:, 1]
    v3_full = np.asarray(Image.open(args.v3_texture).convert("RGB"))
    v4_full = np.asarray(Image.open(args.v4_texture).convert("RGB"))
    original_full = np.asarray(Image.open(args.original_texture).convert("RGB"))
    v3_levels = mip_chain(v3_full)
    v4_levels = mip_chain(v4_full)
    band_mask = np.asarray(Image.open(args.band_mask).convert("L"))

    view_reports = []
    protected_l0_all_pass = True
    mip_delta_all_pass = True
    dark_all_pass = True
    saved_mipmap_images = []

    for view in VIEWS:
        buffers = np.load(args.audit_dir / f"ASTER_01_v5_audit_{view}_buffers.npz")
        uv = buffers["uv"]
        triangle = buffers["triangle"]
        map_x_band = (uv[:, :, 0] * (band_mask.shape[1] - 1)).astype(np.float32)
        map_y_band = (uv[:, :, 1] * (band_mask.shape[0] - 1)).astype(np.float32)
        band_visible = cv2.remap(band_mask, map_x_band, map_y_band, interpolation=cv2.INTER_NEAREST, borderMode=cv2.BORDER_CONSTANT) > 0

        v3_l0 = remap_texture(v3_levels[0], uv, triangle)
        v4_l0 = remap_texture(v4_levels[0], uv, triangle)
        original_l0 = remap_texture(original_full, uv, triangle)
        masks = semantic_masks(v3_l0, original_l0, triangle, centroids_y, band_visible)
        protected_l0 = {}
        for name, mask in masks.items():
            metrics = color_delta_e(v3_l0, v4_l0, mask)
            protected_l0[name] = metrics
            if metrics["changed_pixels"] != 0:
                protected_l0_all_pass = False

        valid = triangle >= 0
        luma_v3 = 0.2126 * v3_l0[:, :, 0] + 0.7152 * v3_l0[:, :, 1] + 0.0722 * v3_l0[:, :, 2]
        luma_v4 = 0.2126 * v4_l0[:, :, 0] + 0.7152 * v4_l0[:, :, 1] + 0.0722 * v4_l0[:, :, 2]
        coat = np.any(v3_l0 != v4_l0, axis=2) & valid
        coat_core = ndimage.binary_erosion(coat, structure=np.ones((3, 3), np.uint8), iterations=1)
        dark_ratio = float(np.mean(np.all(v4_l0[coat_core] < 18, axis=1))) if np.any(coat_core) else 0.0
        bright_ratio = float(np.mean(np.all(v4_l0[coat_core] > 240, axis=1))) if np.any(coat_core) else 0.0
        if dark_ratio > 0.00005 or bright_ratio > 0.0:
            dark_all_pass = False

        mip_reports = []
        for level in range(5):
            v3_render = remap_texture(v3_levels[level], uv, triangle)
            v4_render = remap_texture(v4_levels[level], uv, triangle)
            semantic_mip = {
                name: color_delta_e(v3_render, v4_render, masks[name])
                for name in ("hair_core", "skin_core", "head_geometry", "back_band_exact", "white_core")
            }
            if any(metrics["max"] > 1.0 for metrics in semantic_mip.values()):
                mip_delta_all_pass = False
            mip_reports.append(
                {
                    "level": level,
                    "texture_size": [int(v4_levels[level].shape[1]), int(v4_levels[level].shape[0])],
                    "semantic_delta_e": semantic_mip,
                    "coat_luma_mean": float(luma_v4[coat_core].mean()) if level == 0 and np.any(coat_core) else None,
                }
            )
            if view in ("front", "back"):
                path = args.output_dir / f"ASTER_01_v5_{view}_mip{level}.png"
                Image.fromarray(v4_render).save(path)
                saved_mipmap_images.append(path)

        view_reports.append(
            {
                "view": view,
                "protected_l0": protected_l0,
                "coat_changed_screen_pixels": int(coat.sum()),
                "coat_dark_below_18_ratio": dark_ratio,
                "coat_bright_above_240_ratio": bright_ratio,
                "mipmaps": mip_reports,
            }
        )

    seam_report = seam_continuity(document, binary, v3_full, v4_full)
    # Continuous seams that were already close in v3 must remain close in v4. A small number of
    # duplicate-position pairs can represent intentional mirrored material boundaries, so use p95
    # as the convergence gate and retain max/outlier counts for audit.
    seam_pass = seam_report["v4_p95_delta_e"] <= 2.5

    checks = {
        "eight_view_protected_l0_zero_delta": protected_l0_all_pass,
        "mipmap_0_to_4_cross_material_delta_e_max_le_1": mip_delta_all_pass,
        "coat_dark_and_bright_clipping_within_threshold": dark_all_pass,
        "continuous_uv_seam_p95_delta_e_le_2_5": seam_pass,
    }
    report = {
        "schema": "aster01-final-convergence-qa-v5",
        "status": "PASS" if all(checks.values()) else "FAIL",
        "checks": checks,
        "views": view_reports,
        "uv_seam_continuity": seam_report,
        "saved_mipmap_images": [str(path) for path in saved_mipmap_images],
    }
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"status": report["status"], "checks": checks, "uv_seam_continuity": seam_report}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
