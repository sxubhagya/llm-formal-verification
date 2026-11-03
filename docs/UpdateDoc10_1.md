# Update 10.1 — Gemini API Reliability and Model Discovery

## Purpose
This increment follows the first live Gemini API attempt. Authentication succeeded, but generation failed because the selected model returned HTTP 503 (temporary high demand). It also corrects the stale provider default and removes credentials from the example environment file.

## Changes
1. Gemini provider default model changed to `gemini-3.8-flash`; the actual runtime model remains configurable through `LLM_MODEL`.
2. Added bounded retry handling for transient HTTP statuses (408, 429, 500, 502, 503, 504), timeouts, and network request errors.
3. Retry policy uses at most three total attempts, exponential delays (1s, 2s), and respects a numeric `Retry-After` header up to an 8-second cap.
4. HTTP 401/403 and non-transient errors are not retried.
5. Added `GET /api/llm/models`, which lists only models visible to the configured API key and advertising `generateContent` support. It does not return or log credentials.
6. Sanitized `.env.example`: all API key values are blank; the sample model is `gemini-3.8-flash`.
7. Application version is now 0.5.1.
8. Added offline tests for transient retries, retry exhaustion, authentication non-retry, model filtering, and missing-key handling.

## Important configuration
- `.env` remains a local-only file and is intentionally excluded from release ZIPs.
- Copy `.env.example` to `.env` if needed.
- Put the actual key only in `.env` as `GEMINI_API_KEY=...`.
- `LLM_MODEL` selects the generation model. Query `GET /api/llm/models` to see the models exposed to the current key.
- No billing setup is performed by this application. Google account/project tier and quotas remain controlled by Google.

## Limitations
- Model discovery is a live call to Google's `models.list` endpoint and has not been verified against the user's account in this offline build.
- Retries cannot resolve a sustained provider outage, exhausted daily quota, or model access restriction; they only absorb transient failures.
- No automatic model fallback is performed. Choosing an available model remains explicit so the framework does not silently change the model being evaluated.

## Validation
- Unit tests are included for the retry and model-discovery logic.
- A real Gemini request must still be run by the user after installing this update.
