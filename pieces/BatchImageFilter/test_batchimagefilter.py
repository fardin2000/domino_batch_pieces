from domino.testing import piece_dry_run


def test_batch_image_filter_single_url():
    out = piece_dry_run(
        piece_name="BatchImageFilter",
        input_data=dict(
            image_urls=[
                "https://upload.wikimedia.org/wikipedia/commons/3/3a/Cat03.jpg",
            ],
            filter_type="BLUR",
        ),
        secrets_data={},
    )
    assert len(out["filtered_image_paths"]) == 1
    assert len(out["filtered_images_base64"]) == 1


def test_batch_image_filter_multiple_urls():
    out = piece_dry_run(
        piece_name="BatchImageFilter",
        input_data=dict(
            image_urls=[
                "https://upload.wikimedia.org/wikipedia/commons/3/3a/Cat03.jpg",
                "https://upload.wikimedia.org/wikipedia/commons/4/4d/Cat_November_2010-1a.jpg",
            ],
            filter_type="CONTOUR",
        ),
        secrets_data={},
    )
    assert len(out["filtered_image_paths"]) == 2
