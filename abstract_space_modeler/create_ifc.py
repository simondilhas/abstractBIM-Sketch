import ifcopenshell
from svgpathtools import svg2paths2
import uuid
import time


def create_ifc_space_model(svg_file, ifc_file, default_height=3.0):
    # Parse the SVG file
    paths, attributes, svg_attributes = svg2paths2(svg_file)

    # Create a new IFC file
    ifc = ifcopenshell.file(schema="IFC4")

    def new_guid():
        return str(uuid.uuid4().hex[:22])

    # Define mandatory IFC header information
    application = ifc.create_entity(
        "IfcApplication",
        ApplicationFullName="Space Modeler Plugin",
        Version="1.0",
        ApplicationIdentifier="SpaceModeler"
    )
    owner_history = ifc.create_entity(
        "IfcOwnerHistory",
        OwningApplication=application,
        CreationDate=int(time.time())
    )

    project = ifc.create_entity("IfcProject", GlobalId=new_guid(), Name="Space Project", OwnerHistory=owner_history)
    context = ifc.create_entity(
        "IfcGeometricRepresentationContext",
        ContextType="Model",
        CoordinateSpaceDimension=3,
        Precision=0.0001,
        WorldCoordinateSystem=ifc.create_entity(
            "IfcAxis2Placement3D",
            Location=ifc.create_entity("IfcCartesianPoint", Coordinates=[0.0, 0.0, 0.0])
        )
    )
    project.RepresentationContexts = [context]

    # Define global units
    units = ifc.create_entity(
        "IfcUnitAssignment",
        Units=[ifc.create_entity("IfcSIUnit", UnitType="LENGTHUNIT", Name="METRE")]
    )
    project.UnitsInContext = units

    # Create IfcBuildingStorey
    storey = ifc.create_entity(
        "IfcBuildingStorey",
        GlobalId=new_guid(),
        Name="Default Storey",
        OwnerHistory=owner_history,
        ObjectPlacement=ifc.create_entity(
            "IfcLocalPlacement",
            RelativePlacement=ifc.create_entity(
                "IfcAxis2Placement3D",
                Location=ifc.create_entity("IfcCartesianPoint", Coordinates=[0.0, 0.0, 0.0])
            )
        )
    )

    def create_space(coords):
        # Create bottom and top points
        bottom_points = [ifc.create_entity("IfcCartesianPoint", Coordinates=coord) for coord in coords]
        top_points = [ifc.create_entity("IfcCartesianPoint", Coordinates=[x, y, default_height]) for x, y, _ in coords]

        # Create IfcSpace
        space = ifc.create_entity(
            "IfcSpace",
            GlobalId=new_guid(),
            Name="Space",
            OwnerHistory=owner_history
        )

        # Create faces and BRep representation
        bottom_loop = ifc.create_entity("IfcPolyLoop", Polygon=bottom_points)
        top_loop = ifc.create_entity("IfcPolyLoop", Polygon=top_points)
        bottom_face = ifc.create_entity("IfcFace", Bounds=[ifc.create_entity("IfcFaceOuterBound", Bound=bottom_loop)])
        top_face = ifc.create_entity("IfcFace", Bounds=[ifc.create_entity("IfcFaceOuterBound", Bound=top_loop)])
        vertical_faces = []
        for i in range(len(bottom_points) - 1):
            face_loop = ifc.create_entity("IfcPolyLoop", Polygon=[
                bottom_points[i], bottom_points[i + 1], top_points[i + 1], top_points[i]
            ])
            vertical_faces.append(ifc.create_entity("IfcFace", Bounds=[ifc.create_entity("IfcFaceOuterBound", Bound=face_loop)]))

        all_faces = [bottom_face, top_face] + vertical_faces
        closed_shell = ifc.create_entity("IfcClosedShell", CfsFaces=all_faces)
        brep = ifc.create_entity("IfcFacetedBrep", Outer=closed_shell)
        geometry = ifc.create_entity(
            "IfcShapeRepresentation",
            ContextOfItems=context,
            RepresentationType="Brep",
            Items=[brep]
        )
        space.Representation = ifc.create_entity("IfcProductDefinitionShape", Representations=[geometry])

        # Relate space to storey
        ifc.create_entity(
            "IfcRelContainedInSpatialStructure",
            GlobalId=new_guid(),
            RelatingStructure=storey,
            RelatedElements=[space]
        )

    # Process each rectangle in the SVG
    for attr in attributes:
        if 'x' in attr and 'y' in attr and 'width' in attr and 'height' in attr:
            x = float(attr['x']) / 1000
            y = float(attr['y']) / 1000
            width = float(attr['width']) / 1000
            height = float(attr['height']) / 1000
            coords = [[x, y, 0.0], [x + width, y, 0.0], [x + width, y + height, 0.0], [x, y + height, 0.0], [x, y, 0.0]]
            create_space(coords)

    # Write to IFC file
    ifc.write(ifc_file)
    print(f"IFC file saved: {ifc_file}")
