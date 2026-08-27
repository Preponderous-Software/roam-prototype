import json
import os
from uuid import UUID

import jsonschema
from config.config import Config
from entity.apple import Apple
from entity.banana import Banana
from entity.bearMeat import BearMeat
from entity.bed import Bed
from entity.campfire import Campfire
from entity.caveEntrance import CaveEntrance
from entity.caveFloor import CaveFloor
from entity.caveLadder import CaveLadder
from entity.chest import Chest
from entity.chickenMeat import ChickenMeat
from entity.coalOre import CoalOre
from entity.excrement import Excrement
from entity.fence import Fence
from entity.food import Food
from entity.goldenLantern import GoldenLantern
from entity.goldOre import GoldOre
from entity.grass import Grass
from entity.gravestone import Gravestone
from entity.ironChest import IronChest
from entity.ironOre import IronOre
from entity.jungleWood import JungleWood
from entity.leaves import Leaves
from entity.living.livingEntity import LivingEntity
from entity.living.livingEntityRegistry import LIVING_ENTITY_TYPES
from entity.living.npc import Npc
from entity.matureCrop import MatureCrop
from entity.oakWood import OakWood
from entity.stone import Stone
from entity.stoneBed import StoneBed
from entity.stoneFloor import StoneFloor
from entity.storableInventory import StorableInventory
from entity.torch import Torch
from entity.wheat import Wheat
from entity.wheatSeed import WheatSeed
from entity.woodFloor import WoodFloor
from entity.youngCrop import YoungCrop
from rendering.renderer import Renderer
from lib.pyenvlib.grid import Grid
from lib.pyenvlib.location import Location
from gameLogging.logger import getLogger
from jsonPersistence import readJsonFile, writeJsonAtomically

from world.room import Room
from world.tickCounter import TickCounter

_logger = getLogger(__name__)


class RoomJsonReaderWriter:
    def __init__(
        self, gridSize, renderer: Renderer, tickCounter: TickCounter, config: Config
    ):
        self.gridSize = gridSize
        self.renderer = renderer
        self.tickCounter = tickCounter
        self.config = config
        with open("schemas/room.json", encoding="utf-8") as roomSchemaFile:
            self.roomSchema = json.load(roomSchemaFile)
        self.livingEntities = dict()
        self.entityConstructors = {
            "Apple": Apple,
            "CaveEntrance": CaveEntrance,
            "CaveFloor": CaveFloor,
            "CaveLadder": CaveLadder,
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
            "Chest": Chest,
            "IronChest": IronChest,
            "Torch": Torch,
            "GoldenLantern": GoldenLantern,
            "WheatSeed": WheatSeed,
            "Wheat": Wheat,
        }

    def saveRoom(self, room, path):
        _logger.info("saving room", path=path, roomX=room.getX(), roomY=room.getY())
        roomJson = self.generateJsonForRoom(room)
        os.makedirs(self.config.getRoomsDirectory(), exist_ok=True)
        writeJsonAtomically(path, roomJson)

    def loadRoom(self, path):
        _logger.info("loading room", path=path)
        roomJson = readJsonFile(path)
        if roomJson is None:
            return None
        return self.generateRoomFromJson(roomJson)

    def generateJsonForRoom(self, room):
        roomJson = {}
        roomJson["backgroundColor"] = str(room.getBackgroundColor())
        roomJson["x"] = room.getX()
        roomJson["y"] = room.getY()
        roomJson["z"] = room.getZ()
        roomJson["name"] = room.getName()
        roomJson["id"] = str(room.getID())
        roomJson["livingEntityIds"] = [
            str(entityId) for entityId in room.getLivingEntities().keys()
        ]
        roomJson["grid"] = self.generateJsonForGrid(room.getGrid())
        roomJson["creationDate"] = str(room.getCreationDate())

        jsonschema.validate(roomJson, self.roomSchema)
        return roomJson

    def generateJsonForGrid(self, grid):
        gridJson = {}
        gridJson["id"] = str(grid.getID())
        gridJson["columns"] = grid.getColumns()
        gridJson["rows"] = grid.getRows()
        gridJson["locations"] = self.generateJsonForLocations(grid.getLocations())
        return gridJson

    def generateJsonForLocations(self, locations):
        locationsJson = []
        for locationId in locations:
            location = locations[locationId]
            locationsJson.append(self.generateJsonForLocation(location))
        return locationsJson

    def generateJsonForLocation(self, location):
        locationJson = {}
        locationJson["id"] = str(location.getID())
        locationJson["x"] = location.getX()
        locationJson["y"] = location.getY()
        locationJson["entities"] = self.generateJsonForEntities(location.getEntities())
        return locationJson

    def generateJsonForEntities(self, entities):
        entitiesJson = []
        for entityId in entities:
            entity = entities[entityId]
            entitiesJson.append(self.generateJsonForEntity(entity))
        return entitiesJson

    def generateJsonForEntity(self, entity):
        entityJson = {}
        entityJson["id"] = str(entity.getID())
        entityJson["entityClass"] = entity.__class__.__name__
        entityJson["name"] = entity.getName()
        entityJson["creationDate"] = str(entity.getCreationDate())
        entityJson["environmentId"] = str(entity.getEnvironmentID())
        entityJson["gridId"] = str(entity.getGridID())
        entityJson["locationId"] = str(entity.getLocationID())
        if isinstance(entity, Food):
            entityJson["energy"] = entity.getEnergy()
        elif isinstance(entity, LivingEntity):
            entityJson["energy"] = entity.getEnergy()
            entityJson["tickCreated"] = entity.getTickCreated()
            entityJson["tickLastReproduced"] = entity.getTickLastReproduced()
            entityJson["imagePath"] = entity.getImagePath()
            if isinstance(entity, Npc):
                entityJson["npcMode"] = entity.getMode()
                entityJson["npcInventory"] = self._generateJsonForStoredInventory(
                    entity.getInventory()
                )
        elif isinstance(entity, Excrement):
            entityJson["tickCreated"] = entity.getTickCreated()
        elif isinstance(entity, (YoungCrop, MatureCrop)):
            entityJson["tickPlanted"] = entity.getTickPlanted()
        elif isinstance(entity, StorableInventory):
            entityJson["storedInventory"] = self._generateJsonForStoredInventory(
                entity.getStoredInventory()
            )
        return entityJson

    def generateRoomFromJson(self, roomJson):
        backgroundColor = self._parseBackgroundColor(roomJson["backgroundColor"])
        room = Room(
            roomJson["name"],
            self.gridSize,
            backgroundColor,
            roomJson["x"],
            roomJson["y"],
            self.renderer,
            roomJson.get("z", 0),
        )
        room.setID(roomJson["id"])
        room.setGrid(self.generateGridFromJson(roomJson["grid"]))
        room.setLivingEntities(self.livingEntities)
        self.livingEntities = dict()
        return room

    def generateGridFromJson(self, gridJson):
        grid = Grid(self.gridSize, self.gridSize)
        grid.setID(gridJson["id"])
        grid.setLocations(self.generateLocationsFromJson(gridJson["locations"]))
        return grid

    def generateLocationsFromJson(self, locationsJson):
        locations = {}
        for locationJson in locationsJson:
            location = self.generateLocationFromJson(locationJson)
            locations[location.getID()] = location
        return locations

    def generateLocationFromJson(self, locationJson):
        location = Location(locationJson["x"], locationJson["y"])
        location.setID(locationJson["id"])
        location.setEntities(self.generateEntitiesFromJson(locationJson["entities"]))
        return location

    def generateEntitiesFromJson(self, entitiesJson):
        entities = {}
        for entityJson in entitiesJson:
            entity = self.generateEntityFromJson(entityJson)
            if entity is None:
                continue
            entities[entity.getID()] = entity

            if isinstance(entity, LivingEntity):
                self.livingEntities[entity.getID()] = entity
        return entities

    def generateEntityFromJson(self, entityJson):
        entityClass = entityJson["entityClass"]
        if entityClass == "Player":
            return None

        entity = self._createEntity(entityClass, entityJson)
        if entity is None:
            raise ValueError("Unknown entity class: " + entityClass)

        entity.setID(UUID(entityJson["id"]))

        if isinstance(entity, LivingEntity):
            entity.setEnergy(entityJson["energy"])
            entity.setTickCreated(entityJson["tickCreated"])
            entity.setTickLastReproduced(entityJson["tickLastReproduced"])
            entity.setImagePath(entityJson["imagePath"])
        elif isinstance(entity, Food) and "energy" in entityJson:
            entity.setEnergy(entityJson["energy"])

        entity.setEnvironmentID(UUID(entityJson["environmentId"]))
        entity.setGridID(UUID(entityJson["gridId"]))
        entity.setLocationID(entityJson["locationId"])
        entity.setName(entityJson["name"])

        if isinstance(entity, StorableInventory) and "storedInventory" in entityJson:
            self._restoreStoredInventory(
                entity.getStoredInventory(), entityJson["storedInventory"]
            )

        if isinstance(entity, Npc):
            entity.setMode(entityJson.get("npcMode", "npc"))
            if "npcInventory" in entityJson:
                self._restoreStoredInventory(
                    entity.getInventory(), entityJson["npcInventory"]
                )

        return entity

    def _parseBackgroundColor(self, backgroundColorText):
        colorParts = backgroundColorText.replace("(", "").replace(")", "").split(",")
        red = int(colorParts[0])
        green = int(colorParts[1])
        blue = int(colorParts[2])
        return red, green, blue

    def _createEntity(self, entityClass, entityJson):
        if entityClass == "Npc":
            from entity.living.npc import randomNpcName

            return Npc(randomNpcName(), entityJson["tickCreated"])
        livingEntityConstructor = LIVING_ENTITY_TYPES.get(entityClass)
        if livingEntityConstructor is not None:
            return livingEntityConstructor(entityJson["tickCreated"])
        if entityClass == "Excrement":
            return Excrement(entityJson["tickCreated"])
        if entityClass == "YoungCrop":
            return YoungCrop(entityJson["tickPlanted"])
        if entityClass == "MatureCrop":
            return MatureCrop(entityJson["tickPlanted"])
        if entityClass == "Gravestone":
            return Gravestone()

        constructor = self.entityConstructors.get(entityClass)
        if constructor is None:
            return None
        return constructor()

    def _generateJsonForStoredInventory(self, inventory):
        slotsJson = []
        for slotIndex, slot in enumerate(inventory.getInventorySlots()):
            contentsJson = []
            for item in slot.getContents():
                itemJson = {
                    "entityId": str(item.getID()),
                    "entityClass": item.__class__.__name__,
                    "name": item.getName(),
                    "assetPath": item.getImagePath(),
                }
                if isinstance(item, Food):
                    itemJson["energy"] = item.getEnergy()
                elif isinstance(item, LivingEntity):
                    itemJson["energy"] = item.getEnergy()
                    itemJson["tickCreated"] = item.getTickCreated()
                    itemJson["tickLastReproduced"] = item.getTickLastReproduced()
                    itemJson["imagePath"] = item.getImagePath()
                elif isinstance(item, (YoungCrop, MatureCrop)):
                    itemJson["tickPlanted"] = item.getTickPlanted()
                contentsJson.append(itemJson)
            slotsJson.append({"slotIndex": slotIndex, "slotContents": contentsJson})
        return {"inventorySlots": slotsJson}

    def _restoreStoredInventory(self, inventory, storedInventoryJson):
        for slotJson in storedInventoryJson.get("inventorySlots", []):
            slotIndex = slotJson.get("slotIndex")
            for itemJson in slotJson.get("slotContents", []):
                item = self._createStoredItem(itemJson)
                if item is None:
                    continue
                # Restore into the saved slot so a chest keeps the arrangement
                # it was packed with; fall back to first-available when the
                # index no longer fits so nothing is dropped.
                if inventory.placeIntoSlot(slotIndex, item):
                    continue
                if not inventory.placeIntoFirstAvailableInventorySlot(item):
                    _logger.error(
                        "failed to restore stored inventory item: no inventory space available",
                        entityClass=itemJson.get("entityClass"),
                        entityId=itemJson.get("entityId"),
                        slotIndex=slotIndex,
                    )

    def _createStoredItem(self, itemJson):
        entityClass = itemJson["entityClass"]

        livingEntityConstructor = LIVING_ENTITY_TYPES.get(entityClass)
        if livingEntityConstructor is not None:
            item = livingEntityConstructor(itemJson["tickCreated"])
            item.setEnergy(itemJson["energy"])
            item.setTickLastReproduced(itemJson["tickLastReproduced"])
            item.setImagePath(itemJson["imagePath"])
        elif entityClass == "YoungCrop":
            item = YoungCrop(itemJson["tickPlanted"])
        elif entityClass == "MatureCrop":
            item = MatureCrop(itemJson["tickPlanted"])
        else:
            constructor = self.entityConstructors.get(entityClass)
            if constructor is None:
                raise ValueError(f"unknown stored item class: {entityClass}")
            item = constructor()
            if isinstance(item, Food) and "energy" in itemJson:
                item.setEnergy(itemJson["energy"])

        item.setID(UUID(itemJson["entityId"]))
        return item
