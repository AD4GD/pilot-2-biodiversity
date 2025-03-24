import os
import subprocess
import numpy as np
from osgeo import gdal
from rich import print

class LandscapeAffinityEstimator:
    """
    This class is responsible for computing affinity based on the impedance dataset. 
    Affinity is the reciprocal of impedance, where the impedance is the cost of moving between two locations.
    """

    def __init__(self, impedance_dir:str, affinity_dir:str) -> None:
        """
        Initialize the Landscape_Affinity_Estimator class.
            impedance_dir (str): The path to the impedance directory
            affinity_dir (str): The path to the affinity
        """
        self.impedance_dir = impedance_dir
        self.affinity_dir = affinity_dir

        # create output directory if it doesn't exist
        os.makedirs(affinity_dir, exist_ok=True)

        # list all impedance files in the directory
        impedance_files = [f for f in os.listdir(impedance_dir) if f.endswith('_pa.tif')] # ADDED SUFFIX (UPDATED LULC)
        print(impedance_files)

    def compute_affinity(self,impedance_files) -> None:
        # loop through each TIFF file in impedance_dir
        for impedance_file in impedance_files:
            if impedance_file.endswith('_pa.tif'):
                # construct full paths for impedance and affinity files
                impedance_path = os.path.join(self.impedance_dir, impedance_file)
                affinity_path = os.path.join(self.affinity_dir, impedance_file.replace('impedance', 'affinity'))

                # open impedance file
                ds = gdal.Open(impedance_path)

                if ds is None:
                    print(f"Failed to open impedance file: {impedance_file}")
                    continue

                # get raster band
                band = ds.GetRasterBand(1)
                # read raster band as a NumPy array
                data = band.ReadAsArray()
                # reverse values with condition (if it is 9999
                # or 0 leave it, otherwise make it reversed)
                reversed_data = np.where((data == 9999) | (data == 0), data, 1 / data)

                # write reversed data to affinity file
                driver = gdal.GetDriverByName("GTiff")
                out_ds = driver.Create(affinity_path, ds.RasterXSize, ds.RasterYSize, 1, gdal.GDT_Float32)
                out_ds.GetRasterBand(1).WriteArray(reversed_data)

                # copy georeferencing info
                out_ds.SetGeoTransform(ds.GetGeoTransform())
                out_ds.SetProjection(ds.GetProjection())

                # close files
                ds = None
                out_ds = None

                print(f"Affinity computed for: {impedance_file}")

                # compression
                compressed_raster_path = os.path.splitext(affinity_path)[0] + '_compr.tif'
                subprocess.run(['gdal_translate', affinity_path, compressed_raster_path,'-a_nodata', '9999', '-ot', 'Float32', '-co', 'COMPRESS=LZW'])
            
                # as soon as gdal_translate doesn't support rewriting, we should delete non-compressed GeoTIFFs...
                os.remove(affinity_path)
                # ...and rename COG in the same way as the original GeoTIFF
                os.rename(compressed_raster_path, affinity_path)
                print(f"Affinity file is successfully compressed.", end="\n------------------------------------------\n")

        print("[green] All LULC affinities have been successfully computed. [green]")