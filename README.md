# BatchImageFilterPiece

A Domino Piece that downloads a list of image URLs and applies one or more
color-matrix filters (sepia, B&W, brightness, etc.) to each image.

It is the batch version of the gallery `ImageFilterPiece` from
`Tauffer-Consulting/default_domino_pieces`, with the network call (originally a
separate `HTTPRequestPiece`) folded in so the workflow needs only one node.

---

## Repository layout

```
domino_batch_pieces/
├── config.toml                            # Repo metadata; bump VERSION to trigger release
├── requirements-tests.txt                 # Deps for the CI test runner
├── dependencies/
│   └── requirements_0.txt                 # Runtime deps baked into the piece's Docker image
├── pieces/
│   └── BatchImageFilterPiece/
│       ├── metadata.json                  # Name, description, GUI label/icon, dep ref
│       ├── models.py                      # Pydantic InputModel / OutputModel
│       ├── piece.py                       # The piece_function — actual logic
│       └── test_batchimagefilter.py       # Pytest dry-run tests (runs in CI)
└── .github/workflows/
    └── validate-and-organize.yml          # Builds image, publishes to GHCR, cuts release
```

---

## How it works

### 1. Inputs (`models.py`)

The `InputModel` has three groups of fields:

| Field             | Type           | Purpose                                                     |
| ----------------- | -------------- | ----------------------------------------------------------- |
| `image_urls`      | `List[str]`    | The batch — any number of HTTP(S) URLs.                     |
| `sepia` … `warm`  | `bool` × 10    | One toggle per color-matrix filter. Combinable.             |
| `output_type`     | `OutputType`   | `file`, `base64_string`, or `both`. Default `both`.         |

Each `bool` field becomes a checkbox/toggle in the Domino GUI. The 10 filter
names mirror the original `ImageFilterPiece` exactly, so the UI feels the same.

### 2. Outputs (`models.py`)

```
image_file_paths:      List[str]   # Paths under self.results_path (shared storage)
image_base64_strings:  List[str]   # PNG bytes, base64-encoded
```

Both lists are populated based on `output_type`. Lists are aligned by index —
`image_file_paths[i]` and `image_base64_strings[i]` are the same image.

If a URL fails, **it is skipped entirely** — the lists end up shorter than
`len(image_urls)`. If all URLs fail, the piece raises so the workflow run is
marked failed instead of "succeeded with empty output."

### 3. Logic (`piece.py`)

```
1. Validate input_data.image_urls is non-empty.
2. Walk the InputModel bool fields and collect enabled filter names
   in the order defined by FILTER_MASKS.
3. Ensure self.results_path exists (mkdir parents=True, exist_ok=True).
4. For each URL:
     a. requests.get with a browser-like User-Agent.
     b. On any exception, log a warning, append to `failed`, continue.
     c. Open with Pillow, convert to RGB.
     d. Apply each enabled filter via a vectorized 3×3 matrix multiply:
            arr[..., :3] = clip(arr[..., :3] @ mask.T, 0, 255)
        (The original loops over every pixel in Python — this is ~1000×
         faster but produces the same result.)
     e. Save to disk and/or encode to base64 depending on output_type.
5. Set self.display_result to the last successful image for the GUI preview.
6. Return the parallel lists.
```

The 3×3 matrices in `FILTER_MASKS` are copied verbatim from the original
`ImageFilterPiece` so the colors come out identical.

### 4. Filters available

| Name              | Effect                                                |
| ----------------- | ----------------------------------------------------- |
| `sepia`           | Classic sepia warm-brown tone                         |
| `black_and_white` | Desaturate via equal RGB averaging                    |
| `brightness`      | Scale RGB by 1.4                                      |
| `darkness`        | Scale RGB by 0.6                                      |
| `contrast`        | Push channels apart                                   |
| `red`/`green`/`blue` | Boost one channel by 1.6                           |
| `cool`            | Reduce R, slight G, boost B                           |
| `warm`            | Boost R, reduce G and B                               |

Multiple filters can be enabled; they apply in the order listed in
`FILTER_MASKS`, with `clip(0, 255)` between each.

---

## Differences vs. the gallery `ImageFilterPiece`

| Aspect             | Gallery `ImageFilterPiece`             | `BatchImageFilterPiece`                              |
| ------------------ | -------------------------------------- | ---------------------------------------------------- |
| Nodes per workflow | 2 (HTTPRequest → ImageFilter)          | 1                                                    |
| Input              | Single base64 string from upstream     | `List[str]` URLs                                     |
| Network I/O        | HTTPRequest owns it                    | The piece owns it                                    |
| Failure handling   | Any error fails the run                | Per-URL skip-on-error; fails only if all fail        |
| Math               | Python pixel loop with `np.dot`        | Vectorized matrix multiply on whole image            |
| Output             | One image (file/base64)                | Two parallel lists (paths + base64)                  |
| GUI preview        | The one filtered image                 | The last successful image in the batch               |
| User-Agent         | Default `python-requests`              | Browser-like Mozilla/Chrome                          |

---

## Major design decisions

**Single piece instead of `BatchHTTPRequest → BatchImageFilter`.**
The task could be split into two pieces mirroring the original. We chose a
single piece because passing a list of base64 strings through Domino XCom is
bulky and hard to inspect. Cost: less reusable — anyone who wants only batched
downloads (without filtering) can't pick this off the shelf.

**Bool-per-filter, not a single enum.**
Matches the original UI exactly (checkboxes you can combine), and avoids the
Domino limitation that enums can't accept upstream values. Cost: 10 fields in
the form vs. one — more visual clutter.

**Return both paths AND base64.**
File paths only work when the workflow has shared storage configured. Base64
works in either case. Returning both makes the piece usable in any workflow
config. Cost: doubles the XCom payload — fine for small batches, not great for
hundreds of large images.

**Skip-on-error.**
A batch piece should give you what it can, not zero things because one URL was
bad. We log warnings for skipped URLs and only raise if the *entire* batch
failed. Cost: output lists may be shorter than input lists — downstream pieces
need to handle that.

**Vectorized matrix math.**
The original loops `for y: for x: np.dot(...)` which is dog-slow Python. The
equivalent `arr[..., :3] @ mask.T` produces the same result on the whole image
in one operation. Same colors, no semantic change, dramatically faster.

**Browser-like User-Agent.**
Default `python-requests` UA gets 403'd by many CDNs (Wikipedia,
Shutterstock, etc.). A Mozilla string gets past most polite filters. Sites
that *intentionally* block hotlinking (Shutterstock, Getty) still fail —
those just get skipped per the error-handling policy above.

**No `SecretsModel`.**
Domino only injects `secrets_data` if `models.py` defines a `SecretsModel`
(see `domino/base_piece.py` line 292). Omitting keeps the piece signature
clean. If we ever need API keys for protected image sources, we add it.

**Folder/class/metadata names all end in `Piece`.**
Forced by Domino — its CLI globs `pieces/*Piece` when building the repo
manifest. Anything without the suffix is silently dropped from the build,
which is exactly what broke us on the first CI run.

---

## Changelog

### 0.3.1 — PNG collage preview (replaces HTML gallery)
- The 0.3.0 HTML gallery never showed because (a) a stale `display_result`
  assignment was overwriting the gallery with the last single image, and
  (b) even with the bug fixed, Domino's frontend renders `display_result`
  HTML in a sandboxed iframe that blocks `data:` URIs for security, so the
  embedded images would never have loaded.
- Replaced with a PIL-generated PNG collage: all filtered images
  thumbnailed (≤320px each) and tiled into a `ceil(sqrt(n))`-wide grid on
  a dark background. PNG is rendered universally by Domino.
- The collage doubles as Domino's "Download content" artifact — one PNG
  containing every filtered image at thumbnail size.
- Full-resolution per-image files are still saved to `self.results_path`
  and listed in the `image_file_paths` output for downstream pieces.

### 0.3.0 — HTML gallery preview (broken — see 0.3.1)
- `display_result` is now a self-contained HTML gallery (one card per
  filtered image, each clickable to download just that image) instead of a
  single PNG showing only the last image.
- "Download content" in the Domino GUI now gives you one HTML file you can
  open in any browser to see and save every image. Individual download links
  are per-card so you don't have to extract anything manually.
- Failed URLs are shown in a collapsible block at the bottom of the gallery.
- No code-level breaking changes — output schema is unchanged from 0.2.x.

### 0.2.1 — Skip-on-error per URL
- Wrapped the per-URL download+process in try/except so a single bad URL
  doesn't kill the batch.
- Tracked `failed` URLs and logged a summary warning.
- Raise only when *every* URL fails (avoids silent empty-success).
- Upgraded the User-Agent to a Mozilla/Chrome string to get past more
  bot-filters.

### 0.2.0 — Rewrite to match the original filter set (breaking)
- Replaced single `filter_type` enum with 10 bool fields (`sepia`,
  `black_and_white`, `brightness`, `darkness`, `contrast`, `red`, `green`,
  `blue`, `cool`, `warm`).
- Switched from PIL `ImageFilter` convolution kernels to numpy color-matrix
  transforms — same math as the original `ImageFilterPiece`.
- Added `output_type` selector (`file` / `base64_string` / `both`).
- Vectorized the matrix multiply (`arr @ mask.T`) — original looped in Python.
- Added `numpy>=1.24.0` to `dependencies/requirements_0.txt`.
- Output schema field names changed: `filtered_image_paths` →
  `image_file_paths`, `filtered_images_base64` → `image_base64_strings`.
  Workflows pinned to 0.1.x must re-add the node.

### 0.1.4 — Robustness in CI
- Added `User-Agent` header so Wikipedia (and similar) stop returning 403.
- `mkdir(results_path, parents=True, exist_ok=True)` for the dry-run harness.
- Switched test image URLs from Wikipedia to `picsum.photos` (smaller,
  no UA gate, no rate limit).

### 0.1.3 — Discovery fix
- Renamed folder/class/metadata from `BatchImageFilter` to
  `BatchImageFilterPiece`. Domino globs `pieces/*Piece` — without the
  suffix the piece was silently dropped from the compiled manifest.

### 0.1.0–0.1.2 — Initial scaffold
- Pieces repo scaffolding, `config.toml`, GitHub Actions workflows.
- Initial piece using PIL `ImageFilter` convolution kernels (BLUR, CONTOUR,
  EMBOSS, etc.) — wrong filter family, replaced in 0.2.0.

---

## Releasing

1. Edit `config.toml` and bump `VERSION`.
2. `git add -A && git commit -m "..." && git push`
3. The `validate-and-organize` GitHub Action fires on any push to `main`
   that touches `config.toml`. It:
   - Validates the repo structure.
   - Generates `.domino/compiled_metadata.json` and `dependencies_map.json`.
   - Builds and pushes a Docker image to GHCR (one per dependency group).
   - Runs the pytest dry-run tests against the built image.
   - Auto-commits the `.domino/*` files.
   - Cuts a GitHub Release tagged with `VERSION`.
4. `gh run watch` to follow it. On failure: `gh run view --log-failed`.

## Installing in a local Domino instance

1. Open the Domino GUI (`localhost:3000`).
2. Left nav → **Pieces Repositories** → **Add Repository**.
3. URL: `https://github.com/fardin2000/domino_batch_pieces`, version: e.g. `0.2.1`.
4. Open the Workflow Editor — **Batch Image Filter** appears in the sidebar.
5. Set workflow Storage to **Local** if you want file outputs to flow between
   pieces; base64 outputs flow either way via XCom.

## Local dev loop (no GitHub round-trip)

```powershell
conda activate domino
cd C:\Development\Repos\Interview\domino_batch_pieces
pip install -r requirements-tests.txt
pytest pieces/BatchImageFilterPiece -v
```

Note: `domino.testing.piece_dry_run` builds a temporary Docker image and runs
the piece in a container, so Docker Desktop has to be running.
