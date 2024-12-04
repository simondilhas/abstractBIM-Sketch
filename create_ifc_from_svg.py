from dataclasses import dataclass
from typing import List, Tuple, Dict, Any
import ifcopenshell
import svgpathtools
from svgpathtools import svg2paths2
import uuid
import time
from ifcopenshell.file import file as IfcFile


@dataclass
class Point3D:
    x: float
    y: float
    z: float = 0.0

    def to_list(self) -> List[float]:
        return [self.x, self.y, self.z]


class IfcModelCreator:
    def __init__(self, schema: str = "IFC4"):
        self.ifc: IfcFile = ifcopenshell.file(schema=schema)
        self.owner_history = None
        self.context = None
        self.project = None
        self.building_storey = None

    def create_owner_history(self) -> None:
        """Create IfcOwnerHistory with required entities."""
        app_dev = self.ifc.create_entity("IfcOrganization", Name="CustomApp Developer")
        application = self.ifc.create_entity(
            "IfcApplication",
            ApplicationDeveloper=app_dev,
            ApplicationFullName="Custom IFC Generator",
            Version="1.0",
            ApplicationIdentifier="CustomApp"
        )
        person = self.ifc.create_entity("IfcPerson", FamilyName="Doe", GivenName="John")
        org = self.ifc.create_entity("IfcOrganization", Name="Example Organization")
        person_and_org = self.ifc.create_entity(
            "IfcPersonAndOrganization", 
            ThePerson=person, 
            TheOrganization=org
        )
        self.owner_history = self.ifc.create_entity(
            "IfcOwnerHistory",
            OwningUser=person_and_org,
            OwningApplication=application,
            CreationDate=int(time.time())
        )

    def create_project_context(self) -> None:
        """Create project and geometric context."""
        self.project = self.ifc.create_entity(
            "IfcProject",
            GlobalId=self._create_guid(),
            Name="Example Project",
            OwnerHistory=self.owner_history
        )
        
        origin = self.ifc.create_entity(
            "IfcCartesianPoint", 
            Coordinates=[0.0, 0.0, 0.0]
        )
        axis_placement = self.ifc.create_entity(
            "IfcAxis2Placement3D",
            Location=origin
        )
        
        self.context = self.ifc.create_entity(
            "IfcGeometricRepresentationContext",
            ContextType="Model",
            ContextIdentifier="Model",
            CoordinateSpaceDimension=3,
            Precision=0.0001,
            WorldCoordinateSystem=axis_placement
        )
        self.project.RepresentationContexts = [self.context]
        self._create_units()

    def _create_units(self) -> None:
        """Create SI units for the project."""
        units = self.ifc.create_entity(
            "IfcUnitAssignment",
            Units=[
                self.ifc.create_entity("IfcSIUnit", UnitType="LENGTHUNIT", Name="METRE"),
                self.ifc.create_entity("IfcSIUnit", UnitType="AREAUNIT", Name="SQUARE_METRE"),
                self.ifc.create_entity("IfcSIUnit", UnitType="VOLUMEUNIT", Name="CUBIC_METRE"),
            ]
        )
        self.project.UnitsInContext = units

    def create_spatial_hierarchy(self) -> None:
        """Create site, building, and storey hierarchy."""
        global_placement = self._create_axis_placement()
        
        # Create site
        site_placement = self._create_local_placement(None, global_placement)
        site = self._create_spatial_element(
            "IfcSite", "Default Site", site_placement
        )
        
        # Create building
        building_placement = self._create_local_placement(site_placement, global_placement)
        building = self._create_spatial_element(
            "IfcBuilding", "Default Building", building_placement
        )
        
        # Create storey
        storey_placement = self._create_local_placement(building_placement, global_placement)
        self.building_storey = self._create_spatial_element(
            "IfcBuildingStorey", "Ground Floor", storey_placement
        )
        
        # Create relationships
        self._create_aggregation(self.project, [site])
        self._create_aggregation(site, [building])
        self._create_aggregation(building, [self.building_storey])

    def create_space(self, coordinates: List[Point3D], space_height: float) -> None:
        """Create an IFC space with given coordinates and height."""
        space_placement = self._create_local_placement(
            self.building_storey.ObjectPlacement
        )
        
        ifc_space = self._create_spatial_element(
            "IfcSpace", "Space", space_placement
        )

        geometry = self._create_space_geometry(coordinates, space_height)
        ifc_space.Representation = geometry

        # Relate space to storey
        self._create_containment(self.building_storey, [ifc_space])

    def _create_space_geometry(
        self, coordinates: List[Point3D], space_height: float
    ) -> Any:
        """Create the geometric representation of a space."""
        bottom_points = [
            self.ifc.create_entity("IfcCartesianPoint", Coordinates=p.to_list())
            for p in coordinates
        ]
        
        top_points = [
            self.ifc.create_entity(
                "IfcCartesianPoint",
                Coordinates=[p.x, p.y, space_height]
            )
            for p in coordinates
        ]

        faces = self._create_faces(bottom_points, top_points)
        closed_shell = self.ifc.create_entity("IfcClosedShell", CfsFaces=faces)
        brep = self.ifc.create_entity("IfcFacetedBrep", Outer=closed_shell)

        return self.ifc.create_entity(
            "IfcProductDefinitionShape",
            Representations=[
                self.ifc.create_entity(
                    "IfcShapeRepresentation",
                    ContextOfItems=self.context,
                    RepresentationIdentifier="Body",
                    RepresentationType="Brep",
                    Items=[brep]
                )
            ]
        )

    def _create_faces(
        self, bottom_points: List[Any], top_points: List[Any]
    ) -> List[Any]:
        """Create all faces for a space geometry."""
        bottom_face = self._create_horizontal_face(bottom_points)
        top_face = self._create_horizontal_face(top_points)
        vertical_faces = self._create_vertical_faces(bottom_points, top_points)
        return [bottom_face, top_face] + vertical_faces

    def _create_horizontal_face(self, points: List[Any]) -> Any:
        """Create a horizontal face from points."""
        loop = self.ifc.create_entity("IfcPolyLoop", Polygon=points)
        return self.ifc.create_entity(
            "IfcFace",
            Bounds=[
                self.ifc.create_entity(
                    "IfcFaceOuterBound",
                    Bound=loop,
                    Orientation=True
                )
            ]
        )

    def _create_vertical_faces(
        self, bottom_points: List[Any], top_points: List[Any]
    ) -> List[Any]:
        """Create vertical faces between bottom and top points."""
        faces = []
        for i in range(len(bottom_points) - 1):
            wall_points = [
                bottom_points[i],
                bottom_points[i + 1],
                top_points[i + 1],
                top_points[i]
            ]
            loop = self.ifc.create_entity("IfcPolyLoop", Polygon=wall_points)
            faces.append(
                self.ifc.create_entity(
                    "IfcFace",
                    Bounds=[
                        self.ifc.create_entity(
                            "IfcFaceOuterBound",
                            Bound=loop,
                            Orientation=True
                        )
                    ]
                )
            )
        return faces

    def _create_spatial_element(
        self, element_type: str, name: str, placement: Any
    ) -> Any:
        """Create a spatial element with given type and name."""
        return self.ifc.create_entity(
            element_type,
            GlobalId=self._create_guid(),
            Name=name,
            ObjectPlacement=placement,
            OwnerHistory=self.owner_history
        )

    def _create_axis_placement(self) -> Any:
        """Create an axis placement at origin."""
        return self.ifc.create_entity(
            "IfcAxis2Placement3D",
            Location=self.ifc.create_entity(
                "IfcCartesianPoint",
                Coordinates=[0.0, 0.0, 0.0]
            )
        )

    def _create_local_placement(
        self, placement_ref: Any = None, relative_placement: Any = None
    ) -> Any:
        """Create a local placement."""
        return self.ifc.create_entity(
            "IfcLocalPlacement",
            PlacementRelTo=placement_ref,
            RelativePlacement=relative_placement or self._create_axis_placement()
        )

    def _create_aggregation(self, relating_object: Any, related_objects: List[Any]) -> None:
        """Create an aggregation relationship."""
        self.ifc.create_entity(
            "IfcRelAggregates",
            GlobalId=self._create_guid(),
            RelatingObject=relating_object,
            RelatedObjects=related_objects
        )

    def _create_containment(self, structure: Any, elements: List[Any]) -> None:
        """Create a containment relationship."""
        self.ifc.create_entity(
            "IfcRelContainedInSpatialStructure",
            GlobalId=self._create_guid(),
            RelatingStructure=structure,
            RelatedElements=elements
        )

    @staticmethod
    def _create_guid() -> str:
        """Create a new GUID."""
        return str(uuid.uuid4().hex[:22])


def create_ifc_space_model(
    svg_file: str,
    ifc_file: str,
    space_height: float
) -> None:
    """Create an IFC model from SVG file."""
    paths, attributes, svg_attributes = svg2paths2(svg_file)
    
    model_creator = IfcModelCreator()
    model_creator.create_owner_history()
    model_creator.create_project_context()
    model_creator.create_spatial_hierarchy()

    for attr in attributes:
        if all(key in attr for key in ['x', 'y', 'width', 'height']):
            # Convert SVG dimensions (mm) to meters
            x = float(attr.get('x', 0)) / 1000
            y = float(attr.get('y', 0)) / 1000
            width = float(attr.get('width', 0)) / 1000
            height = float(attr.get('height', 0)) / 1000

            coordinates = [
                Point3D(x, y),
                Point3D(x + width, y),
                Point3D(x + width, y + height),
                Point3D(x, y + height),
                Point3D(x, y)
            ]
            model_creator.create_space(coordinates, space_height)

    model_creator.ifc.write(ifc_file)

svg_input = "test/groundfloor_test1.svg"
ifc_output = "output.ifc"
space_height = 2.5
create_ifc_space_model(svg_input, ifc_output, space_height)