/**
 * ROME Router (v1) — assigns execution backend to each Plan step.
 * Reads mode from Step, cross-references registered workers.
 * DOES NOT execute. Returns RouteResult per step.
 */
import type { DecompStep, ExecutionMode, Plan, PeerInfo } from './rome_types.js';

export interface RouteResult {
  step: DecompStep;
  capability: string;
  effectiveMode: ExecutionMode;
}

export function routeStep(step: DecompStep, workers: PeerInfo[]): RouteResult {
  const { role, mode } = step.payload;
  const hasPersistent = workers.some(w => w.capabilities.includes(role) && !w.one_shot);

  let effectiveMode: ExecutionMode = mode;
  if (mode === 'native_ws' && !hasPersistent) {
    /* explicit downgrade — no silent magic */
    effectiveMode = 'fallback';
  }

  return { step, capability: role, effectiveMode };
}

export async function executePlan(
  plan: Plan,
  workers: PeerInfo[],
  dispatchFn: (capability: string, input: string, mode: ExecutionMode) => Promise<string>
): Promise<Map<string, string>> {
  const results = new Map<string, string>();
  const promises = new Map<string, Promise<string>>();

  for (const step of plan.steps) {
    const p = (async () => {
      if (step.dependsOn?.length) {
        await Promise.all(step.dependsOn.map(dep => {
          const dep_p = promises.get(dep);
          if (!dep_p) throw new Error(`Router: unknown dependency "${dep}" in step "${step.id}"`);
          return dep_p;
        }));
      }
      const { capability, effectiveMode } = routeStep(step, workers);
      const result = await dispatchFn(capability, step.payload.input, effectiveMode);
      results.set(step.id, result);
      return result;
    })();
    promises.set(step.id, p);
  }

  await Promise.all(promises.values());
  return results;
}
