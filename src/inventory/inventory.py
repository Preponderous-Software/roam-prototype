from gameLogging.logger import getLogger
from inventory.inventorySlot import InventorySlot

_logger = getLogger(__name__)


# @author Daniel McCoy Stephenson
class Inventory:
    def __init__(self):
        self.inventorySlots = []
        self.size = 25
        for _ in range(self.size):
            self.inventorySlots.append(InventorySlot())
        self.selectedInventorySlotIndex = 0

    def getInventorySlots(self):
        return self.inventorySlots

    def getNumInventorySlots(self):
        return len(self.inventorySlots)

    def placeIntoFirstAvailableInventorySlot(self, item):
        for inventorySlot in self.inventorySlots:
            if inventorySlot.isEmpty():
                # set the item
                inventorySlot.add(item)
                _logger.debug("item placed in inventory", itemName=item.getName())
                return True
            elif (
                inventorySlot.getContents()[0].getName() == item.getName()
                and inventorySlot.getNumItems() < inventorySlot.getMaxStackSize()
            ):
                # increment the amount
                inventorySlot.add(item)
                _logger.debug("item stacked in inventory", itemName=item.getName())
                return True
        _logger.debug("inventory full", itemName=item.getName())
        return False

    def placeIntoSlot(self, index, item):
        """Place an item into a specific slot.

        Used when restoring a save so items land back in the slot they were
        stored in. Returns False when the index is not a usable slot number or
        the slot cannot accept the item, so the caller can fall back to
        placeIntoFirstAvailableInventorySlot rather than lose the item."""
        if isinstance(index, bool) or not isinstance(index, int):
            return False
        if index < 0 or index >= len(self.inventorySlots):
            return False
        inventorySlot = self.inventorySlots[index]
        if inventorySlot.isEmpty():
            inventorySlot.add(item)
            return True
        if (
            inventorySlot.getContents()[0].getName() == item.getName()
            and inventorySlot.getNumItems() < inventorySlot.getMaxStackSize()
        ):
            inventorySlot.add(item)
            return True
        return False

    def removeByItem(self, item):
        for inventorySlot in self.inventorySlots:
            if inventorySlot.isEmpty():
                continue
            if inventorySlot.getContents()[0].getName() == item.getName():
                if inventorySlot.getNumItems() > 1:
                    inventorySlot.remove(item)
                else:
                    inventorySlot.clear()
                return True
        return False

    def clear(self):
        for inventorySlot in self.inventorySlots:
            inventorySlot.clear()

    def getNumFreeInventorySlots(self):
        count = 0
        for inventorySlot in self.inventorySlots:
            if inventorySlot.isEmpty():
                count += 1
        return count

    def getNumTakenInventorySlots(self):
        return self.getNumInventorySlots() - self.getNumFreeInventorySlots()

    def getNumItems(self):
        count = 0
        for inventorySlot in self.inventorySlots:
            if inventorySlot.isEmpty():
                continue
            count += inventorySlot.getNumItems()
        return count

    def getNumItemsByType(self, itemType):
        count = 0
        for inventorySlot in self.inventorySlots:
            if inventorySlot.isEmpty():
                continue
            item = inventorySlot.getContents()[0]
            if isinstance(item, itemType):
                count += inventorySlot.getNumItems()
        return count

    def getSelectedInventorySlotIndex(self):
        return self.selectedInventorySlotIndex

    def setSelectedInventorySlotIndex(self, index):
        self.selectedInventorySlotIndex = index

    def getItemByIndex(self, index):
        return self.inventorySlots[index].getItem()

    def getSelectedInventorySlot(self):
        return self.inventorySlots[self.selectedInventorySlotIndex]

    def removeSelectedItem(self):
        return self.inventorySlots[self.selectedInventorySlotIndex].pop()

    def mergeIntoSlot(self, sourceSlot, destSlot):
        if sourceSlot.isEmpty() or destSlot.isEmpty():
            return
        sourceName = sourceSlot.getContents()[0].getName()
        destName = destSlot.getContents()[0].getName()
        if sourceName != destName:
            return
        maxStack = destSlot.getMaxStackSize()
        available = maxStack - destSlot.getNumItems()
        toTransfer = min(available, sourceSlot.getNumItems())
        for _ in range(toTransfer):
            destSlot.add(sourceSlot.pop())

    def placeIntoFirstAvailableNonHotbarSlot(self, item):
        for inventorySlot in self.inventorySlots[10:]:
            if inventorySlot.isEmpty():
                inventorySlot.add(item)
                return True
            elif (
                inventorySlot.getContents()[0].getName() == item.getName()
                and inventorySlot.getNumItems() < inventorySlot.getMaxStackSize()
            ):
                inventorySlot.add(item)
                return True
        return False

    def hasAvailableSlotFor(self, entityClass):
        probe = entityClass()
        probeName = probe.getName()
        for inventorySlot in self.inventorySlots:
            if inventorySlot.isEmpty():
                return True
            if (
                inventorySlot.getContents()[0].getName() == probeName
                and inventorySlot.getNumItems() < inventorySlot.getMaxStackSize()
            ):
                return True
        return False

    def getFirstTenInventorySlots(self):
        if len(self.inventorySlots) > 10:
            return self.inventorySlots[:10]
        else:
            return self.inventorySlots
