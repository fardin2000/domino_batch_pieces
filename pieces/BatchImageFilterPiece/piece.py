import base64
import io
from pathlib import Path
from typing import List

import numpy as np
import requests
from PIL import Image

from domino.base_piece import BasePiece

from .models import InputModel, OutputModel


FILTER_MASKS = {
    "sepia": ((0.393, 0.769, 0.189), (0.349, 0.686, 0.168), (0.272, 0.534, 0.131)),
    "black_and_white": ((0.333, 0.333, 0.333), (0.333, 0.333, 0.333), (0.333, 0.333, 0.333)),
    "brightness": ((1.4, 0, 0), (0, 1.4, 0), (0, 0, 1.4)),
    "darkness": ((0.6, 0, 0), (0, 0.6, 0), (0, 0, 0.6)),
    "contrast": ((1.2, 0.6, 0.6), (0.6, 1.2, 0.6), (0.6, 0.6, 1.2)),
    "red": ((1.6, 0, 0), (0, 1, 0), (0, 0, 1)),
    "green": ((1, 0, 0), (0, 1.6, 0), (0, 0, 1)),
    "blue": ((1, 0, 0), (0, 1, 0), (0, 0, 1.6)),
    "cool": ((0.9, 0, 0), (0, 1.1, 0), (0, 0, 1.3)),
    "warm": ((1.2, 0, 0), (0, 0.9, 0), (0, 0, 0.8)),
}


class BatchImageFilterPiece(BasePiece):

    @staticmethod
    def _build_gallery_html(
        images_b64: List[str],
        enabled_filters: List[str],
        failed: List[str],
        total: int,
    ) -> str:
        filters_str = ", ".join(enabled_filters) if enabled_filters else "none (passthrough)"
        cards = []
        for idx, b64 in enumerate(images_b64):
            uri = f"data:image/png;base64,{b64}"
            fname = f"filtered_{idx}.png"
            cards.append(
                f"<div class='card'>"
                f"<a href='{uri}' download='{fname}' title='Click to download {fname}'>"
                f"<img src='{uri}' alt='{fname}'/></a>"
                f"<a class='dl' href='{uri}' download='{fname}'>{fname}</a>"
                f"</div>"
            )
        failed_block = ""
        if failed:
            items = "".join(f"<li>{u}</li>" for u in failed)
            failed_block = (
                f"<details class='failed'><summary>{len(failed)} URL(s) failed</summary>"
                f"<ul>{items}</ul></details>"
            )
        return (
            "<!doctype html><html><head><meta charset='utf-8'>"
            "<style>"
            "body{font-family:system-ui,sans-serif;margin:1em;background:#1e1e1e;color:#eee}"
            "h1{font-size:1.1em;font-weight:500;margin:0 0 .25em}"
            ".meta{color:#aaa;font-size:.85em;margin-bottom:1em}"
            ".grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(260px,1fr));gap:1em}"
            ".card{background:#2a2a2a;border-radius:8px;padding:.5em;text-align:center}"
            ".card img{max-width:100%;height:auto;display:block;margin:0 auto .5em;border-radius:4px;cursor:pointer}"
            ".card .dl{color:#7ab8ff;text-decoration:none;font-size:.85em;word-break:break-all}"
            ".card .dl:hover{text-decoration:underline}"
            ".failed{margin-top:1.5em;background:#3a2a2a;padding:.5em 1em;border-radius:6px}"
            ".failed summary{cursor:pointer;color:#ffb3b3}"
            ".failed ul{font-size:.85em;word-break:break-all}"
            "</style></head><body>"
            f"<h1>BatchImageFilter — {len(images_b64)}/{total} images</h1>"
            f"<div class='meta'>Filters applied: {filters_str} · Click any image to download</div>"
            f"<div class='grid'>{''.join(cards)}</div>"
            f"{failed_block}"
            "</body></html>"
        )

    def piece_function(self, input_data: InputModel):
        urls = input_data.image_urls
        if not urls:
            raise ValueError("image_urls is empty — provide at least one URL.")

        enabled_filters = [
            name for name in FILTER_MASKS
            if getattr(input_data, name)
        ]
        self.logger.info(f"Enabled filters: {enabled_filters or '(none — passthrough)'}")

        Path(self.results_path).mkdir(parents=True, exist_ok=True)
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
            ),
            "Accept": "image/avif,image/webp,image/png,image/jpeg,image/*,*/*;q=0.8",
        }

        out_paths: List[str] = []
        out_b64: List[str] = []
        failed: List[str] = []
        want_file = input_data.output_type in ("file", "both")
        want_b64 = input_data.output_type in ("base64_string", "both")

        for idx, url in enumerate(urls):
            self.logger.info(f"[{idx + 1}/{len(urls)}] downloading {url}")
            try:
                resp = requests.get(url, timeout=30, headers=headers)
                resp.raise_for_status()
                img = Image.open(io.BytesIO(resp.content)).convert("RGB")
            except Exception as exc:
                self.logger.warning(f"[{idx + 1}/{len(urls)}] skipping {url}: {exc}")
                failed.append(url)
                continue

            arr = np.asarray(img, dtype=np.float32)
            for name in enabled_filters:
                mask = np.array(FILTER_MASKS[name], dtype=np.float32)
                arr[..., :3] = np.clip(arr[..., :3] @ mask.T, 0, 255)

            modified = Image.fromarray(arr.astype(np.uint8))

            if want_file:
                path = str(Path(self.results_path) / f"filtered_{idx}.png")
                modified.save(path, format="PNG")
                out_paths.append(path)

            if want_b64:
                buf = io.BytesIO()
                modified.save(buf, format="PNG")
                out_b64.append(base64.b64encode(buf.getvalue()).decode("utf-8"))

        if failed:
            self.logger.warning(f"{len(failed)}/{len(urls)} URLs failed: {failed}")
        if not out_paths and not out_b64:
            raise RuntimeError(f"All {len(urls)} URLs failed to download. See logs.")

        gallery_b64_source = out_b64 if out_b64 else [
            base64.b64encode(Path(p).read_bytes()).decode("utf-8") for p in out_paths
        ]
        gallery_html = self._build_gallery_html(
            gallery_b64_source,
            enabled_filters,
            failed,
            total=len(urls),
        )
        self.display_result = {
            "file_type": "html",
            "base64_content": base64.b64encode(gallery_html.encode("utf-8")).decode("utf-8"),
        }

        preview_b64 = out_b64[-1] if out_b64 else None
        if preview_b64 is None and out_paths:
            with open(out_paths[-1], "rb") as f:
                preview_b64 = base64.b64encode(f.read()).decode("utf-8")
        if preview_b64:
            self.display_result = {
                "file_type": "png",
                "base64_content": preview_b64,
            }

        return OutputModel(
            image_file_paths=out_paths,
            image_base64_strings=out_b64,
        )
