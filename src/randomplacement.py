import random
import matplotlib.pyplot as plt
from evaluator import calculate_HPWL  # เรียกใช้ฟังก์ชัน HPWL
from chip import Chip

class RandomPlacement:
    def __init__(self, chip: Chip):
        """
        Initialize the random placement algorithm
        Parameters:
        - chip: Chip object
        """
        self.chip = chip

    def place_randomly(self):
        """
        Perform random placement of movable modules
        Returns:
        - None (positions are updated in the Chip object)
        """
        for module in self.chip.get_movable_modules():
            x = random.uniform(0, self.chip.width - module.width)
            y = random.uniform(0, self.chip.height - module.height)
            module.set_position(x, y)

    def visualize_placement(self):
        """
        Visualize placement of modules and nets
        """
        plt.figure(figsize=(8, 8))
        ax = plt.gca()
        ax.set_xlim(0, self.chip.width)
        ax.set_ylim(0, self.chip.height)
        ax.set_title("VLSI Random Placement Visualization")
        ax.set_xlabel("X-coordinate")
        ax.set_ylabel("Y-coordinate")

        # วาด modules
        for module in self.chip.get_all_modules():
            rect = plt.Rectangle(
                (module.x, module.y),
                module.width,
                module.height,
                fill=True,
                color=(random.random(), random.random(), random.random()),
                alpha=0.5
            )
            ax.add_patch(rect)
            plt.text(module.x + module.width/2,
                     module.y + module.height/2,
                     module.name,
                     ha='center', va='center', fontsize=10, weight='bold')

        # วาด nets
        for net in self.chip.get_all_nets():
            xs, ys = [], []
            for mod_name in net.modules:
                mod = self.chip.get_module(mod_name)
                if mod is not None:
                    xs.append(mod.x + mod.width/2)
                    ys.append(mod.y + mod.height/2)
            if len(xs) >= 2:
                plt.plot(xs, ys, 'k--', linewidth=1)
                mid_x, mid_y = sum(xs)/len(xs), sum(ys)/len(ys)
                hpwl = calculate_HPWL(self.chip, net)
                plt.text(mid_x, mid_y, f'HPWL:{hpwl:.1f}', fontsize=10, color='Maroon')

        plt.grid(True, linestyle='--', alpha=0.3)
        plt.show()

def main():
    # สร้าง Chip object
    chip = Chip(100, 100)
    # เพิ่มโมดูล
    chip.add_module("A", 10, 10)
    chip.add_module("B", 15, 15)
    chip.add_module("C", 20, 20)
    # เพิ่ม nets
    chip.add_net("Net1", ["A", "B"])
    chip.add_net("Net2", ["B", "C"])

    # สุ่มวางโมดูล
    placer = RandomPlacement(chip)
    placer.place_randomly()

    # แสดงตำแหน่งโมดูล
    print("Module Placements:")
    for mod in chip.get_all_modules():
        print(f"{mod.name}: x={mod.x:.2f}, y={mod.y:.2f}")

    # คำนวณ HPWL
    total_hpwl = calculate_HPWL(chip)
    print(f"\nTotal HPWL: {total_hpwl:.2f}")

    # Visualize
    placer.visualize_placement()


if __name__ == "__main__":
    main()
