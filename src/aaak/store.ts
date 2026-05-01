import * as fs from 'fs';
import * as path from 'path';
import { fileURLToPath } from 'url';
import { LocalIndex } from 'vectra';
import { embed } from './embedding.js';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const DEFAULT_TTL = 7200; // 2 hours
const DEFAULT_MAX_RECALL = 7;

export interface Fact {
  ts?: number;
  content: string;
  [key: string]: any;
}

export class FactStore {
  private _storeDir: string;
  private _ttl: number;
  private _saveCount: number = 0;
  private _index: LocalIndex;
  private _knownContent: Set<string> | null = null;
  private _isInit: boolean = false;

  constructor(storeDir?: string, prefix: string = "default", ttlSeconds: number = DEFAULT_TTL) {
    this._storeDir = storeDir || path.join(__dirname, '..', '..', 'aaak', '.facts');
    if (!fs.existsSync(this._storeDir)) {
      fs.mkdirSync(this._storeDir, { recursive: true });
    }
    const indexPath = path.join(this._storeDir, prefix);
    this._index = new LocalIndex(indexPath);
    this._ttl = ttlSeconds;
  }

  private _initPromise: Promise<void> | null = null;

  async init(): Promise<void> {
    if (!this._isInit) {
      if (!this._initPromise) {
        this._initPromise = (async () => {
          if (!await this._index.isIndexCreated()) {
            try {
              await this._index.createIndex();
            } catch (e: any) {
              if (e.message && e.message.includes('already exists')) {
                // ignore race condition
              } else {
                throw e;
              }
            }
          }
          this._isInit = true;
        })();
      }
      await this._initPromise;
    }
  }

  private async getKnownContent(): Promise<Set<string>> {
    if (this._knownContent === null) {
      this._knownContent = new Set();
      try {
        const items = await this._index.listItems();
        for (const item of items) {
          if (item.metadata && (item.metadata as Fact).content) {
            this._knownContent.add((item.metadata as Fact).content);
          }
        }
      } catch (e) {
      }
    }
    return this._knownContent;
  }

  async save(fact: Fact): Promise<void> {
    await this.init();
    if (!fact.ts) fact.ts = Date.now() / 1000;
    
    const known = await this.getKnownContent();
    if (known.has(fact.content)) return;
    known.add(fact.content);
    
    const factText = this._factToText(fact);
    const vector = await embed(factText);
    
    if (vector && vector.length > 0) {
      try {
        await this._index.insertItem({
          vector,
          metadata: fact as any
        });
        
        this._saveCount++;
        if (this._saveCount % 50 === 0) await this.compact();
      } catch (e) {
        console.warn(`Failed to save fact:`, e);
      }
    }
  }

  async loadActive(): Promise<Fact[]> {
    await this.init();
    const cutoff = (Date.now() / 1000) - this._ttl;
    const facts: Fact[] = [];
    
    try {
      const items = await this._index.listItems();
      for (const item of items) {
        const fact = item.metadata as unknown as Fact;
        if (fact && (fact.ts || 0) >= cutoff) {
          facts.push(fact);
        }
      }
    } catch {}
    return facts;
  }

  async query(text: string, limit: number = DEFAULT_MAX_RECALL): Promise<Fact[]> {
    await this.init();
    const vector = await embed(text);
    if (!vector || vector.length === 0) return [];

    try {
      const results = await this._index.queryItems(vector, text, limit);
      const cutoff = (Date.now() / 1000) - this._ttl;
      
      const validFacts: Fact[] = [];
      for (const res of results) {
        const fact = res.item.metadata as unknown as Fact;
        if (fact && (fact.ts || 0) >= cutoff) {
          validFacts.push(fact);
        }
      }
      return validFacts;
    } catch (e) {
      console.warn(`Failed to query index:`, e);
      return [];
    }
  }

  async compact(): Promise<number> {
    await this.init();
    const cutoff = (Date.now() / 1000) - this._ttl;
    
    try {
      const items = await this._index.listItems();
      let keptCount = 0;
      for (const item of items) {
        const fact = item.metadata as unknown as Fact;
        if (!fact || (fact.ts || 0) < cutoff) {
          await this._index.deleteItem(item.id);
        } else {
          keptCount++;
        }
      }
      return keptCount;
    } catch {
      return 0;
    }
  }

  private _factToText(fact: Fact): string {
    const parts = [fact.content || ''];
    if (fact.metadata) parts.push(JSON.stringify(fact.metadata));
    return parts.join(' ');
  }
}