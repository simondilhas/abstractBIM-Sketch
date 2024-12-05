from dataclasses import dataclass
import xml.etree.ElementTree as ET
from typing import List, Tuple, Dict, Any, Optional, Callable
import ifcopenshell
import svgpathtools
from svgpathtools import svg2paths2
import uuid
import time
from ifcopenshell.file import file as IfcFile
from svg.path import Path
import ifcopenshell.guid
import os


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
        self.building = None
        self.storeys = {}  # Store storeys by name
        self.geometry_parser = SVGGeometryParser()

    @staticmethod
    def _create_guid() -> str:
        """Create a new valid IFC GUID."""
        return ifcopenshell.guid.compress(uuid.uuid4().hex)


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

    def create_project_context(self, project_name="Default Project 1") -> None:
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
            Name=project_name,
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

    def create_spatial_hierarchy(self, site_name: str = "Default Site", building_name: str = "Default Building") -> None:
            site = self.ifc.create_entity(
                "IfcSite",
                GlobalId=self._create_guid(),
                OwnerHistory=self.owner_history,
                Name=site_name,
                ObjectPlacement=self._create_local_placement(),
                CompositionType="ELEMENT"
            )
                    
            self.building = self.ifc.create_entity(
                "IfcBuilding",
                GlobalId=self._create_guid(),
                OwnerHistory=self.owner_history,
                Name=building_name,
                ObjectPlacement=self._create_local_placement(site.ObjectPlacement),
                CompositionType="ELEMENT"
            )
            
            self._create_aggregation(self.project, [site])
            self._create_aggregation(site, [self.building])

    def create_storey(self, name: str, height: float) -> None:
        """Create a building storey at specified height."""
        origin = self.ifc.create_entity(
            "IfcCartesianPoint", 
            Coordinates=(0.0, 0.0, float(height))  # Convert to tuple of floats
        )
        axis_placement = self.ifc.create_entity(
            "IfcAxis2Placement3D",
            Location=origin
        )
        storey_placement = self._create_local_placement(
            self.building.ObjectPlacement,
            axis_placement
        )
        
        storey = self.ifc.create_entity(
            "IfcBuildingStorey",
            GlobalId=self._create_guid(),
            OwnerHistory=self.owner_history,
            Name=name,
            ObjectPlacement=storey_placement,
            CompositionType="ELEMENT"
        )
        
        self._create_aggregation(self.building, [storey])
        self.storeys[name] = storey


    def create_space(self, coordinates: List[Point3D], space_height: float, storey_name: str, long_name: Optional[str] = None) -> None:
        storey = self.storeys.get(storey_name)
        if not storey:
            print(f"Warning: Storey {storey_name} not found - skipping space")
            return
        simplified_coords = SVGGeometryParser.simplify_polygon(coordinates)
        if len(simplified_coords) < 4:
            print(f"Warning: Invalid polygon with {len(simplified_coords)} points - skipping")
            return
        space_placement = self._create_local_placement(storey.ObjectPlacement)
        ifc_space = self._create_spatial_element(
            "IfcSpace",
            long_name or "Space",
            space_placement
        )
        ifc_space.LongName = long_name
        geometry = self._create_space_geometry(simplified_coords, space_height)
        ifc_space.Representation = geometry
        self._create_aggregation(storey, [ifc_space])

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

def process_svg_layers(svg_file: str, output_dir: str) -> None:
    tree = ET.parse(svg_file)
    root = tree.getroot()
    ns = {'inkscape': 'http://www.inkscape.org/namespaces/inkscape'}
    
    project_layer = root.find(".//*[@inkscape:label='Project=Testprojekt']", ns)
    project_name = project_layer.get(f'{{{ns["inkscape"]}}}label').split('=')[1]
    
    site_layer = root.find(".//*[@inkscape:label='Site=Perimeter1']", ns)
    site_name = site_layer.get(f'{{{ns["inkscape"]}}}label').split('=')[1]

    # Cache paths data
    paths, attributes, svg_attributes = svg2paths2(svg_file)
    path_dict = {}
    
    for i, (path, attr) in enumerate(zip(paths, attributes)):
        path_dict[attr.get('d', '')] = path

    def parse_transform_matrix(transform_str):
        if not transform_str or 'matrix' not in transform_str:
            return None
        values = [float(x) for x in transform_str.split('(')[1].split(')')[0].split(',')]
        return values

    def apply_transform(point: Point3D, matrix) -> Point3D:
        if not matrix:
            return point
        x = point.x * matrix[0] + point.y * matrix[2] + matrix[4]
        y = point.x * matrix[1] + point.y * matrix[3] + matrix[5]
        return Point3D(x, y)

    def get_accumulated_transform(element):
        transform_matrix = None
        current = element
        while current is not None and current != root:
            transform = current.get('transform')
            if transform:
                matrix = parse_transform_matrix(transform)
                if matrix:
                    if transform_matrix is None:
                        transform_matrix = matrix
                    else:
                        a1, b1, c1, d1, e1, f1 = transform_matrix
                        a2, b2, c2, d2, e2, f2 = matrix
                        transform_matrix = [
                            a1*a2 + c1*b2,
                            b1*a2 + d1*b2,
                            a1*c2 + c1*d2,
                            b1*c2 + d1*d2,
                            a1*e2 + c1*f2 + e1,
                            b1*e2 + d1*f2 + f1
                        ]
            current = current.getparent() if hasattr(current, 'getparent') else None
        return transform_matrix

    def process_space_elements(space_layer, space_height, unique_storey_name, creator, path_dict):
        """Helper function to process all elements in a space layer recursively"""
        for elem in space_layer:
            tag = elem.tag.split('}')[-1]
            space_name = elem.get(f'{{{ns["inkscape"]}}}label') or "Default Space"
            
            transform_matrix = get_accumulated_transform(elem)
            
            coords = None
            if tag == 'rect':
                coords = creator.geometry_parser.parse_rect(elem.attrib)
            elif tag == 'path':
                d = elem.get('d')
                if d and d in path_dict:
                    coords = creator.geometry_parser.parse_path(path_dict[d])
                else:
                    print(f"Warning: Path data not found for space {space_name}")
            
            if coords:
                if transform_matrix:
                    coords = [apply_transform(point, transform_matrix) for point in coords]
                creator.create_space(coords, space_height, unique_storey_name, space_name)

            # Recursively process child elements
            for child in elem:
                child_tag = child.tag.split('}')[-1]
                if child_tag in ['rect', 'path']:
                    space_name = child.get(f'{{{ns["inkscape"]}}}label') or "Default Space"
                    transform_matrix = get_accumulated_transform(child)
                    
                    coords = None
                    if child_tag == 'rect':
                        coords = creator.geometry_parser.parse_rect(child.attrib)
                    elif child_tag == 'path':
                        d = child.get('d')
                        if d and d in path_dict:
                            coords = creator.geometry_parser.parse_path(path_dict[d])
                        else:
                            print(f"Warning: Path data not found for space {space_name}")
                    
                    if coords:
                        if transform_matrix:
                            coords = [apply_transform(point, transform_matrix) for point in coords]
                        creator.create_space(coords, space_height, unique_storey_name, space_name)

    for building_layer in site_layer.findall("*[@inkscape:label]", ns):
        label = building_layer.get(f'{{{ns["inkscape"]}}}label')
        if not label.startswith('Building='):
            continue
            
        building_name = label.split('=')[1]
        ifc_file = f"{output_dir}/{project_name}_{building_name}.ifc"
        
        creator = IfcModelCreator()
        creator.create_owner_history()
        creator.create_project_context(project_name=project_name)
        creator.create_spatial_hierarchy(site_name=site_name, building_name=building_name)
        
        # Dictionary to keep track of storey names and their count
        storey_names = {}
        
        # First pass to collect all storey names
        for storey_layer in building_layer.findall(".//*[@inkscape:label]", ns):
            storey_label = storey_layer.get(f'{{{ns["inkscape"]}}}label')
            if not storey_label.startswith('Storey='):
                continue
                
            parts = storey_label.split(',')
            storey_name = parts[0].split('=')[1].strip()
            storey_names[storey_name] = storey_names.get(storey_name, 0) + 1
        
        # Print warning for duplicate storey names
        duplicates = {name: count for name, count in storey_names.items() if count > 1}
        if duplicates:
            print(f"Warning: Found duplicate storey names in building {building_name}:")
            for name, count in duplicates.items():
                print(f"  - '{name}' appears {count} times")
        
        # Reset counters for the second pass
        name_counters = {name: 1 for name in storey_names.keys()}
        
        # Process each storey
        for storey_layer in building_layer.findall(".//*[@inkscape:label]", ns):
            storey_label = storey_layer.get(f'{{{ns["inkscape"]}}}label')
            if not storey_label.startswith('Storey='):
                continue
                
            parts = storey_label.split(',')
            original_storey_name = parts[0].split('=')[1].strip()
            z_position = float(parts[1].split('h=')[1].strip())
            
            # Generate unique name if necessary
            if storey_names[original_storey_name] > 1:
                unique_storey_name = f"{original_storey_name}_{name_counters[original_storey_name]}"
                name_counters[original_storey_name] += 1
            else:
                unique_storey_name = original_storey_name
            
            creator.create_storey(unique_storey_name, z_position)

            # Process spaces in this storey
            for space_layer in storey_layer.findall(".//*[@inkscape:label]", ns):
                space_label = space_layer.get(f'{{{ns["inkscape"]}}}label')
                if not space_label or 'Space' not in space_label:
                    continue

                try:
                    if 'h=' in space_label:
                        space_height = float(space_label.split('h=')[1].strip())
                        print(f"Found space group height: {space_height}")
                        process_space_elements(space_layer, space_height, unique_storey_name, creator, path_dict)

                except (IndexError, ValueError) as e:
                    print(f"Error processing space group with label '{space_label}': {str(e)}")
                    print("Skipping this space group and continuing...")
                    continue

        os.makedirs(output_dir, exist_ok=True)
        creator.ifc.write(ifc_file)