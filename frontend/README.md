# TurnB PPT Agent frontend

The Next.js chat interface for the TurnB Autonomous PPT Agent. Project-wide setup, configuration, testing, and deployment instructions are in the [root README](../README.md).

## Commands

```bash
npm ci
npm run dev
npm run lint
npm run build
npm start
```

Development runs at `http://localhost:3000`. When `NEXT_PUBLIC_API_URL` is unset, the client uses `http://localhost:8000`; set it in an ignored `.env.local` file to override that URL. An example is provided in `.env.example`.
