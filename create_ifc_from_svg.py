import ifcopenshell
import svgpathtools
from svgpathtools import svg2paths2
import uuid
import time


def create_ifc_space_model(svg_file, ifc_file, space_height):
    # Parse the SVG file
    paths, attributes, svg_attributes = svg2paths2(svg_file)

    # Create a new IFC file
    ifc = ifcopenshell.file(schema="IFC4")

    # Function to generate GUIDs
    def new_guid():
        return str(uuid.uuid4().hex[:22])

    # Add IfcOwnerHistory with mandatory fields
    application_developer = ifc.create_entity("IfcOrganization", Name="CustomApp Developer")
    application = ifc.create_entity(
        "IfcApplication",
        ApplicationDeveloper=application_developer,
        ApplicationFullName="Custom IFC Generator",
        Version="1.0",
        ApplicationIdentifier="CustomApp"
    )
    person = ifc.create_entity("IfcPerson", FamilyName="Doe", GivenName="John")
    organization = ifc.create_entity("IfcOrganization", Name="Example Organization")
    person_and_organization = ifc.create_entity("IfcPersonAndOrganization", ThePerson=person, TheOrganization=organization)
    owner_history = ifc.create_entity(
        "IfcOwnerHistory",
        OwningUser=person_and_organization,
        OwningApplication=application,
        CreationDate=int(time.time())  # Use UNIX timestamp for the creation date
    )

    # Add header information
    project = ifc.create_entity("IfcProject", GlobalId=new_guid(), Name="Example Project", OwnerHistory=owner_history)
    context = ifc.create_entity(
        "IfcGeometricRepresentationContext",
        ContextType="Model",
        ContextIdentifier="Model",
        CoordinateSpaceDimension=3,  # Ensure the dimension is 3 for 3D context
        Precision=0.0001,
        WorldCoordinateSystem=ifc.create_entity(
            "IfcAxis2Placement3D",
            Location=ifc.create_entity("IfcCartesianPoint", Coordinates=[0.0, 0.0, 0.0])
        )
    )
    project.RepresentationContexts = [context]

    # Define units in meters
    units = ifc.create_entity(
        "IfcUnitAssignment",
        Units=[
            ifc.create_entity("IfcSIUnit", UnitType="LENGTHUNIT", Name="METRE"),
            ifc.create_entity("IfcSIUnit", UnitType="AREAUNIT", Name="SQUARE_METRE"),
            ifc.create_entity("IfcSIUnit", UnitType="VOLUMEUNIT", Name="CUBIC_METRE"),
        ]
    )
    project.UnitsInContext = units

    # Define the global placement
    global_placement = ifc.create_entity(
        "IfcAxis2Placement3D",
        Location=ifc.create_entity("IfcCartesianPoint", Coordinates=[0.0, 0.0, 0.0])
    )

    # Create site, building, and storey with local placements
    site_placement = ifc.create_entity("IfcLocalPlacement", PlacementRelTo=None, RelativePlacement=global_placement)
    site = ifc.create_entity(
        "IfcSite",
        GlobalId=new_guid(),
        Name="Default Site",
        ObjectPlacement=site_placement,
        OwnerHistory=owner_history
    )

    building_placement = ifc.create_entity("IfcLocalPlacement", PlacementRelTo=site_placement, RelativePlacement=global_placement)
    building = ifc.create_entity(
        "IfcBuilding",
        GlobalId=new_guid(),
        Name="Default Building",
        ObjectPlacement=building_placement,
        OwnerHistory=owner_history
    )

    storey_placement = ifc.create_entity("IfcLocalPlacement", PlacementRelTo=building_placement, RelativePlacement=global_placement)
    building_storey = ifc.create_entity(
        "IfcBuildingStorey",
        GlobalId=new_guid(),
        Name="Ground Floor",
        ObjectPlacement=storey_placement,
        OwnerHistory=owner_history
    )

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


    def create_space(coordinates, space_height):

        space_placement = ifc.create_entity("IfcLocalPlacement", PlacementRelTo=storey_placement)
        ifc_space = ifc.create_entity(
            "IfcSpace",
            GlobalId=new_guid(),
            Name="Space",
            ObjectPlacement=space_placement,
            OwnerHistory=owner_history
        )

        bottom_points = [ifc.create_entity("IfcCartesianPoint", Coordinates=coord) for coord in coordinates]
        top_points = [ifc.create_entity("IfcCartesianPoint", Coordinates=[x, y, space_height]) for x, y, _ in coordinates]

        bottom_loop = ifc.create_entity("IfcPolyLoop", Polygon=bottom_points)
        top_loop = ifc.create_entity("IfcPolyLoop", Polygon=top_points)

        bottom_face = ifc.create_entity("IfcFace", Bounds=[ifc.create_entity("IfcFaceOuterBound", Bound=bottom_loop, Orientation=True)])
        top_face = ifc.create_entity("IfcFace", Bounds=[ifc.create_entity("IfcFaceOuterBound", Bound=top_loop, Orientation=True)])
        vertical_faces = []
        for i in range(len(bottom_points) - 1):
            wall_points = [
                bottom_points[i],
                bottom_points[i + 1],
                top_points[i + 1],
                top_points[i]
            ]
            wall_loop = ifc.create_entity("IfcPolyLoop", Polygon=wall_points)
            vertical_faces.append(ifc.create_entity("IfcFace", Bounds=[ifc.create_entity("IfcFaceOuterBound", Bound=wall_loop, Orientation=True)]))

        all_faces = [bottom_face, top_face] + vertical_faces
        closed_shell = ifc.create_entity("IfcClosedShell", CfsFaces=all_faces)
        brep = ifc.create_entity("IfcFacetedBrep", Outer=closed_shell)

        geometry_representation = ifc.create_entity(
            "IfcShapeRepresentation",
            ContextOfItems=context,
            RepresentationIdentifier="Body",
            RepresentationType="Brep",
            Items=[brep]
        )
        ifc_space.Representation = ifc.create_entity(
            "IfcProductDefinitionShape",
            Representations=[geometry_representation]
        )

        # Relate space to building storey
        ifc.create_entity(
            "IfcRelContainedInSpatialStructure",
            GlobalId=new_guid(),
            RelatingStructure=building_storey,
            RelatedElements=[ifc_space]
        )

    # Convert SVG dimensions (in cm) to meters Carfull!!!! with svg scale
    for attr in attributes:
        if 'x' in attr and 'y' in attr and 'width' in attr and 'height' in attr:
            x = float(attr.get('x', 0)) / 1000
            y = float(attr.get('y', 0)) / 1000
            width = float(attr.get('width', 0)) / 1000
            height = float(attr.get('height', 0)) / 1000

            coordinates = [
                [x, y, 0.0],
                [x + width, y, 0.0],
                [x + width, y + height, 0.0],
                [x, y + height, 0.0],
                [x, y, 0.0]
            ]
            create_space(coordinates, space_height)

    # Write the IFC file
    ifc.write(ifc_file)
    print(f"IFC file created: {ifc_file}")


# Example Usage
svg_input = "test/groundfloor_test1.svg"  # Replace with your SVG file path
ifc_output = "output.ifc"  # Replace with your desired IFC file path
space_height = 2.5
create_ifc_space_model(svg_input, ifc_output, space_height)
