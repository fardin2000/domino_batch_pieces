from enum import Enum
from typing import List

from pydantic import BaseModel, Field


class FilterType(str, Enum):
    BLUR = "BLUR"
    CONTOUR = "CONTOUR"
    DETAIL = "DETAIL"
    EDGE_ENHANCE = "EDGE_ENHANCE"
    EMBOSS = "EMBOSS"
    SHARPEN = "SHARPEN"
    SMOOTH = "SMOOTH"


class InputModel(BaseModel):
    """BatchImageFilter Input"""
    image_urls: List[str] = Field(
        default=[],
        description="List of image URLs to download and filter.",
    )
    filter_type: FilterType = Field(
        default=FilterType.BLUR,
        description="PIL ImageFilter to apply to each downloaded image.",
    )


class OutputModel(BaseModel):
    """BatchImageFilter Output"""
    filtered_image_paths: List[str] = Field(
        description="Paths to filtered images written to shared storage.",
    )
    filtered_images_base64: List[str] = Field(
        description="Base64-encoded PNGs of the filtered images.",
    )
