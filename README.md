# Star Party Handout

Help star-party visitors find their way around the sky and understand what they can expect through a telescope. This program creates a printable, two-sided US Letter handout with a sky chart for your date and location and sketches of four observing targets. It also includes first-time observing tips and links to further resources, and works with black-and-white printers.

The included [monthly target guide](docs/seasonal-targets.md) recommends four objects for each month near Austin. All of those objects have built-in sketches and facts. You can use the recommended set or choose your own four targets. Currently, you select a month's recommended set using `--targets`; the program's automatic suggestions consider the available catalog rather than choosing directly from the monthly guide.

## First-time setup

Open a terminal in this project directory. Install Python 3.10 or newer, then:

```sh
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python scripts/doctor.py
```

Activate `.venv` again in each new terminal. On Windows, create the environment with `py -m venv .venv` and activate with `.venv\Scripts\Activate.ps1` in PowerShell. All following `python` commands use that environment. Quote directory/file paths containing spaces.

Optional: install Poppler for grayscale previews (`brew install poppler` on macOS; `sudo apt install poppler-utils` on Ubuntu/Debian). Without it, handouts still generate but preview images are unavailable. Python handles astronomy calculations, cached NASA/JPL checks, sketches, and PDFs; Node.js, npm, and curl are not required. Setup requires internet to install Python packages; later builds reuse local data.

## Generate tonight's handout

```sh
python scripts/handout.py
```

Defaults are Austin, Texas, today in `America/Chicago`, and 21:00 (9 p.m.). Confirm the displayed event with Enter. Then approve the four suggested targets with Enter, enter `edit` and four comma-separated supported IDs, or enter `n` to cancel. Review altitude and conditions before approving the suggestions.

For another date and chosen targets:

```sh
python scripts/handout.py --date 2026-09-19 --time 21:00 --targets M13,M11,M27,M31
```

For an existing saved event:

```sh
python scripts/handout.py --config config/event-2026-09-19-dripping-springs.json
```

A saved date remains fixed. Omit date in a reusable config to use today, or override with `--date YYYY-MM-DD`. Time is local 24-hour `HH:MM`; the IANA timezone handles daylight saving time.

For an unattended/offline run:

```sh
python scripts/handout.py --date 2026-09-19 --targets M13,M11,M27,M31 --non-interactive --offline
```

Unattended builds require explicit targets, four saved `manual_overrides`, or `--accept-suggested-targets`. Four saved overrides skip the target-choice prompt even in interactive mode. Offline mode forbids JPL requests; missing cached validation is recorded as a warning.

## Supported targets

```sh
python scripts/handout.py --list-targets
```

Start with the [monthly target guide](docs/seasonal-targets.md), then use `--targets` to choose the four objects you want on the handout. For example, the October set is:

```sh
python scripts/handout.py --date 2026-10-17 --targets 'M31,NGC869/884,M15,M27'
```

The catalog contains 21 choices, each with a telescope sketch and a few facts for visitors. `--list-targets` shows their names and the IDs to enter. An ID is an object's catalog designation, such as `M31` for the Andromeda Galaxy. Enter NGC IDs without spaces, for example `NGC2392`.

Some choices show two objects together: `NGC869/884` is the Double Cluster, while `M81/M82` and `M65/M66` are galaxy pairs. Each pair uses one of the handout's four spaces.

If you omit `--targets`, the program suggests four objects and lets you accept or change them. By default it considers the whole catalog. A saved configuration can limit those suggestions using `target_candidates`; this does not prevent you from choosing other supported objects with `--targets`.

Prepare or check the entire offline library and create a contact sheet:

```sh
python scripts/prepare_target_library.py
```

This creates any missing sketches, checks the library, and writes a sheet showing every sketch to `output/images/cached-target-library.png`. It works without internet access. See [reference notes](docs/target-library-sources.md) for sources and the approximations used in the drawings and facts.

## Configure a location

Use your editor to copy `config/event-template.json` to a new file. JSON requires double quotes and no trailing commas. Minimal example:

```json
{
  "event_title": "Dripping Springs Star Party",
  "date": "2026-09-19",
  "time": "21:00",
  "timezone": "America/Chicago",
  "location": {
    "name": "Dripping Springs, Texas",
    "latitude": 30.1873402,
    "longitude": -98.087601,
    "elevation_m": 354
  }
}
```

West longitude is negative. Custom locations require a name, numeric latitude/longitude, and explicit IANA timezone; elevation is meters and defaults to zero. Check without building or contacting JPL:

```sh
python scripts/handout.py --config config/my-event.json --check-config
```

Other useful settings:

| Setting | Meaning |
|---|---|
| `organization.name`, `organization.website` | Club heading and QR link |
| `telescope.aperture_inches`, `telescope.sky` | Expected telescope/sky description |
| `target_candidates` | At least four different supported IDs |
| `target_selection.manual_overrides` | Empty for suggestions, or four different supported IDs in the candidate pool |
| `sky_map.star_magnitude_limit` | Default 5; smaller means fewer stars; bundled catalog maximum is 6 |
| `sky_map.show_constellation_lines` | Default true; constellation boundaries default false |
| `resources.beginner_telescope_guide` | Buying-guide link and QR code |

Command-line date, time, magnitude, and targets override their configuration choices. `config/event.schema.json` provides basic editor hints; the runner also checks timezone, artwork, and layout constraints. Paper/layout are fixed to Letter and four sketches; changing `print` fields does not change page geometry. Scoring and precession/refraction settings are developer options; operators can retain defaults.

## Change links and QR codes

There are no command-line options specifically for resource links. Edit your event JSON instead: `organization.website` controls the club link and QR code, and `resources.beginner_telescope_guide` controls the buying-guide link and QR code. The QR codes are generated from these URLs when you build the handout.

To change the project-wide defaults, edit `DEFAULTS` in [scripts/handout.py](scripts/handout.py). Values in a saved event configuration override those defaults. The printed resource labels and descriptions are currently written in [scripts/eyepiece.py](scripts/eyepiece.py), in the `WANT TO LEARN MORE?` section. If you replace the club or buying guide, update the corresponding printed URL, title, and description there too, so the text agrees with the QR destination.

## Output and printing

The program prints absolute PDF and manifest paths. Default output:

```text
output/pdf/<event-title>-<date>.pdf
output/data/<event-title>-<date>-config.json
output/data/<event-title>-<date>-astronomy.json
output/data/<event-title>-<date>-manifest.json
output/data/<event-title>-<date>-jpl-validation.json (when available)
```

The manifest records targets, resolved inputs, validation, warnings, and cache results. Its `cache.render.path` identifies the grayscale preview directory relative to the project. The handout uses black, white, and gray only. Review both pages and print at actual size/100%, US Letter, double-sided, flip on long edge. Print one copy first and scan both QR codes.

The same event title and date overwrite the same outputs, even if time/location changes. Use a different event title or `--output-dir output/my-version` to preserve alternatives. Files from a previous build can remain after failure: trust the latest successful completion and manifest, not PDF presence alone.

## Help and errors

```sh
python scripts/handout.py --help
python scripts/doctor.py
```

| Problem | Remedy |
|---|---|
| Missing Python dependency | Activate `.venv`; run `python -m pip install -r requirements.txt`. Doctor reports the interpreter. |
| Missing astronomy catalog | Restore the project's `data/catalogs/` directory. |
| Config file not found | Check path relative to the terminal's working directory; quote paths with spaces. |
| Invalid JSON | Use reported line/column; fix quotes or trailing commas. |
| Invalid timezone | Use `America/Chicago` or another IANA name; install `tzdata` if the system has no timezone data. |
| Unsupported target | Run `--list-targets`; use the exact IDs listed, with no spaces in NGC IDs. |
| Four targets required | Enter four different supported IDs separated by commas. |
| Unattended approval missing | Use `--targets`, four config overrides, or `--accept-suggested-targets`. |
| JPL unavailable | Local calculation can still produce a PDF with a manifest warning. Restore connectivity and rerun to fill the cache, or intentionally use `--offline`. |
| JPL validation failed | Build stops on disagreement; check event inputs and refresh validation before using the result. |
| Preview tool missing | Install Poppler and rerun with `--refresh-render`. |
| Permission denied | Choose writable output; project cache/, assets/generated/, and tmp/ must also be writable. |
| Cancelled/input ended | Use a terminal for prompts or `--non-interactive` with approved targets. |

Exit codes: 0 means completion (possibly with warnings), 2 means invalid input/build failure, 130 means cancellation.

## Cache and maintenance

The Python edition of Astronomy Engine computes positions locally from J2000 catalogs included in `data/catalogs/`. The catalogs originate from d3-celestial and retain its license notice; no JavaScript runs. JPL responses are cached per body, instant, and site; exact aggregates are reused. Original deterministic sketches remain in `assets/generated/sketches/` with a hash manifest. Computed astronomy and previews live in `cache/`. A changed date/location generally needs new JPL data once; sketches do not require downloads.

Refresh intentionally with `--refresh-astronomy`, `--refresh-artwork`, `--refresh-render`, or `--refresh-validation`. Validation refresh requires network and cannot combine with `--offline`. Cache has no automatic expiry. Keep resolved configs/manifests for reproducibility. Astronomy Engine's version is pinned in `requirements.txt`; other Python dependencies specify minimum versions. The astronomy cache includes hashes of the Python calculations and local catalogs, so a change to either triggers a fresh calculation.

Use `scripts/handout.py` to generate event handouts. Production generation automatically checks page count, Letter size, page order, and double-sided printing settings.

The production modules are `astronomy_data.py` (local sky calculations), `sky_map.py` (chart and astronomy report), `eyepiece.py` (sketches and reverse page), and `build_handout.py` (two-sided PDF assembly). The `verify_*.py` scripts check their corresponding sample outputs. Developer commands are ordinary Python commands:

```sh
python scripts/doctor.py
python scripts/prepare_target_library.py
python -m unittest discover -s tests
```

## Testing and misc notes

Run operator tests with `python -m unittest discover -s tests`. To extend the library, update metadata, catalog lookup, sketches, ID validation, and docs together. NGC objects use `catalog_id`; pairs use `catalog_members`. Their chart marker is the mean of member coordinates (with right ascension wrap handled), while magnitude scoring uses the brighter member. Sketches are schematic expectations, not measured field-star charts; rounded distances and cluster populations are educational estimates.

## License

Project code and original procedural sketches are available under the [MIT License](LICENSE). Dependencies retain their own licenses; see [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md). 


