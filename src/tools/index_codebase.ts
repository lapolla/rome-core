import * as path from 'path';
import { fileURLToPath } from 'url';
import { CodeIndex } from '../aaak/code_index.js';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const ROME_ROOT = process.env.ROME_ROOT || path.resolve(__dirname, '../../..');

async function main() {
  const indexDir = path.join(ROME_ROOT, '.rome', 'code');
  const srcDir = path.join(ROME_ROOT, 'src');
  const idx = new CodeIndex(indexDir);
  const count = await idx.indexFiles(srcDir);
  console.log(`Indexed ${count} files into ${indexDir}`);
}

main().catch(console.error);
