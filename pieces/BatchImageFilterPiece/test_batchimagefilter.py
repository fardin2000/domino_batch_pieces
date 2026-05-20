from domino.testing import piece_dry_run


def test_batch_image_filter_single_url():
    out = piece_dry_run(
        piece_name="BatchImageFilterPiece",
        input_data=dict(
            image_urls=[
                "https://picsum.photos/seed/domino1/200/200",
            ],
            filter_type="BLUR",
        ),
        secrets_data={},
    )
    assert len(out["filtered_image_paths"]) == 1
    assert len(out["filtered_images_base64"]) == 1


def test_batch_image_filter_multiple_urls():
    out = piece_dry_run(
        piece_name="BatchImageFilterPiece",
        input_data=dict(
            image_urls=[
                "https://picsum.photos/seed/domino1/200/200",
                "https://picsum.photos/seed/domino2/200/200",
            ],
            filter_type="CONTOUR",
        ),
        secrets_data={},
    )
    assert len(out["filtered_image_paths"]) == 2
