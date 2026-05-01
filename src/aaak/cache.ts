import * as fs from 'fs';
import * as path from 'path';
import * as crypto from 'crypto';
import { fileURLToPath } from 'url';
import { LocalIndex } from 'vectra';
import { embed } from './embedding.js';
import type { Manifest } from './compress.js';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const ROME_ROOT = process.env.ROME_ROOT || process.cwd();

export interface CachedManifest extends Manifest {
  _cache_hash?: string;
  [key: string]: any;
}

export class SemanticCache {
  private _cacheDir: string;
  private _index: LocalIndex;
  private _isInit: boolean = false;

  constructor(cacheDir?: string) {
    this._cacheDir = cacheDir || path.join(__dirname, '..', '..', 'aaak', '.cache');
    if (!fs.existsSync(this._cacheDir)) {
      fs.mkdirSync(this._cacheDir, { recursive: true });
    }
    this._index = new LocalIndex(path.join(this._cacheDir, 'manifests'));
  }

  async init(): Promise<void> {
    if (!this._isInit) {
      if (!await this._index.isIndexCreated()) {
        try {
          await this._index.createIndex();
        } catch (e: any) {
          if (e.message && !e.message.includes('already exists')) {
            throw e;
          }
        }
      }
      this._isInit = true;
    }
  }

  private _hashEnvironment(): string {
    const hash = crypto.createHash('sha256');
    const searchDirs = [path.join(ROME_ROOT, 'src'), path.join(ROME_ROOT, 'aaak')];
    
    try {
      for (const dir of searchDirs) {
        if (!fs.existsSync(dir)) continue;
        this._hashDir(dir, hash);
      }
      return hash.digest('hex');
    } catch (e) {
      console.warn('Environment hashing failed, falling back to static hash:', e);
      return process.env.ROME_TASK_DIR || 'global-fallback';
    }
  }

  private _hashDir(dir: string, hash: crypto.Hash) {
    const entries = fs.readdirSync(dir, { withFileTypes: true });
    // Sort entries to ensure deterministic hashing
    entries.sort((a, b) => a.name.localeCompare(b.name));

    for (const entry of entries) {
      const fullPath = path.join(dir, entry.name);
      if (entry.isDirectory()) {
        // Skip hidden dirs and node_modules
        if (entry.name.startsWith('.') || entry.name === 'node_modules') continue;
        this._hashDir(fullPath, hash);
      } else if (entry.isFile()) {
        const stat = fs.statSync(fullPath);
        hash.update(`${entry.name}:${stat.mtimeMs}`);
      }
    }
  }

  async get(capability: string, prompt: string): Promise<CachedManifest | null> {
    await this.init();
    const queryStr = `${capability}:${prompt}`;
    const vector = await embed(queryStr);
    
    if (!vector || vector.length === 0) return null;

    try {
      const results = await this._index.queryItems(vector, queryStr, 1);
      if (results.length > 0) {
        const top = results[0];
        // > 0.98 similarity indicates semantic equivalence
        if (top.score > 0.98) {
          const manifest = top.item.metadata as unknown as CachedManifest;
          if (manifest._cache_hash === this._hashEnvironment()) {
            return manifest;
          }
        }
      }
    } catch (e) {
      console.warn('SemanticCache query failed:', e);
    }
    
    return null;
  }

  async set(capability: string, prompt: string, manifest: Manifest): Promise<void> {
    await this.init();
    const queryStr = `${capability}:${prompt}`;
    const vector = await embed(queryStr);
    
    if (vector && vector.length > 0) {
      try {
        const cacheData: CachedManifest = {
          ...manifest,
          _cache_hash: this._hashEnvironment()
        };
        await this._index.insertItem({
          vector,
          metadata: cacheData as any
        });
      } catch (e) {
        console.warn('SemanticCache insert failed:', e);
      }
    }
  }

  isStatelessAnalysis(capability: string, prompt: string): boolean {
    const isLLM = !['SAFE_SHELL', 'NATIVE_SHELL', 'TEST'].includes(capability.toUpperCase());
    const lowerPrompt = prompt.toLowerCase();
    // Heuristic: If it asks for an explanation, summary, review, or question without mutating intent
    const isAnalysis = /^(analyze|explain|summarize|what|how|why|review)\b/i.test(lowerPrompt) || 
                       !/(create|write|implement|fix|refactor|update|delete|replace)/i.test(lowerPrompt);
    return isLLM && isAnalysis;
  }
}
