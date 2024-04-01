import os
import glob
from skimage.morphology import skeletonize
import arcpy
import rasterio
import geopandas as gpd
import rasterio.transform

gdb_path = "D:/IWP_net.gdb"
arcpy.env.workspace = gdb_path

def extract_network(dir):
    for shp_file in glob.glob(os.path.join(dir, '*.shp')):
        print("Processing shapefile:", shp_file)
        # Extract basename to use in output filename
        new_file_name = os.path.splitext(os.path.basename(shp_file))[0].replace('-', '_')

        # Output filenames
        out_buff_path = os.path.join("D:/manuscripts/Chandi_Anna_Nature/IWP_net_out", "%s_buffer.shp" % new_file_name)
        # out_erase_path = os.path.join("D:/manuscripts/Chandi_Anna_Nature/IWP_net_out", "%s_erase.shp" % new_file_name)
        out_buff_ras = os.path.join("D:/manuscripts/Chandi_Anna_Nature/IWP_net_out", "%s_buffer.tif" % new_file_name[:20])
        out_skeleton_ras = os.path.join("D:/manuscripts/Chandi_Anna_Nature/IWP_net_out", "%s_skeleton.tif" % new_file_name)
        out_polyline_path = os.path.join("D:/manuscripts/Chandi_Anna_Nature/IWP_net_out", "%s_IWP_net.shp" % new_file_name)

        # # Run the shapefile through Repair Geometry first to avoid any issues
        # print("Repairing geometry...")
        # arcpy.management.RepairGeometry(shp_file)

        # Load the shapefile of IWP detection
        print("Reading input shapefile of IWP features...")
        gdf = gpd.read_file(shp_file)

        # Apply a 5 meter buffer to each polygon
        print("Creating buffer of IWP features...")
        buffered_polygons = []
        for geom in gdf.geometry:
            buffered_polygon = geom.buffer(5)
            outer_buffer = buffered_polygon.difference(geom)  # Remove the inner portion of the buffer
            buffered_polygons.append(outer_buffer)

        print("Saving buffer shapefile...")
        # Convert the buffered polygons to a GeoDataFrame and save to shapefile
        gdf_buffered = gpd.GeoDataFrame(geometry=buffered_polygons, crs=gdf.crs)
        # Add a new field named "Value" and populate it with a constant value of 1
        gdf_buffered['Value'] = 1
        gdf_buffered.to_file(out_buff_path)

        # Convert IWP outer buffer to raster
        print("Converting IWP outer buffer to raster...")
        arcpy.conversion.PolygonToRaster(out_buff_path, "Value", out_buff_ras, cellsize=0.5)

        # Read the input GeoTIFF file
        print("Reading input GeoTIFF...")
        with rasterio.open(out_buff_ras) as src:
            # Read the raster data
            raster_data = src.read(1)
            # Extract metadata
            transform = src.transform
            crs = src.crs

        # Skeletonize the raster data
        print("Skeletonizing GeoTIFF...")
        skeleton = skeletonize(raster_data)

        # Save the skeletonized GeoTIFF before polygonization
        print("Saving skeletonized GeoTIFF...")
        with rasterio.open(out_skeleton_ras, 'w', driver='GTiff', width=skeleton.shape[1],
                           height=skeleton.shape[0], count=1, dtype='uint8', crs=crs, transform=transform) as dst:
            dst.write(skeleton.astype('uint8'), 1)

        # Convert skeletonized raster to polyline shapefile
        print("Converting buffer skeleton raster to polyline shapefile...")
        arcpy.conversion.RasterToPolyline(out_skeleton_ras, out_polyline_path)

        # Delete files at all paths except out_polyline_path
        paths_to_delete = [out_buff_path, out_buff_ras, out_skeleton_ras]
        for path in paths_to_delete:
            if arcpy.Exists(path):
                arcpy.Delete_management(path)



def clip_polyline_to_footprint(polyline_dir, footprint_shp, output_dir):

    # Create a feature layer from the footprint shapefile
    arcpy.management.MakeFeatureLayer(footprint_shp, "footprint_lyr")

    # Loop through each polyline shapefile
    for polyline_file in os.listdir(polyline_dir):
        if polyline_file.endswith(".shp"):
            # Extract the filename match without the suffix
            filename_match = os.path.splitext(polyline_file)[0].replace('_u16rf3413_pansh_IWP_net', '').replace('-', '_')
            print(filename_match)

            # Find the corresponding footprint by matching the filename
            where_clause = f"Name = '{filename_match}'"
            arcpy.management.SelectLayerByAttribute("footprint_lyr", "NEW_SELECTION", where_clause)

            # Check if any features are selected
            if int(arcpy.management.GetCount("footprint_lyr").getOutput(0)) > 0:
                # Perform the clip operation
                output_filename = os.path.join(output_dir, f"{filename_match}_clipped.shp")
                arcpy.analysis.PairwiseClip(os.path.join(polyline_dir, polyline_file), "footprint_lyr", output_filename)

                print(f"Clipped polyline saved to {output_filename}")
            else:
                print(f"No matching footprint found for {polyline_file}")

    # Clean up
    arcpy.management.Delete("footprint_lyr")


def calculate_polylines_length(directory):
    total_length_km = 0
    lengths_km = []

    # Loop through all files in the directory
    for filename in os.listdir(directory):
        if filename.endswith(".shp"):
            print(f"Processing {filename}...")
            # Read the polyline shapefile
            polyline_gdf = gpd.read_file(os.path.join(directory, filename))

            # Calculate the length of the polylines in kilometers
            length_km = polyline_gdf.length.sum() / 1000  # Converting to kilometers
            lengths_km.append(length_km)
            total_length_km += length_km
            print(f"Length of {filename}: {length_km:.2f} km")

    return lengths_km, total_length_km


# Directories for processing

# Input directory containing IWP detection shapefiles for Banks Island
input_dir = 'D:/manuscripts/Chandi_Anna_Nature/Banks_Island_watershed_IWPs'
# Directory which will contain the extracted polyline shapefiles
polyline_dir = "D:/manuscripts/Chandi_Anna_Nature/IWP_net_out"
# Path to the image footprint shapefile with overlaps removed
footprint_shp = "D:/manuscripts/Chandi_Anna_Nature/BanksIsland_FPs_noOverlap.shp"
# Directory which will contain the polyline shapefiles clipped to the overlap-removed footprints
clipped_line_dir = "D:/manuscripts/Chandi_Anna_Nature/IWP_net_out_clipped"

# Extract polyline shapefile of ice-wedge network from ice-wedge polygon detection shapefile
# extract_network(input_dir)

# Clip polyline shapefiles to original image footprint which had overlaps removed
# clip_polyline_to_footprint(polyline_dir, footprint_shp, clipped_line_dir)

# Calculate lengths of polylines and their sum
polylines_lengths, total_length = calculate_polylines_length(clipped_line_dir)

print("\nSummary:")
for idx, length_km in enumerate(polylines_lengths, start=1):
    print(f"Polyline {idx}: {length_km:.2f} km")

print(f"Total length of all polylines: {total_length:.2f} km")





