import warnings
from osgeo import gdal
import numpy as np
import os
# local imports
from utils import find_stressor_params

class ImpedanceProcessor():
    """
    The Impedance_processor class processes the impedance raster dataset to calculate the edge effect on habitats.
    It computes the proximity raster for each stressor and calculates the edge effect based on the proximity data and the configuration parameters.
    """

    def __init__(self, max_result:float,cumul_result:float, current_dir:str, output_dir:str, config_impedance:dict, yaml_stressor:str, stressor_raster:str, driver:gdal.Driver, mem_driver:gdal.Driver, impedance_ds:gdal.Dataset, impedance_max:float, verbose:bool) -> None:
        """
        Initialize the Impedance class with the configuration file paths and other parameters.

        Args:
            max_result (float): The maximum result for the impedance calculation.
            cumul_result (float):  **NOT IMPLEMENTED YET** The cumulative result for the impedance calculation.
            current_dir (str): The parent directory
            output_dir (str): The output directory
            config_impedance (dict): The impedance configuration file.
            yaml_stressor (str): The YAML alias for the stressor.
            stressor_raster (str): The path to the stressor raster dataset.
            driver: The GDAL driver for the raster dataset.
            mem_driver: The GDAL driver for the in-memory dataset.
            impedance_ds: The impedance raster dataset.
            impedance_max: The maximum value for the impedance dataset.
            verbose (bool): The flag to print the debug statements.
        """
        self.max_result = max_result
        self.cumul_result = cumul_result
        self.current_dir = current_dir
        self.output_dir = output_dir
        self.config_impedance = config_impedance
        self.yaml_stressor = yaml_stressor
        self.stressor_raster = stressor_raster
        self.driver = driver
        self.mem_driver = mem_driver
        self.impedance_ds = impedance_ds
        self.impedance_max = impedance_max
        # open the input raster dataset
        self.ds = gdal.Open(stressor_raster)
        self.verbose = verbose #TODO: implement verbose mode

    def handle_no_data(self) -> tuple[int, tuple[float,float], str]:
        """
        Handle the no data values in the input raster dataset.

        Returns:
            tuple: Tuple containing the no data value, the geotransform, and the projection of the input raster dataset.
        """

        self.input_band = self.ds.GetRasterBand(1)
        self.nodata_value = self.input_band.GetNoDataValue()
        print(f"Original no data value for input dataset is {self.nodata_value}") # debug
        if self.nodata_value is None:
            self.nodata_value = -9999  
            self.input_band.SetNoDataValue(self.nodata_value)
        print(f"No data value for input dataset is {self.nodata_value}") # debug

        data = self.input_band.ReadAsArray()
        # debug
        min_value = np.min(data)
        max_value = np.max(data)
        print(f"Range of values in the data: {min_value} to {max_value}")

        no_data_count = np.sum(data == self.nodata_value) # supposed to be non-zero
        print (f"No data count: {no_data_count}")

        # get the geo-transform (affine transformation parameters)
        self.geotransform = self.ds.GetGeoTransform()
        self.projection = self.ds.GetProjection()
        return self.nodata_value, self.geotransform, self.projection

    def compute_proximity(self):
        """
        Compute the proximity raster for the stressor raster dataset.

        Returns:
            np.ndarray: The proximity data as a NumPy array.
        """
        output_ds = self.mem_driver.Create('', self.impedance_ds.RasterXSize, self.impedance_ds.RasterYSize, 1, gdal.GDT_Int32) # Int64 might not support .SetNoDataValue()
        # NOTE: it is not possible to specify no data value directly in gdal_create

        # set geotransform parameters from input file
        if self.geotransform:
            output_ds.SetGeoTransform(self.geotransform)
        if self.projection:
            output_ds.SetProjection(self.projection)

        output_band = output_ds.GetRasterBand(1)
        
        try:
            gdal.ComputeProximity(self.input_band, output_band, ['DISTUNITS=GEO', f'NODATA={self.nodata_value}']) 
        except RuntimeError as e:
            print(f"Error computing proximity for {self.stressor_raster}: {str(e)}")

        # 3.1 read proximity data as a NumPy array for validation/debugging
        proximity_data = output_band.ReadAsArray()
        output_nodata_value = output_band.GetNoDataValue()
        print(f"NoData value of output raster is {output_nodata_value}")
        # print(proximity_data) # debug: 0 for all pixels of last raster

        output_nodata_count = np.sum(proximity_data == output_nodata_value)
        print(f"Output no data count is {output_nodata_count}") # supposed to be 0
        print(f"No data value for output dataset is {output_nodata_value}") # debug

        # warn if no data values are detected
        if output_nodata_count > 0:
            warnings.warn(f"No data values have been detected in the proximity raster for {self.stressor_raster}. Check the validity of the input vector dataset.")

        # create a VRT file as a reference to the proximity raster in memory
        vrt_output_path = os.path.join(self.output_dir, f'{os.path.basename(self.stressor_raster).replace(".tif", "")}_dist.vrt')
        vrt_options = gdal.BuildVRTOptions(resampleAlg='nearest')

        # build VRT from the in-memory proximity dataset
        vrt_ds = gdal.BuildVRT(vrt_output_path, [output_ds], options=vrt_options)

        # debug: export proximity raster to GeoTIFF
        tiff_output = f'{os.path.basename(self.stressor_raster).replace(".tif", "")}_dist.tif'
        dist_tiff_output = os.path.normpath(os.path.join(self.current_dir, self.output_dir ,tiff_output))
        print(f"Distance path: {dist_tiff_output}") # debug
        gdal.Translate(dist_tiff_output, vrt_ds, format="GTiff", outputType=gdal.GDT_Int32, creationOptions=["COMPRESS=LZW"])
        # debug
        if os.path.exists(dist_tiff_output):
            print(f"File successfully created: {dist_tiff_output}")
        else:
            print(f"Error: File not created at: {dist_tiff_output}")

        # flush the cache
        output_band.FlushCache()
        vrt_ds.FlushCache()
        output_ds.FlushCache()

        return proximity_data
    
    def find_param(self, stressor_dict, search_key):
        """
        Find the parameter in the stressor dictionary by searching the key recursively

        Args: 
            stressor_dict (dict): The dictionary of stressor parameters.
            search_key (str): The key to search in the dictionary.

        Returns:
            value: The value of the key in the dictionary.
        """
        for key, value in stressor_dict.items():
            if key == search_key:
                return value
            elif isinstance(value, dict):
                result = self.find_param(value, search_key)
                if result is not None: # added for recursive search because otherwise if the first nested dict doesn't contain key, it will return None
                    return result
        return None
                
    def calculate_edge_effect(self, proximity_data: np.ndarray):
        """
        Calculate the edge effect based on the proximity data and the impedance configuration parameters (decay type, lambda decay, k-value).

        Args:
            proximity_data (np.ndarray): The proximity data as a NumPy array.

        Returns:
            np.ndarray: The maximum result for the impedance calculation.
        """
        # NOTE: decay might vary across classes of stressors. For example, primary and tertiary roads will have the different negative impact on natural habitats. 
        # In first case it will occur more likely at some distance than in the second case.
        # therefore, we attempt to define different decay parameter by types of vector dataset
         # set decay output path
        edgeEff_output_path = os.path.join(self.output_dir, f'{os.path.basename(self.stressor_raster).replace(".tif", "")}_edge.tif')
        print(f"Path to output raster dataset with calculated edge effect: {edgeEff_output_path}") # debug

        # get corresponding parameter for each stressor
        stressor_params = find_stressor_params(self.config_impedance, self.yaml_stressor) # !if the output of find_stressor_params it will be automatically replaced with sample values!
        print(f"self.yaml_stressor is {self.yaml_stressor}")
        print(f"Stressor parameters: {stressor_params}") # debug 
        decline_type = self.find_param(stressor_params, 'decline_type')
        lambda_decay = self.find_param(stressor_params, 'lambda_decay')
        k_value = self.find_param(stressor_params, 'k_value')

        # debug
        print(f"""Fetched parameters for the stressor: 
            {decline_type} (type of decline), 
            {lambda_decay} (lambda decay parameter), 
            {k_value} (k-value of proportional decline)"""
        )

        # calculate impedance now
        if decline_type == 'exp_decline':
            result = self.impedance_max * np.exp(-proximity_data / lambda_decay) # impedance_max value has already been extracted through a separate function
            print(f"Decline type is {decline_type}. Expression to calculate edge effect: {self.impedance_max} * exp(- proximity_data / {lambda_decay})") # debug
        elif decline_type == 'prop_decline':  # proportional decay 
            result = np.maximum(self.impedance_max - k_value * proximity_data, 0)
            print(f"Decline type is {decline_type}. Expression to calculate edge effect: max({self.impedance_max} - {k_value} * proximity_data, 0)") # debugt

        # set values < 0 to no data value
        result[result <= 0] = self.nodata_value
        result = np.ma.masked_equal(result, self.nodata_value)

        # combine the results: keep the maximum value for each pixel throutgh iterations (keep the larger impedance)
        if self.max_result is None:
            self.max_result = result.copy()  # initialize with the first raster's result
        else:
            self.max_result = np.maximum(self.max_result, result)  # take max of previous and current
        
        # FOR CUMULATIVE FUNCTION OF DIFFERENT STRESSORS 
        '''
        # combine the results from each raster by summing
        if self.cumul_result is None:
            self.cumul_result = result.copy()  # initialize with a copy of the first raster
        else:
            self.cumul_result += result  # increment cumulative result
        '''
        # define edge effect result for export
        out_result = self.driver.Create(edgeEff_output_path, self.impedance_ds.RasterXSize, self.impedance_ds.RasterYSize, 1, gdal.GDT_Int32, ['COMPRESS=LZW']) # compress
        # set geotransform and projection before exporting
        out_result.SetGeoTransform(self.geotransform)
        out_result.SetProjection(self.projection)
        
        # write the masked result to the output raster's first band
        out_band = out_result.GetRasterBand(1)

        # set the nodata value in the band
        if self.nodata_value is not None:
            out_band.SetNoDataValue(self.nodata_value)  # define nodata 

        # write array to the band of output dataset (export)
        out_band.WriteArray(result)

        # clean up intermediate objects by flushing the cache
        # flush the cache
        out_band.FlushCache()
        out_result.FlushCache()
        self.ds.FlushCache()   

        print(f"Finished processing: {self.stressor_raster}")
        print("-" * 40)
        
        return self.max_result # return the maximum result to be used in the next iteration

    def update_impedance_with_decay(self) -> str:
        """
        Once the edge effect for all stressors is calculated, this function will be called to generate a maximum result raster.
        The maximum result is the maximum impedance value for each pixel across all stressors.

        Returns:
            str: The path to the maximum result raster GeoTIFF file.
        """
        impedance_band = self.impedance_ds.GetRasterBand(1)
        impedance_array = impedance_band.ReadAsArray()

        #let's choose the maximum value from initial impedance dataset and edge effect calculated previously:
        self.max_result = np.maximum(self.max_result, impedance_array)
        #then, apply the maximum value of initial impedance dataset as a cap to the maximum result (impedance can't be higher than in the initial impedance dataset):
        self.max_result[self.max_result > self.impedance_max] = self.impedance_max

        # DEBUG: ensure the size of the final result matches initial impedance dataset. In theory, they should be identical, but rasterised OSM datasets can have larger spatial extent than input LULC or impedance datasets.
        impedance_array_shape = impedance_array.shape # shape of input impedance dataset
        max_result_shape = self.max_result.shape # shape of output dataset with maximum values of edfe effect
        if impedance_array.shape != self.max_result.shape:
            warnings.showwarning("The impedance raster dimensions do not match the cumulative decay raster dimensions.")
            print(f"Initial impedance shape is {impedance_array_shape} and maximum result shape is {max_result_shape}.")
        else:
            print(f"The shape of maximum result is the same as the shape of initial impedance array shape: {impedance_array_shape} and {max_result_shape}.") # debug

        # write the maximum result to the output raster's first band
        max_output_path = os.path.join(self.output_dir, 'max_result.tif') # TODO - to cast filename to config.yaml: 'impedance_lulc_ukceh_25m_{year}_upd.tif' 
        max_out_result = self.driver.Create(max_output_path, self.impedance_ds.RasterXSize,  self.impedance_ds.RasterYSize, 1, gdal.GDT_Int32, ['COMPRESS=LZW'])
        # set geotransform and projection for export
        max_out_result.SetGeoTransform(self.geotransform)
        max_out_result.SetProjection(self.projection)

        # Then, export the maximum result to the output raster. No data value should be explicitly specified to avoid any potential issues:
        try:
            max_out_band = max_out_result.GetRasterBand(1)
            max_out_band.WriteArray(self.max_result)
            print(f"The updated impedance raster dataset has been exported to: {max_output_path}")
        except Exception as e:
            raise ValueError("The updated impedance raster dataset has not been exported: {e}")

        if self.nodata_value is not None: # set nodata value for maximum result
            max_out_band.SetNoDataValue(self.nodata_value)

        # flush the cache
        max_out_band.FlushCache()
        max_out_result.FlushCache()
        self.impedance_ds.FlushCache()

        return max_output_path
        