/**
 * The palette from index.css, for places CSS variables cannot reach: SVG
 * presentation attributes and the hero canvas.
 */
export const C = {
  paper: 'oklch(0.972 0.006 85)',
  card: 'oklch(0.992 0.004 85)',
  wash: 'oklch(0.965 0.006 85)',
  ink: 'oklch(0.23 0.012 70)',
  mute: 'oklch(0.50 0.012 70)',
  faint: 'oklch(0.70 0.01 75)',
  line: 'oklch(0.62 0.01 75)',
  rule: 'oklch(0.89 0.008 80)',
  ruleSoft: 'oklch(0.94 0.006 80)',
  red: 'oklch(0.56 0.19 30)',
  redBg: 'oklch(0.955 0.035 30)',
  amber: 'oklch(0.55 0.12 70)',
  amberLine: 'oklch(0.74 0.14 75)',
  amberBg: 'oklch(0.955 0.045 85)',
  green: 'oklch(0.50 0.11 155)',
  greenBg: 'oklch(0.955 0.035 155)',
  blue: 'oklch(0.48 0.13 262)',
  blueBg: 'oklch(0.95 0.03 262)',
} as const;

/** sRGB triples of the same tokens, for canvas strokes that need an alpha. */
export const RGB = {
  ink: '33,28,23',
  mute: '104,98,92',
  line: '138,133,128',
  red: '204,53,38',
  green: '30,117,70',
  blue: '51,90,166',
} as const;

export const BRAND = 'SENTRA';

/** Where the source lives. Left empty until the public repository exists. */
export const REPO_URL = '';

export const isMac =
  typeof navigator !== 'undefined' && /Mac|iPhone|iPad/.test(navigator.platform || '');

export const MOD_KEY = isMac ? '⌘' : 'Ctrl';
