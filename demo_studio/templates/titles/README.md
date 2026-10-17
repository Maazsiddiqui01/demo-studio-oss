# Slides, captions and the overlay look

`overlay.css` styles everything demo-studio draws on top of the app, inside a shadow root:

- the intro layouts (statement, product, agenda, cinematic) and outro layouts (summary, cta,
  cinematic);
- the step caption styles (card, pill, lower);
- the highlight ring, the cursor and its click pulse, and the "sped up" badge.

Colours come from the theme on `.wrap[data-theme]` (petrol, kinetic, navy); `style.accent` in a
storyboard replaces the accent and ring colour. Fonts (Archivo, Mona Sans, JetBrains Mono, Inter)
are bundled in `../fonts` under the SIL Open Font License. Preview every design over your own app
with `studio slides <storyboard>`.
