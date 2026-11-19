Workpal current brand assets

workpal-logo.svg       Current orange tile with the serif W and dot.
workpal-mark.svg       Transparent W-and-dot symbol; uses currentColor.
workpal-wordmark.svg   Current italic Inter 600 Workpal wordmark, embedded font.
workpal-favicon.svg    Small orange-tile variant for browser tabs.

The existing welcome-screen design is the reference; these are not new designs.
The wordmark embeds assets/fonts/inter-latin.woff2, whose license is in
assets/fonts/LICENSE.txt. No remote font or image requests are needed.

Edit SVG sources here. scripts/build-brand.mjs generates src/brand.js, and
npm run build embeds the assets and favicon into dist/Workpal.html.
Workspace initials such as TAP's T are workspace identities, not product logos.
