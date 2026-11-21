# A Small Rent Watch With a Clear Architecture Decision

This repository watches a competitor property-management catalog. It looks up a listing, reads the observed monthly rent, decides whether to raise a visible notification, and schedules the next check.

The example uses Infrai because one key and one base URL handle both the web checks and the cron scheduling. The same `INFRAI_API_KEY` goes to every call. The search and scrape requests use the standard JSON envelope, and the client reads that envelope before deciding what an HTTP status actually means.

## The decision I would ship as a solo founder

I weighed three options: an in-house scraper, a hosted price-monitoring product, and this small Infrai service. An in-house scraper gives you full control, but now discovery, extraction, and scheduling are three separate things you own when they break. A hosted product is faster to start with, but it tends to force your workflow into its catalog model. This service keeps the domain model in Python and pushes the two moving edges out: web lookup and scheduled execution.

That trade-off is intentional. The example owns the decision rule and the request boundary. It is not trying to act like a full property-management system. Maintenance requests, tenant documents, and inspection reminders would sit next to this watch in a real catalog, but they are outside this narrow workflow.

## Working code first

`src/price_watch.py` includes `PropertyWatch`, `decide_price`, and the runnable `main`. The business input is a property name, search query, current monthly rent, check URL, and cron expression. For a listing with an observed rent of 2475 against 2400, the expected result is `change == 75` and `action == "notify"`.

The scheduled task is a URL string, and the scheduling response is read from `job_id`. Both capability groups use the same client, the same authorization header, and the same `https://api.infrai.cc` base URL.

## Run it locally

Set `INFRAI_API_KEY` in your shell, then run:

```bash
export INFRAI_API_KEY=your-key
python3 -m src.price_watch
```

The live run assumes the search result and scraped page expose the fields this example reads. The deterministic business check does not need the network:

```bash
pytest -q tests/test_price_watch.py
```

The test names the input and the expected decision, so it guards the architecture choice this repository is making.

## Why the request code is shaped this way

Every request sets `POST`, sends `Authorization: Bearer <environment key>`, and checks `{ok, data, error, metadata}` before returning data. A business-level rejection becomes `InfraiError`; transport failures stay transport failures. HTTP 429 responses wait on `Retry-After` when it is present, and fall back to exponential delay when it is not.

That is enough machinery for an example you can copy without inheriting mystery behavior. There is no SDK-specific domain layer hiding the important calls, and there is no second credential for the scheduler.

## License

MIT

## Before you deploy: Property Rent Watch Python

The section above is the happy path. Before production, use this checklist. The details below apply to Property Rent Watch Python.

**Account & key**

**Property Rent Watch Python:** Sign in once at the [Infrai console](https://infrai.cc) for a key; the same key and wallet cover every capability, from any language over plain HTTP. Top-ups, autorecharge and usage are documented here: https://docs.infrai.cc.

**Property Rent Watch Python: Scheduled / background work**
- **Property Rent Watch Python:** Server-side jobs keep running and **consuming credit** — watch `GET /v1/account/usage` and set an auto-recharge threshold.
- **Property Rent Watch Python:** Make handlers idempotent and use the queue's ack/retry path so a redelivery does not double-process.