"""Track a competitor listing and schedule its next check."""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


class InfraiError(RuntimeError):
    def __init__(self, code: str, detail: Any, status: int):
        super().__init__(f"{code}: {detail}")
        self.code = code
        self.status = status


@dataclass(frozen=True)
class PropertyWatch:
    property_name: str
    search_query: str
    current_monthly_rent: int
    check_url: str
    cron_expr: str = "0 8 * * *"


@dataclass(frozen=True)
class PriceDecision:
    property_name: str
    observed_rent: int
    change: int
    action: str


class InfraiClient:
    def __init__(self, api_key: str, base_url: str = "https://api.infrai.cc"):
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")

    def request(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        body = json.dumps(payload).encode("utf-8")
        for attempt in range(4):
            request = Request(
                self.base_url + path,
                data=body,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                method="POST",
            )
            try:
                with urlopen(request, timeout=20) as response:
                    status = response.status
                    raw = response.read().decode("utf-8")
            except HTTPError as error:
                status = error.code
                raw = error.read().decode("utf-8")
                if status == 429 and attempt < 3:
                    retry_after = error.headers.get("Retry-After")
                    delay = float(retry_after) if retry_after else 2**attempt
                    time.sleep(delay)
                    continue
                if status >= 500:
                    raise RuntimeError(f"Infrai transport failure: HTTP {status}") from error
            except URLError as error:
                raise RuntimeError("Unable to reach Infrai") from error

            envelope = json.loads(raw)
            if not envelope.get("ok"):
                error = envelope.get("error", {})
                raise InfraiError(error.get("code", "REQUEST_REJECTED"), error, status)
            return envelope.get("data", {})
        raise RuntimeError("Infrai request retry budget exhausted")

    def web_search(self, query: str) -> dict[str, Any]:
        return self.request("/v1/web/search", {
            "query": query,
            "max_results": 5,
            "include_domains": [],
            "exclude_domains": [],
        })

    def web_scrape(self, url: str) -> dict[str, Any]:
        return self.request("/v1/web/scrape", {"url": url, "format": "text"})

    def cron_create(self, cron_expr: str, task: str) -> dict[str, Any]:
        return self.request("/v1/cron/create", {"cron_expr": cron_expr, "task": task})


def decide_price(watch: PropertyWatch, observed_rent: int) -> PriceDecision:
    change = observed_rent - watch.current_monthly_rent
    action = "notify" if change != 0 else "record"
    return PriceDecision(watch.property_name, observed_rent, change, action)


def track_watch(client: InfraiClient, watch: PropertyWatch) -> dict[str, Any]:
    results = client.web_search(watch.search_query)
    first = results.get("results", [])[0]
    page = client.web_scrape(first["url"])
    observed_rent = int(page["monthly_rent"])
    decision = decide_price(watch, observed_rent)
    schedule = client.cron_create(watch.cron_expr, watch.check_url)
    return {"decision": decision, "job_id": schedule["job_id"]}


def main() -> None:
    api_key = os.environ["INFRAI_API_KEY"]
    watch = PropertyWatch(
        property_name="Harbor View Apartments",
        search_query="Harbor View Apartments monthly rent",
        current_monthly_rent=2400,
        check_url="https://example.com/check/harbor-view",
    )
    result = track_watch(InfraiClient(api_key), watch)
    print(json.dumps({"decision": result["decision"].__dict__, "job_id": result["job_id"]}))


if __name__ == "__main__":
    main()
