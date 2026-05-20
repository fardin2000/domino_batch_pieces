# Interview prep: BatchImageFilterPiece

## 60-second framing

> "The task was to take Domino's `Image Filter` example workflow — which
> processes one image — and make it work on a list. I built a single new
> piece, `BatchImageFilterPiece`, that takes a list of URLs, downloads each,
> applies one or more color-matrix filters, and returns the filtered images.
> It deliberately mirrors the original piece's filter set and UI conventions,
> but folds the `HTTPRequest → ImageFilter` two-node pattern into one node
> and adds batch-specific behavior like per-URL error isolation and a
> gallery-style result preview."

That arc — **understood the original → made a deliberate change → handled
the new failure modes batching introduces** — is what they'll be listening for.

---

## Walkthrough order

1. **`config.toml`** (10 sec) — Standard Domino Pieces repo metadata. Bumping
   `VERSION` here is what triggers the CI workflow that builds the Docker
   image and cuts a release.

2. **`metadata.json`** (10 sec) — Name has to match the folder name and the
   class name. The folder name has to end in `Piece` — that's how Domino's
   CLI discovers pieces (`glob('pieces/*Piece')`). I found this the hard way
   when the first CI run reported "No pieces found."

3. **`models.py`** — design choices live here:
   - `image_urls: List[str]` → batch input.
   - Ten `bool` fields, one per filter → "renders as combinable checkboxes
     in the Domino GUI, exactly like the original. I tried a single `Enum`
     first and learned that enums render as a single dropdown and can't
     accept upstream values."
   - `output_type: OutputType` → "lets users pick file/base64/both depending
     on whether their workflow has shared storage configured."
   - `OutputModel` returns two parallel lists.

4. **`piece.py`** — top to bottom:
   - `FILTER_MASKS` — "3×3 RGB transform matrices copied verbatim from the
     original so the colors match exactly."
   - Validation + `enabled_filters` collection.
   - Per-URL loop wrapped in try/except — "this is the key batch behavior:
     one bad URL shouldn't kill the run."
   - The matrix multiply `arr[..., :3] @ mask.T` — "the original loops
     pixel-by-pixel in Python; this is the same math vectorized, ~1000×
     faster on a large image."
   - The fail-if-all-failed check — "otherwise the workflow would report
     success with empty outputs, which is worse than a clear failure."
   - The HTML gallery for `display_result` — "Domino's `display_result` only
     takes one file, so a batch piece either shows one image (bad UX) or
     builds one composite artifact. I went with a self-contained HTML page
     with embedded base64 images so the user can preview all images AND
     save them individually."

---

## Decisions to defend

Each has a real trade-off — know both sides.

| Decision | Why | What I gave up |
|---|---|---|
| **One piece, not `BatchHTTPRequest → BatchImageFilter`** | Passing a list of base64 strings through Domino XCom is bulky and hard to inspect; fewer moving parts. | Less composable — someone who only wants batched downloads can't use it. |
| **`bool`-per-filter, not an `Enum`** | Matches original UI (combinable toggles); enums can't take upstream values. | 10 fields is visually busy. |
| **Return both file paths AND base64** | File paths require shared storage; base64 works either way. | Doubles XCom payload size. |
| **Skip-on-error per URL** | A batch operation should give you what it can. | Output lists may be shorter than input lists — downstream pieces need to handle that. |
| **Fail if ALL URLs fail** | Silent empty success is worse than a clear failure. | One more line, slight loss of "pure" skip semantics. |
| **Vectorized matrix math** | Original's pixel loop is slow; the operation IS a matrix product. | Nothing — same result, fewer lines. (Freebie — flag it.) |
| **Browser-like User-Agent** | Default `python-requests` UA gets 403'd by Wikipedia, CDNs, etc. | Doesn't help against sites that block hotlinking on purpose (Shutterstock). |
| **HTML gallery for preview** | `display_result` takes one file; showing only the last image is bad UX. | HTML inlines images twice (img + a-href), so large batches make the file chunky. |

---

## Likely questions + good answers

**"Walk me through what happens when this piece runs."**
> Domino spins up the piece's Docker image as a container, sets
> `self.results_path` to a path on the shared volume, calls
> `piece_function(input_data)`. The pydantic models validate the input. I
> collect enabled filters, then for each URL I download, decode, apply
> filters, save to results_path, and base64-encode. After the loop I
> generate the HTML gallery and assign it to `self.display_result`. The
> return value is pydantic-validated against `OutputModel` and pushed to
> Domino's XCom so downstream pieces can consume the lists.

**"Why didn't you parallelize the downloads?"**
> Sequential is fine for the assignment — likely small batches. Concurrency
> adds real complexity: error aggregation, log interleaving, partial
> failures. For 10+ URLs it'd start to matter; my first move would be
> `concurrent.futures.ThreadPoolExecutor` for the I/O since `requests`
> releases the GIL on the network call. Image processing itself is
> CPU-bound and benefits less from threads.

**"What if a URL returns a non-image file?"**
> `Image.open(io.BytesIO(resp.content))` raises `UnidentifiedImageError`,
> which my generic `except Exception` catches — that URL gets logged and
> skipped just like a 403. I picked broad exception handling deliberately
> because a batch piece should be defensive about any per-item failure.

**"The original takes a file path OR a base64 string. Why doesn't yours?"**
> By collapsing the HTTPRequest piece into this one, the input is just
> URLs. If I wanted to keep upstream chaining as an option I'd add an
> optional `input_images_base64: List[str]` field with
> `from_upstream='allowed'` and use it if `image_urls` is empty.
> Trade-off: more conditional logic and a second valid input path users
> could be confused by.

**"How did you debug when CI failed?"**
> Three real failures:
> 1. "No pieces found" — read the Domino CLI source, found it globs
>    `pieces/*Piece`. Renamed folder/class/metadata.
> 2. Test container returned HTML 500 — the body was a Bottle 500 page,
>    which told me the piece raised inside the container. Suspected
>    Wikipedia's UA gating. Added a User-Agent header and switched test
>    URLs to picsum.photos.
> 3. Shutterstock 403 in the live workflow — same UA story, but for a site
>    that blocks all hotlinking. Realized fail-fast was wrong for a batch
>    piece and switched to skip-on-error.

**"What would you change with another day?"**
> 1. Concurrent downloads via a thread pool with configurable max-parallelism.
> 2. Make the HTML gallery use thumbnails inline and keep full-res only in
>    the download links, so the HTML stays compact for large batches.
> 3. Smarter retry on 5xx with exponential backoff before giving up on a URL.

**"Anything you'd do differently in hindsight?"**
> Shipped the wrong filter family on the first pass — used PIL's
> convolution filters (BLUR, EMBOSS) without checking what the original
> actually did. Should have read the original `piece.py` first, not just
> the workflow description. Easy lesson: when the task says "extend X,"
> read X's source before designing Y.

---

## Flag these proactively

Interviewers like candidates who pre-empt obvious questions:

- **"The folder/class/metadata suffix `Piece` is required by Domino's
  discovery. I learned that from the CLI source."** Shows you read
  framework code, not just docs.
- **"I vectorized the matrix math — same op as the original but as one
  numpy expression instead of a Python loop."** Shows you understood the
  original well enough to see the optimization.
- **"The output schema returns both paths and base64 because shared
  storage isn't always configured."** Shows you understood Domino's
  deployment model.
- **"I built an HTML gallery for the preview because `display_result`
  only takes one file."** Shows you hit and worked around a framework
  constraint.

---

## What NOT to say

- Don't dwell on CI/release plumbing (branch renames, repo permissions).
  Interesting but it's plumbing — they care about design judgment, not `gh`
  CLI skills.
- Don't oversell. "It's a single-piece MVP; for production I'd add X, Y, Z"
  is way better than presenting it as finished.
- Don't claim more than you did. If they ask about something not covered
  above (Domino's scheduler internals, K8s deploy path), say "I haven't
  dug into that part of Domino yet."
