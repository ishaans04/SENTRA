/**
 * Console state.
 *
 * One rule governs this store: it holds what the engine said, never a
 * conclusion of its own. The console renders findings, plans and verifications
 * exactly as the core produced them. It does not compute risk, re-rank
 * candidates, or soften a failed verification into a successful one.
 */

import { create } from 'zustand';

import {
  type ApplyResult,
  type SourceKind,
  type Transport,
  TransportError,
  selectTransport,
} from '../api/client';
import type {
  Architecture,
  ContainmentPlan,
  Finding,
  Health,
  ImmunityPattern,
  ReplayState,
  ScenarioDescriptor,
  SwarmConfig,
  SwarmResult,
} from '../lib/types';

type SourceKindAlias = SourceKind;

export interface Problem {
  message: string;
  hint?: string;
}

interface ConsoleState {
  // -- source -------------------------------------------------------------
  ready: boolean;
  source: SourceKindAlias | null;
  health: Health | null;
  problem: Problem | null;

  // -- scenario -----------------------------------------------------------
  scenarios: ScenarioDescriptor[];
  scenarioId: string | null;
  architecture: Architecture | null;

  // -- replay -------------------------------------------------------------
  state: ReplayState | null;
  cursor: number;
  playing: boolean;
  busy: boolean;

  // -- analysis -----------------------------------------------------------
  findings: Finding[];
  plans: ContainmentPlan[];
  immunity: ImmunityPattern[];
  selectedFindingId: string | null;

  // -- lab ----------------------------------------------------------------
  labConfig: SwarmConfig;
  labResult: SwarmResult | null;
  labRunning: boolean;
  labProblem: Problem | null;

  // -- actions ------------------------------------------------------------
  boot(): Promise<void>;
  selectScenario(id: string): Promise<void>;
  seek(cursor: number): Promise<void>;
  step(): Promise<void>;
  runToEnd(): Promise<void>;
  restart(): Promise<void>;
  play(): void;
  pause(): void;
  selectFinding(id: string | null): void;
  applyPlan(planId: string): Promise<void>;
  promotePattern(patternId: string, to: string): Promise<void>;
  updateLab(patch: Partial<SwarmConfig>): void;
  runLab(): Promise<void>;
  dismissProblem(): void;
}

let transport: Transport | null = null;

function describe(error: unknown): Problem {
  if (error instanceof TransportError) return { message: error.message, hint: error.hint };
  if (error instanceof Error) return { message: error.message };
  return { message: 'Something went wrong talking to the analysis engine.' };
}

export const DEFAULT_LAB: SwarmConfig = {
  population: 24,
  connectivity: 'normal',
  shared_memory: 'enabled',
  delegation: 'normal',
  external_access: 'limited',
  perturbation: 'unregistered_shared_resource',
};

export const useConsole = create<ConsoleState>((set, get) => ({
  ready: false,
  source: null,
  health: null,
  problem: null,

  scenarios: [],
  scenarioId: null,
  architecture: null,

  state: null,
  cursor: 0,
  playing: false,
  busy: false,

  findings: [],
  plans: [],
  immunity: [],
  selectedFindingId: null,

  labConfig: DEFAULT_LAB,
  labResult: null,
  labRunning: false,
  labProblem: null,

  // ------------------------------------------------------------------

  async boot() {
    try {
      const selected = await selectTransport();
      transport = selected.transport;
      const scenarios = await transport.scenarios();
      set({
        ready: true,
        source: transport.kind,
        health: selected.health,
        scenarios,
      });
      if (scenarios.length) await get().selectScenario(scenarios[0].id);
    } catch (error) {
      set({ ready: true, problem: describe(error) });
    }
  },

  async selectScenario(id) {
    if (!transport) return;
    set({ busy: true, playing: false, scenarioId: id, selectedFindingId: null });
    try {
      const architecture = await transport.architecture(id);
      set({ architecture });
      await get().seek(0);
      const immunity = await transport.immunity(id);
      set({ immunity });
    } catch (error) {
      set({ problem: describe(error) });
    } finally {
      set({ busy: false });
    }
  },

  async seek(cursor) {
    const { scenarioId } = get();
    if (!transport || !scenarioId) return;
    set({ busy: true });
    try {
      const state = await transport.state(scenarioId, cursor);
      const envelope = await transport.findings(scenarioId, cursor);
      set({
        state,
        cursor: state.cursor,
        findings: envelope.findings,
        plans: envelope.plans,
        selectedFindingId:
          envelope.findings.find((f) => f.id === get().selectedFindingId)?.id ??
          envelope.findings[0]?.id ??
          null,
        problem: null,
      });
    } catch (error) {
      set({ problem: describe(error), playing: false });
    } finally {
      set({ busy: false });
    }
  },

  async step() {
    const { cursor, state } = get();
    const last = state?.last_sequence ?? 0;
    if (cursor >= last) {
      set({ playing: false });
      return;
    }
    await get().seek(cursor + 1);
  },

  async runToEnd() {
    const { state } = get();
    set({ playing: false });
    await get().seek(state?.last_sequence ?? 0);
  },

  async restart() {
    set({ playing: false, selectedFindingId: null });
    await get().seek(0);
    const { scenarioId } = get();
    if (transport && scenarioId) set({ immunity: await transport.immunity(scenarioId) });
  },

  play() {
    const { state, cursor } = get();
    if (cursor >= (state?.last_sequence ?? 0)) return;
    set({ playing: true });
  },

  pause() {
    set({ playing: false });
  },

  selectFinding(id) {
    set({ selectedFindingId: id });
  },

  async applyPlan(planId) {
    const { scenarioId } = get();
    if (!transport || !scenarioId) return;
    set({ busy: true, playing: false });
    try {
      const result: ApplyResult = await transport.apply(scenarioId, planId);
      const immunity = await transport.immunity(scenarioId);
      set({
        state: result.state,
        cursor: result.state.cursor,
        findings: result.findings.findings,
        plans: result.findings.plans,
        immunity,
        selectedFindingId: result.findings.findings[0]?.id ?? null,
        problem: null,
      });
    } catch (error) {
      set({ problem: describe(error) });
    } finally {
      set({ busy: false });
    }
  },

  async promotePattern(patternId, to) {
    const { scenarioId } = get();
    if (!transport || !scenarioId) return;
    try {
      await transport.promote(scenarioId, patternId, to);
      set({ immunity: await transport.immunity(scenarioId) });
    } catch (error) {
      set({ problem: describe(error) });
    }
  },

  updateLab(patch) {
    set((current) => ({ labConfig: { ...current.labConfig, ...patch }, labProblem: null }));
  },

  async runLab() {
    if (!transport) return;
    set({ labRunning: true, labProblem: null });
    try {
      const result = await transport.simulate(get().labConfig);
      set({ labResult: result });
    } catch (error) {
      set({ labProblem: describe(error), labResult: null });
    } finally {
      set({ labRunning: false });
    }
  },

  dismissProblem() {
    set({ problem: null });
  },
}));

/** Lab axes the active source can vary, for disabling controls honestly. */
export function labConstraints(): { held: (keyof SwarmConfig)[]; populations: number[] } {
  return transport?.labConstraints() ?? { held: [], populations: [12, 24, 48, 96] };
}

/** Test seam: swap the transport without booting. */
export function __setTransport(next: Transport | null): void {
  transport = next;
}
