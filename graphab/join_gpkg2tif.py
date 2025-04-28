#!/usr/bin/python

# To run on Ubuntu VM:
# python3 ./join_gpkg2tif.py

import datetime
import os
import sys
from osgeo import gdal, ogr
import re
import argparse

print("Logs are redirected to /logs")
sys.stdout = open('logs/join_gpkg2tif.log', 'w') #to log
sys.stderr = sys.stdout

def open_tiff(tif_path):
    """Opens a TIFF file and returns the dataset and its spatial properties."""
    tif_ds = gdal.Open(tif_path, gdal.GA_ReadOnly)
    if tif_ds is None:
        print(f"Error: Could not open TIFF file {tif_path}")
        return None, None, None, None
    
    geotransform = tif_ds.GetGeoTransform()
    projection = tif_ds.GetProjection()
    nodata_value = tif_ds.GetRasterBand(1).GetNoDataValue()
    return tif_ds, geotransform, projection, nodata_value

def create_output_tiff(output_path, x_size, y_size, dtype, geotransform, projection, nodata_value, compression="COMPRESS=LZW"):
    """Creates an output TIFF with specified parameters."""
    driver = gdal.GetDriverByName('GTiff')
    output_ds = driver.Create(output_path, x_size, y_size, 1, dtype, options=[compression])
    if output_ds is None:
        print(f"Error: Could not create output TIFF {output_path}")
        return None
    
    output_ds.SetGeoTransform(geotransform)
    output_ds.SetProjection(projection)
    output_band = output_ds.GetRasterBand(1)
    output_band.SetNoDataValue(nodata_value)
    
    return output_ds, output_band

def get_relevant_fields(layer, exclude_fields):
    """Returns a list of field names excluding specified fields."""
    return [field.name for field in layer.schema if field.name not in exclude_fields]

def extract_timestamp_xml(input_file):
    current_dir = os.path.dirname(input_file)
    
    xml_files = [f for f in os.listdir(current_dir) if f.endswith('.xml') and not f.endswith('aux.xml')] # check current dir for xml files

    if not xml_files: # if xml not found
        parent_dir = os.path.dirname(current_dir)
        xml_files = [f for f in os.listdir(parent_dir) if f.endswith('.xml') and not f.endswith('aux.xml')]
    
    if xml_files: # if xml found
        xml_filename = xml_files[0]  # take the first XML file found
        print(xml_filename)
        # Extract the year from the XML filename (assuming the year is at the end of the filename)
        year_match = re.search(r'(\d{4})\.xml$', xml_filename)
        
        if year_match:
            year = year_match.group(1)  # Extract the year
            timestamp = f"{year}-12-31 23:59:59"
            return timestamp
        else:
            print("No valid year found in the XML filename.")
            return None
    else:
        print("No .xml file found in the current or parent directory.")
        return None

def rasterize_geopackage(gpkg_path, tif_ds, output_tif_path, gdal_dtype, exclude_fields):
    """Rasterises each relevant field from the GeoPackage into a separate TIFF."""
    x_size, y_size = tif_ds.RasterXSize, tif_ds.RasterYSize
    geotransform, projection, nodata_value = tif_ds.GetGeoTransform(), tif_ds.GetProjection(), tif_ds.GetRasterBand(1).GetNoDataValue()

    gpkg_ds = ogr.Open(gpkg_path)
    if gpkg_ds is None:
        print(f"Error: Could not open GeoPackage {gpkg_path}")
        return
    
    timestamp = extract_timestamp_xml(gpkg_path) # extract timestamp
    
    for layer_index in range(gpkg_ds.GetLayerCount()):
        layer = gpkg_ds.GetLayerByIndex(layer_index)
        field_names = get_relevant_fields(layer, exclude_fields)

        for field in field_names:
            print(f"Processing field: {field}")
            
            # create output tiff for the current field
            field_output_tif = output_tif_path.replace(".tif", f"_{field}.tif")
            output_tif_ds, output_band = create_output_tiff(field_output_tif, x_size, y_size, gdal_dtype, geotransform, projection, nodata_value)
            if output_tif_ds is None:
                continue
            
            # rasterize layer
            gdal.RasterizeLayer(output_tif_ds, [1], layer, options=["ATTRIBUTE=" + field], burn_values=[nodata_value])
            
            # write index name to metadata
            index_name = field.split('_')[0] # first part of index name
            description = f"INDEX:{index_name}; TIMESTAMP:{timestamp}"
            software_name = "Graphab (c) Foltete JC, Vuidel G, Clauzel C et al. Licensed under GNU GPL."
            output_tif_ds.SetMetadataItem("TIFFTAG_IMAGEDESCRIPTION", description)
            output_tif_ds.SetMetadataItem("TIFFTAG_SOFTWARE", software_name)

            print(f"Field '{field}' rasterized to {field_output_tif}.")
            print(f"Metadata set: {description}")
            
            output_tif_ds.FlushCache()
            output_tif_ds = None
    
    gpkg_ds = None

def find_patch_files(base_path):
    """Searches for 'patches.tif' and 'patches.gpkg' in the directory tree."""
    patch_files = {}

    for root, _, files in os.walk(base_path):
        tif_path = os.path.join(root, "patches.tif") if "patches.tif" in files else None
        gpkg_path = os.path.join(root, "patches.gpkg") if "patches.gpkg" in files else None
        
        if tif_path and gpkg_path:
            patch_files[root] = (tif_path, gpkg_path)

    return patch_files

def find_corridor_files(base_path):
    """Searches for .tif files with 'corridor' in their name within the directory tree."""
    corridor_files = {}

    for root, _, files in os.walk(base_path):
        for file in files:
            if file.endswith(".tif") and "corridor" in file.lower():
                file_path = os.path.join(root, file)
                if root not in corridor_files:
                    corridor_files[root] = []
                corridor_files[root].append(file_path)
    print(f"COrridor files are: {corridor_files}")
    return corridor_files

def assign_metadata_corridors(base_path, case_study):
    print("-" * 40)
    print(f"Assigning metadata for corridors in case study: {case_study}...")
    corridor_files = find_corridor_files(base_path)
    if not corridor_files:
        print("No valid corridor TIFFs found.")
        return

    for folder_path, tif_paths in corridor_files.items():
        print(f"Folder path: {folder_path}")
        for tif_path in tif_paths:
            print(f"Corridor file: {tif_path}")
        
            # Extract timestamp
            timestamp = extract_timestamp_xml(tif_path)

            # Extract index_name
            filename = os.path.basename(tif_path)
            basename = os.path.splitext(filename)[0]
            parts = basename.split('_')
            if len(parts) >= 3:
                index_name = parts[-1]
            else:
                print("Corridor filename does not follow the expected pattern.")
                continue

            # Prepare metadata
            description = f"INDEX:{index_name}; TIMESTAMP:{timestamp}"

            # Open source dataset read-only
            src_ds = gdal.Open(tif_path, gdal.GA_ReadOnly)
            if src_ds is None:
                print(f"Could not open {tif_path}")
                continue

            # Set metadata in-memory
            src_ds.SetMetadataItem("TIFFTAG_IMAGEDESCRIPTION", description)

            # Write out to temporary path
            tmp_path = tif_path.replace(".tif", "_tmp.tif")
            gdal.Translate(
                tmp_path,
                src_ds
            )
            src_ds = None

            # Replace original with updated version
            os.replace(tmp_path, tif_path)

            print(f"Metadata set: {description}")
    print("-" * 40)
# TODO - to remove intermediate tif.aux.xml

def join_wrapper(case_study, base_path, gdal_dtype, exclude_fields):
    print(f"Running case study: {case_study}...")
    patch_files = find_patch_files(base_path)
    if not patch_files:
        print("No valid patches.tif and patches.gpkg pairs found.")
        return

    for folder, (tif_path, gpkg_path) in patch_files.items():
        output_tif_path = os.path.join(folder, "output.tif")

        # open TIFF and get spatial properties
        tif_ds, geotransform, projection, nodata_value = open_tiff(tif_path)
        if tif_ds is None:
            continue

        # rasterise each attribute of GPKG with the separate
        rasterize_geopackage(gpkg_path, tif_ds, output_tif_path, gdal_dtype, exclude_fields)

    print("Processing complete.")
    print("*" * 40)

def main():
    parser = argparse.ArgumentParser(description="Joining geopackage and tif files with patches, creating output TIFFs by each index ")
    parser.add_argument(
        "case_studies",  # positional arg
        type=lambda s: s.split(","),  # split input by commas
        help="Comma-separated list of case studies (eg. 'case1,case2,case3')"
    )

    """
    parser.add_argument(
        "habitats",  # positional arg
        type=lambda s: s.split(","),  # split input by commas
        help="Comma-separated list of habitats (eg. 'habitat1,habitat2,habitat3')"
    )
    """

    # parsing the argument
    args = parser.parse_args()

    exclude_fields = ['Id', 'area', 'perim', 'capacity', 'idhab']
    gdal_dtype = gdal.GDT_Float32

    for case_study in args.case_studies:
        base_path = f"data/{case_study}/output"
        join_wrapper(case_study, base_path, gdal_dtype, exclude_fields)
        assign_metadata_corridors(base_path, case_study)
        print("Processing complete.")
        print("*" * 40)

if __name__ == "__main__":
    main()
