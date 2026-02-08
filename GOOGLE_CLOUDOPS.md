# Google Cloud Robotics - Operations Manual

## 📡 System Architecture: Edge-to-Cloud

AIPathfinder simulates a production-grade **Cloud Robotics** pipeline. Each robot acts as an "Edge Device" that processes navigation locally but streams operational data to a centralized "Cloud" aggregator.

```ascii
+----------------+       +-------------------+       +-------------------------+
|  EDGE ROBOTS   |       |  TELEMETRY HUB    |       |   GOOGLE CLOUD (MOCK)   |
| (entities/robot)| ---> | (core/telemetry)  | --->  | (cloud_logs/dashboard)  |
+----------------+       +-------------------+       +-------------------------+
   [Events]                  [Aggregation]                [Analytics]
   - Task Assign             - Buffer (Deque)             - Efficiency Score
   - Repath (Warn)           - Sync Interval (5s)         - Fleet Battery Avg
   - Crit Battery            - JSON Formatting            - Uptime Tracking
```

## 📊 Key Performance Indicators (KPIs)

We track two primary metrics to demonstrate the effectiveness of our pathfinding algorithm. These formulas are designed to reward speed and punish inefficiency (deadlocks).

### 1. Workflow Efficiency (W)
*Measures operational throughput vs. friction.*

$$ W = \frac{	ext{Deliveries} 	imes 10}{	ext{Uptime (min)} + 	ext{Conflicts} + 1} $$

*   **Deliveries:** Successful package drops.
*   **Conflicts:** Number of times a robot had to recalculate its path due to a blocker.
*   **Goal:** Maximize deliveries while minimizing conflicts.

### 2. Battery Efficiency (B)
*Measures energy optimization.*

$$ B = \frac{	ext{Deliveries} 	imes 100}{	ext{Total \% Battery Drained}} $$

*   **Interpretation:** A score of **2.5** means the fleet completes 2.5 tasks for every 100% of battery capacity used (across all robots). Higher is better.

## 📝 Data Structure Standards

### Structured Logs
We strictly adhere to **Google Cloud Structured Logging** principles.

**Example `cloud_dashboard.json`:**
```json
{
    "metadata": {
        "sync_time": "14:35:02",
        "elapsed_time": "45s",
        "formula": "(Deliveries * 10) / (Minutes + Conflicts + 1)"
    },
    "kpis": {
        "efficiency": "85.4%",
        "deliveries": 12,
        "fleet_battery": "94%"
    },
    "robots": [
        {
            "id": 0,
            "state": "TO_PICKUP",
            "battery": "98%"
        },
        {
            "id": 1,
            "state": "CHARGING",
            "battery": "24%"
        }
    ]
}
```

## 🖥️ Console Dashboard

To assist Warehouse Operators (Judges), we provide a real-time ASCII dashboard in the terminal:

```text
══════════════════════════════════════════════════════════════════════
 ☁️  GOOGLE CLOUD MONITOR | 14:35:05 | Uptime: 48s
──────────────────────────────────────────────────────────────────────
  EFFICIENCY: 92.1%
  FORMULA:    (Deliveries * 10) / (Minutes + Conflicts + 1)
  DELIVERIES: 5  |  BATTERY: 97% (AVG)

  TRUCK STATUS
  ID  | STATE          | BATT | TASK
  ----|----------------|------|-----
  0   | To pickup      |  99% | a
  1   | Delivering     |  96% | a
  2   | Charging       |  22% | -

  DOCK STATUS
  ID  | STATUS      | ASSIGNED TO
  ----|-------------|------------
  0   | OCCUPIED    | Robot 2
  1   | FREE        | -
══════════════════════════════════════════════════════════════════════
```
