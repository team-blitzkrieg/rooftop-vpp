import type { ReactNode } from "react";

type IconProps = { size?: number; stroke?: string };

function Svg({ size = 22, stroke = "currentColor", children }: IconProps & { children: ReactNode }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke={stroke} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      {children}
    </svg>
  );
}

export function IconSun({ size, stroke }: IconProps) {
  return (
    <Svg size={size} stroke={stroke}>
      <circle cx="12" cy="12" r="4" />
      <path d="M12 2v2M12 20v2M4.93 4.93l1.41 1.41M17.66 17.66l1.41 1.41M2 12h2M20 12h2M6.34 17.66l-1.41 1.41M19.07 4.93l-1.41 1.41" />
    </Svg>
  );
}

export function IconHome({ size, stroke }: IconProps) {
  return (
    <Svg size={size} stroke={stroke}>
      <path d="M3 10.5 12 3l9 7.5V20a1 1 0 0 1-1 1h-5v-6H9v6H4a1 1 0 0 1-1-1z" />
    </Svg>
  );
}

export function IconGrid({ size, stroke }: IconProps) {
  return (
    <Svg size={size} stroke={stroke}>
      <path d="M12 2 4 7v10l8 5 8-5V7l-8-5z" />
      <path d="M12 22V12M4.5 7.5 12 12l7.5-4.5" />
    </Svg>
  );
}

export function IconLeaf({ size, stroke }: IconProps) {
  return (
    <Svg size={size} stroke={stroke}>
      <path d="M11 20A7 7 0 0 1 9.8 6.1C15.5 5 17 4.48 19 2c1 2 2 4.18 2 8 0 5.5-4.78 10-10 10z" />
      <path d="M2 21c0-3 1.85-5.36 5.08-6" />
    </Svg>
  );
}

export function IconBattery({ size, stroke }: IconProps) {
  return (
    <Svg size={size} stroke={stroke}>
      <rect x="2" y="7" width="16" height="10" rx="2" />
      <path d="M22 11v2" />
    </Svg>
  );
}

export function IconPlan({ size, stroke }: IconProps) {
  return (
    <Svg size={size} stroke={stroke}>
      <rect x="3" y="4" width="18" height="18" rx="2" />
      <path d="M16 2v4M8 2v4M3 10h18" />
    </Svg>
  );
}

export function IconSavings({ size, stroke }: IconProps) {
  return (
    <Svg size={size} stroke={stroke}>
      <path d="M19 7V4a1 1 0 0 0-1-1H5a2 2 0 0 0 0 4h15a1 1 0 0 1 1 1v4h-3a2 2 0 0 0 0 4h3a1 1 0 0 0 1-1v-2a1 1 0 0 0-1-1" />
      <path d="M3 5v14a2 2 0 0 0 2 2h15a1 1 0 0 0 1-1v-4" />
    </Svg>
  );
}

export function IconAlerts({ size, stroke }: IconProps) {
  return (
    <Svg size={size} stroke={stroke}>
      <path d="M6 8a6 6 0 0 1 12 0c0 7 3 9 3 9H3s3-2 3-9" />
      <path d="M10.3 21a1.94 1.94 0 0 0 3.4 0" />
    </Svg>
  );
}

export function IconSettings({ size, stroke }: IconProps) {
  return (
    <Svg size={size} stroke={stroke}>
      <path d="M4 21v-7M4 10V3M12 21v-9M12 8V3M20 21v-5M20 12V3M1 14h6M9 8h6M17 16h6" />
    </Svg>
  );
}

export function IconBack({ size, stroke }: IconProps) {
  return (
    <Svg size={size} stroke={stroke}>
      <path d="m15 18-6-6 6-6" />
    </Svg>
  );
}

export function IconClose({ size, stroke }: IconProps) {
  return (
    <Svg size={size} stroke={stroke}>
      <path d="M18 6 6 18M6 6l12 12" />
    </Svg>
  );
}

export function IconPlus({ size, stroke }: IconProps) {
  return (
    <Svg size={size} stroke={stroke}>
      <path d="M12 5v14M5 12h14" />
    </Svg>
  );
}

export function IconCheck({ size, stroke }: IconProps) {
  return (
    <Svg size={size} stroke={stroke}>
      <path d="m5 12 5 5L20 7" />
    </Svg>
  );
}

export function IconMail({ size, stroke }: IconProps) {
  return (
    <Svg size={size} stroke={stroke}>
      <rect x="2" y="4" width="20" height="16" rx="2" />
      <path d="m22 7-10 6L2 7" />
    </Svg>
  );
}

export function IconLock({ size, stroke }: IconProps) {
  return (
    <Svg size={size} stroke={stroke}>
      <rect x="3" y="11" width="18" height="11" rx="2" />
      <path d="M7 11V7a5 5 0 0 1 10 0v4" />
    </Svg>
  );
}

export function IconEye({ size, stroke }: IconProps) {
  return (
    <Svg size={size} stroke={stroke}>
      <path d="M2 12s3-7 10-7 10 7 10 7-3 7-10 7-10-7-10-7Z" />
      <circle cx="12" cy="12" r="3" />
    </Svg>
  );
}

export function IconAlert({ size, stroke }: IconProps) {
  return (
    <Svg size={size} stroke={stroke}>
      <path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3" />
      <path d="M12 9v4M12 17h.01" />
    </Svg>
  );
}

export function IconInfo({ size, stroke }: IconProps) {
  return (
    <Svg size={size} stroke={stroke}>
      <circle cx="12" cy="12" r="10" />
      <path d="M12 16v-4M12 8h.01" />
    </Svg>
  );
}

export function IconShield({ size, stroke }: IconProps) {
  return (
    <Svg size={size} stroke={stroke}>
      <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
      <path d="m9 12 2 2 4-4" />
    </Svg>
  );
}

export function IconOffline({ size, stroke }: IconProps) {
  return (
    <Svg size={size} stroke={stroke}>
      <path d="M2 2l20 20M8.5 16.5a5 5 0 0 1 7 0M2 8.82a15 15 0 0 1 4.17-2.65M10.66 5c4.01-.36 8.14.9 11.34 3.76M16.85 11.25a10 10 0 0 1 2.22 1.68M5 13a10 10 0 0 1 5.24-2.76M12 20h.01" />
    </Svg>
  );
}
