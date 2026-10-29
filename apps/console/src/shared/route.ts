import { useEffect, useState } from 'react';

/**
 * Hash routes, so the build runs unchanged from a static host, a project
 * subpath or the service's static mount. Any hash that is not a route (an
 * in-page anchor such as #how) leaves you on the landing page.
 */
export type Route = 'home' | 'demo' | 'console';

export function parseRoute(hash: string): Route {
  if (hash.startsWith('#/console')) return 'console';
  if (hash.startsWith('#/demo')) return 'demo';
  return 'home';
}

export function navigate(route: Route): void {
  const next = route === 'home' ? '#/' : `#/${route}`;
  if (window.location.hash !== next) window.location.hash = next;
  window.scrollTo(0, 0);
}

export function useRoute(): Route {
  const [route, setRoute] = useState<Route>(() => parseRoute(window.location.hash));
  useEffect(() => {
    const onHash = () => setRoute(parseRoute(window.location.hash));
    window.addEventListener('hashchange', onHash);
    return () => window.removeEventListener('hashchange', onHash);
  }, []);
  return route;
}
