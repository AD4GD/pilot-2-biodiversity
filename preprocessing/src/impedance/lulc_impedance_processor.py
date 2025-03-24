import os
import yaml
import warnings
import geopandas as gpd
import numpy as np
import copy
from osgeo import gdal
from typing import Iterator
# local imports
from utils import get_lulc_template
from impedance.interfaces.impedance_config_handler import ImpedanceConfigurationHandler

class LULCImpedanceProcessor(ImpedanceConfigurationHandler): 
    """
    The LULC_impedance_processor class processes the LULC raster dataset to extract stressors causing edge effect on habitats.
    It creates a masked raster file for each LULC code and updates the impedance configuration file with the LULC stressors.
    """

    def __init__(self, config_impedance:dict, config:dict, params_placeholder:dict, impedance_stressors:dict, year:int, current_dir:str,output_dir:str) -> None:
        """
        Initialize the Impedance class with the configuration file paths and other parameters.

        Args:
            config (dict): The configuration file.
            config_impedance (dict): The impedance configuration file.
            params_placeholder (dict): The dictionary template for the configuration YAML file (for each stressor).
            impedance_stressors (dict): The dictionary for stressors, mapping stressor raster path to YAML alias.
            year (int): The year for which the edge effect is calculated.
            current_dir (str): The parent directory
            output_dir (str): The output directory
        """
        super().__init__(config, config_impedance, params_placeholder, impedance_stressors, year,current_dir,output_dir)
        # additional directories
        self.lulc_dir = self.config.get('lulc_dir')
        if self.config["subcase_study"]:
            self.impedance_dir = os.path.join(current_dir, self.config["case_study_dir"], self.config['impedance_dir'].split('/')[0], self.config["subcase_study"] + "_" + self.config['impedance_dir'].split('/')[-1])
        else:
            self.impedance_dir = os.path.join(current_dir, self.config["case_study_dir"], self.config['impedance_dir'])
  
    def update_impedance_config(self):
        """
        Sequentially calls the methods to update the impedance configuration file with stressors and default decay parameters.
        - Updates the impedance configuration file with stressors and default decay parameters
        - Creates a masked raster file for each LULC code.
        - Updates the impedance stressors dictionary with the LULC stressors and their raster paths.

        Returns:
            impedance_stressors (dict): The dictionary of stressors with the LULC code as the key and the path to the raster file as the value.
            config_impedance (dict): The updated configuration file with the LULC stressors added.
        """
        # define the path to the LULC raster dataset
        self.lulc_path = os.path.normpath(os.path.join(get_lulc_template(self.config,self.year)))
        self.lulc_properties = self.get_lulc_raster_properties(self.lulc_path)
        self.impedance_stressors = self.extract_lulc_stressors(self.year)
        return self.impedance_stressors, self.config_impedance

        
    def get_lulc_raster_properties(self,lulc_path:str):
        """
        Create a dictionary of properties for the LULC raster dataset to be used when masking the raster with LULC codes.

        Args:
            lulc_path (str): The path to the LULC raster dataset.
        Returns:
            lulc_properties (dict): The dictionary of properties for the LULC raster dataset.
        """
        # create a dictionary to store the properties of the LULC raster dataset
        lulc_properties = {}

        # Open the LULC as an array (and extract its no data value and data type for logging):
        lulc = gdal.Open(lulc_path)
        lulc_properties['band'] = lulc.GetRasterBand(1)
        lulc_properties['band_array'] = lulc_properties['band'].ReadAsArray()
        lulc_properties['nodata_value'] = lulc_properties['band'].GetNoDataValue()
        lulc_properties['band_data_type'] = lulc_properties['band'].DataType
        lulc_properties['geotransform'] = lulc.GetGeoTransform()
        lulc_properties['projection'] = lulc.GetProjection()
        lulc_properties["x_size"] = lulc.RasterXSize
        lulc_properties["y_size"] = lulc.RasterYSize

        # close the raster dataset
        lulc = None

        print("NoData value:", lulc_properties['nodata_value']) # debug
        print("Data type of the band:", gdal.GetDataTypeName(lulc_properties['band_data_type']))# debug

        return lulc_properties

    def load_impedance_data(self) -> gpd.GeoDataFrame:
        """
        Load the impedance data from the configuration file and the CSV file.

        Args:
            None

        Returns:
            gpd.GeoDataFrame: The impedance data as a GeoDataFrame
        """
        impedance = self.config.get('impedance')
        if impedance is not None:
            print(f"Using auxiliary tabular data from {impedance}.")
        else:
            warnings.warn("No valid auxiliary tabular data found. Impact from stressors will be estimated from vector features only.") # warning, not error because stressors might come from CSV file pointing out LULC categories and from OSM vector dataset (at least one source or both)
            return None
        impedance_csv = os.path.join(self.impedance_dir,impedance) # define path
        
        return gpd.read_file(impedance_csv) # read CSV file through geopandas as a dataframe


    
    def extract_lulc_stressors(self, year:int, edge_effect_val:int = 1) -> dict:
        """
        Extracts the LULC types causing edge effect on habitats from the input CSV dataset.
        Each stressor is appended into the impedance configuration file as a separate entry and a masked raster file is created for each LULC code.

        Args:
            year (int): The year for which the edge effect is calculated.
            edge_effect_val (int): The value in the 'edge_effect' column of the CSV file which indicates that the LULC code causes edge effect on habitats. Default is 1.
        Returns:
            impedance_stressors (dict): The dictionary of stressors with the LULC code as the key and the path to the raster file as the value.
        """
        # сreate an empty list to store LULC codes which cause negative impact on habitats and edge effect
        edge_effect_list = []
        # 1. check if initial_lulc is enabled
        self.initial_lulc = self.config_impedance.get('initial_lulc', {"enabled":False})
        if self.initial_lulc.get('enabled') is True:
            print("Some categories from the input LULC dataset are considered as stressors...")

            # 2. check if the value in 'edge_effect' column is 1 - user specified that these LULC are affecting habitats
            impedance_df = self.load_impedance_data()
            if impedance_df is not None:
                # convert datatype of 'edge_effect' column into integer one if needed
                impedance_df['edge_effect'] = impedance_df['edge_effect'].astype(int)
                edge_effect_list = impedance_df[impedance_df['edge_effect'] == edge_effect_val]['lulc'].tolist()
                print (f"LULC type codes causing edge effect on habitats are: {edge_effect_list}")
                print("-"*40)
                
                # 3. iterate over each LULC code in edge_effect_list
                for lulc_code, lulc_code_str in self.populate_initial_lulc(edge_effect_list,year,self.params_placeholder):
                    try: 
                        # 4. create a mask for the current LULC code
                        self.impedance_stressors = self.mask_with_lulc_code(lulc_code, lulc_code_str)
                    except Exception as e:
                        print(f"Skipping LULC code {lulc_code}: {e}")
                        continue

                # 5. after processing all LULC codes, save the updated YAML configuration
                self.config_impedance['initial_lulc'] = self.initial_lulc
                with open('config_impedance.yaml', 'w') as yaml_file:
                    yaml.dump(self.config_impedance, yaml_file, default_flow_style=False)
                    print("Updated YAML configuration saved to config_impedance.yaml")

        else:
            print("No LULC categories from the input LULC raster dataset are considered stressors. Therefore, stressors will be extracted from vector data only.")
            print("-" * 40)

        return self.impedance_stressors

    def populate_initial_lulc(self, edge_effect_list: list, year:int, params_placeholder:dict) -> Iterator[tuple[str,str,dict]]:
        """
        Populates the initial_lulc dictionary with the LULC codes causing edge effect on habitats using placeholder values.
        If

        Args:
            edge_effect_list (list): The list of LULC codes causing edge effect on habitats.
            year (int): The year for which the edge effect is calculated.
            params_placeholder (dict): The dictionary template for the configuration YAML file (for each stressor).
        Returns:
            lulc_code (str): The LULC code causing edge effect on habitats.
            lulc_code_str (str): The string representation of the LULC code for YAML. For example, 'stressor_lulc_20_2015'.
        """
        for lulc_code in edge_effect_list:
            # convert lulc_code to string to match YAML keys
            lulc_code_str = f"stressor_lulc_{lulc_code}_{year}"

            # check if the current lulc_code has corresponding settings in the YAML file
            if lulc_code_str not in self.config_impedance['initial_lulc']:
                # if not found, create new keys for the LULC code with placeholders
                print(f"No specific settings found for LULC code {lulc_code}. Creating placeholder values.")
                
                # cast the placeholder dictionary into initial_lulc for a specific LULC code
                self.initial_lulc[lulc_code_str] = copy.deepcopy(params_placeholder) # deep copy, otherwise YAML creates placeholders like &id001
                
                # TODO add prompt to user to fill in the parameters
                print(f"""
                    New entry for LULC code {lulc_code} created in the YAML file with default values. 
                    {self.initial_lulc[lulc_code_str]}
                    Please fill in the values you think are more relevant.
                """)
                # print(f"Settings for LULC code {lulc_code}:\n{self.config_impedance['initial_lulc'][lulc_code_str]}")

            # else the lulc code setting alreay exists, so retain it
            else:
                print(f"Settings for LULC code {lulc_code} already exists in the YAML file.")
                self.initial_lulc[lulc_code_str] = self.config_impedance['initial_lulc'][lulc_code_str]
            # adding the raster structure to self.config_impedance
            self.config_impedance['initial_lulc'] = self.initial_lulc
            '''print(yaml.dump(self.config_impedance, default_flow_style=False))''' # debug

            yield lulc_code, lulc_code_str
            
    def mask_with_lulc_code(self, lulc_code:str, lulc_code_str:str) -> dict:
        """
        Creates a GeoTIFF raster file by masking the LULC raster dataset with a specific LULC code.

        Args:
            lulc_code (str): The LULC code to be used for masking.
            lulc_code_str (str): The string representation of the LULC code for YAML. For example, 'stressor_lulc_20_2015'.
        Returns:
            impedance_stressors (dict): The dictionary of stressors with the LULC code as the key and the path to the raster file as the value.
        """
        # 4. create a mask for the current LULC code
        mask = (self.lulc_properties['band_array'] == int(lulc_code))
        if np.any(mask):
            print(f"True values are present in the mask for LULC code: {lulc_code}.")
        else:
            print(f"No True values are present in the mask for LULC code: {lulc_code}.")

        # apply mask to LULC
        masked_data = np.where(mask, self.lulc_properties['band_array'], self.lulc_properties['nodata_value'])
        if np.any(masked_data != 0):
            print(f"Valid data is present in masked data for LULC code: {lulc_code}.")
        else:
            print(f"Masked data contains only zeros or nodata values for LULC code: {lulc_code}.")
            return self.impedance_stressors # Added to avoid processing empty rasters (for example, if stressors in protected areas are not used in this Notebook)

        #  create unique output raster path for each LULC code
        output_raster_path = os.path.join(self.output_dir, f'{lulc_code_str}.tif')
        # APPEND outputs with stressors to the list
        self.impedance_stressors[lulc_code_str] = output_raster_path  # mapping stressor raster path to LULC code

        # create output raster file
        driver = gdal.GetDriverByName('GTiff')
        out_dataset = driver.Create(output_raster_path, self.lulc_properties["x_size"], self.lulc_properties["y_size"], 1, self.lulc_properties['band_data_type'])
        out_dataset.SetGeoTransform(self.lulc_properties['geotransform'])
        out_dataset.SetProjection(self.lulc_properties['projection'])

        # write the masked data to the new raster file
        out_band = out_dataset.GetRasterBand(1)
        out_band.WriteArray(masked_data)
        nodata_value_int = int(self.lulc_properties['nodata_value'])
        out_band.SetNoDataValue(nodata_value_int)

        # flush data to disk
        out_band.FlushCache() # note: if delete it the last output will be invalid
        out_dataset.FlushCache()

        out_band = None
        out_dataset = None

        print(f"Masked LULC data for code {lulc_code} affecting habitats with edge effect saved to: {output_raster_path}")
        print("-" * 40)

        print(f"All stressors from initial LULC dataset saved successfully: {self.impedance_stressors.keys()}")
        print("-" * 40)
        
        return self.impedance_stressors