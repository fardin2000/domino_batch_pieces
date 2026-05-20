from domino.testing import piece_dry_run


def test_batch_image_filter_single_url_sepia():
    out = piece_dry_run(
        piece_name="BatchImageFilterPiece",
        input_data=dict(
            image_urls=["https://picsum.photos/seed/domino1/200/200"],
            sepia=True,
        ),
        secrets_data={},
    )
    assert len(out["image_file_paths"]) == 1
    assert len(out["image_base64_strings"]) == 1


def test_batch_image_filter_multiple_urls_and_filters():
    out = piece_dry_run(
        piece_name="BatchImageFilterPiece",
        input_data=dict(
            image_urls=[
                "https://picsum.photos/seed/domino1/200/200",
                "https://picsum.photos/seed/domino2/200/200",
            ],
            black_and_white=True,
            contrast=True,
        ),
        secrets_data={},
    )
    assert len(out["image_file_paths"]) == 2
    assert len(out["image_base64_strings"]) == 2


def test_batch_image_filter_output_type_file_only():
    out = piece_dry_run(
        piece_name="BatchImageFilterPiece",
        input_data=dict(
            image_urls=["https://picsum.photos/seed/domino1/200/200"],
            brightness=True,
            output_type="file",
        ),
        secrets_data={},
    )
    assert len(out["image_file_paths"]) == 1
    assert len(out["image_base64_strings"]) == 0
