from reprojection import RasterTransform

class RasterMetadata():
    """
    Stores metadata of a raster file
    """
    def __init__(self, x_min: str, x_max: str, y_min: str, y_max: str, cell_size: str, xres: str, yres: str, is_cartesian: str, crs_info:str, nodata: any) -> None:
        self.x_min = x_min
        self.x_max = x_max
        self.y_min = y_min
        self.y_max = y_max
        self.cell_size = cell_size
        self.xres = xres
        self.yres = yres
        self.is_cartesian = is_cartesian
        self.crs_info = crs_info
        self.nodata = nodata

    def __str__(self) -> str:
        return (f"Extent of LULC files\n"
            f"Minimum X Coordinate: {self.x_min}\n"
            f"Maximum X Coordinate: {self.x_max}\n"
            f"Minimum Y Coordinate: {self.y_min}\n"
            f"Maximum Y Coordinate: {self.y_max}\n"
            f"Spatial resolution (pixel size): {self.cell_size}\n"
            f"No Data value: {self.nodata}\n"
            f"Coordinate reference system: {self.crs_info}\n"
            f"Is Cartesian: {self.is_cartesian}\n")
            

    @staticmethod
    def from_raster(raster_path: str) -> 'RasterMetadata':
        """
        Extracts metadata from a raster file

        Args:
            raster_path (str): path to raster file

        Returns:
            RasterMetadata: metadata of the raster file. (forward referenced type)
        """
        rt = RasterTransform(raster_path)
        
        xres, yres = rt.check_res()
        x_min, x_max, y_min, y_max, cell_size, nodata = rt.get_raster_info()

        # print the results
        print(f"x_min: {x_min}")
        print(f"x_max: {x_max}")
        print(f"y_min: {y_min}")
        print(f"y_max: {y_max}")
        print(f"Spatial resolution of input raster dataset (cell size): {cell_size}")
        print(f"No Data value: {nodata}")

        # check if the input raster dataset has a projected (cartesian) CRS
        is_cartesian, crs_info = rt.check_cart_crs()

        # cast to Raster_Properites object
        # print(crs_info)
        # print(is_cartesian)
        return RasterMetadata(x_min, x_max, y_min, y_max, cell_size, xres, yres, is_cartesian, crs_info, nodata)
        