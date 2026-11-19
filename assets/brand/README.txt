Workpal current brand assets

workpal-logo.svg       Current orange tile with the deep-green lowercase pal.
workpal-mark.svg       Transparent italic pal symbol; uses currentColor.
workpal-wordmark.svg   Current italic Inter 600 Workpal wordmark, embedded font.
workpal-favicon.svg    Small orange-tile variant for browser tabs.

The pal symbol reuses the exact embedded font and text styling from the final
three letters of the Workpal wordmark: Inter 600 italic at a 72px base size,
with -3.24px letter spacing. Scale the SVG instead of changing its font size.
The square tile places the cropped pal SVG at 84% width, centered on both axes.
The assets embed assets/fonts/inter-latin.woff2, whose license is in
assets/fonts/LICENSE.txt. No remote font or image requests are needed.

Edit SVG sources here. scripts/build-brand.mjs generates src/brand.js, and
npm run build embeds the assets and favicon into dist/Workpal.html.
Workspace initials such as TAP's T are workspace identities, not product logos.
