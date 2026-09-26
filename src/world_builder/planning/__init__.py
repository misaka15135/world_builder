"""Scene-driven planning control plane (work orders 013-018).

Stage A (scene brief) and stage C (landmark catalogue) live here; the terrain,
district, designer and assembler stages are 014, 016, 017 and 018.
"""

from .brief import (BRIEF_VERSION, MODEL_CONTRACT_VERSION, FixtureBriefProvider, Landmark, SceneBrief,
                    brief_from_dict, brief_from_response, compile_brief, compile_brief_with_provider, load_brief,
                    validate_brief)
from .catalogue import (CATALOGUE_VERSION, DEFAULT_SETTINGS_ROOT, SETTING_VERSION, CatalogueEntry, SceneError,
                        SettingPack, available_settings, load_setting_pack)
from .terrain import (TERRAIN_VERSION, TerrainPlan, TerrainSpec, WaterChannel, load_terrain_spec, plan_terrain,
                      render_preview, validate_terrain)
from .siting import (DISTRICTS_VERSION, Block, Bridge, DistrictSpec, Domain, Road, Site, SitingPlan,
                     load_districts_spec, plan_siting, validate_siting)
from .designer import (DESIGN_VERSION, BuildingDesign, DesignTemplate, Furniture, Room, Storey,
                       design_building, load_designs, parse_designs, validate_design)

__all__ = [
    "BRIEF_VERSION", "CATALOGUE_VERSION", "SETTING_VERSION", "MODEL_CONTRACT_VERSION", "CatalogueEntry",
    "FixtureBriefProvider", "Landmark", "SceneBrief", "SceneError", "SettingPack", "available_settings",
    "brief_from_dict", "brief_from_response", "compile_brief", "compile_brief_with_provider", "load_brief",
    "load_setting_pack", "validate_brief", "DEFAULT_SETTINGS_ROOT",
    "TERRAIN_VERSION", "TerrainPlan", "TerrainSpec", "WaterChannel", "load_terrain_spec", "plan_terrain",
    "render_preview", "validate_terrain",
    "DISTRICTS_VERSION", "Block", "Bridge", "DistrictSpec", "Domain", "Road", "Site", "SitingPlan",
    "load_districts_spec", "plan_siting", "validate_siting",
    "DESIGN_VERSION", "BuildingDesign", "DesignTemplate", "Furniture", "Room", "Storey", "design_building",
    "load_designs", "parse_designs", "validate_design",
]
