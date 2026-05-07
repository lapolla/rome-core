import { FactStore } from './store.js';
import type { Fact } from './store.js';
import { compress } from './compress.js';
import type { Manifest } from './compress.js';

export { FactStore, compress };
export type { Fact, Manifest };

export interface AAAKConfig {
  enabled: boolean;
  fact_ttl_seconds: number;
  max_recall: number;
}

const SKIP_CAPABILITIES = new Set(["SAFE_SHELL", "NATIVE_SHELL"]);

export class AAAK {
  public enabled: boolean;
  public store: FactStore;
  private maxRecall: number;

  constructor(prefix: string = "default", config?: Partial<AAAKConfig>, storeDir?: string) {
    this.enabled = config?.enabled ?? false;
    this.maxRecall = config?.max_recall ?? 7;
    this.store = new FactStore(storeDir, prefix, config?.fact_ttl_seconds);
  }

  shouldProcess(capability: string): boolean {
    return this.enabled && !SKIP_CAPABILITIES.has(capability.toUpperCase());
  }

  async postResult(manifest: Manifest, taskDescription: string = ""): Promise<Fact> {
    const fact = compress(manifest, taskDescription);
    await this.store.save(fact);
    return fact;
  }
}
