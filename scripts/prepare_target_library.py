#!/usr/bin/env python3
"""Prepare and inspect the complete local library without network requests."""
import hashlib
import json
from pathlib import Path
from PIL import Image, ImageDraw
from eyepiece import make_assets, SKETCH_MANIFEST
from handout import DEFAULTS, AUSTIN_LOCATION
from astronomy_data import compute_astronomy

ROOT = Path(__file__).resolve().parents[1]

def main():
    assets = make_assets()
    metadata = json.loads((ROOT / 'data/targets.json').read_text())
    assert set(assets) == set(metadata)
    config = {**DEFAULTS, 'date': '2026-10-15', 'timezone': 'America/Chicago', 'location': AUSTIN_LOCATION}
    data = compute_astronomy(config, '2026-10-16T02:00:00Z')
    assert {t['id'] for t in data['targets']} == set(metadata), 'Some coordinates did not resolve'
    before = {t: hashlib.sha256(p.read_bytes()).hexdigest() for t,p in assets.items()}
    again = make_assets()
    assert before == {t: hashlib.sha256(p.read_bytes()).hexdigest() for t,p in again.items()}, 'Cache reuse changed artwork'
    tile_w, tile_h, columns = 330, 370, 3
    sheet = Image.new('RGB', (columns * tile_w, ((len(assets)+columns-1)//columns)*tile_h), 'white')
    draw = ImageDraw.Draw(sheet)
    for i, (target, path) in enumerate(assets.items()):
        x, y = i % columns * tile_w, i // columns * tile_h
        with Image.open(path) as source:
            assert source.mode == 'RGBA' and source.getpixel((0,0))[3] == 0
            source = source.resize((300,300))
            sheet.paste(source, (x+15,y+10), source)
        draw.text((x+15,y+315), target, fill='black')
        draw.text((x+15,y+335), metadata[target]['common_name'], fill='black')
    out = ROOT / 'output' / 'images' / 'cached-target-library.png'
    out.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(out)
    print(f'PASS: {len(assets)} local targets, all coordinates resolved, circular transparency, unchanged cache hashes')
    print(f'Review sheet: {out}')
    print(f'Asset manifest: {SKETCH_MANIFEST}')

if __name__ == '__main__':
    main()
