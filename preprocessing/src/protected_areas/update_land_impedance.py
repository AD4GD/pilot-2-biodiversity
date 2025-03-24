#external libraries
from osgeo import gdal
gdal.UseExceptions()
import numpy as np
import os
import subprocess
import pandas as pd

class UpdateLandImpedance():
    """
    This class is responsible for updating the impedance dataset based on the reclassification table or the multiplier effect of protected areas.
    """

    def __init__(self, config:dict, working_dir:str) -> None:
        """
        Initialize the UpdateLandImpedance class.

        Args:
            config (dict): The configuration dictionary.
            working_dir (str): The working directory.
        """
        self.config = config

        # read input folder for LULC data
        self.lulc_dir = self.config.get('lulc_dir')
        self.lulc_pa_dir = os.path.join(working_dir,self.config.get("case_study_dir"), "output", "protected_areas", "lulc_pa")
        # read impedance_dir as the output folder

        if self.config["subcase_study"]:
            self.impedance_dir = os.path.join(working_dir, self.config["case_study_dir"], self.config['impedance_dir'].split('/')[0], self.config["subcase_study"] + "_" + self.config['impedance_dir'].split('/')[-1])
        else:
            self.impedance_dir = os.path.join(working_dir, self.config["case_study_dir"], self.config['impedance_dir'])

        # read flag on reclassification table (lulc-impedance) from configuration file (true or false)
        # TODO - explicitly specify in CLI process-wdpa
        self.lulc_reclass_table = self.config.get('lulc_reclass_table')
        #TODO move to config validator
        # if self.lulc_reclass_table is None:
        #     warnings.warn("Flag on the usage of reclassification table is not found.")

        # read reclassification table (impedance) file with the reclassification table

        self.impedance_reclass_table = os.path.join(self.impedance_dir, self.config.get('impedance'))
        
        # read effect of protected areas (positive effect of protected areas on landscape impedance)
        self.pa_effect = self.config.get('pa_effect',None)
        # #TODO move to config validator
        # if self.pa_effect is None:
        #     warnings.warn("Effect of protected areas (multiplier) to refine landscape impedance is null or not found in the configuration file. If you do not specify the effect please ensure the compatibility of your reclassification table.")
        
        self.tiff_files = [f for f in os.listdir(self.lulc_dir) if f.endswith('_pa.tif')] # ADDED SUFFIX (UPDATED LULC)
        self.impedance_files = [f for f in os.listdir(self.impedance_dir) if f.endswith('.tif')] # IMPEDANCE DATASET
        print(f"Impedance files are: {self.impedance_files}")


    def update_impedance(self) -> None:
        """
        Updates the impedance dataset based on the reclassification table or the multiplier effect of protected areas.
        """

        # 1. If user wants to use reclassification table to update impedance dataset
        if self.lulc_reclass_table is True:
            print ("Impedance dataset is being updated by the reclassification table...")
            for tiff_file in self.tiff_files:
                input_raster_path = os.path.join(self.lulc_dir, tiff_file)
                print(tiff_file)
                # modify the output raster filename to ensure it's different from the input raster filename
                output_filename = "impedance_" + tiff_file
                output_raster_path = os.path.join(self.impedance_dir, output_filename)

                # call function and capture data_type for compression - Float32 or Int32
                data_type = self.reclassify_raster(input_raster_path, output_raster_path, self.impedance_reclass_table)
                print ("Data type used to reclassify LULC as impedance is",data_type)

                # compression using 9999 as nodata
                compressed_raster_path = os.path.splitext(output_raster_path)[0] + '_compr.tif'
                print("Path to compressed raster is:", compressed_raster_path)
                subprocess.run(['gdal_translate', output_raster_path, compressed_raster_path,'-a_nodata', '9999', '-ot', data_type, '-co', 'COMPRESS=LZW'])

                # we should rename compressed file in the same way as the original GeoTIFF
                '''
                # split the path into the base name and extension
                base_name, extension = os.path.splitext(output_raster_path)
                # add the '_pa' suffix to the base name
                pa_output_raster_path = f"{base_name}_pa{extension}"
                '''
            
                # as soon as gdal_translate doesn't support rewriting, we should delete non-compressed GeoTIFFs...
                os.remove(output_raster_path)
            
                os.rename(compressed_raster_path, output_raster_path)

                print("Reclassification complete for:", input_raster_path + "\n------------------------------------")

        else:
            print ("Impedance dataset is being updated by the multiplier (PA effect)...")
            for impedance_file in self.impedance_files:
                impedance_in_path = os.path.join(self.impedance_dir, impedance_file)
                # NOTE: If output_file already exists from a previous run, delete it to avoid errors with naming
                if impedance_file.endswith('_pa.tif'):
                    # remove the file 
                    os.remove(impedance_in_path)
                    continue
                base_name, extension = os.path.splitext(impedance_file)

                # get the corresponding LULC file for this impedance file (get year from the filename)
                year = base_name.split('_')[-1]
                lulc_file_base = f"lulc_{year}_pa.tif"
                lulc_file = os.path.join(self.lulc_pa_dir, lulc_file_base)

                # modify the output raster filename to ensure it's different from the input raster filename
                output_file = f"{base_name}_pa{extension}"
                impedance_out_path = os.path.join(self.impedance_dir, output_file)

                data_type = self.apply_multiplier(impedance_in_path, impedance_out_path, lulc_file, self.impedance_reclass_table, self.pa_effect)
                print ("Data type used to update",data_type)

                # compression using 9999 as nodata
                compressed_raster_path = os.path.splitext(impedance_out_path)[0] + '_compr.tif'
                print("Path to compressed raster is:", compressed_raster_path)
                subprocess.run(['gdal_translate', impedance_out_path, compressed_raster_path,'-a_nodata', '9999', '-ot', data_type, '-co', 'COMPRESS=LZW'])
            
                # as soon as gdal_translate doesn't support rewriting, we should delete non-compressed GeoTIFFs...
                os.remove(impedance_out_path)
                os.rename(compressed_raster_path, impedance_out_path)
                
                print("Multiplication complete for:", impedance_in_path + "\n------------------------------------")
        
    
    def apply_multiplier(self, impedance_in_path:str, impedance_out_path:str, lulc_pa_path:str, reclass_table:str, pa_effect:float) -> str:
        """
        Multiplies a raster based on the effect of protected areas.

        Args:
            impedance_in_path (str): The path to the input impedance raster.
            impedance_out_path (str): The path to the output impedance raster.
            lulc_pa_path (str): The path to the input LULC raster.
            reclass_table (str): The path to the table with values of reclassification from LULC codes to landscape impedance values.
            pa_effect (float): The value of PA effect.

        Returns:
            str: The data type of the output raster.
        """

        reclass_dict,has_decimal,data_type = self.generate_impedance_reclass_dict(reclass_table)
        # open the impedance dataset and LULC dataset in read-only mode
        impedance_ds = gdal.Open(impedance_in_path, gdal.GA_ReadOnly)
        lulc_pa_ds =  gdal.Open(lulc_pa_path, gdal.GA_ReadOnly)
        if impedance_ds is None or lulc_pa_ds is None:
            print("Error: Could not open LULC or impedance dataset.")
            return

        # read raster bands as arrays
        impedance_band = impedance_ds.GetRasterBand(1)
        lulc_pa_band = lulc_pa_ds.GetRasterBand(1)
        impedance_data = impedance_band.ReadAsArray()
        lulc_pa_data = lulc_pa_band.ReadAsArray()
        if impedance_data is None or lulc_pa_data is None:
            print("Error: Could not read LULC or impedance dataset.")
            return

        # apply the multiplier to impedance where intersection with protected areas (LULC > 100)  occurs
        output_data = np.where(lulc_pa_data > 100, impedance_data * pa_effect, impedance_data)

        # write output raster
        out_impedance_ds = gdal.GetDriverByName("GTiff").CreateCopy(
            utf8_path = impedance_out_path, # save to the same folder,
            src = impedance_ds, # copy the metadata
            strict = 1, # use the same data type
            options = ['COMPRESS=LZW']
        )

        # write modified data
        out_impedance_band = out_impedance_ds.GetRasterBand(1)
        out_impedance_band.WriteArray(output_data)
        out_impedance_band.SetNoDataValue(9999)
        
        # flush the cache to save the output raster
        out_impedance_band.FlushCache()
        out_impedance_ds.FlushCache()
        
        # close datasets
        impedance_ds = None
        lulc_pa_ds = None
        out_impedance_ds = None
        print(f"Multiplier has been applied to impedance dataset. Output saved to: {self.impedance_dir}")

        return data_type
    
    def generate_impedance_reclass_dict(self, reclass_table:str) -> tuple[dict, bool, str]:
        """
        Generates a reclassification dictionary from a reclassification table for impedance, depending on the data type.

        Args:
            reclass_table (str): The path to the reclassification table.

        Returns:
            tuple: A tuple containing the reclassification dictionary, a boolean indicating if the data type is decimal, and the data type.
        """
        has_decimal = False

        # read first few lines to detect the delimiter
        with open(reclass_table, 'r', encoding='utf-8-sig') as f:
            first_line = f.readline()
        # check if the first line contains a tab
        delimiter = '\t' if '\t' in first_line else ','
        # read into pandas dataframe and convert to numeric
        df = pd.read_csv(reclass_table, encoding='utf-8-sig', delimiter=delimiter) # allow tab and comma as CSV delimiters
        df = df.apply(pd.to_numeric, errors='coerce')

        # check if there are decimal values in the dataframe
        if np.issubdtype(df['impedance'].dtype, np.floating): #
            has_decimal = True
            # convert lulc to float too
            df['lulc'] = df['lulc'].astype(float)
        # create a dictionary from the dataframe reclass_dict[lulc] = impedance
        reclass_dict = df.set_index('lulc')['impedance'].to_dict()
        
        if has_decimal:
            print("LULC impedance is characterized by decimal values.")
            # update reclassification dictionary to align nodata values with one positive value (Graphab requires positive value as no_data value)
            # assuming nodata value is 9999 (or 9999.00 if estimating decimal values)
            reclass_dict.update({-2147483647: 9999.00, -32768: 9999.00, 0: 9999.00}) # minimum value for int16, int32 and 0 are assigned with 9999.00 (nodata)
            data_type = "Float64"
        else:
            print("LULC impedance is characterized by integer values only.")
            # update dictionary again
            reclass_dict.update({-2147483647: 9999, -32768: 9999, 0: 9999}) # minimum value for int16, int32 and 0 are assigned with 9999.00 (nodata)
            data_type = "Int64"
            
        return reclass_dict , has_decimal , data_type


    def reclassify_raster(self, input_raster:str, output_raster:str, reclass_table:str) -> str:
        """
        Reclassifies a raster based on a reclassification table.

        Args:
            input_raster (str): The path to the input raster.
            output_raster (str): The path to the output raster.
            reclass_table (str): The path to the reclassification table.

        Returns:
            str: The data type of the output raster.
        """
        # read the reclassification table
        reclass_dict = {}
        # map lulc with impedance values from the reclassification table
        reclass_dict,has_decimal,data_type = self.generate_impedance_reclass_dict(reclass_table)
        print ("Mapping dictionary used to classify impedance is:", reclass_dict)
        
        # open input raster
        dataset = gdal.Open(input_raster)
        if dataset is None:
            print("Could not open input raster.")
            return

        # get raster info
        cols = dataset.RasterXSize
        rows = dataset.RasterYSize

        print(f"Output raster path: {output_raster}")
        
        # initialize output raster in edit mode
        driver = gdal.GetDriverByName("GTiff")
       
        try:
            if has_decimal:
                output_dataset = driver.Create(output_raster, cols, rows, 1, gdal.GDT_Float32)
            else:
                output_dataset = driver.Create(output_raster, cols, rows, 1, gdal.GDT_Int32)
        except RuntimeError as e:
            print(f"Error during raster creation: {e}")
            return
        #TODO - to add condition on Int32 if integer values
        output_dataset.SetProjection(dataset.GetProjection())
        output_dataset.SetGeoTransform(dataset.GetGeoTransform())

        # reclassify each pixel value
        input_band = dataset.GetRasterBand(1)
        output_band = output_dataset.GetRasterBand(1)
        # read the raster as a NumPy array
        input_data = input_band.ReadAsArray()

        if input_data is None:
            print("Could not read input raster.")
            return
        elif reclass_dict is None:
            print("Reclassification dictionary is empty.")
            return
        # apply reclassification using dictionary mapping
        output_data = np.vectorize(reclass_dict.get)(input_data)
        output_band.WriteArray(output_data)
        # flush the cache to save the output raster
        output_band.FlushCache()
        output_dataset.FlushCache()

        '''FOR CHECKS
        print (f"input_data_shape is': {input_data.shape}")
        print (f"output_data_shape is': {output_data.shape}")
        '''
        # close datasets
        dataset = None
        output_dataset = None

        return data_type