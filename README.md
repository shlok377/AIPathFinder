<div align="center"\>

# **(Project Name): AI Multi-Agent Warehouse Optimizer**

### **National Level Hackathon Submission | Google Collaboration**

**A high-fidelity 3D Digital Twin for autonomous robot logistics and battery management.**  
[View Demo](https://www.google.com/search?q=%23-simulation-preview) • [System Architecture](https://www.google.com/search?q=%23-system-architecture) • [Installation](https://www.google.com/search?q=%23-getting-started)  


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

### **The Logic Flow**

```
graph TD;
  A[ Start: Robot Assigned Task] --> B{ Battery Level > 20%?};
  B -- Yes --> C[ Calculate A* Path to Shelf];
  B -- No --> D[ Calculate Path to Charging Station];
  C --> E[ Move to Target Node];
  D --> F[ Charge Sequence Initiated];
  E --> G{ Obstacle Detected?};
  G -- Yes --> H[ Recalculate Path (Local Avoidance)];
  G -- No --> I[ Task Complete];
  F --> A;
  H --> E;
  ```

### **The Math: Battery-Weighted A\***

Our heuristic function $f(n)$ incorporates a **Power Penalty** $P(b)$ to influence routing toward chargers when needed:  
$$f(n) = g(n) + h(n) + P(b)$$
Where:

* $g(n)$: Distance from start node.  
* $h(n)$: Estimated distance to target shelf.  
* $P(b)$: Exponential penalty based on current battery charge level ($100 - b$).


## **📂 Project Structure**

A clean architecture separates the simulation engine from the logical core.  
📂 Project Root  
├── 📂 core/  
│   ├── 🐍 a_star.py          # The Brain: Pathfinding logic  
│   ├── 🐍 agent.py           # The Body: Robot state machine  
│   └── 🐍 battery.py         # The Heart: Power management system  
├── 📂 assets/  
│   ├── 📦 shelf_model.obj    # 3D assets for Ursina  
│   └── 🤖 robot_texture.png  
├── 📄 main.py                # Entry point (Simulation Loop)  
├── 📄 warehouse_layout.txt   # Configurable map file  
└── 📄 requirements.txt       # Dependencies

## **🚀 Getting Started**

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

* **Shlok** \- *Lead Developer / Algorithm Design*  
* **Vishva** \- *3D Modeling / Environment Design*  
* **Jashn** \- *Documentation / Research*

<p align="center"\>  
<small\>  
¹ <i\>References: Industry benchmarks suggest 5-20% downtime in autonomous fleets due to power management and navigation bottlenecks (PatentPC 2024; CaPow Energy Research 2025).</i\>  
<a href="\#-project-name-ai-multi-agent-warehouse-optimizer"\>(back to top)</a\>  
</p\>

</small\>


