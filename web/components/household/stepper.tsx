import Link from "next/link";
import { IconCheck } from "./icons";

const STEPS = [
  { href: "/household/collect", label: "Consent" },
  { href: "/household/receipt", label: "Receipt" },
  { href: "/household/profile", label: "Site profile" },
];

export function Stepper({ current }: { current: number }) {
  return (
    <div className="hh-stepper" aria-label={`Step ${current} of 3`}>
      {STEPS.map((step, index) => (
        <span key={step.href} style={{ display: "contents" }}>
          {index > 0 ? <i /> : null}
          <Link className={`hh-step ${index + 1 === current ? "on" : index + 1 < current ? "done" : ""}`} href={step.href}>
            <b>{index + 1 < current ? <IconCheck size={12} stroke="#fff" /> : index + 1}</b>
            <span>{step.label}</span>
          </Link>
        </span>
      ))}
    </div>
  );
}
