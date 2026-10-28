/**
 * HAEGIS console state: one visitor's live sandbox.
 *
 * Same rule as the HIVE store: it holds what the service said. Statuses,
 * epochs, plans and checks come from the server's snapshot. Ledger events are
 * applied in sequence order and a repeated sequence number is ignored, so a
 * reconnecting event stream never shows the same event twice.
 */

import { create } from 'zustand';

import {
  AegisError,
  api,
  isLive,
  loadRecordedFrame,
  loadRecordingIndex,
  type RecordedFrame,
} from '../api/aegis';
import type { LedgerEvent, ProposedDecision, RecoveryPlanView, Snapshot } from '../lib/aegisTypes';

export type AegisMode = 'connecting' | 'live' | 'recorded';

interface AegisState {
  mode: AegisMode;
  snapshot: Snapshot | null;
  ledger: LedgerEvent[];
  lastSeq: number;
  proposal: ProposedDecision | null;
  busy: boolean;
  problem: string | null;
  /** Recorded replay only: the beats on file and the one on screen. */
  frames: RecordedFrame[];
  frame: number;

  boot(): Promise<void>;
  showFrame(index: number): Promise<void>;
  setSnapshot(snapshot: Snapshot): void;
  applyEvent(event: LedgerEvent): boolean;
  refresh(): Promise<void>;
  step(): Promise<void>;
  play(): Promise<void>;
  reset(): Promise<void>;
  interpretApproval(text: string): Promise<void>;
  confirmProposal(): Promise<void>;
  rejectProposal(): Promise<void>;
  decisionCommand(id: string, verb: 'renew' | 'withdraw'): Promise<void>;
  interpretRecovery(text: string): Promise<void>;
  correctRecovery(text: string): Promise<void>;
  confirmRecovery(): Promise<void>;
  abandonRecovery(): Promise<void>;
  resolveConflict(id: string, choice: 'keep_human' | 'leave_for_review'): Promise<void>;
  humanEdit(item: string, content: string): Promise<void>;
  dismissProblem(): void;
}

/** The plan the operator is working on: the newest one that is not abandoned. */
export function currentPlan(snapshot: Snapshot | null): RecoveryPlanView | null {
  const plans = (snapshot?.plans ?? []).filter((p) => p.status !== 'abandoned');
  return plans.length ? plans[plans.length - 1] : null;
}

function message(error: unknown): string {
  if (error instanceof AegisError) return error.message;
  if (error instanceof Error) return error.message;
  return 'Something went wrong talking to the sandbox.';
}

export const useAegis = create<AegisState>((set, get) => {
  async function command(action: () => Promise<unknown>): Promise<void> {
    if (get().mode !== 'live') return;
    set({ busy: true, problem: null });
    try {
      const result = await action();
      if (result && typeof result === 'object' && 'session_id' in result) {
        get().setSnapshot(result as Snapshot);
      } else {
        await get().refresh();
      }
    } catch (error) {
      set({ problem: message(error) });
    } finally {
      set({ busy: false });
    }
  }

  return {
    mode: 'connecting',
    snapshot: null,
    ledger: [],
    lastSeq: 0,
    proposal: null,
    busy: false,
    problem: null,
    frames: [],
    frame: 0,

    async boot() {
      const playRecording = async () => {
        const frames = await loadRecordingIndex();
        set({ mode: 'recorded', frames: frames ?? [], snapshot: null });
        if (frames?.length) await get().showFrame(0);
      };
      if (!(await isLive())) {
        await playRecording();
        return;
      }
      try {
        set({ mode: 'live', ledger: [], lastSeq: 0 });
        get().setSnapshot(await api.createSession());
      } catch {
        await playRecording();
      }
    },

    async showFrame(index) {
      const frames = get().frames;
      if (index < 0 || index >= frames.length) return;
      try {
        const { snapshot, ledger } = await loadRecordedFrame(frames[index]);
        set({ snapshot, ledger, lastSeq: ledger.at(-1)?.seq ?? 0, frame: index });
      } catch (error) {
        set({ problem: message(error) });
      }
    },

    setSnapshot(snapshot) {
      set({ snapshot });
    },

    applyEvent(event) {
      if (event.seq <= get().lastSeq) return false;
      const snapshot = get().snapshot;
      let patched = snapshot;
      if (snapshot && event.decision_id && event.kind.startsWith('decision.')) {
        const status =
          event.kind === 'decision.suspended'
            ? 'suspended'
            : event.kind === 'decision.confirmed' || event.kind === 'decision.renewed'
              ? 'active'
              : null;
        if (status) {
          patched = {
            ...snapshot,
            decisions: snapshot.decisions.map((d) =>
              d.id === event.decision_id
                ? {
                    ...d,
                    status,
                    epoch:
                      event.kind === 'decision.suspended'
                        ? Number(event.payload.new_epoch ?? d.epoch)
                        : d.epoch,
                  }
                : d,
            ),
          };
        }
      }
      set({ ledger: [...get().ledger, event], lastSeq: event.seq, snapshot: patched });
      return true;
    },

    async refresh() {
      if (get().mode !== 'live') return;
      try {
        get().setSnapshot(await api.state());
      } catch (error) {
        set({ problem: message(error) });
      }
    },

    step: () =>
      get().mode === 'recorded' ? get().showFrame(get().frame + 1) : command(() => api.step()),
    play: () => command(() => api.play()),
    reset: () =>
      get().mode === 'recorded'
        ? get().showFrame(0)
        : command(async () => {
            set({ ledger: [], lastSeq: 0, proposal: null });
            return api.reset();
          }),

    interpretApproval: (text) =>
      command(async () => {
        const proposal = await api.interpretDecision(text);
        set({ proposal });
        return proposal;
      }),
    confirmProposal: () =>
      command(async () => {
        const proposal = get().proposal;
        if (!proposal) return null;
        set({ proposal: null });
        return api.decision(proposal.decision.id, 'confirm');
      }),
    rejectProposal: () =>
      command(async () => {
        const proposal = get().proposal;
        if (!proposal) return null;
        set({ proposal: null });
        return api.decision(proposal.decision.id, 'reject');
      }),

    decisionCommand: (id, verb) => command(() => api.decision(id, verb)),

    interpretRecovery: (text) => command(() => api.interpretRecovery(text)),
    correctRecovery: (text) =>
      command(async () => {
        const plan = currentPlan(get().snapshot);
        return plan ? api.correctRecovery(plan.id, text) : api.interpretRecovery(text);
      }),
    confirmRecovery: () =>
      command(async () => {
        const plan = currentPlan(get().snapshot);
        return plan ? api.recovery(plan.id, 'confirm') : null;
      }),
    abandonRecovery: () =>
      command(async () => {
        const plan = currentPlan(get().snapshot);
        return plan ? api.recovery(plan.id, 'abandon') : null;
      }),
    resolveConflict: (id, choice) => command(() => api.resolveConflict(id, choice)),
    humanEdit: (item, content) => command(() => api.humanEdit(item, content)),
    dismissProblem: () => set({ problem: null }),
  };
});
