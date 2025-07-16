import rasterio
import numpy as np
from raster_metadata import RasterMetadata
import os
from osgeo import gdal
from unittest import TestCase



def check_vector_pixels(testing:TestCase, col:int ,row:int, tiff_path:str, expected_value:int):
    """
    Tests the pixel value at a specific location in a raster file against an expected value.

    Args:
        testing (TestCase): The unittest TestCase instance for assertions.
        col (int): Column index of the pixel to check.
        row (int): Row index of the pixel to check.
        tiff_path (str): Path to the raster file.
        expected_value (int): Expected pixel value.
    """
    # open the raster
    ds = gdal.Open(tiff_path)
    rs = ds.GetRasterBand(1)
    pixel_value = rs.ReadAsArray(col, row, 1, 1)[0][0]
    # close the raster
    ds = None
    testing.assertEqual(pixel_value, expected_value)

def check_raster_metadata(testing:TestCase, raster_path:str, expected_nodata:int, expected_cell_size:int, expected_is_cartesian:bool, expected_x_min:int, expected_y_min:int, expected_x_max:int, expected_y_max:int):
    """
    Tests the raster metadata of a given raster file against expected input parameters.
    
    Args:
        testing (TestCase): The unittest TestCase instance for assertions.
        raster_path (str): Path to the raster file.
        expected_nodata (int): Expected NoData value.
        expected_cell_size (int): Expected cell size.
        expected_is_cartesian (bool): Expected Cartesian coordinate system.
        expected_x_min (int): Expected minimum X coordinate.
        expected_y_min (int): Expected minimum Y coordinate.
        expected_x_max (int): Expected maximum X coordinate.
        expected_y_max (int): Expected maximum Y coordinate.
    """
    raster_metadata = RasterMetadata.from_raster(raster_path)
    testing.assertEqual(raster_metadata.nodata, expected_nodata)
    testing.assertEqual(raster_metadata.cell_size, expected_cell_size)
    testing.assertEqual(raster_metadata.is_cartesian, expected_is_cartesian)
    testing.assertEqual(int(raster_metadata.x_min), expected_x_min)
    testing.assertEqual(int(raster_metadata.y_min), expected_y_min)
    testing.assertEqual(int(raster_metadata.x_max), expected_x_max)
    testing.assertEqual(int(raster_metadata.y_max), expected_y_max)


def calculate_raster_difference(before_raster_path:str, after_raster_path:str, output_raster_path:str, write_difference:bool=True) -> bool:
    """
    Calculates the pixel-wise difference between two raster datasets and saves the result.

    Args:
        before_raster_path (str): Path to the 'before' raster file.
        after_raster_path (str): Path to the 'after' raster file.
        output_raster_path (str): Path to save the difference raster.
        write_difference (bool): If True, writes the difference raster to the output path. If False, returns whether the rasters are different.

    Returns:
        bool: True if the rasters are different (if write_difference is False), otherwise None.
    """
    try:
        with rasterio.open(before_raster_path) as src_before, \
            rasterio.open(after_raster_path) as src_after:

            # Ensure both rasters have the same dimensions, data type, and transform
            if src_before.shape != src_after.shape:
                raise ValueError("Input rasters must have the same dimensions.")
            if src_before.dtypes != src_after.dtypes:
                print(f"Warning: Input rasters have different data types: {src_before.dtypes[0]} vs {src_after.dtypes[0]}. Proceeding with the data type of the 'after' raster.")

            # Read the raster data as NumPy arrays
            before_array = src_before.read(1)  # Assuming single-band rasters, adjust band index if needed
            after_array = src_after.read(1)

            # Calculate the difference
            difference_array = after_array.astype(after_array.dtype) - before_array.astype(after_array.dtype)

            # Prepare the metadata for the output raster
            profile = src_after.profile
            profile.update(dtype=difference_array.dtype)

            # Write the difference raster to a new file
            if write_difference:
                with rasterio.open(output_raster_path, 'w', **profile) as dst:
                    dst.write(difference_array, 1)

                print(f"Raster difference calculated and saved to: {output_raster_path}")

            # assert they are different
            if np.array_equal(before_array, after_array):
                return False
            else:
                return True
                

    except rasterio.RasterioIOError as e:
        print(f"Error opening raster file: {e}")
    except ValueError as e:
        print(f"ValueError: {e}")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")