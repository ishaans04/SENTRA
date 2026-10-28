/**
 * The map's layout carries meaning, so the ordering rules are worth pinning.
 *
 * If bands stop running from trusted interior to outside world, the central
 * visual argument — a risk path descends through every band — silently stops
 * being true while the page still renders.
 */

import { describe, expect, it } from 'vitest';

import type { Architecture, GraphEdge, GraphNode } from '../../shared/lib/types';
import { buildLayout, groupParallel, routeEdge, toneFor } from './layout';

function node(id: string, zone: string): GraphNode {
  return {
    id,
    kind: 'agent',
    label: id,
    zone,
    data_classification: 'internal',
    registration: 'expected',
    trust: 'internal',
    declared: true,
  };
}

const architecture: Architecture = {
  version: 'test/v1',
  zones: {
    external: { order: 3, label: 'External', trust: 'external' },
    inner: { order: 1, label: 'Inner', trust: 'internal' },
    shared: { order: 2, label: 'Shared', trust: 'untrusted' },
  },
  nodes: [node('A', 'inner'), node('B', 'inner'), node('C', 'shared'), node('D', 'external')],
  allowed_relationships: [],
  invariants: [],
  control_capabilities: [],
};

function edge(source: string, target: string, action: GraphEdge['action']): GraphEdge {
  return {
    id: `${source}--${action}-->${target}`,
    source,
    target,
    action,
    first_seen: '2026-09-19T10:00:00Z',
    last_seen: '2026-09-19T10:00:00Z',
    expected_status: 'expected',
    observation_count: 1,
    evidence_event_ids: [],
  };
}

describe('buildLayout', () => {
  it('orders bands by the order the manifest declares, not by object key order', () => {
    const layout = buildLayout(architecture, []);
    expect(layout.bands.map((band) => band.id)).toEqual(['inner', 'shared', 'external']);
  });

  it('places the external band below every internal one', () => {
    const layout = buildLayout(architecture, []);
    const inner = layout.bands.find((band) => band.id === 'inner')!;
    const external = layout.bands.find((band) => band.id === 'external')!;
    expect(external.y).toBeGreaterThan(inner.y);
  });

  it('puts every node in its own zone band', () => {
    const layout = buildLayout(architecture, []);
    const a = layout.byId.get('A')!;
    const c = layout.byId.get('C')!;
    const innerBand = layout.bands.find((band) => band.id === 'inner')!;
    expect(a.y).toBe(innerBand.y + innerBand.height / 2);
    expect(c.y).toBeGreaterThan(a.y);
  });

  it('separates nodes that share a band', () => {
    const layout = buildLayout(architecture, []);
    expect(layout.byId.get('A')!.x).not.toBe(layout.byId.get('B')!.x);
  });

  it('keeps every node clear of the zone rail', () => {
    const layout = buildLayout(architecture, []);
    for (const placed of layout.nodes) expect(placed.x).toBeGreaterThan(layout.rail);
  });

  it('places nodes the manifest never declared but the ledger reported', () => {
    const observed = [...architecture.nodes, node('Mystery', 'unknown-zone')];
    const layout = buildLayout(architecture, observed);
    expect(layout.byId.has('Mystery')).toBe(true);
    expect(layout.bands.at(-1)!.id).toBe('unknown-zone');
  });

  it('is a pure function of its inputs, so the map never reflows on replay', () => {
    const first = buildLayout(architecture, []);
    const second = buildLayout(architecture, []);
    expect(first.nodes).toEqual(second.nodes);
  });
});

describe('routeEdge', () => {
  it('arcs relationships that stay inside one band', () => {
    const layout = buildLayout(architecture, []);
    const path = routeEdge(layout.byId.get('A')!, layout.byId.get('B')!, 0, 1);
    expect(path).toContain('Q');
  });

  it('runs a curve between bands', () => {
    const layout = buildLayout(architecture, []);
    const path = routeEdge(layout.byId.get('A')!, layout.byId.get('C')!, 0, 1);
    expect(path).toContain('C');
  });

  it('fans parallel relationships apart so neither is hidden', () => {
    const layout = buildLayout(architecture, []);
    const from = layout.byId.get('A')!;
    const to = layout.byId.get('C')!;
    expect(routeEdge(from, to, 0, 2)).not.toBe(routeEdge(from, to, 1, 2));
  });
});

describe('groupParallel', () => {
  it('collects every action between one pair of nodes', () => {
    const groups = groupParallel([
      edge('A', 'C', 'write'),
      edge('A', 'C', 'discover'),
      edge('B', 'C', 'read'),
    ]);
    expect(groups.size).toBe(2);
    expect([...groups.values()].find((group) => group.length === 2)).toBeDefined();
  });
});

describe('toneFor', () => {
  const incident = new Set(['A--write-->C']);

  it('marks a hop the finding names as the risk path', () => {
    expect(toneFor(edge('A', 'C', 'write'), incident)).toBe('incident');
  });

  it('marks an undeclared relationship even when no finding exists', () => {
    const undeclared = { ...edge('A', 'C', 'discover'), expected_status: 'unexpected' as const };
    expect(toneFor(undeclared, new Set())).toBe('undeclared');
  });

  it('leaves declared relationships quiet', () => {
    expect(toneFor(edge('B', 'C', 'read'), new Set())).toBe('declared');
  });
});
