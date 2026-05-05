import * as fs from 'fs';
import * as path from 'path';
import { fileURLToPath } from 'url';
import { LocalIndex } from 'vectra';
import { embed } from './embedding.js';

const __dirname = path.dirname(fileURLToPath(import.meta.url));

interface ChunkMetadata {
  file: string;
  content: string;
  lines: string;
}

export class CodeIndex {
  private _index: LocalIndex;
  private _isInit = false;

  constructor(indexDir: string) {
    if (!fs.existsSync(indexDir)) fs.mkdirSync(indexDir, { recursive: true });
    this._index = new LocalIndex(indexDir);
  }

  async init(): Promise<void> {
    if (!this._isInit) {
      if (!await this._index.isIndexCreated()) await this._index.createIndex();
      this._isInit = true;
    }
  }

  async indexFiles(srcDir: string): Promise<number> {
    await this.init();
    const files = this._collectTs(srcDir);
    let count = 0;
    for (const file of files) {
      const content = fs.readFileSync(file, 'utf-8');
      const lines = content.split('\n');
      const vector = await embed(`FILE: ${path.basename(file)}\n${content.slice(0, 2000)}`);
      if (!vector || vector.length === 0) continue;
      const metadata: ChunkMetadata = {
        file,
        content: content.slice(0, 4000),
        lines: `1-${lines.length}`
      };
      await this._index.insertItem({ vector, metadata: metadata as any });
      count++;
    }
    return count;
  }

  async search(query: string, k: number = 5): Promise<Array<{ file: string; snippet: string; score: number }>> {
    await this.init();
    const vector = await embed(query);
    if (!vector || vector.length === 0) return [];
    const results = await this._index.queryItems(vector, query, k);
    return results.map(r => ({
      file: (r.item.metadata as any).file,
      snippet: ((r.item.metadata as any).content as string).slice(0, 500),
      score: r.score
    }));
  }

  private _collectTs(dir: string): string[] {
    const results: string[] = [];
    for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
      if (entry.name.startsWith('.') || entry.name === 'node_modules' || entry.name === 'dist') continue;
      const full = path.join(dir, entry.name);
      if (entry.isDirectory()) results.push(...this._collectTs(full));
      else if (entry.isFile() && entry.name.endsWith('.ts')) results.push(full);
    }
    return results;
  }
}
