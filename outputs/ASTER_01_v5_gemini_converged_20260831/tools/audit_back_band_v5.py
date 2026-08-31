from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path

import cv2
import numpy as np
from PIL import Image
from scipy import ndimage

from render_glb_numba import accessor_array, rasterize, read_glb


VIEWS = (
    ("front", 0.0),
    ("front_right_3q", 45.0),
    ("right", 90.0),
    ("back_right_3q", 135.0),
    ("back", 180.0),
    ("back_left_3q", 225.0),
    ("left", 270.0),
    ("front_left_3q", 315.0),
)


def rotate_y(positions: np.ndarray, degrees: float) -> np.ndarray:
    radians = np.deg2rad(degrees)
    cosine = float(np.cos(radians))
    sine = float(np.sin(radians))
    result = positions.copy()
    result[:, 0] = cosine * positions[:, 0] + sine * positions[:, 2]
    result[:, 2] = -sine * positions[:, 0] + cosine * positions[:, 2]
    return result


def bilinear_from_uv(texture: np.ndarray, uv: np.ndarray, triangle: np.ndarray) -> np.ndarray:
    map_x = (uv[:, :, 0] * (texture.shape[1] - 1)).astype(np.float32)
    map_y = (uv[:, :, 1] * (texture.shape[0] - 1)).astype(np.float32)
    output = cv2.remap(texture, map_x, map_y, interpolation=cv2.INTER_LINEAR, borderMode=cv2.BORDER_WRAP)
    output[triangle < 0] = np.asarray([7, 9, 13], np.uint8)
    return output


def normalized_accessor(document: dict, binary: bytes, accessor_index: int) -> np.ndarray:
    result = accessor_array(document, binary, accessor_index).astype(np.float64)
    accessor = document["accessors"][accessor_index]
    if accessor.get("normalized"):
        if accessor["componentType"] == 5121:
            result /= 255.0
        elif accessor["componentType"] == 5123:
            result /= 65535.0
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", type=Path, required=True)
    parser.add_argument("--texture", type=Path, required=True)
    parser.add_argument("--band-render", type=Path, required=True)
    parser.add_argument("--band-buffers", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--width", type=int, default=768)
    parser.add_argument("--height", type=int, default=1152)
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    args.report.parent.mkdir(parents=True, exist_ok=True)

    document, binary = read_glb(args.model)
    primitive = document["meshes"][0]["primitives"][0]
    positions = accessor_array(document, binary, primitive["attributes"]["POSITION"]).astype(np.float32)
    uvs = accessor_array(document, binary, primitive["attributes"]["TEXCOORD_0"]).astype(np.float32)
    indices = accessor_array(document, binary, primitive["indices"]).astype(np.int32).reshape(-1, 3)
    joints = accessor_array(document, binary, primitive["attributes"]["JOINTS_0"]).astype(np.int32)
    weights = normalized_accessor(document, binary, primitive["attributes"]["WEIGHTS_0"])
    texture = np.asarray(Image.open(args.texture).convert("RGB"))

    source_render = np.asarray(Image.open(args.band_render).convert("RGB"))
    source_buffers = np.load(args.band_buffers)
    source_triangle = source_buffers["triangle"]
    source_uv = source_buffers["uv"]
    red, green, blue = [source_render[:, :, channel].astype(np.int16) for channel in range(3)]
    yy, xx = np.mgrid[: source_render.shape[0], : source_render.shape[1]]
    band_screen = (
        (red > 132)
        & (green > 116)
        & (blue > 98)
        & ((red - green) < 55)
        & ((green - blue) < 55)
        & (xx >= 210)
        & (xx <= 430)
        & (yy >= 330)
        & (yy <= 425)
        & (source_triangle >= 0)
    )
    band_triangles = np.unique(source_triangle[band_screen])
    band_triangle_lookup = np.zeros(indices.shape[0], dtype=bool)
    band_triangle_lookup[band_triangles] = True
    band_vertices = np.unique(indices[band_triangles])

    skin_joint_nodes = document["skins"][0]["joints"]
    joint_names = [document["nodes"][node].get("name", f"joint_{index}") for index, node in enumerate(skin_joint_nodes)]
    joint_distribution: dict[int, float] = defaultdict(float)
    for vertex in band_vertices:
        for joint, weight in zip(joints[vertex], weights[vertex]):
            joint_distribution[int(joint)] += float(weight)
    joint_summary = [
        {"joint_index": index, "name": joint_names[index], "mean_weight": weight / len(band_vertices)}
        for index, weight in sorted(joint_distribution.items(), key=lambda item: -item[1])
    ]

    atlas_size = 8192
    band_atlas = np.zeros((atlas_size, atlas_size), dtype=np.uint8)
    for u, v in source_uv[band_screen]:
        x = int(np.clip(round(float(u) * (atlas_size - 1)), 0, atlas_size - 1))
        y = int(np.clip(round(float(v) * (atlas_size - 1)), 0, atlas_size - 1))
        cv2.circle(band_atlas, (x, y), 2, 255, thickness=-1)
    Image.fromarray(band_atlas).save(args.output_dir / "band_exact_uv_mask_8192.png")

    band_small = np.asarray(Image.fromarray(band_atlas).resize((2048, 2048), Image.Resampling.NEAREST)) > 0
    hair_atlas_small = np.zeros((2048, 2048), dtype=bool)
    protected_atlas_small = np.zeros((2048, 2048), dtype=bool)
    view_reports = []
    total_conflict_pixels = 0
    conflict_triangles: set[int] = set()
    dummy = np.zeros((1, 1, 3), dtype=np.uint8)

    for label, angle in VIEWS:
        rotated = rotate_y(positions, angle)
        y_min, y_max = -0.05, 1.75
        x_span = (y_max - y_min) * (args.width / args.height)
        _, uv_buffer, triangle_buffer = rasterize(
            rotated, uvs, indices, dummy, args.width, args.height, 1.0, -x_span / 2.0, x_span / 2.0, y_min, y_max
        )
        rendered = bilinear_from_uv(texture, uv_buffer, triangle_buffer)
        Image.fromarray(rendered).save(args.output_dir / f"ASTER_01_v5_audit_{label}.png")
        np.savez_compressed(args.output_dir / f"ASTER_01_v5_audit_{label}_buffers.npz", uv=uv_buffer, triangle=triangle_buffer)

        map_x = (uv_buffer[:, :, 0] * (atlas_size - 1)).astype(np.float32)
        map_y = (uv_buffer[:, :, 1] * (atlas_size - 1)).astype(np.float32)
        band_visible = cv2.remap(band_atlas, map_x, map_y, interpolation=cv2.INTER_NEAREST, borderMode=cv2.BORDER_CONSTANT) > 0
        valid = triangle_buffer >= 0
        same_triangle_family = np.zeros_like(valid)
        same_triangle_family[valid] = band_triangle_lookup[triangle_buffer[valid]]
        conflict = band_visible & valid & ~same_triangle_family
        conflict_ids = np.unique(triangle_buffer[conflict])
        conflict_triangles.update(int(value) for value in conflict_ids)
        total_conflict_pixels += int(conflict.sum())

        r, g, b = [rendered[:, :, channel].astype(np.int16) for channel in range(3)]
        hair = (r >= 55) & (r > g + 45) & (r > b + 50) & (g < 105) & (b < 100) & valid
        white = (r >= 205) & (g >= 200) & (b >= 195) & (np.maximum.reduce([r, g, b]) - np.minimum.reduce([r, g, b]) < 35) & valid
        skin = (r > g + 18) & (g > b + 8) & (r > 150) & (g > 95) & (b > 75) & valid
        protected = hair | white | skin
        sx = np.clip(np.rint(uv_buffer[:, :, 0] * 2047).astype(np.int32), 0, 2047)
        sy = np.clip(np.rint(uv_buffer[:, :, 1] * 2047).astype(np.int32), 0, 2047)
        hair_atlas_small[sy[hair], sx[hair]] = True
        protected_atlas_small[sy[protected], sx[protected]] = True

        conflict_colors = rendered[conflict]
        view_reports.append(
            {
                "view": label,
                "angle_degrees": angle,
                "visible_band_texel_pixels": int((band_visible & valid).sum()),
                "other_triangle_conflict_pixels": int(conflict.sum()),
                "other_triangle_conflict_count": int(conflict_ids.size),
                "conflict_mean_rgb": [float(value) for value in conflict_colors.mean(axis=0)] if conflict_colors.size else None,
            }
        )

    band_points = np.column_stack(np.where(band_small))
    distance_hair = ndimage.distance_transform_edt(~hair_atlas_small)
    distance_protected = ndimage.distance_transform_edt(~protected_atlas_small)
    hair_distances_8192 = distance_hair[band_small] * 4.0
    protected_distances_8192 = distance_protected[band_small] * 4.0

    conflict_vertices = np.unique(indices[np.asarray(sorted(conflict_triangles), dtype=np.int32)]) if conflict_triangles else np.asarray([], np.int32)
    conflict_joint_distribution: dict[int, float] = defaultdict(float)
    for vertex in conflict_vertices:
        for joint, weight in zip(joints[vertex], weights[vertex]):
            conflict_joint_distribution[int(joint)] += float(weight)
    conflict_joint_summary = [
        {"joint_index": index, "name": joint_names[index], "mean_weight": weight / max(len(conflict_vertices), 1)}
        for index, weight in sorted(conflict_joint_distribution.items(), key=lambda item: -item[1])
    ]

    vertices_xyz = positions[indices[band_triangles]].reshape(-1, 3)
    report = {
        "schema": "aster01-back-band-topology-audit-v5",
        "band": {
            "screen_pixels": int(band_screen.sum()),
            "triangle_count": int(band_triangles.size),
            "vertex_count": int(band_vertices.size),
            "triangle_ids": [int(value) for value in band_triangles],
            "position_bounds": {"min": vertices_xyz.min(axis=0).tolist(), "max": vertices_xyz.max(axis=0).tolist()},
            "joint_distribution": joint_summary,
            "hips_mean_weight": next((item["mean_weight"] for item in joint_summary if item["name"] == "Hips"), 0.0),
            "head_hair_mean_weight": sum(
                item["mean_weight"] for item in joint_summary if "head" in item["name"].lower() or "hair" in item["name"].lower()
            ),
            "exact_uv_mask_pixels_8192": int((band_atlas > 0).sum()),
        },
        "multi_view_uv_reuse": {
            "views": view_reports,
            "total_other_triangle_conflict_pixels": total_conflict_pixels,
            "conflict_triangle_count": len(conflict_triangles),
            "conflict_joint_distribution": conflict_joint_summary,
        },
        "atlas_distance": {
            "hair_min_px_8192": float(hair_distances_8192.min()) if hair_distances_8192.size else None,
            "hair_percentiles_px_8192": [float(value) for value in np.percentile(hair_distances_8192, [0, 1, 5, 50, 95, 100])] if hair_distances_8192.size else [],
            "protected_min_px_8192": float(protected_distances_8192.min()) if protected_distances_8192.size else None,
            "protected_percentiles_px_8192": [float(value) for value in np.percentile(protected_distances_8192, [0, 1, 5, 50, 95, 100])] if protected_distances_8192.size else [],
        },
    }
    report["decision"] = {
        "bone_ownership_pass": report["band"]["hips_mean_weight"] >= 0.85 and report["band"]["head_hair_mean_weight"] <= 0.05,
        "uv_reuse_pass": total_conflict_pixels == 0,
        "hair_gutter_16px_pass": bool(hair_distances_8192.size and hair_distances_8192.min() >= 16.0),
    }
    report["decision"]["safe_to_edit"] = all(report["decision"].values())
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
