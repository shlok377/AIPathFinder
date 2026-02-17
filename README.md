<a name="readme-top"></a>

<div align="center"\>
<img src="https://github.com/shlok377/AIPathFinder/blob/master/img/logo.png?raw=true" width="500px;" alt=""/>
    
# **Astra: Advanced A*** **Multi-Agent Warehouse Optimizer**

### **National Level Hackathon Submission • Google Collaboration**

**A high-fidelity 3D Digital Twin for autonomous robot logistics and battery management.**  
[View Demo](#-simulation-preview) • [System Architecture](#logic-flow) • [Installation](#installation-steps)  


## **📌 The Problem**

Modern automated warehouses lose an average of **5% to 20% operational efficiency** due to two primary bottlenecks: **Path-Clashing** (multi-agent congestion) and **Battery Downtime** (suboptimal charging cycles)¹.  
**(Project Name)** solves this by implementing a battery-aware Multi-Agent Pathfinding (MAPF) algorithm within a 3D environment, optimizing throughput while ensuring zero dead-battery incidents.

## **📸 Simulation Preview**

*Replace these placeholders with your actual Ursina recordings.*

| 🏗️ 3D Warehouse Overview | 🤖 Robot Navigation Logic |
| :---- | :---- |
|  |  |

## **⚡ Key Features**

We moved beyond simple pathfinding. Our robots are **self-aware** agents.

| 🧠 Intelligence | ⚡ Power Management | 🏗️ Environment |
| :---- | :---- | :---- |
| *A Algorithm*\* Finds shortest paths dynamically avoiding static shelves. | **Auto-Docking** Robots self-charge at \<20% battery. | **3D Digital Twin** Real-time visualization using Ursina Engine. |
| **Collision Avoidance** Real-time "traffic control" to prevent multi-agent crashes. | **Priority Queuing** Urgent tasks override charging (if safe). | **Custom Layouts** Load warehouse maps via .txt config files. |

## **🧠 System Architecture**

### <a name="logic-flow"></a> **The Logic Flow**

```mermaid
flowchart TD
    %% --- Custom Style Definitions to match the image ---
    %% Blue: Process nodes and Start
    classDef blueFill fill:#203864,stroke:#4472c4,stroke-width:2px,color:white;
    %% Green: Decision diamonds and Positive outcomes (Discount)
    classDef greenFill fill:#1e452a,stroke:#548235,stroke-width:2px,color:white;
    %% Red: Negative outcomes, Penalties, and End states
    classDef redFill fill:#631d1d,stroke:#c00000,stroke-width:2px,color:white;

    %% --- Main Pathfinding Loop ---
    Start([Start Pathfinding<br>Robot at Current Position, Target]):::blueFill --> Init[Initialize Open Set with Start Node<br>x, y, wait_count=0, cost=0]:::blueFill
    Init --> IsEmpty{Is Open Set Empty?}:::greenFill
    
    IsEmpty -- Yes --> Fail([Path Not Found Failure]):::redFill
    IsEmpty -- No --> Select[Select Node with Lowest F-Cost<br>Current Node]:::blueFill
    
    Select --> IsTarget{Is Current Node == Target?}:::greenFill
    IsTarget -- Yes --> Success([Path Found Success, Traceback Path]):::redFill
    IsTarget -- No --> Expand[Expand Neighbors & Evaluate]:::blueFill

    %% --- Neighbor Evaluation Subgraph ---
    subgraph NeighborEval [Neighbor Evaluation]
        direction TB
        
        Expand --> IsHighway{Is Neighbor a<br>Highway Lane?}:::greenFill
        
        %% Branch: Highway Logic
        IsHighway -- Y --> PrefDir{Moving in Preferred<br>Direction?}:::greenFill
        PrefDir -- Y --> HwyDiscount[Apply<br>HIGHWAY_DISCOUNT<br>0.3x Cost]:::greenFill
        PrefDir -- No --> HwyPenalty[Apply<br>HIGHWAY_WRONG_WAY_PENALTY<br>+50.0 Cost]:::redFill
        
        %% Branch: Turn Logic
        IsHighway -- N --> IsTurn{Is Movement a Turn?}:::greenFill
        IsTurn -- Yes --> TurnPenalty[Add<br>TURN_PENALTY<br>+3.0 Cost]:::redFill
        
        %% Branch: Blocked/Wait Logic
        IsTurn -- No --> IsTempBlocked{Is Neighbor Cell<br>Temporarily Blocked?}:::greenFill
        IsTempBlocked -- Yes --> ConsiderWait{Consider 'Stay Put'<br>Wait?}:::greenFill
        ConsiderWait -- Yes --> WaitPenalty[Apply WAIT_PENALTY<br>+1.1 Cost,<br>Increment wait_count]:::redFill
        ConsiderWait -- No --> BlockedCost[Standard Blocked Cell<br>High Cost]:::redFill
        
        %% Branch: Occupied Logic
        IsTempBlocked -- No --> IsOccupied{Is Neighbor<br>occupied by<br>another Robot Soft<br>Obstacle?}:::greenFill
        IsOccupied -- Yes --> SoftAvoid[Add<br>SOFT_AVOIDANCE Cost<br>+8.0 Cost]:::redFill
        
        %% Convergence Point: Calculate Costs
        HwyDiscount --> CalcTotal[Calculate Total<br>G-Cost & H-Cost]:::blueFill
        HwyPenalty --> CalcTotal
        TurnPenalty --> CalcTotal
        WaitPenalty --> CalcTotal
        BlockedCost --> CalcTotal
        SoftAvoid --> CalcTotal
        IsOccupied -- No --> CalcTotal
        
        %% Path Evaluation
        CalcTotal --> IsBetter{Is New Path<br>Better?<br>Lower G-Cost}:::greenFill
        
        IsBetter -- Yes --> Update[Update/Add Neighbor<br>to Open Set with<br>new Cost & Parent]:::blueFill
    end

    %% --- Feedback Loops ---
    %% These arrows go back to the main loop start
    IsBetter -- No --> IsEmpty
    Update --> IsEmpty
  ```

### **The Math: Battery-Weighted A\***

Our heuristic function $f(n)$ incorporates a **Power Penalty** $P(b)$ to influence routing toward chargers when needed:  
$$f(n) = g(n) + h(n) + P(b)$$
Where:

* $g(n)$: Distance from start node.  
* $h(n)$: Estimated distance to target shelf.  
* $P(b)$: Exponential penalty based on current battery charge level ($100 - b$).


<div align="center">

## 📂 Project Structure

<div align="left">
<pre>
📂 AIPathFinder
├── 📂 core                     - Core algorithms (Pathfinding logic)
├── 📂 entities                 - Game objects (Robots, Shelves, Chargers)
├── 📂 models                   - 3D Assets (.obj/.glb models)
├── 📂 textures                 - Visual assets and skins
├── 📂 cloud_logs               - Telemetry logs for Google Cloud
├── 📄 main.py                  - Main Simulation Entry Point
├── 📄 mainUI.py                - User Interface & Menu System
├── 📄 warehouse_layout.txt     - Warehouse Grid Configuration
├── 📄 default_layout.txt       - Backup Layout
├── 📄 cloud_telemetry.json     - Real-time Data Sync
├── 📄 GOOGLE_CLOUD_Features.md - Cloud Documentation
└── 📄 requirements.txt         - Dependencies
</pre>
</div>

</div>

## **🚀 Getting Started** <a name="installation-steps"></a>
### **Prerequisites**

* Python 3.10+  
* Pip (Python Package Manager)

### **Installation**

1. **Clone the repository:**  
  ``` git clone [https://github.com/shlok377/AIPathFinder.git\](https://github.com/shlok377/AIPathFinder.git) ```
   ```cd AIPathFinder```

2. **Install dependencies:**  
   ```pip install -r requirements.txt```

3. **Run the simulation:**  
   ```python main.py```



# Warehouse Layout Map  
**X** = Shelf, **#** = Charger, **T** = Truck, **.** = Empty Aisle
```
.#......#....#......#.
.T......T....T......T.
......................
......................
..XXXX.XXX..XXX.XXXX..
..XXXX.XXX..XXX.XXXX..
......................
......................
..XXXX.XXX..XXX.XXXX..
..XXXX.XXX..XXX.XXXX..
......................
......................
..XXXX.XXX..XXX.XXXX..
..XXXX.XXX..XXX.XXXX..
......................
......................
..XXXX.XXX..XXX.XXXX..
..XXXX.XXX..XXX.XXXX..
......................
......................
..XXXX.XXX..XXX.XXXX..
..XXXX.XXX..XXX.XXXX..
......................
......................
```


## **👥 The Team**

<table>
  <tr>
    <td align="center"><a href="https://github.com/shlok377"><img src="https://github.com/shlok377.png" width="100px;" alt=""/><br /><sub><b>Shlok</b></sub></a><br />Algorithm Lead</td>
    <td align="center"><a href="https://github.com/vishva-19"><img src="https://github.com/vishva-19.png" width="100px;" alt=""/><br /><sub><b>Vishva</b></sub></a><br />3D Design</td>
    <td align="center"><a href="https://github.com/JJstartscoding"><img src="https://github.com/JJstartscoding.png" width="100px;" alt=""/><br /><sub><b>Jashn</b></sub></a><br />Research</td>
  </tr>
</table>

<p align="center"\>  
    <i\>Comparision of Astra with Industry Benchmarks (Generated by Gemini CLI)</i\>  
    <img src="https://github.com/shlok377/AIPathFinder/blob/master/img/ratings.png?raw=true" alt=""/>
</p>
<p align="center">(<a href="#readme-top">back to top</a>)</p>











