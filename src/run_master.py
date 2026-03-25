import os
import sys
import time
import copy
import csv
import random
import numpy as np

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__))))
from parser import load_ucla_benchmark
from evaluator import evaluate_placement
from chip import Chip

# --- 1. การตั้งค่ามาตรฐาน ---
ALPHA = 0.9          
BETA = 1e-5          
MAX_ITER = 200       
CONG_GRID = (32, 32) 
RUNS_PER_ALGO = 3    # จำนวนรอบที่ต้องการรันเพื่อหาค่าเฉลี่ย

# --- 2. ตั้งค่าไฟล์ Benchmark (ใส่ 2 วงจร) ---
DATA_DIR = r"C:\Users\pakde\OneDrive\เดสก์ท็อป\VLSI_Placement_Optimization-Develop\data\ispd2005_benchmarks"
BENCHMARKS = ["adaptec1.inf", "bigblue1.inf"] # ใช้ .inf ตามที่คุณโหลดมา
ALGORITHMS = ['SA', 'SHO', 'WOA', 'GA', 'ACO']

def calculate_overlap_penalty(chip):
    # ก๊อปปี้ฟังก์ชันนี้จากโค้ดเดิมของคุณมาวางได้เลยครับ
    movable = chip.get_movable_modules()
    zero_count = sum(1 for m in movable if m.x < 1.0 and m.y < 1.0)
    # หากโมดูลมากกว่า 10% อยู่ที่จุด (0,0) ให้ลงโทษหนักๆ
    if zero_count > len(movable) * 0.1:
        return 1.0 # ค่า Cost สูงสุด
    return 0.0

# --- 3. รวมทุกอัลกอริทึมไว้ใน Class เดียว ---
class PlacementExperiment:
    def __init__(self, chip: Chip):
        self.chip = chip

    def run_sa(self):
        start_time = time.time()
        history_costs = [] # สร้าง List เก็บค่า Cost ทุกรอบ
        movable_mods = self.chip.get_movable_modules()
        
        temp = 1000.0
        cooling_rate = 0.95
        
        # เก็บคำตอบที่ดีที่สุด
        current_res = evaluate_placement(self.chip, grid_size=CONG_GRID, alpha=ALPHA, beta=BETA)
        current_cost = current_res['total_cost']
        
        for it in range(MAX_ITER):
            # 1. เก็บตำแหน่งเก่าไว้เผื่อกรณีไม่ยอมรับคำตอบ
            old_positions = [(m.x, m.y) for m in movable_mods]
            
            # 2. Perturb: ย้ายโมดูล "ทั้งหมด" พร้อมกันในคราวเดียว
            for mod in movable_mods:
                mod.set_position(random.uniform(0, self.chip.width - mod.width), 
                                 random.uniform(0, self.chip.height - mod.height))
            
            # 3. วัดผลครั้งเดียวต่อ 1 Iteration (ลดเวลาประมวลผลมหาศาล)
            new_res = evaluate_placement(self.chip, grid_size=CONG_GRID, alpha=ALPHA, beta=BETA)
            
            new_cost = new_res['total_cost']
            delta_cost = new_cost - current_cost
            
            # 4. Acceptance Criteria [cite: 992]
            if delta_cost < 0 or random.random() < np.exp(-delta_cost / temp):
                current_cost = new_cost
            else:
                # ถ้าไม่ยอมรับ ให้ย้ายโมดูลทั้งหมดกลับที่เดิม
                for idx, mod in enumerate(movable_mods):
                    mod.set_position(old_positions[idx][0], old_positions[idx][1])
            
            temp *= cooling_rate
            history_costs.append(current_cost)
            
        return time.time() - start_time, history_costs

    def run_sho(self):
        start_time = time.time()
        history_costs = []
        movable_mods = self.chip.get_movable_modules()
        num_modules = len(movable_mods)
        pop_size = 10  # จำนวนกลุ่มประชากรไฮีนา ปกติ 10.
        
        
        # 1. Initialization: สร้างกลุ่มประชากรเริ่มต้น
        population = []
        for _ in range(pop_size):
            pos = np.array([[random.uniform(0, self.chip.width - m.width), 
                             random.uniform(0, self.chip.height - m.height)] for m in movable_mods])
            population.append(pos)
        
        best_pos = None
        min_cost = float('inf')

        # วนลูปตามจำนวน Iteration [cite: 1007, 1030]
        for it in range(MAX_ITER):
            # 2. Evaluation: หาคำตอบที่ดีที่สุดในฝูง
            for i in range(pop_size):
                # อัปเดตตำแหน่งลงชิปชั่วคราวเพื่อวัดผล
                for idx, m in enumerate(movable_mods):
                    m.set_position(population[i][idx][0], population[i][idx][1])
                
                res = evaluate_placement(self.chip, grid_size=CONG_GRID, alpha=ALPHA, beta=BETA)
                
                # เพิ่มบทลงโทษการซ้อนทับ (Manual Overlap Check)
                penalty = calculate_overlap_penalty(self.chip)
                current_total_cost = res['total_cost'] + penalty

                # ป้องกันค่า 0 ที่ไม่สมจริง
                if current_total_cost < min_cost and res['hpwl'] > 0:
                    min_cost = current_total_cost
                    best_pos = copy.deepcopy(population[i])

            # 3. Update Positions: ขั้นตอนการล่า (Encircling, Hunting, Attacking) [cite: 997-999]
            h = 1 - (it * (1 / MAX_ITER)) # ค่า h ลดลงจาก 1 ไป 0 [cite: 998]
            for i in range(pop_size):
                r1, r2 = random.random(), random.random()
                B = 2 * r1 # Coefficient B [cite: 992]
                E = 2 * h * r2 - h # Coefficient E [cite: 993]
                
                # Encircling & Attacking logic [cite: 997, 999]
                D_h = np.abs(B * best_pos - population[i])
                population[i] = best_pos - E * D_h
                
                # จำกัดให้อยู่ในขอบเขตชิป
                for idx, m in enumerate(movable_mods):
                    population[i][idx][0] = np.clip(population[i][idx][0], 0, self.chip.width - m.width)
                    population[i][idx][1] = np.clip(population[i][idx][1], 0, self.chip.height - m.height)

        # ตั้งค่าตำแหน่งที่ดีที่สุดกลับสู่ชิปหลัก
        for idx, m in enumerate(movable_mods):
            m.set_position(best_pos[idx][0], best_pos[idx][1])
            history_costs.append(res['total_cost'])

        return time.time() - start_time, history_costs

    def run_woa(self):
        start_time = time.time()
        history_costs = []
        movable_mods = self.chip.get_movable_modules()
        pop_size = 10 # จำนวนกลุ่มประชากรวาฬ ปกติ 10
        
        # 1. Initialization
        population = []
        for _ in range(pop_size):
            pos = np.array([[random.uniform(0, self.chip.width - m.width), 
                             random.uniform(0, self.chip.height - m.height)] for m in movable_mods])
            population.append(pos)
            
        best_pos = None
        min_cost = float('inf')

        for it in range(MAX_ITER):
            # 2. Evaluation
            for i in range(pop_size):
                for idx, m in enumerate(movable_mods):
                    m.set_position(population[i][idx][0], population[i][idx][1])
                
               # --- ส่วนที่ต้องแก้ไขใน loop ของ SHO และ WOA ---
                res = evaluate_placement(self.chip, grid_size=CONG_GRID, alpha=ALPHA, beta=BETA)
                
                # เพิ่มบทลงโทษการซ้อนทับ (Manual Overlap Check)
                penalty = calculate_overlap_penalty(self.chip)
                current_total_cost = res['total_cost'] + penalty
                
                # ป้องกันค่า 0 ที่ไม่สมจริง
                if current_total_cost < min_cost and res['hpwl'] > 0:
                    min_cost = current_total_cost
                    best_pos = copy.deepcopy(population[i])

            # 3. Update Positions: Bubble-net hunting behavior [cite: 1001]
            a = 1 - it * (1 / MAX_ITER) # ค่า a ลดลงจาก 2 ไป 0 [cite: 1006]
            for i in range(pop_size):
                r = random.random()
                A = 2 * a * r - a
                C = 2 * r
                l = random.uniform(-1, 1)
                p = random.random()
                
                if p < 0.5:
                    if np.abs(A) < 1:
                        # Encircling: ล้อมรอบเป้าหมาย [cite: 1002-1003]
                        D = np.abs(C * best_pos - population[i])
                        population[i] = best_pos - A * D
                    else:
                        # Search for prey: สุ่มกระจายตัว
                        rand_idx = random.randint(0, pop_size - 1)
                        D = np.abs(C * population[rand_idx] - population[i])
                        population[i] = population[rand_idx] - A * D
                else:
                    # Spiral updating position: เคลื่อนที่แบบเกลียว [cite: 1004-1005]
                    distance_to_best = np.abs(best_pos - population[i])
                    # สมการตามเปเปอร์: distance * e^(bl) * cos(2*pi*l) + best_pos
                    population[i] = distance_to_best * np.exp(1 * l) * np.cos(2 * np.pi * l) + best_pos

                # จำกัดให้อยู่ในขอบเขตชิป
                for idx, m in enumerate(movable_mods):
                    population[i][idx][0] = np.clip(population[i][idx][0], 0, self.chip.width - m.width)
                    population[i][idx][1] = np.clip(population[i][idx][1], 0, self.chip.height - m.height)

        for idx, m in enumerate(movable_mods):
            m.set_position(best_pos[idx][0], best_pos[idx][1])
            history_costs.append(res['total_cost'])

        return time.time() - start_time, history_costs

    def run_ga(self):
        start_time = time.time()
        history_costs = []
        movable_mods = self.chip.get_movable_modules()
        pop_size = 10 # ลดประชากรเพื่อเทส ปกติ 10
        
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
            
            # --- 1. เก็บคะแนนที่ดีที่สุดของรอบนี้ลง History ---
            best_cost_this_iter = min(costs)
            history_costs.append(best_cost_this_iter)
            
            # --- 2. หาพ่อแม่ที่ดีที่สุด 2 ตัว ---
            best_indices = np.argsort(costs)[:2]
            
            # (Elitism) คัดลอกพ่อแม่ที่ดีที่สุดเก็บไว้ก่อน
            best_p1 = np.copy(population[best_indices[0]])
            best_p2 = np.copy(population[best_indices[1]])
            
            # บังคับใส่กลับเข้าไปในตำแหน่งที่ 0 และ 1 เพื่อไม่ให้หายไปไหน
            population[0] = best_p1
            population[1] = best_p2
            
            # --- 3. ทำ Crossover สำหรับลูกตัวที่เหลือ (ตำแหน่ง 2 ถึง 9) ---
            for i in range(2, pop_size):
                mask = np.random.rand(len(movable_mods), 2) > 0.5
                population[i] = np.where(mask, best_p1, best_p2)
                
                # --- ใช้ Dynamic Mutation Rate ---
                if random.random() < current_mutation_rate:
                    m_idx = random.randint(0, len(movable_mods)-1)
                    # สุ่มย้ายโมดูลไปยังตำแหน่งใหม่
                    population[i][m_idx] = [random.uniform(0, self.chip.width - movable_mods[m_idx].width), 
                                            random.uniform(0, self.chip.height - movable_mods[m_idx].height)]
            
            # (Optional) แสดงค่า Rate ปัจจุบันใน Terminal เพื่อตรวจสอบ
            if it % 50 == 0:
                print(f"Iteration {it} | Best Cost: {best_cost_this_iter:.6f} | Mutation Rate: {current_mutation_rate:.3f}")
                
        return time.time() - start_time, history_costs

    def run_aco(self):
        start_time = time.time()
        history_costs = []
        movable_mods = self.chip.get_movable_modules()
        pheromone_map = np.ones(CONG_GRID) 
        
        # ขนาดของแต่ละช่อง Grid
        cell_w = self.chip.width / CONG_GRID[1]
        cell_h = self.chip.height / CONG_GRID[0]
        
        # --- เพิ่มตัวแปรเก็บค่าตำแหน่งที่ดีที่สุด (Best Tracking) ---
        best_overall_cost = float('inf')
        best_positions = []
        
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
            current_cost = res['total_cost']
            
            # --- 3. บันทึกคำตอบที่ดีที่สุด (ป้องกันกราฟแกว่งและไม่สูญเสียคำตอบ) ---
            if current_cost < best_overall_cost:
                best_overall_cost = current_cost
                # บันทึกตำแหน่ง x, y ของทุกโมดูลเก็บไว้
                best_positions = [(m.x, m.y) for m in movable_mods]
            
            # เก็บค่าที่ดีที่สุดลงใน History ทุกรอบ (การย่อหน้าถูกต้องแล้ว)
            history_costs.append(best_overall_cost)
            
            # 4. Dynamic Evaporation (ระเหยน้อยลงเมื่อเวลาผ่านไป)
            rho = 0.1 + (0.4 * (1 - it/MAX_ITER)) # จาก 0.5 ลดลงเหลือ 0.1
            pheromone_map *= (1 - rho)
            
            # 5. Localized Update: เพิ่มฟีโรโมนเฉพาะจุดที่ใช้วางโมดูล
            reward = (1.0 / (current_cost + 1e-6))
            for r, c in current_positions:
                pheromone_map[r, c] += reward 
                
            # (Optional) Print เช็คสถานะ
            if it % 50 == 0:
                print(f"Iteration {it} | Best Cost: {best_overall_cost:.6f}")
                
        # --- 6. ก่อนจบลูป ให้จัดวางโมดูลกลับไปยังตำแหน่งที่ดีที่สุดที่เคยทำได้ ---
        if best_positions:
            for idx, m in enumerate(movable_mods):
                m.set_position(best_positions[idx][0], best_positions[idx][1])

        return time.time() - start_time, history_costs

# --- 4. ระบบ Auto-Batch (ไม่ต้องแก้ส่วนนี้) ---
def main():
    print("🚀 เริ่มต้นระบบ Auto-Batch Master Run...")
    
    with open('convergence_history_final.csv', 'w', newline='') as f_conv, \
         open('final_statistical_results_final.csv', 'w', newline='') as f_stat:
        
        conv_writer = csv.writer(f_conv)
        stat_writer = csv.writer(f_stat)
        
        conv_writer.writerow(['Benchmark', 'Algorithm', 'Run'] + [f'Iter_{i}' for i in range(MAX_ITER)])

        stat_writer.writerow([
            'Benchmark', 'Algorithm', 
            'Best_Cost', 'Mean_Cost', 'Std_Cost', 
            'Mean_HPWL', 'Mean_Avg_Cong', 'Mean_Max_Cong', 'Mean_Overflow', 'Avg_Time'
        ])

        for bench in BENCHMARKS:
            print(f"\n======================================")
            print(f"กำลังโหลดวงจร: {bench}...")
            nodes_file = os.path.join(DATA_DIR, f"{bench}.nodes")
            nets_file = os.path.join(DATA_DIR, f"{bench[:-4]}.nets") # ตัด .inf ออกสำหรับชื่อไฟล์ nets
            
            chip_base = load_ucla_benchmark(nodes_file, nets_file)
            
            for algo in ALGORITHMS:
                print(f"--- อัลกอริทึม: {algo} ---")
                algo_costs, algo_hpwls, algo_avg_congs, algo_max_congs, algo_overflows, algo_times = [], [], [], [], [], []
                
                for run_idx in range(RUNS_PER_ALGO):
                    print(f"  > รันรอบที่ {run_idx + 1}/{RUNS_PER_ALGO}...")
                    curr_chip = copy.deepcopy(chip_base)
                    experiment = PlacementExperiment(curr_chip)
                    
                    if algo == 'SA': exec_time, history = experiment.run_sa()
                    elif algo == 'SHO': exec_time, history = experiment.run_sho()
                    elif algo == 'WOA': exec_time, history = experiment.run_woa()
                    elif algo == 'GA': exec_time, history = experiment.run_ga()
                    elif algo == 'ACO': exec_time, history = experiment.run_aco()
                    
                    res = evaluate_placement(curr_chip, grid_size=CONG_GRID, alpha=ALPHA, beta=BETA)
                    
                    algo_costs.append(res['total_cost'])
                    algo_hpwls.append(res['hpwl'])
                    algo_avg_congs.append(res['avg_congestion'])
                    algo_max_congs.append(res['max_congestion'])
                    algo_overflows.append(res['overflow_ratio'])
                    algo_times.append(exec_time)
                    
                    # บันทึกประวัติ Cost เพื่อไปทำกราฟ Convergence ทันที
                    conv_writer.writerow([bench, algo, run_idx + 1] + history)
                
                # บันทึกสถิติ 5 รอบของอัลกอริทึมนี้
                stat_writer.writerow([
                    bench, algo, 
                    np.min(algo_costs), np.mean(algo_costs), np.std(algo_costs),
                    np.mean(algo_hpwls), 
                    np.mean(algo_avg_congs), 
                    np.mean(algo_max_congs), 
                    np.mean(algo_overflows), 
                    np.mean(algo_times)
                ])
                f_conv.flush() 
                f_stat.flush()
                
    print("\n🎉 รันเสร็จสมบูรณ์ 100%! เตรียมเขียนเปเปอร์ได้เลยครับ!")

if __name__ == "__main__":
    main()