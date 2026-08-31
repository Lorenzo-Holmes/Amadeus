from __future__ import annotations

import argparse
import json
from pathlib import Path

import cv2
import numpy as np
from PIL import Image
from scipy import ndimage

from apply_texture_tune_v3 import accessor_digests, sha256
from render_glb_numba import accessor_array, read_glb
from replace_glb_texture import replace_image


VIEWS = ("front", "front_right_3q", "right", "back_right_3q", "back", "back_left_3q", "left", "front_left_3q")


def remap_texture(texture: np.ndarray, uv: np.ndarray, triangle: np.ndarray) -> np.ndarray:
    map_x = (uv[:, :, 0] * (texture.shape[1] - 1)).astype(np.float32)
    map_y = (uv[:, :, 1] * (texture.shape[0] - 1)).astype(np.float32)
    output = cv2.remap(texture, map_x, map_y, interpolation=cv2.INTER_LINEAR, borderMode=cv2.BORDER_WRAP)
    output[triangle < 0] = np.asarray([7, 9, 13], np.uint8)
    return output


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", type=Path, required=True)
    parser.add_argument("--v3-texture", type=Path, required=True)
    parser.add_argument("--v4-texture", type=Path, required=True)
    parser.add_argument("--original-texture", type=Path, required=True)
    parser.add_argument("--audit-dir", type=Path, required=True)
    parser.add_argument("--band-mask", type=Path, required=True)
    parser.add_argument("--output-texture", type=Path, required=True)
    parser.add_argument("--output-model", type=Path, required=True)
    parser.add_argument("--report-dir", type=Path, required=True)
    args = parser.parse_args()
    args.output_texture.parent.mkdir(parents=True, exist_ok=True)
    args.output_model.parent.mkdir(parents=True, exist_ok=True)
    args.report_dir.mkdir(parents=True, exist_ok=True)

    document, binary = read_glb(args.model)
    primitive = document["meshes"][0]["primitives"][0]
    positions = accessor_array(document, binary, primitive["attributes"]["POSITION"]).astype(np.float32)
    indices = accessor_array(document, binary, primitive["indices"]).astype(np.int32).reshape(-1, 3)
    centroids_y = positions[indices].mean(axis=1)[:, 1]
    v3 = np.asarray(Image.open(args.v3_texture).convert("RGB"))
    v4 = np.asarray(Image.open(args.v4_texture).convert("RGB"))
    original = np.asarray(Image.open(args.original_texture).convert("RGB"))
    atlas_height, atlas_width = v4.shape[:2]
    core = np.asarray(Image.open(args.band_mask).convert("L")) > 0
    category_screen_pixels = defaultdict_int = {
        "band": 0,
        "head_geometry": 0,
        "hair_core": 0,
        "skin_core": 0,
        "white_core": 0,
        "lower_body_core": 0,
    }

    for view in VIEWS:
        buffers = np.load(args.audit_dir / f"ASTER_01_v5_audit_{view}_buffers.npz")
        uv = buffers["uv"]
        triangle = buffers["triangle"]
        valid = triangle >= 0
        v3_render = remap_texture(v3, uv, triangle)
        original_render = remap_texture(original, uv, triangle)
        red, green, blue = [v3_render[:, :, channel].astype(np.int16) for channel in range(3)]
        o_red, o_green, o_blue = [original_render[:, :, channel].astype(np.int16) for channel in range(3)]
        maximum = np.maximum.reduce([red, green, blue])
        minimum = np.minimum.reduce([red, green, blue])
        visible_y = np.zeros(triangle.shape, np.float32)
        visible_y[valid] = centroids_y[triangle[valid]]

        hair = (red >= 55) & (red > green + 45) & (red > blue + 50) & (green < 105) & (blue < 100) & valid
        hair = ndimage.binary_erosion(hair, structure=np.ones((5, 5), np.uint8), iterations=1)
        skin = (red > 225) & (green > 175) & (blue > 145) & (red > green + 10) & (green > blue + 8) & valid
        skin = ndimage.binary_erosion(skin, structure=np.ones((5, 5), np.uint8), iterations=1)
        white = (red >= 215) & (green >= 210) & (blue >= 205) & ((maximum - minimum) < 25) & valid
        white = ndimage.binary_erosion(white, structure=np.ones((7, 7), np.uint8), iterations=1)
        head = (visible_y > 1.36) & valid
        original_luma = 0.2126 * o_red + 0.7152 * o_green + 0.0722 * o_blue
        lower = (visible_y < 0.82) & (original_luma < 92) & valid
        lower = ndimage.binary_erosion(lower, structure=np.ones((5, 5), np.uint8), iterations=1)
        categories = {
            "head_geometry": head,
            "hair_core": hair,
            "skin_core": skin,
            "white_core": white,
            "lower_body_core": lower,
        }
        for name, screen_mask in categories.items():
            category_screen_pixels[name] += int(screen_mask.sum())
            selected_uv = uv[screen_mask]
            x = np.clip(np.rint(selected_uv[:, 0] * (atlas_width - 1)).astype(np.int32), 0, atlas_width - 1)
            y = np.clip(np.rint(selected_uv[:, 1] * (atlas_height - 1)).astype(np.int32), 0, atlas_height - 1)
            core[y, x] = True

    # Atlas-native guards close visibility gaps (eyelids, finger sides, and UV fragments that are
    # subpixel from all eight cameras) before mip padding is generated.
    a_red, a_green, a_blue = [v3[:, :, channel].astype(np.int16) for channel in range(3)]
    a_maximum = np.maximum.reduce([a_red, a_green, a_blue])
    a_minimum = np.minimum.reduce([a_red, a_green, a_blue])
    atlas_hair = (a_red >= 55) & (a_red > a_green + 45) & (a_red > a_blue + 50) & (a_green < 105) & (a_blue < 100)
    atlas_skin = (a_red > 225) & (a_green > 175) & (a_blue > 145) & (a_red > a_green + 10) & (a_green > a_blue + 8)
    atlas_white = (a_red >= 215) & (a_green >= 210) & (a_blue >= 205) & ((a_maximum - a_minimum) < 25)
    core |= atlas_hair | atlas_skin | atlas_white
    category_screen_pixels["atlas_hair_guard_texels"] = int(atlas_hair.sum())
    category_screen_pixels["atlas_skin_guard_texels"] = int(atlas_skin.sum())
    category_screen_pixels["atlas_white_guard_texels"] = int(atlas_white.sum())

    # Close the sampling gaps left by screen-space point projection without crossing a mip-level gutter.
    core = cv2.dilate(core.astype(np.uint8), np.ones((7, 7), np.uint8), iterations=1) > 0
    padding_radius = 32.0
    distance = cv2.distanceTransform((~core).astype(np.uint8), cv2.DIST_L2, 5)
    padding = np.clip((padding_radius - distance) / padding_radius, 0.0, 1.0)
    padding[core] = 1.0
    padding = padding * padding * (3.0 - 2.0 * padding)

    output = np.empty_like(v4)
    for channel in range(3):
        blended = v4[:, :, channel].astype(np.float32) * (1.0 - padding) + v3[:, :, channel].astype(np.float32) * padding
        output[:, :, channel] = np.rint(np.clip(blended, 0.0, 255.0)).astype(np.uint8)
    Image.fromarray(output).save(args.output_texture, optimize=False, compress_level=6)
    Image.fromarray((core * 255).astype(np.uint8)).save(args.report_dir / "protected_core_mask_v5.png")
    Image.fromarray(np.rint(padding * 255.0).astype(np.uint8)).save(args.report_dir / "protected_padding_alpha_v5.png")

    replacement = replace_image(args.model, args.output_texture, args.output_model, 0)
    changed_vs_v4 = np.any(output != v4, axis=2)
    report = {
        "schema": "aster01-protected-padding-v5",
        "status": "PASS" if accessor_digests(args.model) == accessor_digests(args.output_model) else "FAIL",
        "category_screen_samples": category_screen_pixels,
        "protected_core_texels": int(core.sum()),
        "padding_texels": int((padding > 0).sum()),
        "padding_radius_px_8192": int(padding_radius),
        "changed_pixels_vs_v4": int(changed_vs_v4.sum()),
        "v3_texture_sha256": sha256(args.v3_texture),
        "v4_texture_sha256": sha256(args.v4_texture),
        "output_texture_sha256": sha256(args.output_texture),
        "output_model_sha256": sha256(args.output_model),
        "replacement": replacement,
    }
    (args.report_dir / "protected_padding_report_v5.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
