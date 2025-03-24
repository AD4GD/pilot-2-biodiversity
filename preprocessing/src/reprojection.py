# reprojection.py
# includes a few methods to optimise transformations between raster files (minimum and maximum coordinates of raster dataset (bounding box) into WGS84, according to the config.yaml file))
# should be imported as a class

from osgeo import gdal, osr
import pyproj
import warnings
from cli_markdown import print_table

class RasterTransform:
    def __init__(self, raster_path):
        self.raster_path = raster_path
        self.epsg_code = None
        self.x_min_before = None
        self.y_min_before = None
        self.x_max_before = None
        self.y_max_before = None
        nodata = None

    def get_raster_info(self):
        raster = gdal.Open(self.raster_path)
        if raster is None:
            raise FileNotFoundError("Input raster is missing.")
        
        geo_transform = raster.GetGeoTransform() # gdal.GetGeoTransform is a method and should be called as (). So, it should be defined as a variable
        if not geo_transform:
            raise RuntimeError("Geotransform is not available in the raster.")
        
        # fetch max/min coordinates to use them later
        # TODO - to check again!
        self.x_min_before = geo_transform[0]  # Top-left x
        self.y_max_before = geo_transform[3]  # Top-left y
        self.x_max_before = self.x_min_before + geo_transform[1] * raster.RasterXSize
        self.y_min_before = self.y_max_before + geo_transform[5] * raster.RasterYSize  

        # fetch spatial resolution
        xres = geo_transform[1]
        yres = geo_transform[5]
        cell_size = abs(xres)

        # extract projection system of input raster file
        info = gdal.Info(raster, format='json')
        print (f"Input raster dataset {self.raster_path} was opened successfully.")
        if 'coordinateSystem' in info and 'wkt' in info['coordinateSystem']:
            srs = osr.SpatialReference(wkt=info['coordinateSystem']['wkt'])
            if srs.IsProjected():
                self.epsg_code = srs.GetAttrValue("AUTHORITY", 1)
                print (f"Coordinate reference system of the input raster dataset is EPSG:{self.epsg_code}")
            else:
                raise ValueError("Input raster does not have a projected coordinate system.")
        else:
            raise ValueError("No projection information found in the input raster.")

        # fetch no-data value from the first raster band
        band = raster.GetRasterBand(1)
        nodata = band.GetNoDataValue()
        print(f"No Data value of the input raster dataset is: {nodata}")
        if nodata is None:
            raise ValueError("Failed to fetch the no data value of the input raster.")
            
        # close the raster to keep memory empty
        raster = None

        return self.x_min_before, self.x_max_before, self.y_min_before, self.y_max_before, cell_size, nodata
    
    def check_cart_crs(self):
        """
        This function checks if the CRS of the input raster dataset is projected (Cartesian).

        Parameters:
        - raster_path: The file path to the raster dataset.

        Returns:
        - is_cartesian: A boolean value indicating if the CRS is projected (True) or not (False).
        - crs_info: A dictionary with details about the CRS, or None if the dataset couldn't be opened.
        """
        dataset = gdal.Open(self.raster_path)
        is_cartesian = False
        crs_info = None

        if dataset:
            try:
                # get the projection information
                projection = dataset.GetProjection()
                srs = osr.SpatialReference()
                srs.ImportFromWkt(projection)

                # check if the CRS is projected (Cartesian)
                is_cart = srs.IsProjected()

                # extract CRS information (optional)
                crs_info = {
                    'proj4': srs.ExportToProj4(),
                    'epsg': srs.GetAttrValue("AUTHORITY", 1),
                }

            except Exception as e:
                warning_message_2 = f"An error occurred while processing the raster dataset: {e}"
                warnings.warn(warning_message_2, Warning)

            finally:
                dataset = None  # close the dataset to free resources

        else:
            warning_message_2 = f"Failed to open the raster dataset. Please check the path and format of the input raster."
            warnings.warn(warning_message_2, Warning)

        # display a warning if the CRS is not Cartesian
        if not is_cart:
            warning_message_3 = "The CRS is not the Cartesian one. To exploit this workflow correctly, you should reproject it."
            warnings.warn(warning_message_3, Warning)
        else:
            is_cartesian = True
            print("Good news! The CRS of your input raster dataset is the Cartesian (projected) one.")
    
        return is_cartesian, crs_info

        # example usage:
        # is_cart, crs_info = check_cart_crs(lulc)

    def check_res (self):
        raster = gdal.Open(self.raster_path)
        if raster is None:
            raise FileNotFoundError("Input raster is missing.")
        
        geo_transform = raster.GetGeoTransform() # gdal.GetGeoTransform is a method and should be called as (). So, it should be defined as a variable
        if not geo_transform:
            raise RuntimeError("Geotransform is not available in the raster.")
        
        xres = geo_transform[1]
        yres = geo_transform[5]

        # compare absolute values, because the y value might be represented in negative coordinates
        if abs(xres) != abs(yres):
            print ("x:",xres,"y:",yres)
            warning_message = f"Spatial resolution (x and y values) of input raster is inconsistent"
            warnings.warn(warning_message, Warning)
        else:
            print ("Good news! The spatial resolution of your raster data is consistent between X and Y.")

        return xres, yres

    def transform_coordinates(self):
        if self.epsg_code is None:
            raise ValueError("EPSG code is not set. Did you call get_raster_info?")

        # to transform coordinates into WGS 84
        transform_cart_to_geog = pyproj.Transformer.from_crs(
            pyproj.CRS(f'EPSG:{self.epsg_code}'),
            pyproj.CRS('EPSG:4326'),
            always_xy=True # to ensure that coordinates are always treated as (x, y).
        )
        
        y_min_after,x_min_after = transform_cart_to_geog.transform(self.x_min_before, self.y_min_before)
        y_max_after,x_max_after = transform_cart_to_geog.transform(self.x_max_before, self.y_max_before)

        return x_min_after, y_min_after, x_max_after, y_max_after

    # run transformation of coordinates
    def transform_and_print(self, print_details=True) -> tuple:
        """
        Transforms coordinates and prints spatial resolution and bounding box details.
        """
        # fetch raster information
        _, _, _, _, cell_size, _ = self.get_raster_info()
        x_min_after, y_min_after, x_max_after, y_max_after = self.transform_coordinates()

        if print_details:
            # print the details in a table
            print_table("Before raster transform extent", 
            {
                "x_min_before": self.x_min_before,
                "x_max_before": self.x_max_before,
                "y_min_before": self.y_min_before,
                "y_max_before": self.y_max_before,
            })

            print_table("After raster transform extent", {
                "x_min_after": x_min_after,
                "x_max_after": x_max_after,
                "y_min_after": y_min_after,
                "y_max_after": y_max_after,
            })
            print(f"Spatial resolution of the raster: {cell_size}")
            print(f"Bounding box coordinates in WGS84: {x_min_after}, {y_min_after}, {x_max_after}, {y_max_after}")

        return x_min_after, y_min_after, x_max_after, y_max_after

    def bbox_to_WGS84(self, print_details=False) -> tuple:
        """
        This method calculates the bounding box coordinates of the raster in WGS84.

        Returns:
        Tuple of four values: Transformed coordinates in WGS84 (x_min_after, y_min_after, x_max_after, y_max_after)
        """

        return self.transform_and_print(print_details) # transform coordinates and print transformed values
    
# Example usage
# raster_file = os.path.join(input_dir,'lulc.tif')
# raster_transform = RasterTransform(raster_file)
# x_min, y_min, x_max, y_max = raster_transform.bbox_to_WGS84()
# or
# x_min, y_min, x_max, y_max = RasterTransform(raster_file).bbox_to_WGS84()
