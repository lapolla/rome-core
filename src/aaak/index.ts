import { FactStore } from './store.js';
import type { Fact } from './store.js';
import { compress } from './compress.js';
import type { Manifest } from './compress.js';
import { distill, needsDistill, DEFAULT_THRESHOLD } from './distill.js';

export { FactStore, compress, distill, needsDistill };
export type { Fact, Manifest };

export interface AAAKConfig {
  enabled: boolean;
  distill_threshold: number;
  fact_ttl_seconds: number;
  max_recall: number;
}

const SKIP_CAPABILITIES = new Set(["SAFE_SHELL", "NATIVE_SHELL"]);

export class AAAK {
  public enabled: boolean;
  public store: FactStore;
  private threshold: number;
  private maxRecall: number;

  constructor(prefix: string = "default", config?: Partial<AAAKConfig>) {
    this.enabled = config?.enabled ?? false;
    this.threshold = config?.distill_threshold ?? DEFAULT_THRESHOLD;
    this.maxRecall = config?.max_recall ?? 7;
    this.store = new FactStore(undefined, prefix, config?.fact_ttl_seconds);
  }

  shouldProcess(capability: string): boolean {
    return this.enabled && !SKIP_CAPABILITIES.has(capability.toUpperCase());
  }

  preDispatch(prompt: string, goal: string, capability: string): string {
    if (!this.shouldProcess(capability)) {
      return prompt;
    }

    const activeFacts = this.store.loadActive();
    if (!needsDistill(prompt, this.threshold) && activeFacts.length === 0) {
      return prompt;
    }

    const facts = this.store.query(goal || prompt.slice(0, 200), this.maxRecall);
    return distill({ prompt, facts }, goal);
  }

  postResult(manifest: Manifest, taskDescription: string = ""): Fact {
    const fact = compress(manifest, taskDescription);
    this.store.save(fact);
    return fact;
  }
}
