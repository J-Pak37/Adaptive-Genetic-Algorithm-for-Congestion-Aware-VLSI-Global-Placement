# Adaptive Genetic Algorithm for Congestion-Aware VLSI Global Placement

This repository contains the implementation and experimental results of an **Enhanced Genetic Algorithm (GA)** featuring an **Adaptive Mutation Rate** mechanism. The project addresses the critical challenge of balancing wirelength minimization and routing congestion in large-scale VLSI design.

##  Research Overview

In modern VLSI physical design, the global placement phase must optimize multiple conflicting objectives. While many swarm intelligence algorithms (e.g., SHO, WOA) can achieve low objective costs by minimizing wirelength (HPWL), they often fail to maintain routability due to extreme module overlapping.

This research proposes an **Adaptive Genetic Algorithm** that:
- Integrates a **Congestion-Aware Fitness Function** to prevent unroutable hotspots.
- Employs an **Adaptive Mutation Rate** to escape local optima and maintain population diversity.
- Successfully handles large-scale benchmarks from the **ISPD 2005** suite (e.g., `adaptec1.inf`, `bigblue1.inf`).

##  Key Features

- **Adaptive Mutation Strategy:** Dynamically adjusts the mutation probability based on convergence stability and congestion feedback.
- **Routability-Driven Optimization:** Unlike standard metaheuristics, our approach ensures that the final placement adheres to routing capacity constraints.
- **Comparative Analysis:** Includes scripts to compare performance against Spotted Hyena Optimizer (SHO) and Whale Optimization Algorithm (WOA).

## Experimental Results

Our findings demonstrate that the Proposed GA maintains a manageable Maximum Congestion level (e.g., **15.62** for `adaptec1.inf`) compared to the extreme values (> $10^{11}$) produced by non-routable swarm algorithms.

### Convergence Analysis
The GA shows a stable and realistic convergence curve, avoiding the "instantaneous but deceptive" convergence seen in algorithms that ignore physical constraints.

## Installation & Usage

### Prerequisites
- Python 3.8+
- Required Libraries: `numpy`, `matplotlib`, `pandas`

### Running the Placement
To run the optimization on a specific benchmark:
```bash
python main.py --benchmark adaptec1.inf --iterations 200
