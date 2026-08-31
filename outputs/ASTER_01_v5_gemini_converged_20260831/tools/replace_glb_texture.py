from __future__ import annotations

import argparse
import hashlib
import json
import struct
from pathlib import Path


JSON_MAGIC = 0x4E4F534A
BIN_MAGIC = 0x004E4942


def read_glb(path: Path) -> tuple[dict, bytes]:
    data = path.read_bytes()
    magic, version, _ = struct.unpack_from("<4sII", data, 0)
    if magic != b"glTF" or version != 2:
        raise ValueError(f"Unsupported GLB header: {path}")
    pos = 12
    document = None
    binary = None
    while pos < len(data):
        size, kind = struct.unpack_from("<II", data, pos)
        pos += 8
        chunk = data[pos : pos + size]
        pos += size
        if kind == JSON_MAGIC:
            document = json.loads(chunk.rstrip(b" \t\r\n\x00").decode("utf-8"))
        elif kind == BIN_MAGIC:
            binary = chunk
    if document is None or binary is None:
        raise ValueError("GLB must contain JSON and BIN chunks")
    return document, binary


def pad4(value: bytes) -> bytes:
    return value + b"\x00" * ((4 - len(value) % 4) % 4)


def write_glb(path: Path, document: dict, binary: bytes) -> None:
    json_chunk = pad4(json.dumps(document, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))
    bin_chunk = pad4(binary)
    total = 12 + 8 + len(json_chunk) + 8 + len(bin_chunk)
    with path.open("wb") as f:
        f.write(struct.pack("<4sII", b"glTF", 2, total))
        f.write(struct.pack("<II", len(json_chunk), JSON_MAGIC))
        f.write(json_chunk)
        f.write(struct.pack("<II", len(bin_chunk), BIN_MAGIC))
        f.write(bin_chunk)


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def replace_image(source: Path, image: Path, destination: Path, image_index: int) -> dict:
    document, binary = read_glb(source)
    image_entry = document["images"][image_index]
    view_index = image_entry["bufferView"]
    view = document["bufferViews"][view_index]
    old_start = view.get("byteOffset", 0)
    old_length = view["byteLength"]
    old_padded = (old_length + 3) // 4 * 4
    new_bytes = image.read_bytes()
    new_padded = pad4(new_bytes)
    delta = len(new_padded) - old_padded
    new_binary = binary[:old_start] + new_padded + binary[old_start + old_padded :]

    view["byteLength"] = len(new_bytes)
    for other in document["bufferViews"]:
        start = other.get("byteOffset", 0)
        if start > old_start:
            other["byteOffset"] = start + delta
    document["images"][image_index]["mimeType"] = "image/png"
    if document.get("buffers"):
        document["buffers"][0]["byteLength"] = len(new_binary)

    destination.parent.mkdir(parents=True, exist_ok=True)
    write_glb(destination, document, new_binary)
    return {
        "source": str(source),
        "source_sha256": sha256(source),
        "image": str(image),
        "image_sha256": sha256(image),
        "destination": str(destination),
        "destination_sha256": sha256(destination),
        "image_index": image_index,
        "old_image_bytes": old_length,
        "new_image_bytes": len(new_bytes),
        "old_binary_bytes": len(binary),
        "new_binary_bytes": len(new_binary),
        "delta_padded_bytes": delta,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("image", type=Path)
    parser.add_argument("destination", type=Path)
    parser.add_argument("--image-index", type=int, default=0)
    args = parser.parse_args()
    print(json.dumps(replace_image(args.source, args.image, args.destination, args.image_index), indent=2))
