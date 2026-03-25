import os
import sys
import re
sys.path.append('.')
from chip import Chip

def read_nodes_file(filepath):
    """
    อ่านไฟล์ .nodes 
    # NodeName  Width  Height  (terminal)
    M1          10     10
    M2          5      5
    VDD         1      1       terminal
 
    Returns:
        dict: {module_name: {width, height, is_terminal}}
    """
    modules = {}
    # เผื่อใช้
    num_nodes = 0
    num_terminals = 0
    
    print(f"📖 อ่านไฟล์: {filepath}")
    
    with open(filepath, 'r') as f:
        for line in f:
            line = line.strip()
            
            # ข้ามบรรทัดว่าง หรือ comment
            if not line or line.startswith('#'):continue
            if line.startswith('UCLA'):continue
            if 'NumNodes' in line or 'NumTerminals' in line:
                '''match = re.search(r'NumNodes\s*:\s*(\d+)', line)
                if match:
                    num_nodes = int(match.group(1))
                match = re.search(r'NumTerminals\s*:\s*(\d+)', line)
                if match:
                    num_terminals = int(match.group(1))'''
                continue
            
            # อ่านข้อมูลโมดูล
            parts = line.split()
            
            if len(parts) >= 3:
                name = parts[0]
                width = float(parts[1])
                height = float(parts[2])
                
                # ตรวจสอบว่าเป็น terminal หรือไม่
                is_terminal = False
                if len(parts) >= 4 and 'terminal' in parts[3].lower():
                    is_terminal = True
                
                modules[name] = {
                    'width': width,
                    'height': height,
                    'is_terminal': is_terminal
                }
    
    print(f"  ✅ อ่านได้ {len(modules)} โมดูล")
    return modules

def read_nets_file(filepath):
    """
    อ่านไฟล์ .nets รูปแบบ UCLA

    NetDegree : 7   n0
        o211278  O : -0.500000  2.000000
        o206457  I : -3.500000  -5.000000
        o121     I : -5.000000  -1.000000

    Returns:
        list: [
                {
                'name': 'n0',
                'modules': ['o211278', 'o206457', 'o121'],
                'pins': [{'module': 'o211278', 'type': 'O', 'offset_x': -0.5, 'offset_y': 2.0},...]
            },
            ...
        ]
    """
    nets = []
    current_net = None
    net_count = 0

    print(f"📖 อ่านไฟล์: {filepath}")
    
    with open(filepath, 'r') as f:
        for line in f:
            line = line.strip()
            
            if not line or line.startswith('#'): continue
            if line.startswith('UCLA'): continue
            if 'NumNets' in line or 'NumPins' in line: continue


            # เจอ NetDegree = เริ่ม net ใหม่
            if line.startswith('NetDegree'):
                # เก็บ net เดิมก่อน
                if current_net is not None:
                    nets.append(current_net)
                
                # แยกข้อมูล NetDegree
                # รูปแบบ: NetDegree : 7   n0
                parts = line.split()
                degree = 0
                net_name = None

                # หา degree เผื่อใช้
                for i, part in enumerate(parts):
                    if part == ':' and i + 1 < len(parts):
                        try:
                            degree = int(parts[i + 1])
                        except ValueError:
                            pass

                # หา net name (ถ้ามี)
                if len(parts) >= 4:
                    net_name = parts[-1]
                
                if net_name is None:
                    net_count += 1
                    net_name = f"n{net_count}"

                current_net = {
                    'name': net_name,
                    'modules': [],
                    'pins': []
                }

             # บรรทัดนี้คือ pin ของ net
            elif current_net is not None:
                parts = line.split()
                
                if len(parts) >= 2:
                    module_name = parts[0]
                    pin_type = parts[1]  # O (output) หรือ I (input)
                    
                    # offset 
                    offset_x = 0.0
                    offset_y = 0.0
                    
                    if len(parts) >= 5:
                        try:
                            offset_x = float(parts[3])
                            offset_y = float(parts[4])
                        except ValueError:
                            pass
                    
                    # เพิ่มเข้า net
                    if module_name not in current_net['modules']:
                        current_net['modules'].append(module_name)
                    
                    current_net['pins'].append({
                        'module': module_name,
                        'type': pin_type,
                        'offset_x': offset_x,
                        'offset_y': offset_y
                    })
        
        # เก็บ net สุดท้าย
        if current_net is not None:
            nets.append(current_net)
    
    print(f"  ✅ อ่านได้ {len(nets)} nets")
    
    return nets

def read_pl_file(filepath):
    """
    อ่านไฟล์ .pl รูปแบบ UCLA
 
    o0    0       0       : N
    o1    100     200     : N
    o2    50      80      : N  /FIXED
 
    Returns:
        dict: {
            module_name: {
                x: float,
                y: float,
                orientation: str,
                is_fixed: bool
            }
        }
    """
    positions = {}
    
    print(f"📖 อ่านไฟล์: {filepath}")
    
    with open(filepath, 'r') as f:
        for line in f:
            line = line.strip()
            
            if not line or line.startswith('#'):continue
            if line.startswith('UCLA'):continue
            
            parts = line.split()
            
            if len(parts) >= 5:
                name = parts[0]
                
                try:
                    x = float(parts[1])
                    y = float(parts[2])
                except ValueError:
                    continue
                
                # Orientation (N, S, E, W, FN, FS, FE, FW)
                orientation = 'N'
                if len(parts) >= 5:
                    orientation = parts[4]
                
                # ตรวจสอบ /FIXED
                is_fixed = False
                if len(parts) >= 6:
                    if '/FIXED' in parts[5].upper():
                        is_fixed = True
                
                positions[name] = {
                    'x': x,
                    'y': y,
                    'orientation': orientation,
                    'is_fixed': is_fixed
                }
    
    print(f"  ✅ อ่านได้ {len(positions)} ตำแหน่ง")
    
    return positions

def load_ucla_benchmark(nodes_file, nets_file, pl_file=None, chip_width=None, chip_height=None):
    """
    อ่าน UCLA benchmark ทั้งหมด แล้วสร้าง Chip object
    
    Args:
        nodes_file: path ของไฟล์ .nodes
        nets_file: path ของไฟล์ .nets
        pl_file: path ของไฟล์ .pl (optional)
        chip_width: ความกว้างของชิป (ถ้าไม่ระบุจะคำนวณจาก placement)
        chip_height: ความสูงของชิป
    
    Returns:
        Chip object
    """
    
    print("\n" + "=" * 60)
    print("กำลังโหลด UCLA Benchmark")
    print("=" * 60)
    
    # 1. อ่านไฟล์ .nodes, .nets, .pl
    modules_data = read_nodes_file(nodes_file)
    nets_data = read_nets_file(nets_file)
    positions = {}
    if pl_file and os.path.exists(pl_file):
        positions = read_pl_file(pl_file)
    else:
        print("ไม่มีไฟล์ .pl")
    
    # 2. คำนวณขนาดชิปถ้าไม่ระบุ
    if chip_width is None or chip_height is None:
        if positions:
            # คำนวณจากตำแหน่งโมดูล
            max_x = max(pos['x'] + modules_data.get(name, {}).get('width', 0) 
                       for name, pos in positions.items() if name in modules_data)
            max_y = max(pos['y'] + modules_data.get(name, {}).get('height', 0)
                       for name, pos in positions.items() if name in modules_data)
            
            chip_width = max_x * 1.1   # เผื่อขอบ 10%
            chip_height = max_y * 1.1
            
            print(f"  📏 คำนวณขนาดชิป: {chip_width:.0f} x {chip_height:.0f}")
        else:
            # ใช้ค่า default
            chip_width = 10000
            chip_height = 10000
            print(f"  📏 ใช้ขนาดชิป default: {chip_width:.0f} x {chip_height:.0f}")
    
    # 3. สร้าง Chip
    print(f"\n  สร้าง Chip object...")
    chip = Chip(chip_width, chip_height)

    # 4. เพิ่มโมดูลทั้งหมด
    print(f"    กำลังเพิ่มโมดูล...")
    module_count = 0
    for name, data in modules_data.items():
        chip.add_module(
            name=name,
            width=data['width'],
            height=data['height'],
            is_fixed=data['is_terminal']
        )
        
        # ถ้ามีตำแหน่ง 
        if name in positions:
            chip.get_module(name).set_position(
                positions[name]['x'],
                positions[name]['y']
            )
            
            # ถ้ามี /FIXED flag ก็ตั้งเป็น fixed
            if positions[name].get('is_fixed', False):
                chip.get_module(name).is_fixed = True
        
        module_count += 1
        
        # แสดง progress ทุกๆ 10000 โมดูล
        if module_count % 10000 == 0:
            print(f"    ... {module_count}/{len(modules_data)} โมดูล")
    
    print(f"  ✅ เพิ่มโมดูล {len(modules_data)} ตัวเรียบร้อย")

    # 5. เพิ่ม nets ทั้งหมด
    print(f"   กำลังเพิ่ม nets...")
    net_count = 0
    for net_data in nets_data:
        chip.add_net(net_data['name'], net_data['modules'])

        net_count += 1
        
        # แสดง progress ทุกๆ 10000 nets
        if net_count % 10000 == 0:
            print(f"    ... {net_count}/{len(nets_data)} nets")
    
    print(f"  ✅ เพิ่ม nets {len(nets_data)} ตัวเรียบร้อย")
    
    print(f"\n  ✅ สร้างเสร็จ: {chip}")
    print("=" * 60)
    
    return chip