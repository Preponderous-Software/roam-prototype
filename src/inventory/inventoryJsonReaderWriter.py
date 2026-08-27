import json
import os
from uuid import UUID

import jsonschema
from entity.apple import Apple
from entity.banana import Banana
from entity.bearMeat import BearMeat
from entity.bed import Bed
from entity.campfire import Campfire
from entity.chest import Chest
from entity.chickenMeat import ChickenMeat
from entity.coalOre import CoalOre
from entity.fence import Fence
from entity.food import Food
from entity.goldenLantern import GoldenLantern
from entity.goldOre import GoldOre
from entity.grass import Grass
from entity.ironChest import IronChest
from entity.ironOre import IronOre
from entity.jungleWood import JungleWood
from entity.leaves import Leaves
from entity.living.livingEntity import LivingEntity
from entity.living.livingEntityRegistry import LIVING_ENTITY_TYPES
from entity.matureCrop import MatureCrop
from entity.oakWood import OakWood
from entity.stone import Stone
from entity.stoneBed import StoneBed
from entity.stoneFloor import StoneFloor
from entity.torch import Torch
from entity.wheat import Wheat
from entity.wheatSeed import WheatSeed
from entity.woodFloor import WoodFloor
from entity.youngCrop import YoungCrop
from inventory.inventory import Inventory
from gameLogging.logger import getLogger
from jsonPersistence import readJsonFile, writeJsonAtomically

_logger = getLogger(__name__)

# Entity registries — must be kept in sync with roomJsonReaderWriter.py
# when adding new entity types.

# Simple entity classes that require no special constructor arguments
_SIMPLE_ENTITY_CONSTRUCTORS = {
    "Apple": Apple,
    "Chest": Chest,
    "IronChest": IronChest,
    "CoalOre": CoalOre,
    "GoldOre": GoldOre,
    "Grass": Grass,
    "IronOre": IronOre,
    "JungleWood": JungleWood,
    "Leaves": Leaves,
    "OakWood": OakWood,
    "Stone": Stone,
    "Banana": Banana,
    "ChickenMeat": ChickenMeat,
    "BearMeat": BearMeat,
    "WoodFloor": WoodFloor,
    "Bed": Bed,
    "StoneFloor": StoneFloor,
    "StoneBed": StoneBed,
    "Fence": Fence,
    "Campfire": Campfire,
    "Torch": Torch,
    "GoldenLantern": GoldenLantern,
    "WheatSeed": WheatSeed,
    "Wheat": Wheat,
}

# Food entity classes that have a restorable energy value
_FOOD_ENTITY_CLASSES = {"Apple", "Banana", "ChickenMeat", "BearMeat", "Wheat"}

# Living entity classes that need a tickCreated constructor argument. Sourced
# from the shared registry so picked-up creatures persist without re-listing
# each one here.
_LIVING_ENTITY_CONSTRUCTORS = LIVING_ENTITY_TYPES

# Crop entity classes that need a tickPlanted constructor argument
_CROP_ENTITY_CONSTRUCTORS = {
    "YoungCrop": YoungCrop,
    "MatureCrop": MatureCrop,
}


class InventoryJsonReaderWriter:
    def __init__(self, config):
        self.config = config

    def saveInventory(self, inventory: Inventory, path):
        _logger.info("saving inventory", path=path)
        toReturn = {"inventorySlots": []}
        slotIndex = 0
        for slot in inventory.getInventorySlots():
            slotContents = []
            for entity in slot.getContents():
                entityData = {
                    "entityId": str(entity.getID()),
                    "entityClass": entity.__class__.__name__,
                    "name": entity.getName(),
                    "assetPath": entity.getImagePath(),
                }
                if isinstance(entity, Food):
                    entityData["energy"] = entity.getEnergy()
                if isinstance(entity, LivingEntity):
                    entityData["energy"] = entity.getEnergy()
                    entityData["tickCreated"] = entity.getTickCreated()
                    entityData["tickLastReproduced"] = entity.getTickLastReproduced()
                    entityData["imagePath"] = entity.getImagePath()
                if isinstance(entity, (YoungCrop, MatureCrop)):
                    entityData["tickPlanted"] = entity.getTickPlanted()
                slotContents.append(entityData)
            toReturn["inventorySlots"].append(
                {"slotIndex": slotIndex, "slotContents": slotContents}
            )
            slotIndex += 1

        with open("schemas/inventory.json") as f:
            inventorySchema = json.load(f)
        try:
            jsonschema.validate(toReturn, inventorySchema)
        except jsonschema.exceptions.ValidationError as e:
            _logger.error(
                "inventory validation failed; aborting save to preserve existing file",
                error=str(e),
                path=path,
            )
            return False

        if not os.path.exists(self.config.pathToSaveDirectory):
            os.makedirs(self.config.pathToSaveDirectory)

        writeJsonAtomically(path, toReturn)
        return True

    def loadInventory(self, path):
        _logger.info("loading inventory", path=path)
        inventory = Inventory()
        inventoryJson = readJsonFile(path)
        if inventoryJson is None:
            return inventory
        for slot in inventoryJson["inventorySlots"]:
            slotIndex = slot.get("slotIndex")
            for entityJson in slot["slotContents"]:
                entity = self._createEntityFromJson(entityJson)
                # Restore into the saved slot so the player's arrangement (and
                # therefore the hotbar) survives the round trip. A slot index
                # that no longer fits the inventory falls back to first-available
                # so older saves still load with nothing lost.
                if inventory.placeIntoSlot(slotIndex, entity):
                    continue
                if not inventory.placeIntoFirstAvailableInventorySlot(entity):
                    _logger.error(
                        "failed to restore inventory item: no inventory space available",
                        entityClass=entityJson.get("entityClass"),
                        entityId=entityJson.get("entityId"),
                        slotIndex=slotIndex,
                    )
        return inventory

    def _createEntityFromJson(self, entityJson):
        entityClass = entityJson["entityClass"]

        if entityClass in _LIVING_ENTITY_CONSTRUCTORS:
            return self._createLivingEntity(entityClass, entityJson)

        if entityClass in _CROP_ENTITY_CONSTRUCTORS:
            return self._createCropEntity(entityClass, entityJson)

        if entityClass in _SIMPLE_ENTITY_CONSTRUCTORS:
            return self._createSimpleEntity(entityClass, entityJson)

        raise Exception("Unknown entity class: " + entityClass)

    def _createSimpleEntity(self, entityClass, entityJson):
        constructor = _SIMPLE_ENTITY_CONSTRUCTORS[entityClass]
        entity = constructor()
        entity.setID(UUID(entityJson["entityId"]))
        if entityClass in _FOOD_ENTITY_CLASSES and "energy" in entityJson:
            entity.setEnergy(entityJson["energy"])
        return entity

    def _createLivingEntity(self, entityClass, entityJson):
        constructor = _LIVING_ENTITY_CONSTRUCTORS[entityClass]
        entity = constructor(entityJson["tickCreated"])
        entity.setID(UUID(entityJson["entityId"]))
        entity.setEnergy(entityJson["energy"])
        entity.setTickLastReproduced(entityJson["tickLastReproduced"])
        entity.setImagePath(entityJson["imagePath"])
        return entity

    def _createCropEntity(self, entityClass, entityJson):
        constructor = _CROP_ENTITY_CONSTRUCTORS[entityClass]
        entity = constructor(entityJson["tickPlanted"])
        entity.setID(UUID(entityJson["entityId"]))
        return entity
