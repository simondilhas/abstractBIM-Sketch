import ifcopenshell
import svgpathtools
from svgpathtools import svg2paths2
import uuid

def create_ifc_space_model(svg_file, ifc_file):
    # Parse the SVG file
    paths, attributes, svg_attributes = svg2paths2(svg_file)
    
    # Create a new IFC file
    ifc = ifcopenshell.file()
    
    # Function to generate GUIDs
    def new_guid():
        return str(uuid.uuid4().hex[:22])  # IFC GUID requires 22 characters
    
    # Add header information
    project = ifc.create_entity("IfcProject", GlobalId=new_guid(), Name="Example Project")
    context = ifc.create_entity("IfcGeometricRepresentationContext", ContextType="Model")
    project.RepresentationContexts = [context]
    
    # Define units in meters
    units = ifc.create_entity(
        "IfcUnitAssignment",
        Units=[
            ifc.create_entity("IfcSIUnit", UnitType="LENGTHUNIT", Name="METRE"),
            ifc.create_entity("IfcSIUnit", UnitType="AREAUNIT", Name="SQUARE_METRE"),
            ifc.create_entity("IfcSIUnit", UnitType="VOLUMEUNIT", Name="CUBIC_METRE")
        ]
    )
    project.UnitsInContext = units
    
    # Create site, building, and storey
    site = ifc.create_entity("IfcSite", GlobalId=new_guid(), Name="Default Site")
    building = ifc.create_entity("IfcBuilding", GlobalId=new_guid(), Name="Default Building")
    building_storey = ifc.create_entity("IfcBuildingStorey", GlobalId=new_guid(), Name="Ground Floor")
    
    # Relate site to project using IfcRelAggregates
    ifc.create_entity(
        "IfcRelAggregates",
        GlobalId=new_guid(),
        RelatingObject=project,
        RelatedObjects=[site]
    )
    
    # Relate building to site
    ifc.create_entity(
        "IfcRelAggregates",
        GlobalId=new_guid(),
        RelatingObject=site,
        RelatedObjects=[building]
    )
    
    # Relate storey to building
    ifc.create_entity(
        "IfcRelAggregates",
        GlobalId=new_guid(),
        RelatingObject=building,
        RelatedObjects=[building_storey]
    )
    
    # Convert SVG dimensions (in cm) to meters
    for attr in attributes:
        if 'x' in attr and 'y' in attr and 'width' in attr and 'height' in attr:
            # Handle rectangles
            x = float(attr.get('x', 0)) / 100  # Convert to meters
            y = float(attr.get('y', 0)) / 100
            width = float(attr.get('width', 0)) / 100
            height = float(attr.get('height', 0)) / 100
            
            coordinates = [
                [x, y],
                [x + width, y],
                [x + width, y + height],
                [x, y + height],
                [x, y]  # Close the loop
            ]
        elif 'points' in attr:
            # Handle polygons
            points = attr['points'].strip().split()
            coordinates = [
                [float(coord) / 100 for coord in point.split(',')]
                for point in points
            ]
        else:
            # Skip unsupported elements
            continue
        
        # Create IfcSpace entity
        ifc_space = ifc.create_entity(
            "IfcSpace",
            GlobalId=new_guid(),
            Name=f"Space"
        )
        
        # Create IfcArbitraryClosedProfileDef for boundary
        boundary = ifc.create_entity(
            "IfcArbitraryClosedProfileDef",
            ProfileType="AREA",
            OuterCurve=ifc.create_entity(
                "IfcPolyline",
                Points=[
                    ifc.create_entity("IfcCartesianPoint", Coordinates=coord)
                    for coord in coordinates
                ]
            )
        )
        
        # Create IfcExtrudedAreaSolid for 3D representation
        extruded_solid = ifc.create_entity(
            "IfcExtrudedAreaSolid",
            SweptArea=boundary,
            ExtrudedDirection=ifc.create_entity(
                "IfcDirection", DirectionRatios=[0.0, 0.0, 1.0]
            ),
            Depth=3.0  # Extrusion height in meters
        )
        
        # Create IfcShapeRepresentation
        geometry_representation = ifc.create_entity(
            "IfcShapeRepresentation",
            ContextOfItems=context,
            RepresentationIdentifier="Body",
            RepresentationType="SweptSolid",
            Items=[extruded_solid]
        )
        ifc_space.Representation = geometry_representation
        
        # Relate space to building storey
        ifc.create_entity(
            "IfcRelContainedInSpatialStructure",
            GlobalId=new_guid(),
            RelatingStructure=building_storey,
            RelatedElements=[ifc_space]
        )
    
    # Write the IFC file
    ifc.write(ifc_file)
    print(f"IFC file created: {ifc_file}")



# Example Usage
svg_input = "test/groundfloor_test1.svg"  # Replace with your SVG file path
ifc_output = "output.ifc"  # Replace with your desired IFC file path
create_ifc_space_model(svg_input, ifc_output)
