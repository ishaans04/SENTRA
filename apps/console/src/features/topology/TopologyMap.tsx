/**
 * The interaction map.
 *
 * This is the console's primary display and the argument the product makes.
 * Zones are horizontal bands running from the trusted interior at the top to
 * the outside world at the bottom, so a path that composes restricted data with
 * external egress is visible as a line descending through every band.
 *
 * Nothing here decides anything. Every stroke reflects a relationship the core
 * reported, and the highlighted path is exactly the one the finding names.
 */

import { useMemo } from 'react';

import type { Finding, GraphEdge } from '../../shared/lib/types';
import { useConsole } from '../../shared/state/store';
import { buildLayout, groupParallel, routeEdge, toneFor, type EdgeTone } from './layout';

const TONE: Record<EdgeTone, { stroke: string; width: number; dash?: string }> = {
  declared: { stroke: '#3c444b', width: 1.1 },
  undeclared: { stroke: '#f2c46b', width: 1.3, dash: '5 5' },
  incident: { stroke: '#f4543c', width: 2.1 },
};

const NODE_GLYPH_RADIUS = 16;

function nodeAccent(
  registration: string,
  trust: string,
  classification: string,
  incident: boolean,
): string {
  if (incident) return '#f4543c';
  if (registration === 'unregistered' || registration === 'unknown') return '#f2c46b';
  if (trust === 'external') return '#9ba1a7';
  if (classification === 'restricted') return '#b79cf0';
  return '#7ff0c0';
}

/** The one caption a node earns, or nothing. */
function flagFor(node: { registration: string; data_classification: string; trust: string }) {
  if (node.registration === 'unregistered') return 'UNDECLARED';
  if (node.registration === 'unknown') return 'UNKNOWN';
  if (node.data_classification === 'restricted') return 'RESTRICTED';
  if (node.trust === 'external') return 'OUTSIDE THE ESTATE';
  return '';
}

/** Agents are circles, stores and sources are diamonds, destinations squares. */
function Glyph({ kind, accent, severed }: { kind: string; accent: string; severed: boolean }) {
  const common = {
    fill: '#0a0c0e',
    stroke: accent,
    strokeWidth: 1.2,
    opacity: severed ? 0.4 : 1,
  };
  if (kind === 'agent') return <circle r={NODE_GLYPH_RADIUS} {...common} />;
  if (kind === 'destination' || kind === 'api')
    return <rect x={-14} y={-14} width={28} height={28} {...common} />;
  return <rect x={-14} y={-14} width={28} height={28} transform="rotate(45)" {...common} />;
}

export function TopologyMap() {
  const architecture = useConsole((s) => s.architecture);
  const state = useConsole((s) => s.state);
  const findings = useConsole((s) => s.findings);
  const selectedId = useConsole((s) => s.selectedFindingId);

  const finding: Finding | null = findings.find((f) => f.id === selectedId) ?? findings[0] ?? null;

  const layout = useMemo(
    () => (architecture ? buildLayout(architecture, state?.graph.nodes ?? []) : null),
    [architecture, state?.graph.nodes],
  );

  const incidentEdges = useMemo(
    () => new Set(finding?.incident_edge_ids ?? []),
    [finding?.incident_edge_ids],
  );
  const incidentNodes = useMemo(
    () => new Set(finding?.incident_node_ids ?? []),
    [finding?.incident_node_ids],
  );

  if (!architecture || !layout) {
    return (
      <div className="flex h-full items-center justify-center label">Loading architecture</div>
    );
  }

  const edges = state?.graph.edges ?? [];
  const parallel = groupParallel(edges);
  const contained = (state?.applied_controls.length ?? 0) > 0;

  const drawable: { edge: GraphEdge; d: string; tone: EdgeTone }[] = [];
  for (const [, group] of parallel) {
    group.forEach((edge, index) => {
      const from = layout.byId.get(edge.source);
      const to = layout.byId.get(edge.target);
      if (!from || !to) return;
      drawable.push({
        edge,
        d: routeEdge(from, to, index, group.length),
        tone: toneFor(edge, incidentEdges),
      });
    });
  }

  // Draw declared relationships first so a risk path is never occluded.
  const order: Record<EdgeTone, number> = { declared: 0, undeclared: 1, incident: 2 };
  drawable.sort((a, b) => order[a.tone] - order[b.tone]);

  return (
    <figure className="m-0 h-full w-full">
      <figcaption className="sr-only">
        Interaction map. Zones run from the trusted interior at the top to external destinations at
        the bottom.
        {finding
          ? ` A ${finding.severity} severity path is highlighted: ${finding.incident_path
              .map((step) => `${step.source} ${step.action} ${step.target}`)
              .join(', then ')}.`
          : ' No risky composition is present in the current state.'}
      </figcaption>

      <svg
        viewBox={`0 0 ${layout.width} ${layout.height}`}
        className="h-full w-full"
        role="img"
        aria-label="Agent interaction map"
        preserveAspectRatio="xMidYMid meet"
      >
        <defs>
          <marker
            id="arrow-declared"
            viewBox="0 0 8 8"
            refX="7"
            refY="4"
            markerWidth="5"
            markerHeight="5"
            orient="auto-start-reverse"
          >
            <path d="M0 0 L8 4 L0 8 z" fill="#3c444b" />
          </marker>
          <marker
            id="arrow-undeclared"
            viewBox="0 0 8 8"
            refX="7"
            refY="4"
            markerWidth="5"
            markerHeight="5"
            orient="auto-start-reverse"
          >
            <path d="M0 0 L8 4 L0 8 z" fill="#f2c46b" />
          </marker>
          <marker
            id="arrow-incident"
            viewBox="0 0 8 8"
            refX="7"
            refY="4"
            markerWidth="6"
            markerHeight="6"
            orient="auto-start-reverse"
          >
            <path d="M0 0 L8 4 L0 8 z" fill="#f4543c" />
          </marker>
        </defs>

        {/* Zone bands. The rail labels are the map's legend for what a row is. */}
        {layout.bands.map((band) => {
          const external = band.trust === 'external';
          const untrusted = band.trust === 'untrusted';
          return (
            <g key={band.id}>
              <rect
                x={0}
                y={band.y}
                width={layout.width}
                height={band.height}
                fill={
                  external
                    ? 'rgba(244,84,60,.035)'
                    : untrusted
                      ? 'rgba(242,196,107,.03)'
                      : 'transparent'
                }
              />
              <line
                x1={0}
                x2={layout.width}
                y1={band.y}
                y2={band.y}
                stroke="#1a1e22"
                strokeWidth={1}
              />
              <text
                x={16}
                y={band.y + band.height / 2 - 4}
                fill={external ? '#f4543c' : untrusted ? '#f2c46b' : '#7e858c'}
                fontFamily="'IBM Plex Mono', monospace"
                fontSize={10}
                letterSpacing="0.16em"
              >
                {band.label.toUpperCase()}
              </text>
              <text
                x={16}
                y={band.y + band.height / 2 + 11}
                fill="#4d5459"
                fontFamily="'IBM Plex Mono', monospace"
                fontSize={9}
                letterSpacing="0.1em"
              >
                {band.trust}
              </text>
            </g>
          );
        })}
        <line
          x1={0}
          x2={layout.width}
          y1={layout.height - 16}
          y2={layout.height - 16}
          stroke="#1a1e22"
        />
        <line
          x1={layout.rail - 28}
          x2={layout.rail - 28}
          y1={0}
          y2={layout.height}
          stroke="#1a1e22"
        />

        {/* Relationships */}
        {drawable.map(({ edge, d, tone }) => {
          const style = TONE[tone];
          return (
            <g key={edge.id}>
              <path
                d={d}
                fill="none"
                stroke={style.stroke}
                strokeWidth={style.width}
                strokeDasharray={style.dash}
                markerEnd={`url(#arrow-${tone})`}
                style={
                  tone === 'undeclared'
                    ? { animation: 'hvDash 1.4s linear infinite' }
                    : tone === 'incident'
                      ? {
                          ['--draw-length' as string]: '600',
                          strokeDasharray: 600,
                          animation: 'hvDraw .9s ease-out forwards',
                        }
                      : undefined
                }
              >
                <title>{`${edge.source} ${edge.action} ${edge.target} — ${
                  edge.expected_status === 'expected' ? 'declared' : 'not declared'
                }, seen ${edge.observation_count}×`}</title>
              </path>
            </g>
          );
        })}

        {/* Actors and resources */}
        {layout.nodes.map((node) => {
          const incident = incidentNodes.has(node.id);
          const accent = nodeAccent(
            node.registration,
            node.trust,
            node.data_classification,
            incident,
          );
          const severed =
            contained && node.registration === 'unregistered' && !incidentNodes.has(node.id);
          return (
            <g key={node.id} transform={`translate(${node.x} ${node.y})`}>
              {incident && (
                <circle
                  r={NODE_GLYPH_RADIUS}
                  fill="none"
                  stroke={accent}
                  strokeWidth={1}
                  style={{
                    transformBox: 'fill-box',
                    transformOrigin: 'center',
                    animation: 'hvPing 2.6s ease-out infinite',
                  }}
                />
              )}
              <Glyph kind={node.kind} accent={accent} severed={severed} />
              <circle r={2.6} fill={accent} />
              <text
                y={34}
                textAnchor="middle"
                fill={incident ? '#f6f3ed' : '#8a9096'}
                fontFamily="'IBM Plex Mono', monospace"
                fontSize={10.5}
                letterSpacing="0.04em"
              >
                {node.label}
              </text>
              {/* Only the facts that change how a node should be read. A plain
                  internal agent needs no caption; the band already says where
                  it sits and the glyph already says what it is. */}
              {flagFor(node) && (
                <text
                  y={46}
                  textAnchor="middle"
                  fill={
                    node.registration === 'unregistered'
                      ? '#f2c46b'
                      : node.data_classification === 'restricted'
                        ? '#b79cf0'
                        : '#7e858c'
                  }
                  fontFamily="'IBM Plex Mono', monospace"
                  fontSize={9}
                  letterSpacing="0.1em"
                >
                  {flagFor(node)}
                </text>
              )}
            </g>
          );
        })}
      </svg>
    </figure>
  );
}

export function TopologyLegend() {
  const items: { label: string; swatch: React.ReactNode }[] = [
    {
      label: 'Declared relationship',
      swatch: <span className="block h-px w-6 bg-[#3c444b]" />,
    },
    {
      label: 'Not in the manifest',
      swatch: (
        <span className="block h-px w-6 [background:repeating-linear-gradient(90deg,#f2c46b_0_4px,transparent_4px_8px)]" />
      ),
    },
    {
      label: 'Composed risk path',
      swatch: <span className="block h-[2px] w-6 bg-[#f4543c]" />,
    },
    {
      label: 'Restricted data',
      swatch: <span className="block size-2 rotate-45 border border-[#b79cf0]" />,
    },
  ];
  return (
    <ul className="flex flex-wrap items-center gap-x-6 gap-y-2">
      {items.map((item) => (
        <li key={item.label} className="flex items-center gap-2">
          {item.swatch}
          <span className="label">{item.label}</span>
        </li>
      ))}
    </ul>
  );
}
