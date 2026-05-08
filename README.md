# ui_copycat

Prototype for replicating a live UI into React/Tailwind with an `observe -> generate -> evaluate` loop.

## Run

```bash
uv sync
npm install --prefix generated-page
export GOOGLE_API_KEY=your_key
python generate_agent_images.py
npm --prefix generated-page run dev
```
