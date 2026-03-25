class Module:
    # โมดูล/เซลล์ที่จะวางบนชิป
    def __init__(self, name, width, height):
        self.name = name
        self.x = 0
        self.y = 0
        self.width = width
        self.height = height
        self.is_fixed = False  # เป็น pin ตายตัวหรือเปล่า

    # set ตำแหน่งโมดูล
    def set_position(self, x, y):
        self.x = x
        self.y = y

    # get ตำแหน่งโมดูล
    def get_position(self):
        return (self.x, self.y)
    
    # string แสดงชื่อและตำแหน่งโมดูล
    def __str__(self):
        return f"{self.name} at ({self.x:.1f}, {self.y:.1f})"


class Net:
    # การเชื่อมต่อระหว่างโมดูลหลายๆ ตัว
    def __init__(self, name):
        self.name = name
        self.modules = [] # list ของชื่อโมดูล

    # เพิ่มโมดูลเข้าไปใน List ของ net
    def add_module(self, module_name):
        if module_name not in self.modules:
            self.modules.append(module_name)

    # จำนวนโมดูลที่เชื่อม
    def get_num_modules(self): 
        return len(self.modules)
 
    def __str__(self):
        return f"Net {self.name} connects: {' - '.join(self.modules)}"
    
class Chip:
    # พื้นที่ชิปทั้งหมด

    def __init__(self, width, height):
        self.width = width
        self.height = height
        self.modules = {} # เก็บเป็น dict: {ชื่อ: Module object}
        self.nets = [] # เก็บเป็น list ของ Net objects

    # เพิ่มโมดูลใหม่ลงในชิป {dict}
    def add_module(self, name, width, height, is_fixed=False):
        if name not in self.modules:
            module = Module(name, width, height)
            module.is_fixed = is_fixed
            self.modules[name] = module
    
    # เพิ่ม net ใหม่ลงในชิป [list]
    def add_net(self, net_name, module_list):
        net = Net(net_name)
        for module_name in module_list:
            net.add_module(module_name)
        self.nets.append(net)

    # get โมดูลจากชื่อ คืนค่าเป็น Module object
    def get_module(self, name):
        return self.modules.get(name, None)

    # get net จากชื่อ คืนค่าเป็น Net object
    def get_net(self, net_name):
        for net in self.nets:
            if net.name == net_name:
                return net
        return None

    # get list ของ module ทั้งหมดในชิป
    def get_all_modules(self):
        return list(self.modules.values())

    # get list ของ net ทั้งหมดในชิป
    def get_all_nets(self):
        return self.nets
    
    # get list ของ module ที่ไม่ใช่ fixed (movable modules)
    def get_movable_modules(self):
        return [m for m in self.modules.values() if not m.is_fixed]
    
    def __str__(self):
        return (f"Chip {self.width}x{self.height} | "
                f"{len(self.modules)} modules | "
                f"{len(self.nets)} nets")
