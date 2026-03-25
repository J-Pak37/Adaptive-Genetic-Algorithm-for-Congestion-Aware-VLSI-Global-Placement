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
ALPHA = 0.9          # น้ำหนัก HPWL [cite: 1012]
BETA = 1e-5          # น้ำหนัก Congestion [cite: 1013]
MAX_ITER = 200       # จำนวน Iteration ตามเปเปอร์ 200 [cite: 1007, 1030]
CONG_GRID = (32, 32) # ขนาด Grid สำหรับความแออัด [cite: 988, 1031]

# --- เส้นทางไฟล์ (อิงตามที่คุณระบุ) ---
DATA_DIR = r"C:\Users\pakde\OneDrive\เดสก์ท็อป\VLSI_Placement_Optimization-Develop\data\ispd2005_benchmarks"
NODES_FILE = os.path.join(DATA_DIR, "bigblue1.inf.nodes")
NETS_FILE = os.path.join(DATA_DIR, "bigblue1.nets")

def calculate_overlap_penalty(chip):
    """คำนวณบทลงโทษหากโมดูลกระจุกตัวอยู่ที่จุด (0,0) มากเกินไป"""
    movable = chip.get_movable_modules()
    zero_count = sum(1 for m in movable if m.x < 1.0 and m.y < 1.0)
    # หากโมดูลมากกว่า 10% อยู่ที่จุด (0,0) ให้ลงโทษหนักๆ
    if zero_count > len(movable) * 0.1:
        return 1.0 # ค่า Cost สูงสุด
    return 0.0

class PlacementExperiment:
    def __init__(self, chip: Chip):
        self.chip = chip

    def run_sa(self):
        """อัลกอริทึม SA ฉบับปรับปรุงเพื่อความเร็ว (Batch Processing)"""
        start_time = time.time()
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
            
        return time.time() - start_time

    def run_sho(self):
        """อัลกอริทึม Spotted Hyena Optimizer (SHO) [cite: 994]"""
        start_time = time.time()
        movable_mods = self.chip.get_movable_modules()
        num_modules = len(movable_mods)
        pop_size = 10  # จำนวนกลุ่มประชากรไฮีนา ปกติ 10
        
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
            
        return time.time() - start_time

    def run_woa(self):
        """อัลกอริทึม Whale Optimization Algorithm (WOA) [cite: 1001]"""
        start_time = time.time()
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

        return time.time() - start_time

def print_table_i(results):
    """ฟังก์ชันแสดงผลตารางเปรียบเทียบตาม Table I ในเปเปอร์ """
    header = f"{'Metric':<20} | {'SA':<15} | {'SHO':<15} | {'WOA':<15}"
    separator = "-" * len(header)
    print("\n" + separator)
    print("TABLE I. COMPARISON OF SA, SHO, AND WOA ON BIGBLUE1")
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
        for algo in ['SA', 'SHO', 'WOA']:
            val = results[algo][key]
            row += f"{val:<15.6f} | " if isinstance(val, float) else f"{val:<15} | "
        print(row)
        
    # เพิ่มบรรทัด Time
    time_row = f"{'Time (s)':<20} | "
    for algo in ['SA', 'SHO', 'WOA']:
        time_row += f"{results[algo]['time']:<15.2f} | "
    print(time_row)
    print(separator)

def main():
    print("🚀 กำลังเริ่มการทดลอง...")
    
    # 1. โหลดข้อมูล Benchmark 
    chip_base = load_ucla_benchmark(NODES_FILE, NETS_FILE)
    
    algorithms = ['SA', 'SHO', 'WOA']
    final_results = {}

    for algo in algorithms:
        print(f"กำลังรัน {algo}...")
        current_chip = copy.deepcopy(chip_base)
        experiment = PlacementExperiment(current_chip)
        
        # 2. รันอัลกอริทึมและจับเวลา [cite: 1053]
        exec_time = 0
        if algo == 'SA': exec_time = experiment.run_sa()
        elif algo == 'SHO': exec_time = experiment.run_sho()
        elif algo == 'WOA': exec_time = experiment.run_woa()
        
        # 3. ประเมินผลผ่าน Evaluator [cite: 1021]
        metrics = evaluate_placement(current_chip, grid_size=CONG_GRID, alpha=ALPHA, beta=BETA)
        metrics['time'] = exec_time
        final_results[algo] = metrics

    # 4. แสดงผลตาราง 
    print_table_i(final_results)

if __name__ == "__main__":
    main()