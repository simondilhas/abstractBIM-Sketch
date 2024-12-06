import ifcopenshell
import ifcopenshell.geom
from typing import Dict, List, Tuple
import numpy as np

def get_space_geometry(space, settings) -> List[Tuple[float, float]]:
    """Get 2D points from tessellated space geometry"""
    try:
        shape = ifcopenshell.geom.create_shape(settings, space)
        verts = shape.geometry.verts
        
        points_3d = [(verts[i], verts[i+1], verts[i+2]) for i in range(0, len(verts), 3)]
        
        if not points_3d:
            return []
            
        bottom_z = min(p[2] for p in points_3d)
        bottom_points = [(p[0], p[1]) for p in points_3d if abs(p[2] - bottom_z) < 0.01]
        
        unique_points = list({(round(x, 5), round(y, 5)) for x, y in bottom_points})
        if not unique_points:
            return []
            
        center = np.mean(unique_points, axis=0)
        sorted_points = sorted(unique_points, 
                             key=lambda p: np.arctan2(p[1]-center[1], p[0]-center[0]))
        
        return sorted_points
    except Exception as e:
        print(f"Error processing space {space.GlobalId}: {str(e)}")
        return []

def get_spaces_by_storey(ifc_file) -> Dict[str, List]:
    """Get all spaces organized by storey"""
    spaces_by_storey = {}
    
    # Get all spaces and their containing storeys through decomposition
    for space in ifc_file.by_type('IfcSpace'):
        # Get containing storey through decomposition relationship
        for rel in space.Decomposes:
            if rel.RelatingObject.is_a('IfcBuildingStorey'):
                storey = rel.RelatingObject
                if storey.GlobalId not in spaces_by_storey:
                    spaces_by_storey[storey.GlobalId] = {
                        'storey': storey,
                        'spaces': []
                    }
                spaces_by_storey[storey.GlobalId]['spaces'].append(space)
                break
    
    return spaces_by_storey

def process_ifc(file_path: str) -> str:
    """Process IFC file and create SVG"""
    settings = ifcopenshell.geom.settings()
    settings.set(settings.USE_WORLD_COORDS, True)
    
    ifc_file = ifcopenshell.open(file_path)
    
    project = ifc_file.by_type("IfcProject")[0]
    site = ifc_file.by_type("IfcSite")[0]
    building = ifc_file.by_type("IfcBuilding")[0]
    
    project_data = {
        "name": project.Name or "Unnamed Project",
        "guid": project.GlobalId,
        "site": site.Name or "Unnamed Site",
        "site_guid": site.GlobalId,
        "building": building.Name or "Unnamed Building",
        "building_guid": building.GlobalId
    }
    
    spaces_by_storey = get_spaces_by_storey(ifc_file)
    spaces_by_level = {}
    
    for storey_guid, data in spaces_by_storey.items():
        storey = data['storey']
        elevation = float(storey.Elevation or 0)
        
        for space in data['spaces']:
            points = get_space_geometry(space, settings)
            if not points:
                continue
                
            space_data = {
                "guid": space.GlobalId,
                "long_name": space.LongName or space.Name or "Unnamed Space",
                "storey": storey.Name or f"Level {elevation}",
                "storey_guid": storey.GlobalId,
                "points": points
            }
            
            if elevation not in spaces_by_level:
                spaces_by_level[elevation] = []
            spaces_by_level[elevation].append(space_data)
    
    return create_svg(spaces_by_level, project_data)

def create_svg(spaces_by_level: Dict[float, List[dict]], project_data: dict) -> str:
    """Generate SVG with Inkscape template structure"""
    svg_header = f'''<?xml version="1.0" encoding="UTF-8" standalone="no"?>
<svg
    width="10000cm"
    height="10000cm"
    viewBox="0 0 100000 100000"
    version="1.1"
    id="svg1"
    inkscape:version="1.4 (e7c3feb100, 2024-10-09)"
    sodipodi:docname="ifc_spaces.svg"
    xmlns:inkscape="http://www.inkscape.org/namespaces/inkscape"
    xmlns:sodipodi="http://sodipodi.sourceforge.net/DTD/sodipodi-0.dtd"
    xmlns="http://www.w3.org/2000/svg"
    xmlns:svg="http://www.w3.org/2000/svg">
'''

    namedview = '''    <sodipodi:namedview
        id="namedview1"
        pagecolor="#ffffff"
        bordercolor="#000000"
        borderopacity="0.25"
        inkscape:showpageshadow="2"
        inkscape:pageopacity="0.0"
        inkscape:pagecheckerboard="0"
        inkscape:deskcolor="#d1d1d1"
        inkscape:document-units="cm"
        showguides="true"
        inkscape:zoom="0.01"
        inkscape:cx="188950"
        inkscape:cy="127550"
        inkscape:window-width="1832"
        inkscape:window-height="1076"
        inkscape:window-x="0"
        inkscape:window-y="0"
        inkscape:window-maximized="1"
        inkscape:current-layer="layer3"
        showgrid="true">
        <inkscape:grid
            id="grid1"
            units="cm"
            originx="0"
            originy="0"
            spacingx="125"
            spacingy="125"
            empcolor="#0099e5"
            empopacity="0.30196078"
            color="#0099e5"
            opacity="0.14901961"
            empspacing="5"
            enabled="true"
            visible="true"
            dotted="false" />
    </sodipodi:namedview>
    <defs id="defs1" />
'''

    # Start main content
    svg_content = f'''    <g
        inkscape:groupmode="layer"
        id="{project_data['guid']}"
        inkscape:label="Project={project_data['name']}">
        <g
            inkscape:groupmode="layer"
            id="{project_data['site_guid']}"
            inkscape:label="Site={project_data['site']}">
            <g
                inkscape:groupmode="layer"
                id="{project_data['building_guid']}"
                inkscape:label="Building={project_data['building']}"
                style="display:inline">
'''

    # Add storeys and spaces
    for height, spaces in spaces_by_level.items():
        storey_guid = spaces[0]['storey_guid']
        svg_content += f'''                <g
                    inkscape:groupmode="layer"
                    id="{storey_guid}"
                    inkscape:label="Storey={spaces[0]['storey']}, h={height}">
                    <g
                        inkscape:groupmode="layer"
                        id="space_{storey_guid}"
                        inkscape:label="Space, h={height}">
'''
        
        for space in spaces:
            points = space['points']
            if points:
                path_data = f"M {points[0][0]},{points[0][1]}"
                for point in points[1:]:
                    path_data += f" L {point[0]},{point[1]}"
                path_data += " Z"
                
                svg_content += f'''                        <path
                            id="{space['guid']}"
                            d="{path_data}"
                            inkscape:label="{space['long_name']}"
                            style="fill:#c83737;stroke:#000000;stroke-width:0.1"/>
'''
                
        svg_content += '''                    </g>
                </g>
'''

    # Close building, site, project layers
    svg_content += '''            </g>
        </g>
    </g>
    <g
        inkscape:groupmode="layer"
        id="layer4"
        inkscape:label="Help" />
</svg>'''

    return svg_header + namedview + svg_content

if __name__ == "__main__":
    svg_content = process_ifc("test/Mustermodell V2.ifc")
    with open("output/ifc_to_svg.svg", "w") as f:
        f.write(svg_content)