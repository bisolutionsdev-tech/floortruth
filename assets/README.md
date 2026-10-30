# Pitch deck source

`build_deck.js` is the editable PptxGenJS source. To regenerate on a machine with Node.js 18+:

```bash
npm install pptxgenjs
node assets/build_deck.js
```

The default output is placed beside the `floortruth-starter` directory; override using `FLOORTRUTH_DECK_OUTPUT=/path/to/yourdeck.pptx`. The deck supplied with this package was built from this script, rendered for visual QA, and checked for text overflow.

`FloorTruth_Reference_Architecture.svg` is a completely original scalable reference diagram. The diagram depicts design intent rather than verified third-party architecture.
