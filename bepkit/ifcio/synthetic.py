"""Synthetic IFC models for performance tests.

A grid of walls on a few storeys: enough geometry to time the tessellation path
without shipping a large file in the repository.
"""

from __future__ import annotations

from pathlib import Path


def write_grid_model(path: str | Path, elements: int, *, storeys: int = 4, schema: str = "IFC4") -> Path:
    """Write ``elements`` walls spread over ``storeys`` storeys and return the path."""
    import ifcopenshell
    import ifcopenshell.api

    model = ifcopenshell.api.run("project.create_file", version=schema)
    project = ifcopenshell.api.run("root.create_entity", model, ifc_class="IfcProject", name="Synthetic")
    ifcopenshell.api.run("unit.assign_unit", model)
    context = ifcopenshell.api.run("context.add_context", model, context_type="Model")
    body = ifcopenshell.api.run("context.add_context", model, context_type="Model",
                                context_identifier="Body", target_view="MODEL_VIEW", parent=context)
    site = ifcopenshell.api.run("root.create_entity", model, ifc_class="IfcSite", name="Site")
    building = ifcopenshell.api.run("root.create_entity", model, ifc_class="IfcBuilding", name="Building")
    ifcopenshell.api.run("aggregate.assign_object", model, relating_object=project, products=[site])
    ifcopenshell.api.run("aggregate.assign_object", model, relating_object=site, products=[building])

    levels = []
    for n in range(storeys):
        storey = ifcopenshell.api.run("root.create_entity", model, ifc_class="IfcBuildingStorey",
                                      name=f"Level {n + 1}")
        storey.Elevation = 3.0 * n
        ifcopenshell.api.run("aggregate.assign_object", model, relating_object=building, products=[storey])
        levels.append(storey)

    per_row = max(1, int(elements ** 0.5))
    for i in range(elements):
        wall = ifcopenshell.api.run("root.create_entity", model, ifc_class="IfcWall", name=f"Wall {i}")
        storey = levels[i % storeys]
        matrix = [[1.0, 0.0, 0.0, float(i % per_row) * 6.0],
                  [0.0, 1.0, 0.0, float(i // per_row) * 6.0],
                  [0.0, 0.0, 1.0, storey.Elevation],
                  [0.0, 0.0, 0.0, 1.0]]
        ifcopenshell.api.run("geometry.edit_object_placement", model, product=wall, matrix=matrix)
        shape = ifcopenshell.api.run("geometry.add_wall_representation", model, context=body,
                                     length=5.0, height=3.0, thickness=0.2)
        ifcopenshell.api.run("geometry.assign_representation", model, product=wall, representation=shape)
        ifcopenshell.api.run("spatial.assign_container", model, relating_structure=storey, products=[wall])

    path = Path(path)
    model.write(str(path))
    return path
