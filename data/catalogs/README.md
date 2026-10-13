# Included astronomy catalogs

J2000 catalogs from d3-celestial 0.7.35: https://github.com/ofrohn/d3-celestial . Retain the adjacent BSD-3-Clause LICENSE when redistributing these files.

stars.6.json, starnames.json, constellations.lines.json, constellations.borders.json, and constellations.json are unchanged upstream files. targets.json is a reduced lookup extracted from upstream Messier and dsos.14 catalogs, containing only supported objects and pair members, with coordinates in degrees and apparent magnitudes. Messier entries take precedence over the larger DSO catalog, preserving the original chart data.

Catalog hashes participate in the astronomy cache key. These files are included in the source repository and need no download during handout generation. To extend the library, add catalog coordinates, metadata, and a sketch builder together.
