import { BRAND } from './theme';

export function Brand({ size = 17 }: { size?: number }) {
  return (
    <span className="brand">
      <span className="brand-mark" aria-hidden="true" />
      <span className="brand-name" style={{ fontSize: size }}>
        {BRAND}
      </span>
    </span>
  );
}
