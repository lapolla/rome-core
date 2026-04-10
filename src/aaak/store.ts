import * as fs from 'fs';
import * as path from 'path';
import { fileURLToPath } from 'url';

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
  private _path: string;
  private _ttl: number;
  private _saveCount: number = 0;

  constructor(storeDir?: string, prefix: string = "default", ttlSeconds: number = DEFAULT_TTL) {
    this._storeDir = storeDir || path.join(__dirname, '..', '..', 'aaak', '.facts');
    if (!fs.existsSync(this._storeDir)) {
      fs.mkdirSync(this._storeDir, { recursive: true });
    }
    this._path = path.join(this._storeDir, `${prefix}.jsonl`);
    this._ttl = ttlSeconds;
  }

  save(fact: Fact): void {
    if (!fact.ts) {
      fact.ts = Date.now() / 1000;
    }
    const line = JSON.stringify(fact);
    fs.appendFileSync(this._path, line + "\n", 'utf-8');
    
    this._saveCount++;
    if (this._saveCount % 50 === 0) {
      this.compact();
    }
  }

  loadActive(): Fact[] {
    const cutoff = (Date.now() / 1000) - this._ttl;
    const facts: Fact[] = [];
    
    if (!fs.existsSync(this._path)) {
      return facts;
    }

    const lines = fs.readFileSync(this._path, 'utf-8').split('\n');
    for (let line of lines) {
      line = line.trim();
      if (!line) continue;
      try {
        const fact = JSON.parse(line) as Fact;
        if ((fact.ts || 0) >= cutoff) {
          facts.push(fact); // Error here: TypeScript uses push, not append. Fixing in next turn.
        }
      } catch {
        continue;
      }
    }
    return facts;
  }

  query(text: string, limit: number = DEFAULT_MAX_RECALL): Fact[] {
    const queryTokens = this._tokenize(text);
    if (queryTokens.size === 0) return [];

    const facts = this.loadActive();
    const now = Date.now() / 1000;
    const cutoff = now - this._ttl;

    const scored: Array<{ score: number; fact: Fact }> = [];
    
    for (const fact of facts) {
      const factText = this._factToText(fact);
      const factTokens = this._tokenize(factText);
      if (factTokens.size === 0) continue;

      const intersection = new Set([...queryTokens].filter(x => factTokens.has(x)));
      if (intersection.size === 0) continue;

      const union = new Set([...queryTokens, ...factTokens]);
      const jaccard = intersection.size / union.size;
      const recency = Math.min(1.0, ((fact.ts || 0) - cutoff) / this._ttl);
      
      const score = jaccard * 0.7 + recency * 0.3;
      scored.push({ score, fact });
    }

    scored.sort((a, b) => b.score - a.score);
    return scored.slice(0, limit).map(s => s.fact);
  }

  compact(): number {
    const cutoff = (Date.now() / 1000) - this._ttl;
    if (!fs.existsSync(this._path)) return 0;

    const lines = fs.readFileSync(this._path, 'utf-8').split('\n');
    const activeLines: string[] = [];
    
    for (let line of lines) {
      line = line.trim();
      if (!line) continue;
      try {
        const fact = JSON.parse(line);
        if ((fact.ts || 0) >= cutoff) {
          activeLines.push(line);
        }
      } catch { continue; }
    }

    fs.writeFileSync(this._path, activeLines.join('\n') + (activeLines.length > 0 ? '\n' : ''), 'utf-8');
    return activeLines.length;
  }

  private _tokenize(text: string): Set<string> {
    return new Set(
      text.toLowerCase()
        .replace(/[^\w\s]/g, ' ')
        .split(/\s+/)
        .filter(t => t.length > 2)
    );
  }

  private _factToText(fact: Fact): string {
    const parts = [fact.content || ''];
    if (fact.metadata) parts.push(JSON.stringify(fact.metadata));
    return parts.join(' ');
  }
}
