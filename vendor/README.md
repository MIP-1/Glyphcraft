# Vendored muxers

Offline copies of two MIT-licensed muxers, used by the WebCodecs export path.
No network access is needed at runtime or at build time.

| File | Package | Version | License |
| --- | --- | --- | --- |
| `mp4-muxer.mjs` | `mp4-muxer` | 5.2.2 | MIT, `mp4-muxer.LICENSE.txt` |
| `webm-muxer.mjs` | `webm-muxer` | 5.1.4 | MIT, `webm-muxer.LICENSE.txt` |
| `mp4-muxer.js` | `mp4-muxer` | 5.2.2 | MIT, `mp4-muxer.LICENSE.txt` |
| `webm-muxer.js` | `webm-muxer` | 5.1.4 | MIT, `webm-muxer.LICENSE.txt` |

SHA-256 of the upstream build files, taken from the published npm tarballs:

```
d2c4c782f180c86ed30b1f5d9487a34a0d370bf9b4535285734ea187d38f9bb5  mp4-muxer.mjs
53710543cecc4db7b6cd23fb0d9b308aa3374697f43a6149a8497f0a8547f0cb  webm-muxer.mjs
```

The `.js` files are generated from those two files by `tools/vendor_muxers.py`.
The only change is the final ESM `export { ... }` block, replaced by a
`window.Mp4Muxer` / `window.WebmMuxer` global, because a dynamic `import()` of a
file URL is blocked on `file://` (origin "null"). All other bytes are unchanged.

Both are loaded on demand only when a video export starts, through a classic
`<script>` tag, which works from `file://`, the static site and `dist`.
`npm run build` copies this directory to `dist/vendor/` byte for byte.
