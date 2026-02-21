# Take existing Lab_4.py and create Lab_5.pyt
import arcpy
import os

class Toolbox(object):
    def __init__(self):
        self.label = "Lab 5 Toolbox"
        self.alias = "lab5"
        self.tools = [BuildingProximityTool]

class BuildingProximityTool(object):
    def __init__(self):
        self.label = "Building Proximity Tool"
        self.description = "Create garage points from CSV, buffer them, intersect with campus structures, export CSV."
        self.canRunInBackground = False
        self.category = "Lab 5"

    def getParameterInfo(self):
        # Folder where outputs will be written
        p0 = arcpy.Parameter(
            displayName="Output Folder (Lab_5 folder)",
            name="out_folder",
            datatype="DEFolder",
            parameterType="Required",
            direction="Input"
        )

        # Output GDB name
        p1 = arcpy.Parameter(
            displayName="Output GDB Name",
            name="out_gdb_name",
            datatype="GPString",
            parameterType="Required",
            direction="Input"
        )
        p1.value = "Lab5_Output.gdb"

        # Garage CSV file (Lab_4)
        p2 = arcpy.Parameter(
            displayName="Garage CSV File",
            name="garage_csv",
            datatype="DEFile",
            parameterType="Required",
            direction="Input"
        )

        # Campus GDB (Lab_4)
        p3 = arcpy.Parameter(
            displayName="Campus GDB",
            name="campus_gdb",
            datatype="DEWorkspace",
            parameterType="Required",
            direction="Input"
        )

        # Structures feature class name in Campus.gdb (Lab_4)
        p4 = arcpy.Parameter(
            displayName="Structures Feature Class Name",
            name="structures_name",
            datatype="GPString",
            parameterType="Required",
            direction="Input"
        )
        p4.value = "Structures"

        # Buffer distance (meters)
        p5 = arcpy.Parameter(
            displayName="Buffer Distance (meters)",
            name="buffer_m",
            datatype="GPDouble",
            parameterType="Required",
            direction="Input"
        )
        p5.value = 150

        # Output CSV name
        p6 = arcpy.Parameter(
            displayName="Output CSV Name",
            name="out_csv_name",
            datatype="GPString",
            parameterType="Required",
            direction="Input"
        )
        p6.value = "garage_structure_intersect.csv"

        return [p0, p1, p2, p3, p4, p5, p6]

    def execute(self, parameters, messages):
        arcpy.env.overwriteOutput = True

        out_folder   = parameters[0].valueAsText
        out_gdb_name = parameters[1].valueAsText
        garage_csv   = parameters[2].valueAsText
        campus_gdb   = parameters[3].valueAsText
        structures_name = parameters[4].valueAsText
        buffer_m     = float(parameters[5].value)
        out_csv_name = parameters[6].valueAsText

        # Build directory paths
        out_gdb = os.path.join(out_folder, out_gdb_name)
        structures_src = os.path.join(campus_gdb, structures_name)

        # Output feature class names into output gdb
        garages_fc       = os.path.join(out_gdb, "Garages")
        structures_copy  = os.path.join(out_gdb, "Structures_Copy")
        garages_proj     = os.path.join(out_gdb, "Garages_Proj")
        garages_buffer   = os.path.join(out_gdb, "Garages_Buffer")
        intersect_fc     = os.path.join(out_gdb, "Garage_Structures_Intersect")

        out_csv = os.path.join(out_folder, out_csv_name)

        # Create output GDB
        if not arcpy.Exists(out_gdb):
            arcpy.AddMessage(f"Creating output geodatabase: {out_gdb}")
            arcpy.management.CreateFileGDB(out_folder, out_gdb_name)
        else:
            arcpy.AddMessage(f"Using existing output geodatabase: {out_gdb}")

        # Copy Structures into output GDB
        if arcpy.Exists(structures_copy):
            arcpy.management.Delete(structures_copy)
        arcpy.AddMessage("Copying campus structures into output GDB...")
        arcpy.management.CopyFeatures(structures_src, structures_copy)

        # Detect X/Y fields from the CSV
        fields = [f.name for f in arcpy.ListFields(garage_csv)]
        possible_x = ["X", "x", "Lon", "lon", "Longitude", "longitude"]
        possible_y = ["Y", "y", "Lat", "lat", "Latitude", "latitude"]

        x_field = next((f for f in fields if f in possible_x), None)
        y_field = next((f for f in fields if f in possible_y), None)

        if x_field is None or y_field is None:
            raise ValueError(f"Could not detect X/Y fields. CSV has: {fields}. Rename to X and Y or Lon/Lat.")

        arcpy.AddMessage(f"Detected X field: {x_field}, Y field: {y_field}")

        # Make XY Event Layer and copy to feature class
        wgs84 = arcpy.SpatialReference(4326)
        xy_layer = "garages_xy_layer"

        if arcpy.Exists(garages_fc):
            arcpy.management.Delete(garages_fc)

        arcpy.AddMessage("Creating garage points from CSV...")
        arcpy.management.MakeXYEventLayer(garage_csv, x_field, y_field, xy_layer, wgs84)
        arcpy.management.CopyFeatures(xy_layer, garages_fc)

        # Project garages to match structures
        structures_sr = arcpy.Describe(structures_copy).spatialReference

        if arcpy.Exists(garages_proj):
            arcpy.management.Delete(garages_proj)

        arcpy.AddMessage("Projecting garages to match Structures spatial reference...")
        arcpy.management.Project(garages_fc, garages_proj, structures_sr)

        # Buffer garages
        if arcpy.Exists(garages_buffer):
            arcpy.management.Delete(garages_buffer)

        arcpy.AddMessage(f"Buffering garages by {buffer_m} meters...")
        arcpy.analysis.Buffer(garages_proj, garages_buffer, f"{buffer_m} Meters")

        # Intersect Structures with garage buffers
        if arcpy.Exists(intersect_fc):
            arcpy.management.Delete(intersect_fc)

        arcpy.AddMessage("Intersecting Structures with garage buffers...")
        arcpy.analysis.Intersect([structures_copy, garages_buffer], intersect_fc)

        # Export intersect to CSV
        if os.path.exists(out_csv):
            os.remove(out_csv)

        arcpy.AddMessage(f"Exporting intersect table to CSV: {out_csv}")
        arcpy.conversion.TableToTable(intersect_fc, out_folder, os.path.basename(out_csv))

        # Print row count
        count = int(arcpy.management.GetCount(intersect_fc)[0])
        arcpy.AddMessage(f"Intersect row count: {count}")
        arcpy.AddMessage("DONE")