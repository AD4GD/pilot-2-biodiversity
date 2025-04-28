# To run on Ubuntu VM:
# python3 ./postproc.py

from osgeo import gdal
import numpy as np
import pandas as pd
import os
import sys
import random
import subprocess
import argparse
from datetime import datetime
from typing import Optional, Dict, Union
import xml.etree.ElementTree as ET
import matplotlib.pyplot as plt
from matplotlib.ticker import MaxNLocator
from typing import List
import re
os.environ['GDAL_LOG'] = 'DEBUG'

print("Logs are redirected to /logs")
sys.stdout = open('logs/postproc.log', 'w') #to log
sys.stderr = sys.stdout

def get_numpy_dtype(gdal_dtype):
    dtype_mapping = {
        gdal.GDT_Byte: np.uint8,
        gdal.GDT_UInt16: np.uint16,
        gdal.GDT_Int16: np.int16,
        gdal.GDT_UInt32: np.uint32,
        gdal.GDT_Int32: np.int32,
        gdal.GDT_Float32: np.float32,
        gdal.GDT_Float64: np.float64,
        gdal.GDT_CInt16: np.complex64,
        gdal.GDT_CInt32: np.complex128,
        gdal.GDT_CFloat32: np.complex64,
        gdal.GDT_CFloat64: np.complex128,
        gdal.GDT_Int64: np.int64,
        gdal.GDT_UInt64: np.uint64,
    }
    return dtype_mapping.get(gdal_dtype, np.float32)

def apply_nodata_mask(input_path, lulc_tif, nodata_value, cog):
    '''Rewriting input tif with nodata values from the LULC GeoTIFF'''
    # TODO - do not apply if external dataset

    if cog:
        input_ds = gdal.OpenEx(input_path, gdal.OF_RASTER)
    else:
        input_ds = gdal.Open(input_path, gdal.GA_Update)
    
    if input_ds is None:
        raise FileNotFoundError(f"Could not open raster file: {input_path}")
    
    input_band = input_ds.GetRasterBand(1)
    input_data = input_band.ReadAsArray()
    input_nodata_value = input_band.GetNoDataValue()

    description = input_ds.GetMetadataItem("TIFFTAG_IMAGEDESCRIPTION")
    #print(f"Metadata for final output: {description}") NOTE:DEBUG

    # DEBUG
    '''metadata = input_ds.GetMetadata()
    for key, value in metadata.items():
        print(f"{key}: {value}")'''

    lulc_ds = gdal.Open(lulc_tif)
    lulc_band = lulc_ds.GetRasterBand(1)
    lulc_data = np.copy(lulc_band.ReadAsArray())
    lulc_nodata_value = lulc_band.GetNoDataValue()
    
    lulc_mask = lulc_data == lulc_nodata_value
    input_mask = input_data == input_nodata_value
    
    height, width = input_data.shape
    random_pixels = random.sample(range(height * width), 10)
    '''
    print(f"input_data and lulc_data are the same object: {input_data is lulc_data}")
    print(f"input_data and lulc_data identical: {np.array_equal(input_data, lulc_data)}")
    '''
    print("Before applying mask (LULC, index value):")
    for i in random_pixels:
        row, col = divmod(i, width)
        print(f"Pixel ({row}, {col}): LULC={lulc_data[row, col]}, index value={input_data[row, col]}")
    
    combined_mask = np.logical_or(lulc_mask, input_mask) # combine masks
    input_data[combined_mask] = nodata_value

    input_band.WriteArray(input_data)
    input_band.SetNoDataValue(nodata_value)
    input_ds.FlushCache()

    # copy metadata
    input_ds.SetMetadataItem("TIFFTAG_IMAGEDESCRIPTION", description)
    
    input_ds = None
    lulc_ds = None

    print(f"Applied NoData mask to {input_path} and saved changes.")

def translate_tif(input_tif, nodata_value, cog:bool=True):
    output_tif = f"compressed_{os.path.basename(input_tif)}"
    output_tif_path = os.path.join(os.path.dirname(input_tif), output_tif)
    
    print(f"Compressing: {input_tif}")

    driver = gdal.GetDriverByName('GTiff')
    tif_ds = gdal.Open(input_tif, gdal.GA_ReadOnly)

    metadata = driver.GetMetadata()
    print(f"Data types available: {metadata.get('DMD_CREATIONDATATYPES')}")

    # extract metadata
    metadata = tif_ds.GetMetadata()
    description = tif_ds.GetMetadataItem("TIFFTAG_IMAGEDESCRIPTION")
    print(f"Metadata for final output: {description}")

    dtype = gdal.GDT_Float32 if "beta" in input_tif else gdal.GDT_Float32 #NOTE: do not use Int64, it might be not supported (and silently fall to Float64 instead)
    compression = "ZSTD" if dtype in [gdal.GDT_Float32, gdal.GDT_Float64, gdal.GDT_CFloat32, gdal.GDT_CFloat64] else "LZW"
    print(f"Compression: {compression}, data type: {dtype}, {gdal.GetDataTypeName(dtype)}")
    #NOTE: ZSTD compression is better for Float datasets, LZW - for Int

    if not tif_ds:
        print(f"Error: Could not open {input_tif}")
        print("-" *40)
        return

    if cog:
        output_tif_path = f"{os.path.splitext(input_tif)[0]}_cog.tif"

        # Run the `gdal_translate` command with the specified options to create a COG
        gdal_translate_command = [
            "gdal_translate", 
            "-of", "COG",  # Output format: COG
            "-co", f"COMPRESS={compression}",  
            "-ot", gdal.GetDataTypeName(dtype),
            "-mo", f"TIFFTAG_IMAGEDESCRIPTION={description}",
            input_tif,  # Input file path
            output_tif_path  # Output COG file path
        ]
        
        # Run the gdal_translate command
        subprocess.run(gdal_translate_command, check=True)

        print(f"Cloud Optimized GeoTIFF created: {output_tif_path}")
        '''
        # after translation, re-open the COG file to add metadata
        cog_ds = No habitat match found in: 
        if cog_ds:
            if description:
                # re-apply the description metadata
                cog_ds.SetMetadataItem("TIFFTAG_IMAGEDESCRIPTION", description)
                print("Added metadata from non-transformed GeoTIFF")
        
            # flush any changes (such as metadata) to disk
            cog_ds.FlushCache()
        
            # close the dataset
            cog_ds = None
        else:
            print(f"Failed to open the file: {output_tif_path}")
        '''
        os.remove(input_tif)
        os.rename(output_tif_path, input_tif)
        print(f"Replaced {input_tif} with COG version.")
        print("-" *40)
    
    else: #NOTE: If COG is not defined
        output_tif_ds = driver.Create(
        output_tif_path, tif_ds.RasterXSize, tif_ds.RasterYSize,
        tif_ds.RasterCount, dtype, options=[f"COMPRESS={compression}"]
        )
    
        if not output_tif_ds:
            print(f"Error: Could not create {output_tif_path}")
            print("-" * 40)
            return
    
        output_tif_ds.SetGeoTransform(tif_ds.GetGeoTransform())
        output_tif_ds.SetProjection(tif_ds.GetProjection())
    
        for band_index in range(tif_ds.RasterCount):
            input_band = tif_ds.GetRasterBand(band_index + 1)
            input_data = input_band.ReadAsArray()
            output_band = output_tif_ds.GetRasterBand(band_index + 1)
            output_band.WriteArray(input_data)
            output_band.SetNoDataValue(nodata_value)
    
        output_tif_ds.FlushCache()

        os.remove(input_tif)
        os.rename(output_tif_path, input_tif)
        print(f"Replaced {input_tif} with compressed version.")
        print("-" *40)

def is_cog(file_path):
    """Check if a TIFF file is already a Cloud Optimized GeoTIFF (COG)."""
    try:
        result = subprocess.run(["gdalinfo", file_path], capture_output=True, text=True)
        return "LAYOUT=COG" in result.stdout
    except Exception as e:
        print(f"Error checking COG status: {e}")
        print("-" *40)
        return False
    
def clip_output(input_tif, size:int=1):
    """
    Clip a specified number of pixels from all four sides of a GeoTIFF dataset.
    Rewriting input dataset.
    
    Parameters:
    input_tif (str): path to the input GeoTIFF file.
    size (int): number of pixels to clip from each side. Default is 1.
    
    Returns:
    None
    """
    driver = gdal.GetDriverByName('GTiff')
    tif_ds = gdal.Open(input_tif, gdal.GA_ReadOnly)
    if tif_ds is None:
        raise ValueError(f"Could not open {input_tif}")
    description = tif_ds.GetMetadataItem("TIFFTAG_IMAGEDESCRIPTION") #inherit metadata
    #print(f"Metadata for final output: {description}") NOTE:DEBUG
    
    # Get dimensions
    x_size = tif_ds.RasterXSize
    y_size = tif_ds.RasterYSize
    new_x_size = x_size - (2*size)
    new_y_size = y_size - (2*size)
    if new_x_size <= 0 or new_y_size <= 0:
        raise ValueError(f"Size parameter ({size}) is too large for the input image")
    
    # adjust corners
    geo_transform = list(tif_ds.GetGeoTransform())
    geo_transform[0] += size*geo_transform[1] # x min
    geo_transform[3] += size*geo_transform[5] # y max

    # Read all the data we need
    band_count = tif_ds.RasterCount
    bands_data = []
    nodata_values = []
    dtype = tif_ds.GetRasterBand(1).DataType
    
    for band_idx in range(1, band_count + 1):
        band = tif_ds.GetRasterBand(band_idx)
        data = band.ReadAsArray(size, size, new_x_size, new_y_size)
        bands_data.append(data)
        nodata_values.append(band.GetNoDataValue())
    
    projection = tif_ds.GetProjection()
    
    tif_ds = None
    
    # Create a new dataset with the same name (overwrite)
    driver = gdal.GetDriverByName('GTiff')
    out_ds = driver.Create(
        input_tif,
        new_x_size,
        new_y_size,
        band_count,
        dtype
    )
    
    out_ds.SetGeoTransform(geo_transform)
    out_ds.SetProjection(projection)
    
    # Write the data for each band
    for band_idx in range(band_count):
        out_band = out_ds.GetRasterBand(band_idx + 1)
        # Verify the array has the correct shape
        if bands_data[band_idx].shape != (new_y_size, new_x_size):
            raise ValueError(f"Array shape {bands_data[band_idx].shape} doesn't match expected shape ({new_y_size}, {new_x_size})")
        
        out_band.WriteArray(bands_data[band_idx])
        
        # set nodata value if it exists
        if nodata_values[band_idx] is not None:
            out_band.SetNoDataValue(nodata_values[band_idx])
        
        out_band.FlushCache()
    
    out_ds.SetMetadataItem("TIFFTAG_IMAGEDESCRIPTION", description)  # set inherited metadata

    out_ds = None

    return None

def check_and_clip(input_tif, ref_tif, size:int=1):
    """
    Checks if the input GeoTIFF dimensions are larger by the same number of pixels from each side than the 
    dimensions of the reference lulc_tif. If they are, triggers the clip_output 
    function to clip pixels from each side.
    
    Parameters:
    input_tif (str): Path to the GeoTIFF file to check and potentially clip.
    lulc_tif (str): Path to the reference GeoTIFF file to extract dimensions from.
    size (int): pixel size to clip the input GeoTiff.
    
    Returns:
    bool: True if clipping was performed, False otherwise.
    """
    # input dataset
    input_ds = gdal.Open(input_tif, gdal.GA_ReadOnly)

    #description = input_ds.GetMetadataItem("TIFFTAG_IMAGEDESCRIPTION")
    #print(f"CHECK AND CLIP Metadata for final output: {description}") NOTE: DEBUG

    if input_ds is None:
        raise ValueError(f"Could not open {input_tif}")
    x_size = input_ds.RasterXSize
    y_size = input_ds.RasterYSize
    input_ds = None

    # reference dataset
    lulc_ds = gdal.Open(ref_tif, gdal.GA_ReadOnly)
    if lulc_ds is None:
        raise ValueError(f"Could not open reference file {ref_tif}")
    ref_x_size = lulc_ds.RasterXSize
    ref_y_size = lulc_ds.RasterYSize
    lulc_ds = None
    
    # check if dimensions are different by the same number of pixels (extent buffer)
    if x_size == (ref_x_size + (2 * size)) and y_size == (ref_y_size + (2 * size)):
        print(f"Input dimensions ({x_size}x{y_size}) are larger than reference dimensions "
              f"({ref_x_size}x{ref_y_size}). Clipping {size} pixel(s) from each side.")
        
        try:
            # clip size pixels from each side
            clip_output(input_tif, size=size)
            return True
        except Exception as e:
            print(f"Error during clipping: {str(e)}")
            return False
    else:
        print(f"Input dimensions ({x_size}x{y_size}) are not more than {2*size} pixels larger than "
              f"reference dimensions ({ref_x_size}x{ref_y_size}). No clipping needed.")
        return False

def extract_habitat_xml(input_file):
    current_dir = os.path.dirname(input_file)
    
    xml_files = [f for f in os.listdir(current_dir) if f.endswith('.xml') and not f.endswith('aux.xml')] # check current dir for xml files

    if not xml_files: # if xml not found
        parent_dir = os.path.dirname(current_dir)
        xml_files = [f for f in os.listdir(parent_dir) if f.endswith('.xml') and not f.endswith('aux.xml')]
        xml_dir = parent_dir
    else:
        xml_dir = current_dir
    
    if xml_files: # if xml found
        xml_path = os.path.join(xml_dir, xml_files[0])
        
        try:
            tree = ET.parse(xml_path)
            root = tree.getroot()

            # Find the first habitat name in the XML structure
            for entry in root.findall(".//habitats/entry"):
                name_tag = entry.find(".//Habitat/name")
                if name_tag is not None:
                    return name_tag.text
            print("No <name> tag found in <Habitat>.")
            return None

        except ET.ParseError as e:
            print(f"Failed to parse XML: {e}")
            return None
    else:
        print("No .xml file found in the current or parent directory.")
        return None

def extract_metadata_filename(input_file) -> tuple[str, str, float, str]:
    """Extracting metadata (case study, habitat, year and name of index) from filename.
    Should be used if there are no available metadata in GeoTIFF files (for example, from the external bucket).
    Arguments:
        input_file(str): path to the file to try to extract metadata from (for example, downloaded from external bucket)

    Returns:
        case_study(str): name of case study the file belongs to
        habitat(str): name of habitat the file describes
        year(float): year the file belongs to
        metric(str): metric (parameter) the file describes
    """
    filename = os.path.basename(input_file).lower().strip()

    # 1. case study
    case_study = habitat = year = None 
    case_study_map = {
        '_30_': 'cat_aggr_buf_30m',
        '_390_': 'cat_aggr_buf_390m_test',
        'high': 'cat_aggr_buf_30m',
        'low': 'cat_aggr_buf_390m_test'
    } # mapping between names of case studies (external and internal)
    for key, value in case_study_map.items():
        if key.lower() in ['high','low','output']:
            habitat='ml_output'
        if key.lower() in filename:
            case_study = value.lower()
            break

    # 2. habitat
    habitat_map = {
        'Aquatics': 'aquatic',
        'Boscos': 'forest',
        'Herbacis': 'herbaceous',
        'Llenyosos': 'woody',
        'PratsMatollars': 'shrubland'
    } # mapping between names of habitats (external and internal)
    for key,value in habitat_map.items(): # 
        if key.lower() in filename:
            if habitat:
                habitat += f"_{value.lower()}"
            else:
                habitat = value.lower()
            break

    # 3. year
    #parts = filename.split('_')
    #if len(parts) > 0 and re.fullmatch(r'\d{4}', parts[0]): # first check
        #print(11111111111111111111111111)
        #year = parts[0]
        #print(f"Year is {year}")
    #elif len(parts) > 1 and re.fullmatch(r'\d{4}', parts[-2]): # second check
        #print(2222222222222222222222222)
        #year = parts[-2]
        #print(f"Year is {year}")
    #else:
        #print("Year not found")

    parts = filename.split('_')
    for part in parts:
        if re.fullmatch(r'\d{4}', part):
            if 1800 <= int(part) <= 2050:  #sanity check 
                year = part
                print(f"Year found: {year}")
                break

    if year is None:
        print("Year not found")
    

    # 4. metric
    metric='ICT' # hardcoded - there are no other metrics

    print(f"Extracted metadata are: {case_study,habitat,year,metric}")
    return case_study,habitat,year,metric

def create_stats(case_study:str, input_tif: str, nodata_value, csv_stats: str) -> tuple[dict, str]:
    ds = gdal.Open(input_tif)
    band = ds.GetRasterBand(1)

    habitat=extract_habitat_xml(input_tif) # extract name of habitat from XML

    if nodata_value is not None: # set nodata if provided
        band.SetNoDataValue(nodata_value)
    
    # call metadata
    description = str(ds.GetMetadataItem("TIFFTAG_IMAGEDESCRIPTION")).strip()
    # check if description is available
    if description is not None and description.strip().lower() != 'none':
        print(f"Metadata to read: {description}")
        # split the string by ';' to separate the parts
        parts = description.split("; ")

        # extract the index and timestamp from the description
        metric = parts[0].split(":")[1]  # Extract after "INDEX:"
        timestamp = parts[1].split(":", 1)[1].strip() # split once by semicolon
        timestamp = datetime.strptime(timestamp, "%Y-%m-%d %H:%M:%S")
        
        year = timestamp.year

        # print the extracted values
        print(f"Extracted Metric: {metric}")
        print(f"Extracted Timestamp: {timestamp}")
    else:
        print("No description found in metadata. Trying to extract description from the filename...")
        case_study,habitat,year,metric=extract_metadata_filename(input_tif)

    # force computation of statistics: min, max, mean, stddev
    stats_tuple = band.ComputeStatistics(False)  # approx=False
    min_val, max_val, mean_val, stddev_val = stats_tuple

    if np.isnan(mean_val) or np.isinf(stddev_val): # invalid data
        stats = {
            'case_study': case_study,
            'habitat': habitat,
            'metric': metric,
            'year': year,
            'min': None,
            'max': None,
            'mean': None,
            'stddev': None,
            'path': input_tif
        }
    else:
        stats = {
            'case_study': case_study,
            'habitat': habitat,
            'metric': metric,
            'year': year,
            'min': min_val,
            'max': max_val,
            'mean': mean_val,
            'stddev': stddev_val,
            'path': input_tif
        }

    ds=None

    df = pd.DataFrame([stats])
    if os.path.exists(csv_stats):
        df.to_csv(csv_stats, mode='a', header=False, index=False)
    else:
        df.to_csv(csv_stats, mode='w', header=True, index=False)
    print(f"Stats written to {csv_stats}")
    return stats, csv_stats

def create_vis(csv: str, case_study: str, habitats: bool) -> str:
    '''Creates plots for the output CSV

    Parameters:
    csv (str): path to the final CSV
    case_study (str): name of case study
    habitats (bool): specifies if there are multiple habitats defined

    Returns:
    plot (str): path to the final visualisation (local indices)
    '''
    df = pd.read_csv(csv, sep=',')

    # NOTE: to filter by metrics (ICT, PC, corridors etc.)
    #if values: # filter by required metrics
        #df = df[df['metric'].isin(values)]
    
    # filter by the 'case_study' column
    df = df[df['case_study'] == case_study]

    # clean up 'year' column
    initial_rows = len(df)
    df = df.dropna(subset=['year'])
    df['year'] = pd.to_numeric(df['year'], errors='coerce')
    df = df.dropna(subset=['year'])
    df['year'] = df['year'].astype(int)
    dropped = initial_rows - len(df)
    if dropped > 0:
        print(f"Dropped {dropped} rows due to missing or invalid 'year' values.")
    
    # indices = df[]
    # years = df[]

    dfs = dict(tuple(df.groupby('metric')))
    num_metric = len(dfs)
    fig,axs=plt.subplots(num_metric, 1, figsize=(7,5*num_metric), sharex=True)

    if num_metric==1:
        axs=[axs] # make list iterable

    # predefined color mapping for habitats
    habitat_colours = {
        'aquatic': 'blue',
        'forest': 'green',
        'herbaceous': 'orange',
        'woody': 'lightgreen',
        'shrubland': 'brown',
    }

    # predefined max values for each metric
    metric_max_values = {
        'ict': 2.5
    }
    # for metric 'corridor with  beta=0"
    metric_max_values.update({
        metric.lower(): 1
        for metric in dfs.keys()
        if 'corridor' in metric.lower() and 'beta' not in metric.lower()
    })
    # TODO - to extend the dictionary of predefined maximum values

    for ax, (metric, metric_df) in zip(axs, dfs.items()):
        sorted_df = metric_df.sort_values('year')  # sort for x-axis consistency

        if habitats and 'habitat' in sorted_df.columns:
            for habitat, sub_df in sorted_df.groupby('habitat'):
                colour = habitat_colours.get(habitat, 'black')
                ax.plot(
                    sub_df['year'],
                    sub_df['mean'],
                    marker='o',
                    linestyle='--',
                    color=colour,
                    label=habitat
                )
        else:
                ax.plot(
                    sorted_df['year'],
                    sorted_df['mean'],
                    marker='o',
                    linestyle='--',
                    label=metric
                )

        # NOTE - errorbar won't work because stddev is too big

        # get predefined max value for the current metric and set up max value for Y axis
        max_value = metric_max_values.get(metric.lower(), None)
        if max_value is not None:
            ax.set_ylim(0, max_value)

        ax.set_title(metric)
        ax.set_ylabel('Value')
        ax.yaxis.set_major_locator(MaxNLocator(nbins=10))
        ax.set_xticks(sorted(sorted_df['year'].unique())) # put ticks on each unique year
        ax.legend(title='Habitats', loc='center left', bbox_to_anchor=(1.0, 0.5)) # move legend out

    # plt.figure(figsize=(9, 20))
    axs[-1].set_xlabel('Year') # make label for last plot
    plt.xlabel('Year') 
    # plt.plot()
    plt.suptitle('Dynamics of local indices', fontsize=14, fontweight='bold')
    plt.tight_layout(rect=[0, 0, 0.85, 0.97])
    plt.show()

    output_path = os.path.splitext(csv)[0] + '_plot.png'
    plt.savefig(output_path)
    plt.close(fig)

    return output_path

# TODO - to create plt.subplot for multiple case studies (if True)

def wrapper(case_study, base_path, lulc_dir, csv_stats, int_data, nodata_value):
    excluded_dirs = ['ml', 'output']  # folders to skip
    lulc_tif = next((os.path.join(lulc_dir, f) for f in os.listdir(lulc_dir) if f.endswith('.tif')), None)
    os.remove(csv_stats) if os.path.exists(csv_stats) else None
    
    for root, _, files in os.walk(base_path):  # recursively walk through nested directories
        if any(excluded in os.path.basename(root).lower() for excluded in excluded_dirs):
            print(f"Skipping excluded folder: {root}")
            continue

        #print(f"FILES ARE: {files}") NOTE: DEBUG
        for file in files:
            #print(f"FILE IS {file}") NOTE: DEBUG
            file_lower = file.lower()
            if ('corridor' in file_lower or 'output' in file_lower or 'ict' in file_lower) and file.endswith('.tif') and not file.startswith('compressed_'):
                input_tif = os.path.join(root, file)
                
                # skip processing if the file is already a COG (only for internal outputs)
                if is_cog(input_tif) and 'ict' not in file_lower:
                    print(f"Skipping COG file: {input_tif}")
                    print("-" * 40)
                    continue
                
                print(f"Processing file: {input_tif}") # NOTE: DEBUG
                
                if lulc_tif:
                    was_clipped = check_and_clip(input_tif, lulc_tif, size=1)
                    print("File was clipped successfully by {size} pixels." if was_clipped else "No clipping needed.")
                    if int_data: # if data is fetched from internal datasource. Do not apply mask for external datasource (Miramon outputs are already clipped)
                        apply_nodata_mask(input_tif, lulc_tif, nodata_value,cog=True)
                    stats, csv_stats=create_stats(case_study, input_tif, nodata_value, csv_stats)
                    plot=create_vis(csv_stats, case_study, habitats=True)
                    translate_tif(input_tif, nodata_value, cog=True)
                else:
                    print(f"No LULC TIFF file found in {lulc_dir}. Skipping {input_tif}.")
                    print("-" * 40)

def main():
    parser = argparse.ArgumentParser(description="Postprocessing outputs (compression, clipping, masking, no data values)")
    parser.add_argument(
        "case_studies",  # positional arg
        type=lambda s: s.split(","),  # split input by commas
        help="Comma-separated list of case studies (eg. 'case1,case2,case3')"
    )
    parser.add_argument(
        "--nodata",
        type=float,
        default=-9999.0,
        help="No data value to be applied for output files (default -9999.0)"
    )

    # parsing the arguments
    args = parser.parse_args()

    for case_study in args.case_studies:
        base_path = f"data/{case_study}/output"
        lulc_dir = f"data/{case_study}/input/lulc"
        csv_stats = os.path.join(base_path, 'stats_loc.csv')

        # 1. postprocessing of internal outputs
        wrapper(case_study, base_path, lulc_dir, csv_stats, int_data=True, nodata_value=args.nodata)
        print("-"*40)

        # 2. postprocessing of external outputs (MinIO)
        ext_path = "bucket_ext"
        ext_csv_stats = os.path.join(base_path, 'ext_stats_loc.csv')
        wrapper(case_study, ext_path, lulc_dir, ext_csv_stats, int_data=False, nodata_value=args.nodata)

        # NOTE - use code below if ML outputs are harmonised
        """
        ext_path = f"bucket_ext"
        ext_csv_stats = os.path.join(base_path, 'ext_stats_loc.csv')
        wrapper(case_study, ext_path, lulc_dir, ext_csv_stats, nodata_value=args.nodata)"""

        print("Processing complete.")
        print("*" * 40)

if __name__ == "__main__":
    main()

# python3 ./postproc.py cat_aggr_buf_390m_test