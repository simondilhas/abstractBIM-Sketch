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
    
    # Process SVG paths to create IfcSpace
    for attr in attributes:
        if 'x' in attr and 'y' in attr and 'width' in attr and 'height' in attr:
            # Handle rectangles
            x = float(attr.get('x', 0))
            y = float(attr.get('y', 0))
            width = float(attr.get('width', 0))
            height = float(attr.get('height', 0))
            
            coordinates = [
                [x, y, 0.0],
                [x + width, y, 0.0],
                [x + width, y + height, 0.0],
                [x, y + height, 0.0],
                [x, y, 0.0]  # Close the loop
            ]
        elif 'points' in attr:
            # Handle polygons
            points = attr['points'].strip().split()
            coordinates = [
                [float(coord) for coord in point.split(',')] + [0.0]
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
        
        # Create IfcGeometric representation
        polyline = ifc.create_entity(
            "IfcPolyline",
            Points=[
                ifc.create_entity("IfcCartesianPoint", Coordinates=[float(c) for c in coord])  # Ensure flat list of floats
                for coord in coordinates
            ]
        )
        geometry_representation = ifc.create_entity(
            "IfcShapeRepresentation",
            ContextOfItems=context,
            RepresentationType="Curve2D",
            Items=[polyline]
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
