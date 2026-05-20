from enum import Enum
from typing import List

from pydantic import BaseModel, Field


class OutputType(str, Enum):
    file = "file"
    base64_string = "base64_string"
    both = "both"


class InputModel(BaseModel):
    """BatchImageFilter Input"""
    image_urls: List[str] = Field(
        default=[],
        description="List of image URLs to download and filter.",
    )
    sepia: bool = Field(default=False, description="Apply sepia effect.")
    black_and_white: bool = Field(default=False, description="Apply black and white effect.")
    brightness: bool = Field(default=False, description="Apply brightness effect.")
    darkness: bool = Field(default=False, description="Apply darkness effect.")
    contrast: bool = Field(default=False, description="Apply contrast effect.")
    red: bool = Field(default=False, description="Apply red effect.")
    green: bool = Field(default=False, description="Apply green effect.")
    blue: bool = Field(default=False, description="Apply blue effect.")
    cool: bool = Field(default=False, description="Apply cool effect.")
    warm: bool = Field(default=False, description="Apply warm effect.")
    output_type: OutputType = Field(
        default=OutputType.both,
        description="Format of the output images. Options: `file`, `base64_string`, `both`.",
    )


class OutputModel(BaseModel):
    """BatchImageFilter Output"""
    image_file_paths: List[str] = Field(
        default=[],
        description="Paths to filtered images written to shared storage.",
    )
    image_base64_strings: List[str] = Field(
        default=[],
        description="Base64-encoded PNGs of the filtered images.",
    )
