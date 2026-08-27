/**
 * SAFE SYNTHETIC OPERATIONAL DATA.
 *
 * Deterministic demo records for the operational surfaces of the product.
 * These are NOT drawn from the frozen 300-case TEST benchmark and carry no
 * hidden simulator variables. Every value is a plausible decision-time
 * quantity: observable payment facts, calibrated model estimates, and the
 * frozen V1 economics applied to them.
 */

import { evBreakdown, ECONOMICS } from "./economics";

export type FailureClass =
  | "SOFT_DECLINE"
  | "HARD_DECLINE"
  | "GATEWAY_ERROR"
  | "AUTHENTICATION_FAILURE";

export type PolicyRuleId =
  | "VALID_ACTION_TYPE"
  | "OPPORTUNITY_ACTIONABLE"
  | "DO_NOT_CONTACT_CHECK"
  | "DUPLICATE_ACTION_CHECK"
  | "AUTONOMOUS_AMOUNT_LIMIT_CHECK"
  | "MAX_CONTACTS_CHECK"
  | "DAILY_CAPACITY_CHECK";

export const POLICY_RULES: PolicyRuleId[] = [
  "VALID_ACTION_TYPE",
  "OPPORTUNITY_ACTIONABLE",
  "DO_NOT_CONTACT_CHECK",
  "DUPLICATE_ACTION_CHECK",
  "AUTONOMOUS_AMOUNT_LIMIT_CHECK",
  "MAX_CONTACTS_CHECK",
  "DAILY_CAPACITY_CHECK",
];

export type Outcome =
  | "RECOVERED"
  | "PENDING"
  | "NOT_RECOVERED"
  | "BLOCKED"
  | "SKIPPED";

export interface Opportunity {
  id: string;
  customer: string;
  customerId: string;
  amountInr: number;
  failureClass: FailureClass;
  failureDetail: string;
  time: string;
  probability: number;
  grossEv: number;
  netEv: number;
  doNothingEv: number;
  incrementalEv: number;
  action: "CREATE_PAYMENT_LINK" | "DO_NOTHING";
  actionReason?: string;
  policy: "ALLOW" | "BLOCK" | "NOT_EVALUATED";
  blockedRule?: PolicyRuleId;
  blockedReason?: string;
  execution?: {
    executionId: string;
    paymentLinkId: string;
    referenceId: string;
    shortUrl: string;
    status: "SUCCEEDED" | "PENDING";
    createdAt: string;
  };
  webhook?: {
    event: string;
    signature: "VERIFIED";
    paymentId: string;
    receivedAt: string;
  };
  outcome: Outcome;
  recoveredInr?: number;
  diagnosis?: { class: string; confidence: number; summary: string };
  history: { payments: number; successes: number; recoveries: number; recoveryRate: number };
}

function opp(o: {
  id: string;
  customer: string;
  customerId: string;
  amountInr: number;
  failureClass: FailureClass;
  failureDetail: string;
  time: string;
  probability: number;
  action: "CREATE_PAYMENT_LINK" | "DO_NOTHING";
  actionReason?: string;
  policy: "ALLOW" | "BLOCK" | "NOT_EVALUATED";
  blockedRule?: PolicyRuleId;
  blockedReason?: string;
  execution?: Opportunity["execution"];
  webhook?: Opportunity["webhook"];
  outcome: Outcome;
  recoveredInr?: number;
  diagnosis?: Opportunity["diagnosis"];
  history: Opportunity["history"];
}): Opportunity {
  const ev = evBreakdown(o.amountInr, o.probability);
  return {
    ...o,
    grossEv: ev.grossEv,
    netEv: ev.netEv,
    doNothingEv: ev.doNothingEv,
    incrementalEv: ev.incrementalEv,
  };
}

/* ------------------------------------------------------------------ */
/* Operational feed — today's synthetic decision activity              */
/* ------------------------------------------------------------------ */

export const OPPORTUNITIES: Opportunity[] = [
  opp({
    id: "opp_d4x1a2",
    customer: "Meridian Textiles",
    customerId: "cust_demo_0114",
    amountInr: 4200,
    failureClass: "SOFT_DECLINE",
    failureDetail: "Insufficient funds — issuer decline 51",
    time: "10:42:11",
    probability: 0.634,
    action: "CREATE_PAYMENT_LINK",
    policy: "ALLOW",
    execution: {
      executionId: "exec_9f2e41c7",
      paymentLinkId: "plink_NxT4h2Vd8mQa1z",
      referenceId: "RAY-D12-0114-01",
      shortUrl: "https://rzp.io/i/demo4200",
      status: "SUCCEEDED",
      createdAt: "10:42:12",
    },
    webhook: {
      event: "payment_link.paid",
      signature: "VERIFIED",
      paymentId: "pay_NxT6q1Wc3rLb7y",
      receivedAt: "10:44:19",
    },
    outcome: "RECOVERED",
    recoveredInr: 4200,
    diagnosis: {
      class: "SOFT_DECLINE",
      confidence: 0.92,
      summary:
        "Issuer reported insufficient funds. Balance-timing failure with a strong retry profile via an alternate collection path.",
    },
    history: { payments: 34, successes: 31, recoveries: 4, recoveryRate: 0.44 },
  }),
  opp({
    id: "opp_d4x1b7",
    customer: "Kavya Sharma",
    customerId: "cust_demo_0287",
    amountInr: 1850,
    failureClass: "SOFT_DECLINE",
    failureDetail: "Transaction timeout at issuer",
    time: "10:38:54",
    probability: 0.512,
    action: "CREATE_PAYMENT_LINK",
    policy: "ALLOW",
    execution: {
      executionId: "exec_2b8c31da",
      paymentLinkId: "plink_NxT2p9Xe5nRc4w",
      referenceId: "RAY-D12-0287-01",
      shortUrl: "https://rzp.io/i/demo1850",
      status: "SUCCEEDED",
      createdAt: "10:38:55",
    },
    outcome: "PENDING",
    diagnosis: {
      class: "SOFT_DECLINE",
      confidence: 0.85,
      summary: "Issuer-side timeout. Transient failure; customer intent likely intact.",
    },
    history: { payments: 12, successes: 11, recoveries: 2, recoveryRate: 0.38 },
  }),
  opp({
    id: "opp_d4x1c3",
    customer: "Northline Logistics",
    customerId: "cust_demo_0342",
    amountInr: 31000,
    failureClass: "SOFT_DECLINE",
    failureDetail: "Issuer decline — do not honor",
    time: "10:31:22",
    probability: 0.58,
    action: "CREATE_PAYMENT_LINK",
    policy: "BLOCK",
    blockedRule: "AUTONOMOUS_AMOUNT_LIMIT_CHECK",
    blockedReason: "Amount ₹31,000.00 exceeds autonomous limit ₹25,000.00",
    outcome: "BLOCKED",
    diagnosis: {
      class: "SOFT_DECLINE",
      confidence: 0.88,
      summary: "Generic issuer decline with retry potential; amount requires human authorization.",
    },
    history: { payments: 56, successes: 52, recoveries: 6, recoveryRate: 0.41 },
  }),
  opp({
    id: "opp_d4x1d9",
    customer: "Arjun Mehta",
    customerId: "cust_demo_0405",
    amountInr: 920,
    failureClass: "HARD_DECLINE",
    failureDetail: "Card reported stolen — issuer decline 43",
    time: "10:27:03",
    probability: 0.09,
    action: "DO_NOTHING",
    actionReason: "Incremental EV below zero — recovery attempt not economically justified",
    policy: "NOT_EVALUATED",
    outcome: "SKIPPED",
    diagnosis: {
      class: "HARD_DECLINE",
      confidence: 0.95,
      summary: "Terminal card-status failure. Payment-link retry has near-zero success profile.",
    },
    history: { payments: 3, successes: 1, recoveries: 0, recoveryRate: 0.0 },
  }),
  opp({
    id: "opp_d4x1e5",
    customer: "Bluepeak Studios",
    customerId: "cust_demo_0523",
    amountInr: 7600,
    failureClass: "GATEWAY_ERROR",
    failureDetail: "Gateway 5xx during authorization",
    time: "10:19:47",
    probability: 0.571,
    action: "CREATE_PAYMENT_LINK",
    policy: "ALLOW",
    execution: {
      executionId: "exec_7e1f92ab",
      paymentLinkId: "plink_NxSz8kYf2tMd6v",
      referenceId: "RAY-D12-0523-01",
      shortUrl: "https://rzp.io/i/demo7600",
      status: "SUCCEEDED",
      createdAt: "10:19:48",
    },
    webhook: {
      event: "payment_link.paid",
      signature: "VERIFIED",
      paymentId: "pay_NxT1c4Zd9uNe2x",
      receivedAt: "10:33:02",
    },
    outcome: "RECOVERED",
    recoveredInr: 7600,
    diagnosis: {
      class: "GATEWAY_ERROR",
      confidence: 0.9,
      summary: "Infrastructure failure unrelated to customer intent. High recovery profile.",
    },
    history: { payments: 22, successes: 21, recoveries: 3, recoveryRate: 0.5 },
  }),
  opp({
    id: "opp_d4x1f1",
    customer: "Riya Kapoor",
    customerId: "cust_demo_0611",
    amountInr: 2400,
    failureClass: "AUTHENTICATION_FAILURE",
    failureDetail: "3DS authentication abandoned",
    time: "10:12:30",
    probability: 0.468,
    action: "CREATE_PAYMENT_LINK",
    policy: "BLOCK",
    blockedRule: "MAX_CONTACTS_CHECK",
    blockedReason: "Customer already contacted today (limit 1 per day)",
    outcome: "BLOCKED",
    diagnosis: {
      class: "AUTHENTICATION_FAILURE",
      confidence: 0.82,
      summary: "Customer abandoned 3DS challenge. Recoverable via lower-friction link flow.",
    },
    history: { payments: 9, successes: 8, recoveries: 1, recoveryRate: 0.33 },
  }),
  opp({
    id: "opp_d4x1g8",
    customer: "Sagar Traders",
    customerId: "cust_demo_0688",
    amountInr: 12750,
    failureClass: "SOFT_DECLINE",
    failureDetail: "Insufficient funds — issuer decline 51",
    time: "09:58:16",
    probability: 0.545,
    action: "CREATE_PAYMENT_LINK",
    policy: "ALLOW",
    execution: {
      executionId: "exec_4c6a58fe",
      paymentLinkId: "plink_NxSw3mUg7pKf9t",
      referenceId: "RAY-D12-0688-01",
      shortUrl: "https://rzp.io/i/demo12750",
      status: "SUCCEEDED",
      createdAt: "09:58:17",
    },
    outcome: "PENDING",
    diagnosis: {
      class: "SOFT_DECLINE",
      confidence: 0.92,
      summary: "Balance-timing failure. Historical pattern indicates strong retry window.",
    },
    history: { payments: 41, successes: 37, recoveries: 5, recoveryRate: 0.45 },
  }),
  opp({
    id: "opp_d4x1h4",
    customer: "Vantage Analytics",
    customerId: "cust_demo_0740",
    amountInr: 5400,
    failureClass: "SOFT_DECLINE",
    failureDetail: "Issuer decline — try again later",
    time: "09:41:52",
    probability: 0.601,
    action: "CREATE_PAYMENT_LINK",
    policy: "BLOCK",
    blockedRule: "DUPLICATE_ACTION_CHECK",
    blockedReason: "Action already executed (idempotency violation)",
    outcome: "BLOCKED",
    diagnosis: {
      class: "SOFT_DECLINE",
      confidence: 0.87,
      summary: "Transient decline. A payment link already exists for this opportunity.",
    },
    history: { payments: 28, successes: 26, recoveries: 4, recoveryRate: 0.47 },
  }),
  opp({
    id: "opp_d4x1j6",
    customer: "Ishaan Verma",
    customerId: "cust_demo_0815",
    amountInr: 3100,
    failureClass: "GATEWAY_ERROR",
    failureDetail: "Network failure during capture",
    time: "09:24:08",
    probability: 0.553,
    action: "CREATE_PAYMENT_LINK",
    policy: "ALLOW",
    execution: {
      executionId: "exec_8d2b74c1",
      paymentLinkId: "plink_NxSt6nVh4qJg2s",
      referenceId: "RAY-D12-0815-01",
      shortUrl: "https://rzp.io/i/demo3100",
      status: "SUCCEEDED",
      createdAt: "09:24:09",
    },
    webhook: {
      event: "payment_link.expired",
      signature: "VERIFIED",
      paymentId: "—",
      receivedAt: "21:24:09",
    },
    outcome: "NOT_RECOVERED",
    diagnosis: {
      class: "GATEWAY_ERROR",
      confidence: 0.9,
      summary: "Capture-phase network failure. Retry profile favorable.",
    },
    history: { payments: 17, successes: 15, recoveries: 2, recoveryRate: 0.36 },
  }),
  opp({
    id: "opp_d4x1k2",
    customer: "Crestwave Media",
    customerId: "cust_demo_0902",
    amountInr: 9800,
    failureClass: "SOFT_DECLINE",
    failureDetail: "Insufficient funds — issuer decline 51",
    time: "09:02:41",
    probability: 0.588,
    action: "CREATE_PAYMENT_LINK",
    policy: "ALLOW",
    execution: {
      executionId: "exec_1a9d63e5",
      paymentLinkId: "plink_NxSq1oWj8rHh5r",
      referenceId: "RAY-D12-0902-01",
      shortUrl: "https://rzp.io/i/demo9800",
      status: "SUCCEEDED",
      createdAt: "09:02:42",
    },
    webhook: {
      event: "payment_link.paid",
      signature: "VERIFIED",
      paymentId: "pay_NxSs5pXk1vGj8q",
      receivedAt: "09:17:55",
    },
    outcome: "RECOVERED",
    recoveredInr: 9800,
    diagnosis: {
      class: "SOFT_DECLINE",
      confidence: 0.92,
      summary: "Insufficient balance at charge time. Alternate-path collection succeeded historically.",
    },
    history: { payments: 63, successes: 58, recoveries: 8, recoveryRate: 0.53 },
  }),
  opp({
    id: "opp_d4x1m9",
    customer: "Tanvi Joshi",
    customerId: "cust_demo_0968",
    amountInr: 640,
    failureClass: "HARD_DECLINE",
    failureDetail: "Account closed — issuer decline 46",
    time: "08:47:13",
    probability: 0.07,
    action: "DO_NOTHING",
    actionReason: "Incremental EV below zero — recovery attempt not economically justified",
    policy: "NOT_EVALUATED",
    outcome: "SKIPPED",
    diagnosis: {
      class: "HARD_DECLINE",
      confidence: 0.95,
      summary: "Terminal account-status failure. No viable retry path.",
    },
    history: { payments: 5, successes: 2, recoveries: 0, recoveryRate: 0.0 },
  }),
  opp({
    id: "opp_d4x1n5",
    customer: "Helios Components",
    customerId: "cust_demo_1033",
    amountInr: 15200,
    failureClass: "AUTHENTICATION_FAILURE",
    failureDetail: "3DS OTP delivery failure",
    time: "08:31:29",
    probability: 0.497,
    action: "CREATE_PAYMENT_LINK",
    policy: "ALLOW",
    execution: {
      executionId: "exec_5f3c82b9",
      paymentLinkId: "plink_NxSm4qYl2wFk3p",
      referenceId: "RAY-D12-1033-01",
      shortUrl: "https://rzp.io/i/demo15200",
      status: "SUCCEEDED",
      createdAt: "08:31:30",
    },
    outcome: "PENDING",
    diagnosis: {
      class: "AUTHENTICATION_FAILURE",
      confidence: 0.82,
      summary: "OTP never reached the customer. Link flow bypasses the failed channel.",
    },
    history: { payments: 30, successes: 27, recoveries: 3, recoveryRate: 0.38 },
  }),
];

/* ------------------------------------------------------------------ */
/* Aggregate operational stats (derived from records above)            */
/* ------------------------------------------------------------------ */

const recovered = OPPORTUNITIES.filter((o) => o.outcome === "RECOVERED");
const executed = OPPORTUNITIES.filter((o) => o.execution);
const blocked = OPPORTUNITIES.filter((o) => o.outcome === "BLOCKED");

export const TODAY = {
  opportunities: OPPORTUNITIES.length,
  actionsSelected: OPPORTUNITIES.filter((o) => o.action === "CREATE_PAYMENT_LINK").length,
  executed: executed.length,
  recoveredInr: recovered.reduce((s, o) => s + (o.recoveredInr ?? 0), 0),
  recoveredCount: recovered.length,
  realizedRate: executed.length > 0 ? recovered.length / executed.length : 0,
  policyBlocks: blocked.length,
  capacityUsed: executed.length,
  capacityTotal: ECONOMICS.maxActionsPerDay,
  predictedNetEv: executed.reduce((s, o) => s + o.incrementalEv, 0),
};

export function getOpportunity(id: string): Opportunity | undefined {
  return OPPORTUNITIES.find((o) => o.id === id);
}

/* ------------------------------------------------------------------ */
/* Guided demo scenarios (deterministic)                               */
/* ------------------------------------------------------------------ */

export interface DemoScenario {
  id: string;
  index: string;
  title: string;
  summary: string;
  opportunity: Opportunity;
  storyline: "RECOVERY" | "SKIP" | "BLOCK";
}

export const DEMO_SCENARIOS: DemoScenario[] = [
  {
    id: "soft-decline-recovery",
    index: "01",
    title: "Soft decline — full recovery",
    summary: "A viable failure travels the entire rail: diagnosis to verified recovery.",
    storyline: "RECOVERY",
    opportunity: OPPORTUNITIES[0],
  },
  {
    id: "hard-decline-skip",
    index: "02",
    title: "Hard decline — economically skipped",
    summary: "A terminal failure with negative incremental EV. RAY spends nothing.",
    storyline: "SKIP",
    opportunity: OPPORTUNITIES[3],
  },
  {
    id: "amount-limit-block",
    index: "03",
    title: "Amount limit — policy block",
    summary: "The optimizer chooses; policy refuses. ₹31,000 exceeds the autonomous limit.",
    storyline: "BLOCK",
    opportunity: OPPORTUNITIES[2],
  },
  {
    id: "contact-limit-block",
    index: "04",
    title: "Contact limit — policy block",
    summary: "One contact per customer per day. The second attempt is refused.",
    storyline: "BLOCK",
    opportunity: OPPORTUNITIES[5],
  },
  {
    id: "duplicate-block",
    index: "05",
    title: "Duplicate execution — policy block",
    summary: "Idempotency enforcement. The same action can never execute twice.",
    storyline: "BLOCK",
    opportunity: OPPORTUNITIES[7],
  },
];

export function getScenario(id: string): DemoScenario | undefined {
  return DEMO_SCENARIOS.find((s) => s.id === id);
}
