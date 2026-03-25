import os
import sys
import time
import copy
import csv
import random
import numpy as np

# โหลดโมดูลเดิมของคุณ
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__))))
from parser import load_ucla_benchmark
from evaluator import evaluate_placement
from chip import Chip

# --- Configuration (Fixed for fair comparison) ---
ALPHA = 0.9          
BETA = 1e-5          
MAX_ITER = 200       # ตั้งค่าจริง 200 รอบ
CONG_GRID = (32, 32) 
POP_SIZE = 10        # จำนวนประชากรมาตรฐาน

# เส้นทางไฟล์ (อิงตามเครื่องของคุณ)
DATA_DIR = r"C:\Users\pakde\OneDrive\เดสก์ท็อป\VLSI_Placement_Optimization-Develop\data\ispd2005_benchmarks"
NODES_FILE = os.path.join(DATA_DIR, "bigblue1.inf.nodes")
NETS_FILE = os.path.join(DATA_DIR, "bigblue1.nets")
OUTPUT_CSV = "metaheuristics_results.csv"

class AutomatedExperiment:
    def __init__(self, chip: Chip):
        self.chip = chip

    def run_ga(self):
        """GA with Dynamic Mutation"""
        start_time = time.time()
        movable_mods = self.chip.get_movable_modules()
        P_START, P_END = 0.2, 0.02
        
        population = [np.array([[random.uniform(0, self.chip.width - m.width), 
                                 random.uniform(0, self.chip.height - m.height)] for m in movable_mods]) 
                      for _ in range(POP_SIZE)]
        
        for it in range(MAX_ITER):
            curr_mut_rate = P_START - (it * (P_START - P_END) / MAX_ITER)
            costs = []
            for p in population:
                for idx, m in enumerate(movable_mods): m.set_position(p[idx][0], p[idx][1])
                res = evaluate_placement(self.chip, grid_size=CONG_GRID, alpha=ALPHA, beta=BETA)
                costs.append(res['total_cost'])
            
            best_idx = np.argsort(costs)[:2]
            p1, p2 = population[best_idx[0]], population[best_idx[1]]
            
            for i in range(2, POP_SIZE):
                mask = np.random.rand(len(movable_mods), 2) > 0.5
                population[i] = np.where(mask, p1, p2)
                if random.random() < curr_mut_rate:
                    m_idx = random.randint(0, len(movable_mods)-1)
                    population[i][m_idx] = [random.uniform(0, self.chip.width - movable_mods[m_idx].width), 
                                            random.uniform(0, self.chip.height - movable_mods[m_idx].height)]
            if it % 20 == 0: print(f"GA Progress: {it}/{MAX_ITER}")
        return time.time() - start_time

    def run_aco(self):
        """ACO with Spatial Jittering & Dynamic Evaporation"""
        start_time = time.time()
        movable_mods = self.chip.get_movable_modules()
        pheromone_map = np.ones(CONG_GRID)
        cell_w, cell_h = self.chip.width / CONG_GRID[1], self.chip.height / CONG_GRID[0]
        
        for it in range(MAX_ITER):
            pos_history = []
            for m in movable_mods:
                probs = pheromone_map.flatten() / pheromone_map.sum()
                flat_idx = np.random.choice(range(pheromone_map.size), p=probs)
                r, c = np.unravel_index(flat_idx, CONG_GRID)
                pos_history.append((r, c))
                
                jx, jy = random.uniform(0, max(0, cell_w - m.width)), random.uniform(0, max(0, cell_h - m.height))
                m.set_position((c * cell_w) + jx, (r * cell_h) + jy)
            
            res = evaluate_placement(self.chip, grid_size=CONG_GRID, alpha=ALPHA, beta=BETA)
            rho = 0.1 + (0.4 * (1 - it/MAX_ITER))
            pheromone_map *= (1 - rho)
            reward = 1.0 / (res['total_cost'] + 1e-6)
            for r, c in pos_history: pheromone_map[r, c] += reward
            
            if it % 20 == 0: print(f"ACO Progress: {it}/{MAX_ITER}")
        return time.time() - start_time

def save_to_csv(results, filename):
    metrics = ['total_cost', 'hpwl', 'avg_congestion', 'max_congestion', 'overflow_ratio', 'time']
    with open(filename, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['Metric', 'GA', 'ACO'])
        for m in metrics:
            writer.writerow([m, results['GA'][m], results['ACO'][m]])

def main():
    print("🚦 เริ่มต้นการรันอัตโนมัติ (จะบันทึกลงไฟล์ CSV)...")
    chip_base = load_ucla_benchmark(NODES_FILE, NETS_FILE)
    final_results = {}

    for algo in ['GA', 'ACO']:
        print(f"--- กำลังรัน {algo} ---")
        curr_chip = copy.deepcopy(chip_base)
        runner = AutomatedExperiment(curr_chip)
        exec_time = runner.run_ga() if algo == 'GA' else runner.run_aco()
        
        metrics = evaluate_placement(curr_chip, grid_size=CONG_GRID, alpha=ALPHA, beta=BETA)
        metrics['time'] = exec_time
        final_results[algo] = metrics
        print(f"✅ {algo} เสร็จสมบูรณ์!")

    save_to_csv(final_results, OUTPUT_CSV)
    print(f"🎉 บันทึกผลลัพธ์ลง {OUTPUT_CSV} เรียบร้อยแล้ว!")

if __name__ == "__main__":
    main()