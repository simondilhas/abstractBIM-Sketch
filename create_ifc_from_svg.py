from dataclasses import dataclass
from typing import List, Tuple, Dict, Any, Optional, Callable
import ifcopenshell
import svgpathtools
from svgpathtools import svg2paths2
import uuid
import time
from ifcopenshell.file import file as IfcFile
from svg.path import Path
import ifcopenshell.guid


@dataclass
class Point3D:
    x: float
    y: float
    z: float = 0.0

    def to_list(self) -> List[float]:
        return [self.x, self.y, self.z]

class SVGGeometryParser:
    @staticmethod
    def parse_rect(attr: Dict[str, str], scale: float = 1000.0) -> List[Point3D]:
        """Parse rectangle from SVG attributes."""
        x = float(attr.get('x', 0)) / scale
        y = float(attr.get('y', 0)) / scale
        width = float(attr.get('width', 0)) / scale
        height = float(attr.get('height', 0)) / scale

        return [
            Point3D(x, y),
            Point3D(x + width, y),
            Point3D(x + width, y + height),
            Point3D(x, y + height),
            Point3D(x, y)  # Close the polygon
        ]

    @staticmethod
    def parse_path(path: Path, scale: float = 1000.0) -> List[Point3D]:
        """Parse path from SVG path element."""
        points = []
        for segment in path:
            # Get start point of each segment
            start = segment.start
            points.append(Point3D(
                float(start.real) / scale,
                float(start.imag) / scale
            ))
        
        # Add the end point of the last segment if it's different
        if path:
            end = path[-1].end
            if points and (end.real != points[0].x or end.imag != points[0].y):
                points.append(Point3D(
                    float(end.real) / scale,
                    float(end.imag) / scale
                ))
            
            # Close the polygon if needed
            if points and (points[0].x != points[-1].x or points[0].y != points[-1].y):
                points.append(Point3D(points[0].x, points[0].y))

        points = SVGGeometryParser.ensure_clockwise(points)
        return points

    @staticmethod
    def simplify_polygon(points: List[Point3D], tolerance: float = 0.001) -> List[Point3D]:
        """Simplify polygon by removing collinear points."""
        if len(points) < 3:
            return points

        def is_collinear(p1: Point3D, p2: Point3D, p3: Point3D) -> bool:
            # Calculate the area of the triangle formed by three points
            area = abs((p2.x - p1.x) * (p3.y - p1.y) - 
                      (p3.x - p1.x) * (p2.y - p1.y)) / 2.0
            return area < tolerance

        result = [points[0]]
        for i in range(1, len(points) - 1):
            if not is_collinear(result[-1], points[i], points[i + 1]):
                result.append(points[i])
        result.append(points[-1])
        return result
    
    @staticmethod
    def is_clockwise(points: List[Point3D]) -> bool:
        """Check if points are in clockwise order."""
        if len(points) < 3:
            return True
        area = 0
        for i in range(len(points) - 1):
            j = (i + 1)
            area += points[i].x * points[j].y - points[j].x * points[i].y
        return area < 0
    @staticmethod
    def ensure_clockwise(points: List[Point3D]) -> List[Point3D]:
        """Ensure points are in clockwise order."""
        if not SVGGeometryParser.is_clockwise(points):
            return list(reversed(points))
        return points
    
    

class IfcModelCreator:
    def __init__(self, schema: str = "IFC4"):
        self.ifc: IfcFile = ifcopenshell.file(schema=schema)
        self.owner_history = None
        self.context = None
        self.project = None
        self.building_storey = None
        self.geometry_parser = SVGGeometryParser()

    def create_owner_history(self) -> None:
        """Create IfcOwnerHistory with required entities."""
        # Create organization
        app_dev = self.ifc.create_entity(
            "IfcOrganization",
            Name="CustomApp Developer"
        )
        
        application = self.ifc.create_entity(
            "IfcApplication",
            ApplicationDeveloper=app_dev,
            Version="1.0",
            ApplicationFullName="Custom IFC Generator",
            ApplicationIdentifier="CustomApp"
        )
        
        # Create person
        person = self.ifc.create_entity(
            "IfcPerson",
            FamilyName="Doe",
            GivenName="John"
        )
        
        # Create organization
        org = self.ifc.create_entity(
            "IfcOrganization",
            Name="Example Organization"
        )
        
        person_and_org = self.ifc.create_entity(
            "IfcPersonAndOrganization",
            ThePerson=person,
            TheOrganization=org
        )
        
        # Create owner history with correct ChangeAction
        self.owner_history = self.ifc.create_entity(
            "IfcOwnerHistory",
            OwningUser=person_and_org,
            OwningApplication=application,
            State="READWRITE",
            ChangeAction="NOCHANGE",  # Changed from ADDED to NOCHANGE
            LastModifiedDate=None,
            LastModifyingUser=None,
            LastModifyingApplication=None,
            CreationDate=int(time.time())
        )

        # Set file header information
        self.ifc.wrapped_data.header.file_name.author = ["John Doe"]
        self.ifc.wrapped_data.header.file_name.organization = ["Example Organization"]

    def create_project_context(self) -> None:
        """Create project and geometric context."""
        # Create units first
        length_unit = self.ifc.create_entity("IfcSIUnit", UnitType="LENGTHUNIT", Name="METRE")
        
        units = self.ifc.create_entity(
            "IfcUnitAssignment",
            Units=[length_unit]
        )
        
        # Create project with units
        self.project = self.ifc.create_entity(
            "IfcProject",
            GlobalId=self._create_guid(),
            Name="Example Project",
            UnitsInContext=units,
            OwnerHistory=self.owner_history
        )
        
        # Create axis placement with proper attributes
        z_dir = self.ifc.create_entity("IfcDirection", DirectionRatios=[0.0, 0.0, 1.0])
        x_dir = self.ifc.create_entity("IfcDirection", DirectionRatios=[1.0, 0.0, 0.0])
        origin = self.ifc.create_entity("IfcCartesianPoint", Coordinates=[0.0, 0.0, 0.0])
        
        axis_placement = self.ifc.create_entity(
            "IfcAxis2Placement3D",
            Location=origin,
            Axis=z_dir,  # Added Z direction
            RefDirection=x_dir  # Added X direction
        )
        
        # Create context with proper attributes
        self.context = self.ifc.create_entity(
            "IfcGeometricRepresentationContext",
            ContextType="Model",
            ContextIdentifier="Model",
            CoordinateSpaceDimension=3,
            Precision=0.00001,
            WorldCoordinateSystem=axis_placement,
            TrueNorth=None  # Optional TrueNorth direction
        )
        
        # Set representation contexts
        self.project.RepresentationContexts = [self.context]

    def _create_local_placement(
        self, placement_ref: Any = None, relative_placement: Any = None
    ) -> Any:
        """Create a local placement with proper axis placement."""
        if relative_placement is None:
            z_dir = self.ifc.create_entity("IfcDirection", DirectionRatios=[0.0, 0.0, 1.0])
            x_dir = self.ifc.create_entity("IfcDirection", DirectionRatios=[1.0, 0.0, 0.0])
            origin = self.ifc.create_entity("IfcCartesianPoint", Coordinates=[0.0, 0.0, 0.0])
            relative_placement = self.ifc.create_entity(
                "IfcAxis2Placement3D",
                Location=origin,
                Axis=z_dir,
                RefDirection=x_dir
            )

        return self.ifc.create_entity(
            "IfcLocalPlacement",
            PlacementRelTo=placement_ref,
            RelativePlacement=relative_placement
        )

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
        # Create site
        site = self.ifc.create_entity(
            "IfcSite",
            GlobalId=self._create_guid(),
            OwnerHistory=self.owner_history,
            Name="Default Site",
            ObjectPlacement=self._create_local_placement(),
            CompositionType="ELEMENT"
        )
        
        # Create building
        building = self.ifc.create_entity(
            "IfcBuilding",
            GlobalId=self._create_guid(),
            OwnerHistory=self.owner_history,
            Name="Default Building",
            ObjectPlacement=self._create_local_placement(site.ObjectPlacement),
            CompositionType="ELEMENT"
        )
        
        # Create storey
        self.building_storey = self.ifc.create_entity(
            "IfcBuildingStorey",
            GlobalId=self._create_guid(),
            OwnerHistory=self.owner_history,
            Name="Ground Floor",
            ObjectPlacement=self._create_local_placement(building.ObjectPlacement),
            CompositionType="ELEMENT"
        )
        
        # Create aggregation relationships
        self._create_aggregation(self.project, [site])
        self._create_aggregation(site, [building])
        self._create_aggregation(building, [self.building_storey])
        
    def create_space(self, coordinates: List[Point3D], space_height: float, name: Optional[str] = None) -> None:
        """Create an IFC space with given coordinates and height."""
        # Simplify the polygon before creating the space
        simplified_coords = SVGGeometryParser.simplify_polygon(coordinates)
        
        if len(simplified_coords) < 4:
            print(f"Warning: Invalid polygon with {len(simplified_coords)} points - skipping")
            return

        space_placement = self._create_local_placement(
            self.building_storey.ObjectPlacement
        )
        
        ifc_space = self._create_spatial_element(
            "IfcSpace",
            name or "Space",
            space_placement
        )

        geometry = self._create_space_geometry(simplified_coords, space_height)
        ifc_space.Representation = geometry

        # Use IfcRelAggregates instead of IfcRelContainedInSpatialStructure
        self._create_aggregation(self.building_storey, [ifc_space])

    def _create_aggregation(self, relating_object: Any, related_objects: List[Any]) -> None:
        """Create an aggregation relationship."""
        self.ifc.create_entity(
            "IfcRelAggregates",
            GlobalId=self._create_guid(),
            OwnerHistory=self.owner_history,
            RelatingObject=relating_object,
            RelatedObjects=related_objects
        )
        
    def _create_space_geometry(self, coordinates: List[Point3D], space_height: float) -> Any:
        """Create the geometric representation of a space using extrusion."""
        # Create 2D points for the profile (without Z coordinate)
        points = [
            self.ifc.create_entity(
                "IfcCartesianPoint",
                Coordinates=(float(p.x), float(p.y))  # 2D coordinates
            )
            for p in coordinates[:-1]  # Exclude last point if it's duplicate
        ]
        
        # Close the polyline using the first point reference
        points.append(points[0])
        
        # Create the closed profile
        polyline = self.ifc.create_entity(
            "IfcPolyline",
            Points=points
        )
        
        profile_def = self.ifc.create_entity(
            "IfcArbitraryClosedProfileDef",
            ProfileType="AREA",
            OuterCurve=polyline
        )
        
        direction = self.ifc.create_entity(
            "IfcDirection",
            DirectionRatios=[0.0, 0.0, 1.0]
        )
        
        solid = self.ifc.create_entity(
            "IfcExtrudedAreaSolid",
            SweptArea=profile_def,
            Position=self.ifc.create_entity(
                "IfcAxis2Placement3D",
                Location=self.ifc.create_entity(
                    "IfcCartesianPoint",
                    Coordinates=[0.0, 0.0, 0.0]
                )
            ),
            ExtrudedDirection=direction,
            Depth=float(space_height)
        )
        
        # Create 2D footprint for representation
        footprint_points = [
            self.ifc.create_entity(
                "IfcCartesianPoint",
                Coordinates=(float(p.x), float(p.y))
            )
            for p in coordinates[:-1]
        ]
        footprint_points.append(footprint_points[0])
        
        footprint = self.ifc.create_entity(
            "IfcPolyline",
            Points=footprint_points
        )
        
        body_rep = self.ifc.create_entity(
            "IfcShapeRepresentation",
            ContextOfItems=self.context,
            RepresentationIdentifier="Body",
            RepresentationType="SweptSolid",
            Items=[solid]
        )
        
        footprint_rep = self.ifc.create_entity(
            "IfcShapeRepresentation",
            ContextOfItems=self.context,
            RepresentationIdentifier="FootPrint",
            RepresentationType="Curve2D",
            Items=[footprint]
        )
        
        return self.ifc.create_entity(
            "IfcProductDefinitionShape",
            Representations=[body_rep, footprint_rep]
        )


    def _create_faces(
        self, 
        bottom_vertices: List[Any], 
        top_vertices: List[Any],
        get_or_create_oriented_edge: Any
    ) -> List[Any]:
        """Create all faces for a space geometry."""
        faces = []
        
        def create_face_bounds(vertices, reverse=False):
            if reverse:
                vertices = list(reversed(vertices))
            
            edges = []
            for i in range(len(vertices)):
                next_i = (i + 1) % len(vertices)
                edges.append(get_or_create_oriented_edge(
                    vertices[i], 
                    vertices[next_i]
                ))
            
            edge_loop = self.ifc.create_entity(
                "IfcEdgeLoop",
                EdgeList=edges
            )
            return self.ifc.create_entity(
                "IfcFaceOuterBound",
                Bound=edge_loop,
                Orientation=True
            )

        # Bottom face
        faces.append(
            self.ifc.create_entity(
                "IfcFace",
                Bounds=[create_face_bounds(bottom_vertices)]
            )
        )

        # Top face (reversed orientation)
        faces.append(
            self.ifc.create_entity(
                "IfcFace",
                Bounds=[create_face_bounds(top_vertices, reverse=True)]
            )
        )

        # Vertical faces
        for i in range(len(bottom_vertices)):
            next_i = (i + 1) % len(bottom_vertices)
            vertices = [
                bottom_vertices[i],
                bottom_vertices[next_i],
                top_vertices[next_i],
                top_vertices[i]
            ]
            faces.append(
                self.ifc.create_entity(
                    "IfcFace",
                    Bounds=[create_face_bounds(vertices)]
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

    def _validate_geometry(self, points: List[Point3D]) -> bool:
        """Check if the geometry is valid (no self-intersections)."""
        # Special case for rectangles
        if len(points) == 5:  # Rectangles have 5 points (last point closes the shape)
            # Check if it's actually a rectangle by verifying perpendicular sides
            def is_perpendicular(p1: Point3D, p2: Point3D, p3: Point3D) -> bool:
                v1x, v1y = p2.x - p1.x, p2.y - p1.y
                v2x, v2y = p3.x - p2.x, p3.y - p2.y
                dot_product = v1x * v2x + v1y * v2y
                return abs(dot_product) < 0.001  # Allow small numerical errors
            
            is_rect = (
                is_perpendicular(points[0], points[1], points[2]) and
                is_perpendicular(points[1], points[2], points[3]) and
                is_perpendicular(points[2], points[3], points[0])
            )
            if is_rect:
                return True

        # For non-rectangular shapes, check for self-intersections
        def segments_intersect(p1: Point3D, p2: Point3D, p3: Point3D, p4: Point3D) -> bool:
            def ccw(A: Point3D, B: Point3D, C: Point3D) -> bool:
                return (C.y - A.y) * (B.x - A.x) > (B.y - A.y) * (C.x - A.x)
            return ccw(p1, p3, p4) != ccw(p2, p3, p4) and ccw(p1, p2, p3) != ccw(p1, p2, p4)
        
        n = len(points)
        for i in range(n-1):
            for j in range(i+2, n-1):
                if segments_intersect(points[i], points[i+1], points[j], points[j+1]):
                    return False
        return True

    @staticmethod
    def _create_guid() -> str:
        """Create a new valid IFC GUID."""
        return ifcopenshell.guid.compress(uuid.uuid4().hex)



def create_ifc_space_model(
    svg_file: str,
    ifc_file: str,
    space_height: float
) -> None:
    """Create an IFC model from SVG file containing rectangles and paths."""
    paths, attributes, svg_attributes = svg2paths2(svg_file)
    
    model_creator = IfcModelCreator()
    model_creator.create_owner_history()
    model_creator.create_project_context()
    model_creator.create_spatial_hierarchy()

    # Handle both rectangles and paths
    for i, (path, attr) in enumerate(zip(paths, attributes)):
        space_name = attr.get('id', f'Space_{i}')
        
        if attr.get('d'):  # SVG path
            coordinates = SVGGeometryParser.parse_path(path)
            if coordinates:
                model_creator.create_space(coordinates, space_height, space_name)
        
        elif all(key in attr for key in ['x', 'y', 'width', 'height']):  # SVG rect
            coordinates = SVGGeometryParser.parse_rect(attr)
            model_creator.create_space(coordinates, space_height, space_name)

    model_creator.ifc.write(ifc_file)
    print("model created")


svg_input = "test/groundfloor_test1.svg"
ifc_output = "output.ifc"
space_height = 5
create_ifc_space_model(svg_input, ifc_output, space_height)