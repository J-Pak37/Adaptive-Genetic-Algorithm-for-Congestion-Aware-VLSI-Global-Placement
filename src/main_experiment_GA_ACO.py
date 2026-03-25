import os
import sys
import time
import copy
import random
import numpy as np

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__))))

from parser import load_ucla_benchmark
from evaluator import evaluate_placement
from chip import Chip

# --- ส่วนของการตั้งค่าตามเปเปอร์ ---
ALPHA = 0.9          
BETA = 1e-5          
MAX_ITER = 200       #ปรับเพื่อเทส ปกติคือ 200
CONG_GRID = (32, 32) 

# --- เส้นทางไฟล์ ---
DATA_DIR = r"C:\Users\pakde\OneDrive\เดสก์ท็อป\VLSI_Placement_Optimization-Develop\data\ispd2005_benchmarks"
NODES_FILE = os.path.join(DATA_DIR, "bigblue1.inf.nodes")
NETS_FILE = os.path.join(DATA_DIR, "bigblue1.nets")

def calculate_overlap_penalty(chip):
    movable = chip.get_movable_modules()
    zero_count = sum(1 for m in movable if m.x < 1.0 and m.y < 1.0)
    if zero_count > len(movable) * 0.1:
        return 1.0 
    return 0.0

class PlacementExperiment:
    def __init__(self, chip: Chip):
        self.chip = chip

    def run_ga(self):
        """อัลกอริทึม Genetic Algorithm (GA) พร้อม Dynamic Mutation"""
        start_time = time.time()
        movable_mods = self.chip.get_movable_modules()
        pop_size = 10 #ลดประชากรเพื่อเทส ปกติ 10
        
        # กำหนดช่วงของ Mutation Rate
        P_START = 0.2
        P_END = 0.02
        
        population = [np.array([[random.uniform(0, self.chip.width - m.width), 
                                 random.uniform(0, self.chip.height - m.height)] for m in movable_mods]) 
                      for _ in range(pop_size)]
        
        for it in range(MAX_ITER):
            # --- คำนวณ Dynamic Mutation Rate สำหรับรอบนี้ ---
            current_mutation_rate = P_START - (it * (P_START - P_END) / MAX_ITER)
            
            costs = []
            for p in population:
                for idx, m in enumerate(movable_mods):
                    m.set_position(p[idx][0], p[idx][1])
                res = evaluate_placement(self.chip, grid_size=CONG_GRID, alpha=ALPHA, beta=BETA)
                costs.append(res['total_cost'])
            
            best_indices = np.argsort(costs)[:2]
            parent1, parent2 = population[best_indices[0]], population[best_indices[1]]
            
            for i in range(2, pop_size):
                mask = np.random.rand(len(movable_mods), 2) > 0.5
                population[i] = np.where(mask, parent1, parent2)
                
                # --- ใช้ Dynamic Mutation Rate ---
                if random.random() < current_mutation_rate:
                    m_idx = random.randint(0, len(movable_mods)-1)
                    # สุ่มย้ายโมดูลไปยังตำแหน่งใหม่
                    population[i][m_idx] = [random.uniform(0, self.chip.width - movable_mods[m_idx].width), 
                                            random.uniform(0, self.chip.height - movable_mods[m_idx].height)]
            
            # (Optional) แสดงค่า Rate ปัจจุบันใน Terminal เพื่อตรวจสอบ
            if it % 50 == 0:
                print(f"Iteration {it} | Current Mutation Rate: {current_mutation_rate:.3f}")

        return time.time() - start_time
    
    def run_aco(self):
        """อัลกอริทึม ACO ฉบับปรับปรุงเพื่อลด Congestion และ HPWL"""
        start_time = time.time()
        movable_mods = self.chip.get_movable_modules()
        pheromone_map = np.ones(CONG_GRID) 
        
        # ขนาดของแต่ละช่อง Grid
        cell_w = self.chip.width / CONG_GRID[1]
        cell_h = self.chip.height / CONG_GRID[0]
        
        for it in range(MAX_ITER):
            # 1. การวางตำแหน่งมดพร้อม Jitter
            current_positions = [] # เก็บ grid index ที่มดเลือก
            for m in movable_mods:
                probs = pheromone_map.flatten() / pheromone_map.sum()
                flat_idx = np.random.choice(range(pheromone_map.size), p=probs)
                r, c = np.unravel_index(flat_idx, CONG_GRID)
                current_positions.append((r, c))
                
                # เพิ่ม Jitter เพื่อไม่ให้ซ้อนทับกันที่จุด (0,0) ของ Grid
                jitter_x = random.uniform(0, max(0, cell_w - m.width))
                jitter_y = random.uniform(0, max(0, cell_h - m.height))
                
                new_x = (c * cell_w) + jitter_x
                new_y = (r * cell_h) + jitter_y
                m.set_position(new_x, new_y)
            
            # 2. ประเมินผลรอบปัจจุบัน
            res = evaluate_placement(self.chip, grid_size=CONG_GRID, alpha=ALPHA, beta=BETA)
            
            # 3. Dynamic Evaporation (ระเหยน้อยลงเมื่อเวลาผ่านไป)
            rho = 0.1 + (0.4 * (1 - it/MAX_ITER)) # จาก 0.5 ลดลงเหลือ 0.1
            pheromone_map *= (1 - rho)
            
            # 4. Localized Update: เพิ่มฟีโรโมนเฉพาะจุดที่ใช้วางโมดูล
            reward = (1.0 / (res['total_cost'] + 1e-6))
            for r, c in current_positions:
                # ยิ่ง Cost ต่ำ (Reward สูง) Grid นั้นจะยิ่งน่าสนใจในรอบถัดไป
                pheromone_map[r, c] += reward 
                
            # (Optional) ลงโทษ Grid ที่มีความแออัดสูง (Congestion Punishment)
            # if res['max_congestion'] > 10.0:
            #     pheromone_map *= 0.95 

        return time.time() - start_time

def print_table_i(results):
    """ฟังก์ชันแสดงผลตารางเปรียบเทียบ GA และ ACO"""
    algos = list(results.keys())
    header = f"{'Metric':<20} | " + " | ".join([f"{a:<15}" for a in algos])
    separator = "-" * len(header)
    print("\n" + separator)
    print("TABLE I. COMPARISON OF GA AND ACO ON BIGBLUE1")
    print(separator)
    print(header)
    print(separator)
    
    metrics = [
        ('Best Cost', 'total_cost'),
        ('HPWL', 'hpwl'),
        ('Avg. Congestion', 'avg_congestion'),
        ('Max Congestion', 'max_congestion'),
        ('Overflow Ratio', 'overflow_ratio')
    ]
    
    for label, key in metrics:
        row = f"{label:<20} | "
        for algo in algos:
            val = results[algo][key]
            row += f"{val:<15.6f} | " if isinstance(val, float) else f"{val:<15} | "
        print(row)
        
    time_row = f"{'Time (s)':<20} | "
    for algo in algos:
        time_row += f"{results[algo]['time']:<15.2f} | "
    print(time_row)
    print(separator)

def main():
    print("🚀 กำลังเริ่มการทดลองสำหรับ GA และ ACO...")
    chip_base = load_ucla_benchmark(NODES_FILE, NETS_FILE)
    
    algorithms = ['GA', 'ACO']
    final_results = {}

    for algo in algorithms:
        print(f"กำลังรัน {algo}...")
        current_chip = copy.deepcopy(chip_base)
        experiment = PlacementExperiment(current_chip)
        
        exec_time = 0
        if algo == 'GA': 
            exec_time = experiment.run_ga()
        elif algo == 'ACO': 
            exec_time = experiment.run_aco()
        
        metrics = evaluate_placement(current_chip, grid_size=CONG_GRID, alpha=ALPHA, beta=BETA)
        metrics['time'] = exec_time
        final_results[algo] = metrics
        print(f"✅ {algo} รันเสร็จสิ้น")

    print_table_i(final_results)

if __name__ == "__main__":
    main()