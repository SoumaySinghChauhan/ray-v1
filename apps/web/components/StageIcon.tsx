import {
  AlertTriangle,
  Search,
  Activity,
  IndianRupee,
  Settings,
  Shield,
  Send,
  Wifi,
  CheckCircle2,
  Play,
  TrendingUp,
  type LucideIcon,
} from "lucide-react";

export type StageId =
  | "failed"
  | "diagnosis"
  | "prediction"
  | "value"
  | "optimizer"
  | "policy"
  | "execution"
  | "webhook"
  | "outcome";

export type StageTone = "neutral" | "recovered" | "pending" | "blocked";

export const STAGE_ICONS: Record<StageId, LucideIcon> = {
  failed: AlertTriangle,
  diagnosis: Search,
  prediction: Activity,
  value: IndianRupee,
  optimizer: Settings,
  policy: Shield,
  execution: Send,
  webhook: Wifi,
  outcome: CheckCircle2,
};

/** Alternate icon for the compact horizontal hero rail (fewer, punchier glyphs). */
export const HERO_ICONS: Record<string, LucideIcon> = {
  failed: AlertTriangle,
  diagnosis: Search,
  prediction: Activity,
  value: TrendingUp,
  policy: Shield,
  execution: Play,
  outcome: CheckCircle2,
};

const TONE_BORDER: Record<StageTone, string> = {
  neutral: "border-ink-3 text-ink-2",
  recovered: "border-recovered text-recovered",
  pending: "border-pending text-pending",
  blocked: "border-blocked text-blocked",
};

export function StageNode({
  stage,
  tone = "neutral",
  size = 32,
  iconSize = 15,
  hero = false,
}: {
  stage: StageId | string;
  tone?: StageTone;
  size?: number;
  iconSize?: number;
  hero?: boolean;
}) {
  const Icon = (hero ? HERO_ICONS[stage] : STAGE_ICONS[stage as StageId]) ?? Activity;
  return (
    <span
      className={`t-med inline-flex items-center justify-center rounded-full border bg-canvas shrink-0 ${TONE_BORDER[tone]}`}
      style={{ width: size, height: size }}
      aria-hidden="true"
    >
      <Icon size={iconSize} strokeWidth={1.75} />
    </span>
  );
}
