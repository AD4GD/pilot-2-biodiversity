from osgeo import gdal
import os
# local imports
from utils import load_yaml, save_yaml, get_max_from_tif, find_stressor_params, read_years_from_config
from impedance.impedance_processor import ImpedanceProcessor
from impedance.impedance_config_processor import ImpedanceConfigProcessor
import numpy as np
import csv

#TODO use verbose flag to print debug messages
class ImpedanceWrapper():
    """
    This class is a wrapper for the Impedance processor.
    It abstracts the pipeline process of populating the impedance configuration file, processing the stressors, and calculating the impedance. 
    """
    def __init__(self,
        working_dir: str,
        decline_type: str,
        lambda_decay: float,
        k_value: float,
        config_path:str,
        config_impedance_path:str,
        verbose: bool 
    ):
        """
        Initialize the ImpedanceWrapper class with the configuration file paths and other parameters.

        Args:
            working_dir (str): The working directory for the project.
            decline_type (str): The type of decline.
            lambda_decay (float): The lambda decay value.
            k_value (float): The k value.
            config_path (str): The path to the main configuration file.
            config_impedance_path (str): The path to the impedance configuration file.
            verbose (bool): The verbosity flag.
        """
    
        # load the configuration files
        self.config_path = config_path
        self.config = load_yaml(self.config_path)
        self.config_impedance_path = config_impedance_path
        self.config_impedance = load_yaml(self.config_impedance_path)
        self.verbose = verbose
        
        # define the dictionary template for the configuration YAML file (for each stressor). We are using variables defined above.
        self.params_placeholder = {
            'types': None, # specify whether category of stressors has particular types different in parameters (for example, primary and secondary roads)
            'decline_type': decline_type,  # user will choose from 'exp_decline' and 'prop_decline'
            'exp_decline': {
                'lambda_decay': lambda_decay  # placeholder for exponential decay value
            },
            'prop_decline': {
                'k_value': k_value  # placeholder for proportional decline value
            }
        }

        self.years = read_years_from_config(self.config) # read years from the configuration file
        print(f"Years are: {self.years}")

        # to be passed into other classes
        self.current_dir = os.path.normpath(working_dir)
        self.case_study_dir = os.path.join(self.current_dir, self.config.get('case_study_dir')) # get the case study directory
        self.output_dir = os.path.join(self.case_study_dir, "output") # get the output directory
        self.stressor_dir = os.path.join(self.output_dir, "stressors") # get the directory for stressors
        if self.config["subcase_study"]:
            self.impedance_dir = os.path.join(self.current_dir, self.config["case_study_dir"], self.config['impedance_dir'].split('/')[0], self.config["subcase_study"] + "_" + self.config['impedance_dir'].split('/')[-1])
        else:
            self.impedance_dir = os.path.join(self.current_dir, self.config["case_study_dir"], self.config['impedance_dir'])

        # make a dir for impedance results
        self.impedance_res_dir = os.path.join(self.stressor_dir, 'impedance_results')
        if not os.path.exists(self.impedance_res_dir):
            os.makedirs(self.impedance_res_dir)

        

    def validate_impedance_config(self, impedance_stressors:dict) -> str:
        """
        Validate the impedance configuration file for the stressors.

        Args:
            impedance_stressors (dict): The dictionary of stressors, mapping stressor raster path to YAML alias.
        Returns:
            str: return 'exit' if the configuration file is valid, error message otherwise.
        """

        validation_config = load_yaml(self.config_impedance_path)
        err_msg = ""
        for yaml_stressor in impedance_stressors.keys():
            # use params_placeholder to validate if each stressor has all the required parameters and datatypes
            stressor_params = find_stressor_params(validation_config, yaml_stressor)
            print(f"Validating stressor: {stressor_params}") # debug
            for key, value in stressor_params.items(): 
                if key not in self.params_placeholder:
                    err_msg += f"Parameter {key} is not a valid key name.\n"

                elif type(self.params_placeholder[key]) is dict:
                    value_dict = value
                    # get first key from the dictionary
                    nested_key = list(value_dict.keys())[0]
                    # get the value of the nested key from params_placeholder
                    expected_data = self.params_placeholder[key][nested_key]
                    actual_data = value_dict[nested_key]
                    if not isinstance(actual_data, type(expected_data)):
                        err_msg += f"Parameter {key}:{nested_key} has a different datatype. Expected {type(expected_data)} but got {type(actual_data)}.\n"

            # check if all keys are present in the configuration file
            for key in self.params_placeholder.keys():
                if key not in stressor_params:
                    err_msg += f"Parameter {key} is missing from the configuration file.\n"

            if err_msg != "":
                return err_msg
            else:
                self.config_impedance = validation_config
                return "exit"
            
    def reclassify_lulc2impedance(self, input_raster, impedance_raster, reclass_table, out_nodata):
        """
        Creates impedance raster - reclassifies input raster (LULC) based on table mapping between LULC codes and impedance values

        Args:
            input_raster: Path to input LULC raster.
            impedance_raster: Path to output impedance raster.
            reclass_table: CSV table with mapping between LULC codes and impedance values
            out_nodata: nodata value assigned to the output impedance_raster

        Returns:
            str: Path to the output impedance raster.
        """
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
                Exception(f"Invalid data format in reclassification table: {row}")

        nodata_value = float(out_nodata) if has_decimal_values else out_nodata
        
        dataset = gdal.Open(input_raster)
        if dataset is None:
            Exception("Could not open input raster.")

        cols, rows = dataset.RasterXSize, dataset.RasterYSize
        driver = gdal.GetDriverByName("GTiff")
        output_dataset = driver.Create(impedance_raster, cols, rows, 1, gdal.GDT_Float32 if has_decimal_values else gdal.GDT_Int32)
        output_dataset.SetProjection(dataset.GetProjection())
        output_dataset.SetGeoTransform(dataset.GetGeoTransform())

        input_band = dataset.GetRasterBand(1)
        input_nodata = input_band.GetNoDataValue()
        if input_nodata is not None:
            reclass_dict[int(input_nodata)] = nodata_value

        print(f"Mapping dictionary used to classify impedance is: {reclass_dict}")

        input_data = input_band.ReadAsArray()
        
        unique_values = np.unique(input_data)
        missing_values = [val for val in unique_values if val not in reclass_dict]
        print(f"Missing values in the dictionary are: {missing_values}")

        output_data = np.where(
            np.isin(input_data, list(reclass_dict.keys())), 
            np.vectorize(lambda x: reclass_dict.get(x, float(out_nodata) if has_decimal_values else out_nodata), otypes=[float if has_decimal_values else int])(input_data), 
            float(out_nodata) if has_decimal_values else out_nodata
        )

        output_band = output_dataset.GetRasterBand(1)
        output_band.SetNoDataValue(nodata_value)
        output_band.WriteArray(output_data)

        dataset = None
        output_dataset = None

        return impedance_raster

    def get_impedance_max_value(self, impedance_tif_path:str) -> tuple[gdal.Dataset, float]:
        """
        Get the maximum value from the impedance raster dataset.
        
        Args:
            impedance_tif_path (str): The path to the impedance raster GeoTIFF dataset.

        Returns:
            tuple: Tuple containing the impedance dataset and the maximum value of the impedance dataset.
        """
        
        if impedance_tif_path is not None:
            #NOTE: DEBUG
            print(f"Impedance TIF path is {impedance_tif_path}")
            impedance_ds = gdal.Open(impedance_tif_path) # open raster impedance dataset
            impedance_max = get_max_from_tif(impedance_ds) # call function from above
            print (f"Impedance raster GeoTIFF dataset used is {impedance_tif_path}") # debug
            print (f"Maximum value of impedance dataset: {impedance_max}") # debug
        else:
            raise FileNotFoundError(f"Impedance raster GeoTIFF dataset '{impedance_tif_path}' is not found! Please check the configuration file.") # stop execution
        
        return impedance_ds, impedance_max
    
    def process_impedance_config(self, year:int, use_lulc_pa:bool) -> dict:
        """
        Process the impedance configuration (initial setup + lulc & osm stressors)

        Args:
            year (int): The year to use for the impedance dataset.
            use_lulc_pa (bool): Use LULC PA sum rasters instead of original LULC rasters

        Returns:
            impedance_stressors (dict): dictionary for stressors, mapping stressor raster path to YAML alias
        """
        # initialize the dictionary for stressors, which contains mapping stressor raster path to YAML alias
        impedance_stressors = {} 

        config_dir = os.path.dirname(self.config_path)
        print(f"YEAR is {year}")
        icp = ImpedanceConfigProcessor(year=year, params_placeholder=self.params_placeholder, config=self.config, config_impedance=self.config_impedance, verbose=self.verbose)
        icp.setup_config_impedance()
        impedance_stressors, self.config_impedance = icp.process_stressors(self.current_dir, self.stressor_dir, config_dir,use_lulc_pa)
        # save the updated configuration file
        save_yaml(self.config_impedance, self.config_impedance_path)

        return impedance_stressors
    

    def calculate_impedance(self, year:int, impedance_stressors:dict, impedance_ds:gdal.Dataset, impedance_max:float, out_nodata:int) -> str:
        """
        Calculate the impedance for the stressors and generate the maximum result raster.

        Args:
            year (int): The year to use for the impedance dataset.
            impedance_stressors (dict): The dictionary of stressors, mapping stressor raster path to YAML alias.
            impedance_ds (gdal.Dataset): The impedance raster dataset.
            impedance_max (float): The maximum value of the impedance dataset.
            out_nodata (int): The output nodata value for intermediate dist/edge datasets.
        
        Returns:
            str: The path to the maximum result raster GeoTIFF file.
        """
        # initialise variables with outputs of the effects from all rasters
        max_result = None
        cumul_result = None
        driver = gdal.GetDriverByName('GTiff') # has already been defined above
        mem_driver = gdal.GetDriverByName('MEM')
        impedance_processor = None # initialize the impedance processor to use after the loop
 
        for yaml_stressor, stressor_raster in impedance_stressors.items():
            # read the raster
            print(f"Processing: {stressor_raster}") # debug
            print(f"Corresponding key in YAML configuration: {yaml_stressor}") # debug
            # open the input raster dataset
            impedance_processor = ImpedanceProcessor(
                max_result=max_result,
                cumul_result=cumul_result,
                current_dir=self.current_dir,
                output_dir=self.impedance_res_dir,
                year=year,
                config_impedance=self.config_impedance,
                yaml_stressor=yaml_stressor,
                stressor_raster=stressor_raster,
                driver=driver,
                mem_driver=mem_driver,
                impedance_ds=impedance_ds,
                impedance_max=impedance_max,
                nodata_value=out_nodata,
                verbose=self.verbose
                )
            if impedance_processor.ds is None:
                print(f"Failed to open {stressor_raster}, skipping...")
                continue
            else:
                impedance_processor.handle_no_data()
                proximity_data = impedance_processor.compute_proximity(out_nodata)
                max_result = impedance_processor.calculate_edge_effect(proximity_data)
                # print(f"Maximum result: {max_result}") # debug
        
        # Once all stressors have been processed, update the impedance dataset with decay
        max_result_tif = impedance_processor.update_impedance_with_decay()
        return max_result_tif
    
if __name__ == "__main__":
    stressor_yaml_path = os.path.join('config', 'stressors.yaml')
    use_lulc_pa = True

    if not os.path.exists(stressor_yaml_path):
        raise FileNotFoundError("The stressors.yaml file is not found. Please add the file to the config directory.")
    
    iw = ImpedanceWrapper( 
        decline_type = 'exp_decline', # 'exp_decline' or 'prop_decline'
        lambda_decay = 500,
        k_value = 500,
        config_path = 'config/config.yaml',
        config_impedance_path = 'config/config_impedance.yaml',
        verbose = True
    )

    impedance_stressors = {}
    for year in iw.years:
        print(f"Processing year: {year}")
        # 1. Process the impedance configuration (initial setup + lulc & osm stressors)
        # e.g. impedance_stressors = {'primary': '/data/data/output/roads_primary_2018.tif'}
        # update the impedance_stressors dictionary with the stressors for the current year
        impedance_stressors.update(iw.process_impedance_config(year,use_lulc_pa=False))
        # NOTE: use_lulc_pa=True if you do want to use the updated impedance files

    # 2. Prompt user to update the configuration file
    print("Please check/update the configuration file for impedance dataset (config_impedance.yaml):")

    # 2.1. Or validate after manual update 
    is_valid = iw.validate_impedance_config(impedance_stressors)
    if not is_valid:
        raise ValueError("The configuration file is not valid. Please update the configuration file.")
    
    for year in iw.years:
        # 3.0 set the output path for the new impedance raster dataset 
        impedance_tif_template = str(iw.config.get('impedance_tif'))
        impedance_tif_path = impedance_tif_template.format(year=year) # substitute year from the configuration file
        original_impedance_tiff = os.path.normpath(os.path.join(iw.impedance_dir,impedance_tif_path))
        
        impedance_tif_path = impedance_tif_path.replace(".tif", "_upd.tif")
        #impedance_tif_path = os.path.normpath(os.path.join(iw.impedance_res_dir , impedance_tif_path))
        impedance_tif_path = os.path.normpath(os.path.join(iw.impedance_dir,impedance_tif_path))

        lulc_template = str(iw.config.get('lulc'))
        if lulc_template is None or lulc_template == "":
            raise Exception("lulc in config is null/empty or does not exist")
        elif use_lulc_pa:
            lulc_template = lulc_template.replace("{year}.tif","pa_{year}_upd.tif").format(year = year)
        else:
            lulc_template = lulc_template.replace('.tif', "_upd.tif").format(year=year)
        lulc_upd = os.path.join(iw.config.get('case_study_dir'), "output", lulc_template)
    
        # 3.1 get nodata from original impedance raster
        from utils import get_nodata_from_raster
        nodata_value = get_nodata_from_raster(original_impedance_tiff)

        # 3.2 Reclassify LULC raster to impedance raster
        impedance_tif = iw.reclassify_lulc2impedance(
            input_raster= lulc_upd,
            impedance_raster= impedance_tif_path,
            reclass_table= os.path.join(iw.impedance_dir, iw.config.get('impedance')),
            out_nodata= nodata_value
        )
         
        # 4  Get the maximum value of the impedance raster dataset
        impedance_ds, impedance_max = iw.get_impedance_max_value(impedance_tif_path=impedance_tif)

        #5 Calculate impedance
        max_result_tif = iw.calculate_impedance(year,impedance_stressors,impedance_ds,impedance_max, nodata_value)

    # # delete temporary impedance stressors.yaml
    # os.remove(stressor_yaml_path)
    # print("Temporary file with OSM stressors has been deleted")
