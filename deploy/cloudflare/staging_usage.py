"""Read staging-only Cloudflare counters with the existing environment token."""
from datetime import datetime, timedelta, timezone
import json
import os
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


def main():
    end = datetime.now(timezone.utc).replace(microsecond=0)
    start = end - timedelta(minutes=15)
    window = f'datetime_geq:"{start.isoformat()}",datetime_leq:"{end.isoformat()}"'
    datasets = {
        "workersInvocationsAdaptive": (
            'scriptName:"riburom-application-staging"',
            "sum { requests errors subrequests } quantiles { cpuTimeP50 cpuTimeP99 memoryUsageBytesP50 memoryUsageBytesP99 }",
        ),
        "hyperdriveQueriesAdaptiveGroups": (
            'configId:' + json.dumps(os.environ["HYPERDRIVE_ID"]),
            "count avg { connectionLatency queryLatency } sum { queryBytes resultBytes }",
        ),
    }
    print(f"Staging account analytics for {start.isoformat()} to {end.isoformat()}")
    for dataset, (scope, fields) in datasets.items():
        query = ('query($account: string!) { viewer { accounts(filter: {accountTag: $account}) { '
                 + dataset + '(limit: 1, filter: {' + scope + ',' + window + '}) { ' + fields + ' } } } }')
        payload = {"query": query, "variables": {"account": os.environ["CLOUDFLARE_ACCOUNT_ID"]}}
        request = Request("https://api.cloudflare.com/client/v4/graphql", data=json.dumps(payload).encode(),
                          headers={"Authorization": "Bearer " + os.environ["CLOUDFLARE_API_TOKEN"],
                                   "Content-Type": "application/json"})
        try:
            with urlopen(request, timeout=15) as response:
                result = json.load(response)
            if result.get("errors"):
                codes = [item.get("extensions", {}).get("code") for item in result["errors"]]
                print(f"{dataset}: no measurement; GraphQL error codes {codes}")
            else:
                print(dataset, result["data"]["viewer"]["accounts"][0][dataset])
        except (HTTPError, URLError, TimeoutError, IndexError, KeyError) as exc:
            print(f"{dataset}: unavailable ({type(exc).__name__})")


if __name__ == "__main__":
    main()
