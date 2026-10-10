import { MousePointerClick, PenLine, Play } from "lucide-react";

const STEPS = [
  { icon: MousePointerClick, title: "Pick a ticket", text: "Choose one from the ticket rail on the left." },
  { icon: Play, title: "Start the agent team", text: "Boss reads it and hands work to the right agents." },
  { icon: PenLine, title: "Sign off payments", text: "Agents only prepare money. Click here to sign." },
];

// Three numbered steps; the one you're on lights up.
export function HowTo({ step, onSign }: { step: 1 | 2 | 3; onSign: () => void }) {
  return (
    <ol className="howto" aria-label="How to use the desk">
      {STEPS.map((s, i) => {
        const n = i + 1;
        const Icon = s.icon;
        const cls = `howto__step ${n === step ? "is-current" : n < step ? "is-done" : ""}`;
        const body = (
          <>
            <span className="howto__num">{n}</span>
            <Icon size={18} />
            <div>
              <b>{s.title}</b>
              <span>{s.text}</span>
            </div>
          </>
        );
        // Step 3 is a shortcut straight to the signature tray.
        return n === 3 ? (
          <li key={s.title}><button type="button" className={`${cls} howto__step--link`} onClick={onSign}>{body}</button></li>
        ) : (
          <li key={s.title} className={cls}>{body}</li>
        );
      })}
    </ol>
  );
}
