# Target library provenance

Coordinates and apparent magnitudes are read locally from data/catalogs/targets.json, a reduced J2000 lookup extracted from d3-celestial 0.7.35's Messier and dsos.14 catalogs. The local catalogs retain the upstream BSD license and require no JavaScript runtime. The expanded library uses approximate educational distances and cluster populations; these are not precise measurements of membership. Paired distances are representative rounded distances, and the Double Cluster population represents both clusters together. Nebula distances in particular vary among published estimates.

Primary reference collections:

- NASA Hubble Messier catalog: https://science.nasa.gov/mission/hubble/science/explore-the-night-sky/hubble-messier-catalog/
- NASA Hubble Caldwell catalog (Double Cluster, NGC 2392, NGC 3242, NGC 7662): https://science.nasa.gov/mission/hubble/science/explore-the-night-sky/hubble-caldwell-catalog/
- NASA M3 (34,000 light-years; over 500,000 stars): https://science.nasa.gov/mission/hubble/science/explore-the-night-sky/hubble-messier-catalog/messier-3/
- NASA M81 (11.6 million light-years, rounded for the pair): https://science.nasa.gov/mission/hubble/science/explore-the-night-sky/hubble-messier-catalog/messier-81/

All current sketches are deterministic procedural illustrations built from drawn stars, shapes, and simulated glow. The generator does not load third-party image pixels. They approximate morphology and faint eyepiece impressions for 6-8 inch telescopes, not photographic details or exact star positions. Source paper sketches, inverted circular RGBA images, and SHA-256 hashes are cached in assets/generated/sketches/. This documents the generation method rather than guaranteeing copyright clearance. Dependencies retain their own licenses; see THIRD_PARTY_NOTICES.md.

Early review used downloaded Deep Sky Watch sketches, which have been removed from the project. Old review PDFs may embed those works; output/ is ignored and those PDFs are not licensed for redistribution by this project. Historical visual guidance also included this linked reference: https://www.astroshop.eu/CMS/images/text/category/deepsky-land_messier_81_messier_82_rund_all.jpg . No reference image is bundled.

M81/M82 revision 3 independently derives relative centers and optical major-axis directions from de Blok et al. (2018), Table 2: https://arxiv.org/pdf/1808.02840 (DOI: 10.3847/1538-4357/aad557). Only numerical facts are stored in data/m81-m82-geometry.json; no paper figures are reproduced. Position angles are 157 and 65 degrees east of north. A north-up/east-left small-field projection is rotated 23 degrees for display; the whole field rotation is arbitrary. Brightness profiles, visible extent, and unrelated field stars remain schematic. Individual asset versions invalidate revised cached drawings.
