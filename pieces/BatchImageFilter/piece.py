import base64
import io
from pathlib import Path
from typing import List

import requests
from PIL import Image, ImageFilter

from domino.base_piece import BasePiece

from .models import InputModel, OutputModel


PIL_FILTERS = {
    "BLUR": ImageFilter.BLUR,
    "CONTOUR": ImageFilter.CONTOUR,
    "DETAIL": ImageFilter.DETAIL,
    "EDGE_ENHANCE": ImageFilter.EDGE_ENHANCE,
    "EMBOSS": ImageFilter.EMBOSS,
    "SHARPEN": ImageFilter.SHARPEN,
    "SMOOTH": ImageFilter.SMOOTH,
}


class BatchImageFilter(BasePiece):

    def piece_function(self, input_data: InputModel):
        urls = input_data.image_urls
        if not urls:
            raise ValueError("image_urls is empty — provide at least one URL.")

        pil_filter = PIL_FILTERS[input_data.filter_type.value]

        out_paths: List[str] = []
        out_b64: List[str] = []

        for idx, url in enumerate(urls):
            self.logger.info(f"[{idx + 1}/{len(urls)}] downloading {url}")
            resp = requests.get(url, timeout=30)
            resp.raise_for_status()

            img = Image.open(io.BytesIO(resp.content)).convert("RGB")
            filtered = img.filter(pil_filter)

            out_path = str(Path(self.results_path) / f"filtered_{idx}.png")
            filtered.save(out_path, format="PNG")
            out_paths.append(out_path)

            buf = io.BytesIO()
            filtered.save(buf, format="PNG")
            out_b64.append(base64.b64encode(buf.getvalue()).decode("utf-8"))

        self.display_result = {
            "file_type": "png",
            "base64_content": out_b64[-1],
        }

        return OutputModel(
            filtered_image_paths=out_paths,
            filtered_images_base64=out_b64,
        )
