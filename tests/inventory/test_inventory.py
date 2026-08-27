from src.entity.grass import Grass
from src.entity.stone import Stone
from src.inventory import inventory


def createInventory():
    return inventory.Inventory()


def createGrassEntity():
    return Grass()


def test_initialization():
    inventoryInstance = createInventory()
    assert inventoryInstance.getNumInventorySlots() == 25
    assert inventoryInstance.getNumFreeInventorySlots() == 25
    assert inventoryInstance.getNumTakenInventorySlots() == 0


def test_placeIntoFirstAvailableInventorySlot():
    inventoryInstance = createInventory()
    item = createGrassEntity()
    inventoryInstance.placeIntoFirstAvailableInventorySlot(item)
    assert inventoryInstance.getNumFreeInventorySlots() == 24
    assert inventoryInstance.getNumTakenInventorySlots() == 1
    assert inventoryInstance.getNumItems() == 1
    assert inventoryInstance.getInventorySlots()[0].getContents() == [item]


def test_removeByItem():
    inventoryInstance = createInventory()
    item = createGrassEntity()
    inventoryInstance.placeIntoFirstAvailableInventorySlot(item)
    inventoryInstance.removeByItem(item)
    assert inventoryInstance.getNumFreeInventorySlots() == 25
    assert inventoryInstance.getNumTakenInventorySlots() == 0
    assert inventoryInstance.getNumItems() == 0
    assert inventoryInstance.getInventorySlots()[0].getContents() == []


def test_clear():
    inventoryInstance = createInventory()
    item = createGrassEntity()
    inventoryInstance.placeIntoFirstAvailableInventorySlot(item)
    inventoryInstance.clear()
    assert inventoryInstance.getNumFreeInventorySlots() == 25
    assert inventoryInstance.getNumTakenInventorySlots() == 0
    assert inventoryInstance.getNumItems() == 0
    assert inventoryInstance.getInventorySlots()[0].getContents() == []


def test_getNumFreeInventorySlots():
    inventoryInstance = createInventory()
    for i in range(5 * 20):
        item = createGrassEntity()
        inventoryInstance.placeIntoFirstAvailableInventorySlot(item)
    assert inventoryInstance.getNumFreeInventorySlots() == 20
    assert inventoryInstance.getNumTakenInventorySlots() == 5


def test_getNumTakenInventorySlots():
    inventoryInstance = createInventory()
    for i in range(5 * 20):
        item = createGrassEntity()
        inventoryInstance.placeIntoFirstAvailableInventorySlot(item)
    assert inventoryInstance.getNumTakenInventorySlots() == 5
    assert inventoryInstance.getNumFreeInventorySlots() == 20


def test_getNumItems():
    inventoryInstance = createInventory()
    for i in range(5):
        item = createGrassEntity()
        inventoryInstance.placeIntoFirstAvailableInventorySlot(item)
    assert inventoryInstance.getNumItems() == 5


def test_getNumItemsByType():
    inventoryInstance = createInventory()
    for i in range(5):
        item = createGrassEntity()
        inventoryInstance.placeIntoFirstAvailableInventorySlot(item)
    assert inventoryInstance.getNumItemsByType(Grass) == 5


def test_getSelectedInventorySlotIndex():
    inventoryInstance = createInventory()
    assert inventoryInstance.getSelectedInventorySlotIndex() == 0


def test_setSelectedInventorySlotIndex():
    inventoryInstance = createInventory()
    inventoryInstance.setSelectedInventorySlotIndex(5)
    assert inventoryInstance.getSelectedInventorySlotIndex() == 5


def test_getSelectedInventorySlot():
    inventoryInstance = createInventory()
    assert (
        inventoryInstance.getSelectedInventorySlot()
        == inventoryInstance.getInventorySlots()[0]
    )


def test_removeSelectedItem():
    inventoryInstance = createInventory()
    item = createGrassEntity()
    inventoryInstance.placeIntoFirstAvailableInventorySlot(item)
    inventoryInstance.removeSelectedItem()
    assert inventoryInstance.getNumFreeInventorySlots() == 25
    assert inventoryInstance.getNumTakenInventorySlots() == 0
    assert inventoryInstance.getNumItems() == 0
    assert inventoryInstance.getInventorySlots()[0].getContents() == []


def test_getFirstTenInventorySlots():
    inventoryInstance = createInventory()
    assert (
        inventoryInstance.getFirstTenInventorySlots()
        == inventoryInstance.getInventorySlots()[:10]
    )


def test_mergeIntoSlot_full_merge():
    inventoryInstance = createInventory()
    sourceSlot = inventoryInstance.getInventorySlots()[0]
    destSlot = inventoryInstance.getInventorySlots()[1]
    for i in range(5):
        sourceSlot.add(createGrassEntity())
    for i in range(10):
        destSlot.add(createGrassEntity())
    inventoryInstance.mergeIntoSlot(sourceSlot, destSlot)
    assert sourceSlot.getNumItems() == 0
    assert destSlot.getNumItems() == 15


def test_mergeIntoSlot_dest_full():
    inventoryInstance = createInventory()
    sourceSlot = inventoryInstance.getInventorySlots()[0]
    destSlot = inventoryInstance.getInventorySlots()[1]
    for i in range(5):
        sourceSlot.add(createGrassEntity())
    for i in range(20):
        destSlot.add(createGrassEntity())
    inventoryInstance.mergeIntoSlot(sourceSlot, destSlot)
    assert sourceSlot.getNumItems() == 5
    assert destSlot.getNumItems() == 20


def test_mergeIntoSlot_partial_merge():
    inventoryInstance = createInventory()
    sourceSlot = inventoryInstance.getInventorySlots()[0]
    destSlot = inventoryInstance.getInventorySlots()[1]
    for i in range(10):
        sourceSlot.add(createGrassEntity())
    for i in range(15):
        destSlot.add(createGrassEntity())
    inventoryInstance.mergeIntoSlot(sourceSlot, destSlot)
    assert destSlot.getNumItems() == 20
    assert sourceSlot.getNumItems() == 5


def test_mergeIntoSlot_different_types_no_merge():
    from src.entity.apple import Apple

    inventoryInstance = createInventory()
    sourceSlot = inventoryInstance.getInventorySlots()[0]
    destSlot = inventoryInstance.getInventorySlots()[1]
    for i in range(5):
        sourceSlot.add(createGrassEntity())
    for i in range(5):
        destSlot.add(Apple())
    inventoryInstance.mergeIntoSlot(sourceSlot, destSlot)
    assert sourceSlot.getNumItems() == 5
    assert destSlot.getNumItems() == 5


def test_placeIntoFirstAvailableNonHotbarSlot_empty_inventory():
    inventoryInstance = createInventory()
    item = createGrassEntity()
    result = inventoryInstance.placeIntoFirstAvailableNonHotbarSlot(item)
    assert result is True
    # should be placed in slot 10 (first non-hotbar slot)
    assert inventoryInstance.getInventorySlots()[10].getNumItems() == 1
    # first 10 slots should be empty
    for i in range(10):
        assert inventoryInstance.getInventorySlots()[i].isEmpty()


def test_placeIntoFirstAvailableNonHotbarSlot_stacks_with_matching():
    inventoryInstance = createInventory()
    slot10 = inventoryInstance.getInventorySlots()[10]
    slot10.add(createGrassEntity())
    item = createGrassEntity()
    result = inventoryInstance.placeIntoFirstAvailableNonHotbarSlot(item)
    assert result is True
    assert slot10.getNumItems() == 2


def test_placeIntoFirstAvailableNonHotbarSlot_non_hotbar_full():
    inventoryInstance = createInventory()
    # fill all non-hotbar slots (slots 10-24)
    for i in range(10, 25):
        for j in range(20):
            inventoryInstance.getInventorySlots()[i].add(createGrassEntity())
    item = createGrassEntity()
    result = inventoryInstance.placeIntoFirstAvailableNonHotbarSlot(item)
    assert result is False


def test_hasAvailableSlotFor_empty_inventory():
    inventoryInstance = createInventory()

    # Every slot is empty, so the first one satisfies the request.
    assert inventoryInstance.hasAvailableSlotFor(Grass) is True


def test_hasAvailableSlotFor_matching_stack_with_room():
    inventoryInstance = createInventory()
    slots = inventoryInstance.getInventorySlots()

    # Leave no empty slot: slot 0 holds a single Grass (room to spare, well
    # under the max stack size of 20) and every other slot is filled with a
    # non-matching Stone. The only way a True result can come back is via the
    # matching-stack-with-room branch, not the empty-slot branch.
    slots[0].add(createGrassEntity())
    for slot in slots[1:]:
        slot.add(Stone())

    assert inventoryInstance.hasAvailableSlotFor(Grass) is True


def test_hasAvailableSlotFor_full_inventory_no_match():
    inventoryInstance = createInventory()

    # Occupy every slot with a non-matching item: no empty slot and no Grass
    # stack to add to.
    for slot in inventoryInstance.getInventorySlots():
        slot.add(Stone())

    assert inventoryInstance.hasAvailableSlotFor(Grass) is False


def test_placeIntoSlot_uses_the_requested_slot():
    inventoryInstance = createInventory()
    item = createGrassEntity()

    assert inventoryInstance.placeIntoSlot(7, item) is True
    assert inventoryInstance.getInventorySlots()[7].getContents() == [item]
    assert inventoryInstance.getInventorySlots()[0].isEmpty() is True


def test_placeIntoSlot_stacks_onto_a_matching_item():
    inventoryInstance = createInventory()
    inventoryInstance.placeIntoSlot(4, createGrassEntity())

    assert inventoryInstance.placeIntoSlot(4, createGrassEntity()) is True
    assert inventoryInstance.getInventorySlots()[4].getNumItems() == 2


def test_placeIntoSlot_refuses_a_full_matching_stack():
    inventoryInstance = createInventory()
    slot = inventoryInstance.getInventorySlots()[4]
    for _ in range(slot.getMaxStackSize()):
        slot.add(createGrassEntity())

    assert inventoryInstance.placeIntoSlot(4, createGrassEntity()) is False
    assert slot.getNumItems() == slot.getMaxStackSize()


def test_placeIntoSlot_refuses_a_slot_holding_a_different_item():
    inventoryInstance = createInventory()
    inventoryInstance.placeIntoSlot(2, Stone())

    assert inventoryInstance.placeIntoSlot(2, createGrassEntity()) is False
    assert inventoryInstance.getInventorySlots()[2].getNumItems() == 1


def test_placeIntoSlot_refuses_an_index_outside_the_inventory():
    inventoryInstance = createInventory()

    # A save written when the inventory was larger, or a corrupted index, must
    # not raise and must not wrap around onto an unrelated slot.
    assert inventoryInstance.placeIntoSlot(25, createGrassEntity()) is False
    assert inventoryInstance.placeIntoSlot(-1, createGrassEntity()) is False
    assert inventoryInstance.getNumItems() == 0


def test_placeIntoSlot_refuses_a_non_integer_index():
    inventoryInstance = createInventory()

    # A missing slotIndex arrives as None, and bool is an int subclass, so True
    # would otherwise be accepted as slot 1.
    assert inventoryInstance.placeIntoSlot(None, createGrassEntity()) is False
    assert inventoryInstance.placeIntoSlot(True, createGrassEntity()) is False
    assert inventoryInstance.placeIntoSlot("3", createGrassEntity()) is False
    assert inventoryInstance.getNumItems() == 0
