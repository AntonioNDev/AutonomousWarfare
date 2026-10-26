import yaml

# load configuations
with open("settings.yaml", "r") as settings:
    settings = yaml.safe_load(settings)

INVENTORY = settings["inventory"]

# Inventory logic
class Inventory:
    def __init__(self, slots=INVENTORY["slots"]):
        self.slots = [None] * slots # Initialize N empty Slots

    # Add item in the inventory
    def add(self, item, qty=1):
        for slot in self.slots:
            if slot and slot['item'] == item:
                slot['qty'] += 1
                return True
        for i, slot in enumerate(self.slots):
            if slot is None:
                self.slots[i] = {"item": item, "qty": qty}
                return True
        
        return False
    
    # Remove item from the inventory
    def remove(self, item, qty=1):
        for i, slot in enumerate(self.slots):
            if slot and slot['item'] == item:
                slot['qty'] -= qty
                if slot['qty'] <= 0:
                    self.slots[i] = None
                return True
        return False
    
    def count(self, item):
        for slot in self.slots:
            if slot and slot["item"] == item:
                return slot["qty"]
        return 0

    def is_full(self):
        return all(s is not None for s in self.slots)

    def __repr__(self):
        return str([s for s in self.slots if s])