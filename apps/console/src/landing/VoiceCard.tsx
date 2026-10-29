import { C } from '../shared/theme';
import { VOICE_ITEMS, type Voice } from '../shared/useVoice';

const BARS = Array.from({ length: 32 }, (_, i) => ({
  h: `${30 + Math.abs(Math.sin(i * 1.7)) * 70}%`,
  d: `${(-(i * 0.083) % 0.5).toFixed(2)}s`,
}));

const LABEL = {
  idle: 'TAP THE MIC TO SPEAK',
  listening: 'LISTENING…',
  typed: 'HERE’S WHAT I HEARD',
  confirmed: 'CONFIRMED',
} as const;

function micLook(phase: Voice['phase']) {
  const listening = phase === 'listening';
  const idle = phase === 'idle';
  return {
    bg: listening ? C.blue : idle ? C.ink : C.blueBg,
    fg: listening || idle ? C.paper : C.blue,
    anim: listening ? 'ring 1.2s infinite' : idle ? 'ring 2.4s infinite' : 'none',
    wave: listening ? C.blue : idle ? C.rule : 'oklch(0.48 0.13 262 / .35)',
    play: listening ? 'running' : 'paused',
  };
}

function Mic({ voice, size, onPress }: { voice: Voice; size: number; onPress: () => void }) {
  const mic = micLook(voice.phase);
  const waveH = size === 64 ? 44 : 36;
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: size === 64 ? 20 : 16 }}>
      <button
        type="button"
        className="mic"
        aria-label="Speak"
        onClick={onPress}
        style={{
          width: size,
          height: size,
          background: mic.bg,
          color: mic.fg,
          animation: mic.anim,
        }}
      >
        <span
          style={{ width: size === 64 ? 14 : 12, height: size === 64 ? 22 : 20 }}
          aria-hidden="true"
        />
      </button>
      <div className="mic-wave" style={{ height: waveH }} aria-hidden="true">
        {BARS.map((b, i) => (
          <span
            key={i}
            style={{
              height: b.h,
              background: mic.wave,
              animation: `wave .5s ease-in-out ${b.d} infinite alternate`,
              animationPlayState: mic.play,
            }}
          />
        ))}
      </div>
    </div>
  );
}

function Items({ voice, big }: { voice: Voice; big: boolean }) {
  return (
    <>
      {VOICE_ITEMS.map((text, i) => {
        const done = voice.phase === 'confirmed' && voice.done > i;
        return (
          <div
            key={text}
            className="v-item"
            style={{
              padding: big ? '12px 14px' : '10px 12px',
              background: done ? C.greenBg : C.wash,
              border: `1px solid ${done ? 'oklch(0.5 0.11 155 / .3)' : C.ruleSoft}`,
              animation: `up .45s ${i * 0.12}s both`,
            }}
          >
            <span
              className="v-dot"
              style={{
                width: big ? 20 : 18,
                height: big ? 20 : 18,
                fontSize: big ? 11 : 10,
                background: done ? C.green : 'transparent',
                border: `1px solid ${done ? C.green : C.rule}`,
              }}
            >
              {done ? '✓' : ''}
            </span>
            <span style={{ font: `500 ${big ? 15 : 14}px/1.35 var(--font-sans)` }}>{text}</span>
          </div>
        );
      })}
    </>
  );
}

function Transcript({ voice, size, minH }: { voice: Voice; size: number; minH: number }) {
  const caret = voice.phase === 'listening' || voice.phase === 'typed';
  return (
    <p
      style={{
        margin: 0,
        minHeight: minH,
        font: `400 ${size}px/1.45 var(--font-display)`,
        letterSpacing: '-.01em',
      }}
    >
      {voice.phase === 'idle' ? '' : voice.text}
      <span className="caret" style={{ opacity: caret ? 1 : 0 }} />
    </p>
  );
}

/** The landing page's "Just say it" card. */
export function VoiceCardHome({ voice }: { voice: Voice }) {
  const press = () => {
    if (voice.phase === 'idle') voice.start();
    else if (voice.phase === 'confirmed') voice.reset();
  };
  const showItems = voice.phase === 'typed' || voice.phase === 'confirmed';
  return (
    <div className="ld-voice-card">
      <Mic voice={voice} size={64} onPress={press} />
      <span className="mono" style={{ fontSize: 12, letterSpacing: '.06em', color: C.mute }}>
        {LABEL[voice.phase]}
      </span>
      <Transcript voice={voice} size={22} minH={92} />
      {showItems && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
          <span className="mono" style={{ fontSize: 11, letterSpacing: '.08em', color: C.mute }}>
            HAEGIS WILL:
          </span>
          <Items voice={voice} big />
          {voice.phase === 'typed' && (
            <div style={{ display: 'flex', gap: 10, marginTop: 8, animation: 'up .5s .8s both' }}>
              <button
                type="button"
                className="btn-primary"
                style={{ height: 46, padding: '0 22px', fontSize: 15 }}
                onClick={voice.confirm}
              >
                Yes, do it
              </button>
              <button
                type="button"
                className="btn-ghost"
                style={{ height: 46, padding: '0 18px', fontSize: 15 }}
                onClick={voice.reset}
              >
                Start over
              </button>
            </div>
          )}
          {voice.phase === 'confirmed' && voice.done >= 4 && (
            <span
              style={{
                marginTop: 6,
                font: '500 15px var(--font-sans)',
                color: C.green,
                animation: 'up .5s both',
              }}
            >
              Done. Only the report was redone — everything else kept running.
            </span>
          )}
        </div>
      )}
    </div>
  );
}

/** The compact card on step 5 of the guided walkthrough. */
export function VoiceCardDemo({ voice }: { voice: Voice }) {
  const showItems = voice.phase === 'typed' || voice.phase === 'confirmed';
  return (
    <div
      className="gd-card"
      style={{ padding: 22, borderRadius: 22, gap: 16, animation: 'up .5s both' }}
    >
      <Mic voice={voice} size={56} onPress={() => voice.phase === 'idle' && voice.start()} />
      <span className="mono" style={{ fontSize: 11, letterSpacing: '.06em', color: C.mute }}>
        {LABEL[voice.phase]}
      </span>
      <Transcript voice={voice} size={19} minH={60} />
      {showItems && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 7 }}>
          <Items voice={voice} big={false} />
        </div>
      )}
      {voice.phase === 'typed' && (
        <button
          type="button"
          className="btn-primary"
          style={{
            height: 48,
            fontSize: 15,
            animation: 'up .5s .8s both, ring 1.8s 1.4s infinite',
          }}
          onClick={voice.confirm}
        >
          Yes, do it
        </button>
      )}
    </div>
  );
}
