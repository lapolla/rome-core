import fs from 'fs';
import path from 'path';

interface EmbeddingsConfig {
  url: string;
  model: string;
}

let config: EmbeddingsConfig = {
  url: 'http://localhost:11434/api/embeddings',
  model: 'nomic-embed-text'
};

try {
  const configPath = path.join(process.cwd(), 'dictator', 'config.json');
  if (fs.existsSync(configPath)) {
    const raw = fs.readFileSync(configPath, 'utf8');
    const parsed = JSON.parse(raw);
    if (parsed.embeddings) {
      config = parsed.embeddings;
    }
  }
} catch (e) {
  console.warn('Failed to load embeddings config, using defaults.', e);
}

export async function embed(text: string): Promise<number[]> {
  try {
    const response = await fetch(config.url, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        model: config.model,
        prompt: text
      })
    });

    if (!response.ok) {
      throw new Error(`Ollama returned ${response.status}: ${response.statusText}`);
    }

    const data = await response.json();
    if (data && Array.isArray(data.embedding)) {
      return data.embedding;
    }
    
    console.warn('Unexpected response format from Ollama embeddings:', data);
    return [];
  } catch (error) {
    console.warn(`Failed to embed text using Ollama: ${error}`);
    return [];
  }
}
