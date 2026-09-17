# Homepage gallery and torn-paper design notes

The homepage refinements in this branch use native horizontal scrolling and scroll snapping for touch/trackpad accessibility rather than hijacking vertical page scroll.

For the **Why RI BUROM** section, the implementation follows established torn-paper techniques: an irregular polygon silhouette for the torn edge, layered paper-colour gradients for aged fibre/stain variation, and drop-shadow depth. This keeps the visual effect lightweight and responsive without requiring a stock-paper image. The implementation intentionally avoids applying an SVG displacement filter to live text, which can reduce readability.

References consulted during implementation:

- MDN, `mask-image`: https://developer.mozilla.org/en-US/docs/Web/CSS/Reference/Properties/mask-image
- MDN, SVG `feTurbulence`: https://developer.mozilla.org/en-US/docs/Web/SVG/Reference/Element/feTurbulence
- Torn-paper experiment using turbulence/displacement techniques: https://codepen.io/wakana-k/pen/ExJbXVe
- CSS paper-effect examples, including jagged `clip-path` torn edges: https://freefrontend.com/css-paper-effects/
