import numpy as np
from typing import List, Optional
from chip import Chip, Net

def calculate_HPWL(chip: Chip, net: Optional[Net] = None) -> float:
    """
    HPWL calculator (ฟังก์ชันเดียวใช้ได้ 2 โหมด)
    - calculate_HPWL(chip)            -> รวมทุกเน็ต (Total HPWL)
    - calculate_HPWL(chip, net=...)   -> เฉพาะเน็ตเดียว
    """
    def _hpwl_one(n: Net) -> float:
        """คำนวณ HPWL ของ net เดียว"""
        x_positions: List[float] = []
        y_positions: List[float] = []
        
        for name in n.modules:
            mod = chip.modules.get(name)
                
            x, y = mod.get_position()
            x_positions.append(x)
            y_positions.append(y)
        
        # ต้องมีอย่างน้อย 2 modules ที่ถูก place
        if len(x_positions) < 2:
            return 0.0
            
        return (max(x_positions) - min(x_positions)) + (max(y_positions) - min(y_positions))
    # Single net mode
    if net is not None:
        return _hpwl_one(net)

    # Total HPWL mode
    return sum(_hpwl_one(n) for n in chip.get_all_nets())

def calculate_congestion(chip, grid_size=(10, 10)):
    
    rows, cols = grid_size
    
    # สร้างตารางเปล่าๆ (เริ่มต้นทุกช่อง = 0)
    congestion_map = np.zeros((rows, cols))
    
    # คำนวณขนาดของแต่ละช่อง
    cell_width = chip.width / cols   # เช่น 100/10 = 10
    cell_height = chip.height / rows  # เช่น 100/10 = 10
    
    # วนลูปแต่ละ net
    for net in chip.nets:
        
        if net.get_num_modules() < 2:
            continue
        
        # เก็บตำแหน่งของโมดูลทั้งหมดใน net
        x_positions = []
        y_positions = []
        
        for module_name in net.modules:
            module = chip.get_module(module_name)
            if module:
                x_positions.append(module.x)
                y_positions.append(module.y)
        
        if len(x_positions) == 0:
            continue
        
        # หากรอบที่ครอบโมดูลทั้งหมด (bounding box)
        min_x = min(x_positions)
        max_x = max(x_positions)
        min_y = min(y_positions)
        max_y = max(y_positions)
        
        # คำนวณ HPWL และพื้นที่ของ net นี้
        hpwl_net = (max_x - min_x) + (max_y - min_y)
        bbox_width = max_x - min_x
        bbox_height = max_y - min_y
        bbox_area = max(bbox_width * bbox_height, 1e-6)  # หลีกเลี่ยง division by zero
        
        # คำนวณ wire density (RUDY)
        # density = ความยาวสาย / พื้นที่
        wire_density = hpwl_net / bbox_area

        # แปลงตำแหน่งเป็นช่อง grid
        start_col = int(min_x / cell_width)
        end_col = int(max_x / cell_width)
        start_row = int(min_y / cell_height)
        end_row = int(max_y / cell_height)
        
        # จำกัดไม่ให้เกินขอบชิป
        start_col = max(0, min(start_col, cols - 1))
        end_col = max(0, min(end_col, cols - 1))
        start_row = max(0, min(start_row, rows - 1))
        end_row = max(0, min(end_row, rows - 1))
        
        # จำนวนช่องที่สายผ่าน
        num_cells = (end_col - start_col + 1) * (end_row - start_row + 1)
        num_cells = max(num_cells, 1)
        
        # กระจาย density เฉลี่ยในแต่ละช่อง
        density_per_cell = wire_density / num_cells

        # เพิ่มค่า congestion ในช่องที่สายผ่าน
        for r in range(start_row, end_row + 1):     # เดินตามแถว
            for c in range(start_col, end_col + 1): # เดินตามคอลัมน์
                congestion_map[r, c] += density_per_cell
    
    # คำนวณค่าสถิติ
    max_congestion = np.max(congestion_map)
    avg_congestion = np.mean(congestion_map)
    
    # คำนวณ overflow ratio (ช่องที่แออัดเกินค่าเฉลี่ย 2 เท่า)
    overflow_threshold = avg_congestion * 2.0
    overflow_cells = np.sum(congestion_map > overflow_threshold)
    overflow_ratio = overflow_cells / (rows * cols)
    
    return congestion_map, max_congestion, avg_congestion, overflow_ratio

def calculate_congestion_penalty(congestion_map, avg_congestion):
    
    penalty = np.zeros_like(congestion_map)
    
    # ช่องที่ <= average → penalty ตามปกติ
    normal_mask = congestion_map <= avg_congestion
    penalty[normal_mask] = congestion_map[normal_mask]
    
    # ช่องที่ > average → penalty แรงขึ้น (ยกกำลัง 2)
    overflow_mask = congestion_map > avg_congestion
    penalty[overflow_mask] = congestion_map[overflow_mask] ** 2
    
    total_penalty = np.sum(penalty)
    
    return total_penalty

def calculate_cost_function(chip, grid_size=(10, 10), alpha=0.5, beta=0.5):
    """
    Cost = alpha * HPWL_normalized + beta * Congestion_normalized
    - Normalize ให้อยู่ในช่วง [0, 1] เพื่อความยุติธรรม
    - alpha = น้ำหนักของ HPWL (default 0.5)
    - beta = น้ำหนักของ Congestion (default 0.5)
    """
    
    # 1. คำนวณ HPWL
    hpwl = calculate_HPWL(chip)
    
    # 2. คำนวณ Congestion (RUDY)
    cong_map, max_cong, avg_cong, overflow_ratio = calculate_congestion(chip, grid_size)
    
    # 3. คำนวณ congestion penalty (ลงโทษ overflow)
    congestion_penalty = calculate_congestion_penalty(cong_map, avg_cong)
    
    # 4. Normalize ให้อยู่ในช่วง [0, 1]
    # ประมาณค่าสูงสุดที่เป็นไปได้
    # HPWL max ≈ จำนวน nets * (chip_width + chip_height)
    max_possible_hpwl = len(chip.nets) * (chip.width + chip.height)
    if max_possible_hpwl == 0:
        max_possible_hpwl = 1
    
    hpwl_normalized = hpwl / max_possible_hpwl
    
    # Congestion penalty max ≈ (rows * cols * max_cong^2)
    rows, cols = grid_size
    max_possible_congestion = rows * cols * (max_cong ** 2)
    if max_possible_congestion == 0:
        max_possible_congestion = 1
    
    congestion_normalized = congestion_penalty / max_possible_congestion
    
    # 5. คำนวณ Total Cost
    total_cost = alpha * hpwl_normalized + beta * congestion_normalized
    
    return {
        'total_cost': total_cost,
        'hpwl': hpwl,
        'hpwl_normalized': hpwl_normalized,     #HPWL หลัง normalize
        'congestion_penalty': congestion_penalty,   #ค่าโทษ congestion
        'congestion_normalized': congestion_normalized, #Congestion หลัง normalize
        'max_congestion': max_cong,
        'avg_congestion': avg_cong,
        'overflow_ratio': overflow_ratio    #สัดส่วน overflow
    }

def evaluate_placement(chip, grid_size=(10, 10), alpha=0.5, beta=0.5): 
    return calculate_cost_function(chip, grid_size, alpha, beta)