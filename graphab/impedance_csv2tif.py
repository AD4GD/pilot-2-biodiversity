#!/usr/bin/python

# To run on Ubuntu VM:
# nohup python3 ./impedance_csv2tif.py {case_study} {habitat1},{habitat2},{habitat3}

import argparse
import os
import sys
import subprocess
import csv
import logging
from osgeo import gdal
import numpy as np

print("Logs are redirected to /logs")
sys.stdout = open('logs/impedance_csv2tif.log', 'w') #to log
sys.stderr = sys.stdout

gdal.UseExceptions()

# Set up logging
log_file = 'logs/test.log'
logging.basicConfig(
    level=logging.INFO,  # Set the logging level
    format='%(asctime)s - %(levelname)s - %(message)s',  # Format of log messages
    handlers=[
        logging.FileHandler(log_file),  # Log to file
        logging.StreamHandler()  # Also log to the console
    ]
)

def reclassify_lulc2impedance(input_raster, impedance_raster, reclass_table, out_nodata):
    reclass_dict = {}

    with open(reclass_table, 'r', encoding='utf-8-sig') as csvfile:
        reader = csv.DictReader(csvfile)
        reclass_list = list(reader)
        has_decimal_values = any('.' in row['impedance'] for row in reclass_list)
        data_type = 'Float32' if has_decimal_values else 'Int32'

    for row in reclass_list:
        try:
            if not row['type'] or row['type'].strip().lower() in {'null', 'none'}:
                continue
            impedance_str = row['impedance'].strip()
            impedance = (
                float(impedance_str) if has_decimal_values else int(impedance_str)
                if impedance_str else 666
            )
            reclass_dict[int(row['lulc'])] = impedance
        except ValueError:
            logging.error(f"Invalid data format in reclassification table: {row}")

    nodata_value = float(out_nodata) if has_decimal_values else out_nodata
    reclass_dict.update({-2147483647: nodata_value, -32768: nodata_value, 0: nodata_value})
    logging.info(f"Mapping dictionary used to classify impedance is: {reclass_dict}")

    dataset = gdal.Open(input_raster)
    if dataset is None:
        logging.error("Could not open input raster.")
        return

    cols, rows = dataset.RasterXSize, dataset.RasterYSize
    driver = gdal.GetDriverByName("GTiff")
    output_dataset = driver.Create(impedance_raster, cols, rows, 1, gdal.GDT_Float32 if has_decimal_values else gdal.GDT_Int32)
    output_dataset.SetProjection(dataset.GetProjection())
    output_dataset.SetGeoTransform(dataset.GetGeoTransform())

    input_band = dataset.GetRasterBand(1)
    output_band = output_dataset.GetRasterBand(1)
    input_data = input_band.ReadAsArray()
    output_data = np.where(
        np.isin(input_data, list(reclass_dict.keys())), 
        np.vectorize(reclass_dict.get, otypes=[float if has_decimal_values else int])(input_data), 
        float(out_nodata) if has_decimal_values else out_nodata
    )
    output_band.WriteArray(output_data)

    dataset = None
    output_dataset = None

    return data_type, has_decimal_values

def reclassify_impedance2affinity(impedance_raster, out_nodata):
    affinity_raster = impedance_raster.replace('impedance', 'affinity')
    os.makedirs(os.path.dirname(affinity_raster), exist_ok=True)
    ds = gdal.Open(impedance_raster)
    if ds is None:
        logging.error(f"Failed to open impedance file: {impedance_raster}")
    
    band = ds.GetRasterBand(1)
    data = band.ReadAsArray()
    reversed_data = np.where((data != out_nodata) & (data != 0), 1 / data, out_nodata)

    driver = gdal.GetDriverByName("GTiff")
    out_ds = driver.Create(affinity_raster, ds.RasterXSize, ds.RasterYSize, 1, gdal.GDT_Float32)
    out_ds.GetRasterBand(1).WriteArray(reversed_data)
    out_ds.SetGeoTransform(ds.GetGeoTransform())
    out_ds.SetProjection(ds.GetProjection())
    ds = None
    out_ds = None

    logging.info(f"Affinity computed for: {impedance_raster}")
    return affinity_raster

def main():
    parser = argparse.ArgumentParser(description='Reclassify LULC to impedance and affinity datasets by CSV table.')
    parser.add_argument('case_study', type=str, help='Case study name')
    parser.add_argument(
        "habitats",
        type=lambda s: s.split(","),  # split input by commas
        help="Comma-separated list of habitat names (e.g., 'shrubland,grassland,wetland')"
    )
    args = parser.parse_args()

    case_study = args.case_study
    habitats = args.habitats
    input_folder = f'data/{case_study}/input/lulc'
    out_nodata = 9999

    for habitat in habitats:
        habitat = habitat.strip()
        impedance_folder = f'data/{case_study}/input/{habitat}_impedance'
        reclass_table = f'data/{case_study}/input/{habitat}_impedance/reclassification_{habitat}.csv'

        os.makedirs(impedance_folder, exist_ok=True)
        tiff_files = [f for f in os.listdir(input_folder) if f.endswith('.tif')]

        for tiff_file in tiff_files:
            input_raster_path = os.path.join(input_folder, tiff_file)
            logging.info(f"Processing {tiff_file} for habitat: {habitat}")

            output_filename = f"impedance_{tiff_file}"
            impedance_raster_path = os.path.join(impedance_folder, output_filename)

            data_type, has_decimal_values = reclassify_lulc2impedance(input_raster_path, impedance_raster_path, reclass_table, out_nodata)
            logging.info(f"Data type used to reclassify LULC as impedance is {data_type}")

            compressed_raster_path = os.path.splitext(impedance_raster_path)[0] + '_compr.tif'
            subprocess.run([ 
                'gdalwarp', 
                impedance_raster_path, 
                compressed_raster_path, 
                '-dstnodata', str(out_nodata), 
                '-ot', data_type, 
                '-co', 'COMPRESS=ZSTD'
            ])

            os.remove(impedance_raster_path)
            os.rename(compressed_raster_path, impedance_raster_path)

            logging.info(f"Reclassification for impedance complete for: {input_raster_path}")
            logging.info("------------------------------------")

            affinity_raster = reclassify_impedance2affinity(impedance_raster_path, out_nodata)

            compressed_affinity = os.path.splitext(affinity_raster)[0] + '_compr.tif'
            subprocess.run([
                'gdalwarp', 
                affinity_raster,  
                compressed_affinity,
                '-dstnodata', str(out_nodata),
                '-ot', data_type,
                '-co', 'COMPRESS=ZSTD',
            ])

            os.remove(affinity_raster)
            os.rename(compressed_affinity, affinity_raster)

            logging.info("Affinity file is successfully compressed.")
            logging.info("------------------------------------------")

if __name__ == "__main__":
    main()
    '''
    Usage example:
    python3 ./impedance_csv2tif.py cat_aggr_30m forest,herbaceous,woody,aquatic,shrubland
    '''
