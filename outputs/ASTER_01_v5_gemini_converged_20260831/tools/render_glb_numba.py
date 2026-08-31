from __future__ import annotations

import argparse
import json
import struct
from pathlib import Path

import numpy as np
from numba import njit
from PIL import Image


COMPONENT_TYPES = {
    5120: ("b", 1),
    5121: ("B", 1),
    5122: ("h", 2),
    5123: ("H", 2),
    5125: ("I", 4),
    5126: ("f", 4),
}
TYPE_COMPONENTS = {"SCALAR": 1, "VEC2": 2, "VEC3": 3, "VEC4": 4, "MAT4": 16}


def read_glb(path: Path) -> tuple[dict, bytes]:
    data = path.read_bytes()
    pos = 12
    document = None
    binary = None
    while pos < len(data):
        size, kind = struct.unpack_from("<II", data, pos)
        pos += 8
        chunk = data[pos : pos + size]
        pos += size
        if kind == 0x4E4F534A:
            document = json.loads(chunk.rstrip(b" \t\r\n\x00").decode("utf-8"))
        elif kind == 0x004E4942:
            binary = chunk
    if document is None or binary is None:
        raise ValueError("Invalid GLB")
    return document, binary


def accessor_array(document: dict, binary: bytes, accessor_index: int) -> np.ndarray:
    accessor = document["accessors"][accessor_index]
    view = document["bufferViews"][accessor["bufferView"]]
    component_count = TYPE_COMPONENTS[accessor["type"]]
    fmt, component_size = COMPONENT_TYPES[accessor["componentType"]]
    stride = view.get("byteStride", component_count * component_size)
    start = view.get("byteOffset", 0) + accessor.get("byteOffset", 0)
    return np.asarray(
        [
            struct.unpack_from("<" + fmt * component_count, binary, start + row * stride)
            for row in range(accessor["count"])
        ]
    )


@njit(cache=True, fastmath=True)
def rasterize(
    positions: np.ndarray,
    uvs: np.ndarray,
    indices: np.ndarray,
    texture: np.ndarray,
    width: int,
    height: int,
    depth_sign: float,
    xmin: float,
    xmax: float,
    ymin: float,
    ymax: float,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    image = np.empty((height, width, 3), dtype=np.uint8)
    image[:, :, 0] = 7
    image[:, :, 1] = 9
    image[:, :, 2] = 13
    depth_buffer = np.full((height, width), -1.0e30, dtype=np.float32)
    uv_buffer = np.full((height, width, 2), -1.0, dtype=np.float32)
    tri_buffer = np.full((height, width), -1, dtype=np.int32)
    texture_height, texture_width = texture.shape[0], texture.shape[1]

    scale_x = (width - 1.0) / (xmax - xmin)
    scale_y = (height - 1.0) / (ymax - ymin)
    for triangle_index in range(indices.shape[0]):
        i0 = indices[triangle_index, 0]
        i1 = indices[triangle_index, 1]
        i2 = indices[triangle_index, 2]
        x0 = (positions[i0, 0] - xmin) * scale_x
        x1 = (positions[i1, 0] - xmin) * scale_x
        x2 = (positions[i2, 0] - xmin) * scale_x
        y0 = (ymax - positions[i0, 1]) * scale_y
        y1 = (ymax - positions[i1, 1]) * scale_y
        y2 = (ymax - positions[i2, 1]) * scale_y

        min_x = max(0, int(np.floor(min(x0, x1, x2))))
        max_x = min(width - 1, int(np.ceil(max(x0, x1, x2))))
        min_y = max(0, int(np.floor(min(y0, y1, y2))))
        max_y = min(height - 1, int(np.ceil(max(y0, y1, y2))))
        if min_x > max_x or min_y > max_y:
            continue

        denominator = (y1 - y2) * (x0 - x2) + (x2 - x1) * (y0 - y2)
        if abs(denominator) < 1.0e-10:
            continue
        inverse = 1.0 / denominator
        for py in range(min_y, max_y + 1):
            sample_y = py + 0.5
            for px in range(min_x, max_x + 1):
                sample_x = px + 0.5
                w0 = ((y1 - y2) * (sample_x - x2) + (x2 - x1) * (sample_y - y2)) * inverse
                w1 = ((y2 - y0) * (sample_x - x2) + (x0 - x2) * (sample_y - y2)) * inverse
                w2 = 1.0 - w0 - w1
                if w0 < -1.0e-5 or w1 < -1.0e-5 or w2 < -1.0e-5:
                    continue
                depth = depth_sign * (
                    w0 * positions[i0, 2] + w1 * positions[i1, 2] + w2 * positions[i2, 2]
                )
                if depth <= depth_buffer[py, px]:
                    continue
                u = w0 * uvs[i0, 0] + w1 * uvs[i1, 0] + w2 * uvs[i2, 0]
                v = w0 * uvs[i0, 1] + w1 * uvs[i1, 1] + w2 * uvs[i2, 1]
                u = u - np.floor(u)
                v = v - np.floor(v)
                tx = min(texture_width - 1, max(0, int(u * (texture_width - 1) + 0.5)))
                ty = min(texture_height - 1, max(0, int(v * (texture_height - 1) + 0.5)))
                image[py, px, 0] = texture[ty, tx, 0]
                image[py, px, 1] = texture[ty, tx, 1]
                image[py, px, 2] = texture[ty, tx, 2]
                depth_buffer[py, px] = depth
                uv_buffer[py, px, 0] = u
                uv_buffer[py, px, 1] = v
                tri_buffer[py, px] = triangle_index
    return image, uv_buffer, tri_buffer


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", type=Path, required=True)
    parser.add_argument("--texture", type=Path, required=True)
    parser.add_argument("--output-prefix", type=Path, required=True)
    parser.add_argument("--width", type=int, default=640)
    parser.add_argument("--height", type=int, default=960)
    args = parser.parse_args()

    document, binary = read_glb(args.model)
    primitive = document["meshes"][0]["primitives"][0]
    positions = accessor_array(document, binary, primitive["attributes"]["POSITION"]).astype(np.float32)
    uvs = accessor_array(document, binary, primitive["attributes"]["TEXCOORD_0"]).astype(np.float32)
    indices = accessor_array(document, binary, primitive["indices"]).astype(np.int32).reshape(-1, 3)
    texture = np.asarray(Image.open(args.texture).convert("RGB"))

    args.output_prefix.parent.mkdir(parents=True, exist_ok=True)
    for label, sign in (("front", 1.0), ("back", -1.0)):
        image, uv_buffer, tri_buffer = rasterize(
            positions,
            uvs,
            indices,
            texture,
            args.width,
            args.height,
            sign,
            -0.60,
            0.60,
            -0.05,
            1.75,
        )
        output = args.output_prefix.with_name(args.output_prefix.name + f"_{label}.png")
        Image.fromarray(image).save(output)
        np.savez_compressed(
            args.output_prefix.with_name(args.output_prefix.name + f"_{label}_buffers.npz"),
            uv=uv_buffer,
            triangle=tri_buffer,
        )


if __name__ == "__main__":
    main()
