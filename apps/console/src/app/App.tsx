import { Console } from '../console/Console';
import { GuidedDemo } from '../landing/GuidedDemo';
import { Landing } from '../landing/Landing';
import { useRoute } from '../shared/route';

/** Three views over one palette: the landing page, its walkthrough, and the console. */
export function App() {
  const route = useRoute();
  if (route === 'console') return <Console />;
  if (route === 'demo') return <GuidedDemo />;
  return <Landing />;
}
