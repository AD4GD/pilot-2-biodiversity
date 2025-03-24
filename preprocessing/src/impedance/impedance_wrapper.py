from osgeo import gdal
import os
# local imports
from utils import load_yaml, save_yaml, get_max_from_tif, find_stressor_params, read_years_from_config
from impedance.impedance_processor import ImpedanceProcessor
from impedance.impedance_config_processor import ImpedanceConfigProcessor

#TODO use verbose flag to print debug messages
class ImpedanceWrapper():
    """
    This class is a wrapper for the Impedance processor.
    It abstracts the pipeline process of populating the impedance configuration file, processing the stressors, and calculating the impedance. 
    """
    def __init__(self,
        types: str, # None on init
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
            types (str): The types of stressors.
            decline_type (str): The type of decline.
            lambda_decay (float): The lambda decay value.
            k_value (float): The k value.
            config_path (str): The path to the main configuration file.
            config_impedance_path (str): The path to the impedance configuration file.
            verbose (bool): The verbosity flag.
        """
    
        # load the configuration files
        self.config = load_yaml(config_path)
        self.config_impedance_path = config_impedance_path
        self.config_impedance = load_yaml(self.config_impedance_path)
        self.verbose = verbose
        
        # define the dictionary template for the configuration YAML file (for each stressor). We are using variables defined above.
        self.params_placeholder = {
            'types': types, # specify whether category of stressors has particular types different in parameters (for example, primary and secondary roads)
            'decline_type': decline_type,  # user will choose from 'exp_decline' and 'prop_decline'
            'exp_decline': {
                'lambda_decay': lambda_decay  # placeholder for exponential decay value
            },
            'prop_decline': {
                'k_value': k_value  # placeholder for proportional decline value
            }
        }

        self.years = read_years_from_config(self.config) # read years from the configuration file

        # to be passed into other classes
        self.current_dir = os.path.normpath(os.getcwd())
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

    def get_impedance_max_value(self, year:int) -> tuple[gdal.Dataset, float]:
        """
        Get the maximum value from the impedance raster dataset.
        
        Args:
            year (int): The year to use for the impedance dataset.

        Returns:
            tuple: Tuple containing the impedance dataset and the maximum value of the impedance dataset.
        """
        impedance_tif_template = self.config.get('impedance_tif')
        impedance_tif = impedance_tif_template.format(year=year) # substitute year from the configuration file
        impedance_tif = os.path.normpath(os.path.join(self.current_dir,self.impedance_dir,impedance_tif))
        
        if impedance_tif is not None:
            impedance_ds = gdal.Open(impedance_tif) # open raster impedance dataset
            impedance_max = get_max_from_tif(impedance_ds) # call function from above
            print (f"Impedance raster GeoTIFF dataset used is {impedance_tif}") # debug
            print (f"Maximum value of impedance dataset: {impedance_max}") # debug
        else:
            raise FileNotFoundError(f"Impedance raster GeoTIFF dataset '{impedance_tif}' is not found! Please check the configuration file.") # stop execution
        
        return impedance_ds, impedance_max
    
    def process_impedance_config(self, year:int) -> dict:
        """
        Process the impedance configuration (initial setup + lulc & osm stressors)

        Args:
            year (int): The year to use for the impedance dataset.

        Returns:
            impedance_stressors (dict): dictionary for stressors, mapping stressor raster path to YAML alias
        """
        # initialize the dictionary for stressors, which contains mapping stressor raster path to YAML alias
        impedance_stressors = {} 

        icp = ImpedanceConfigProcessor(year=year, params_placeholder=self.params_placeholder, config=self.config, config_impedance=self.config_impedance, verbose=self.verbose)
        icp.setup_config_impedance()
        impedance_stressors, self.config_impedance = icp.process_stressors(self.current_dir, self.stressor_dir)
        # save the updated configuration file
        save_yaml(self.config_impedance, self.config_impedance_path)

        return impedance_stressors
    

    def calculate_impedance(self, impedance_stressors:dict, impedance_ds:gdal.Dataset, impedance_max:float) -> str:
        """
        Calculate the impedance for the stressors and generate the maximum result raster.

        Args:
            impedance_stressors (dict): The dictionary of stressors, mapping stressor raster path to YAML alias.
            impedance_ds (gdal.Dataset): The impedance raster dataset.
            impedance_max (float): The maximum value of the impedance dataset.
        
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
                config_impedance=self.config_impedance,
                yaml_stressor=yaml_stressor,
                stressor_raster=stressor_raster,
                driver=driver,
                mem_driver=mem_driver,
                impedance_ds=impedance_ds,
                impedance_max=impedance_max,
                verbose=self.verbose
                )
            if impedance_processor.ds is None:
                print(f"Failed to open {stressor_raster}, skipping...")
                continue
            else:
                impedance_processor.handle_no_data()
                proximity_data = impedance_processor.compute_proximity()
                max_result = impedance_processor.calculate_edge_effect(proximity_data)
                # print(f"Maximum result: {max_result}") # debug
        
        # Once all stressors have been processed, update the impedance dataset with decay
        max_result_tif = impedance_processor.update_impedance_with_decay()
        return max_result_tif
    
if __name__ == "__main__":
    stressor_yaml_path = os.path.join('config', 'stressors.yaml')

    if not os.path.exists(stressor_yaml_path):
        raise FileNotFoundError("The stressors.yaml file is not found. Please add the file to the config directory.")
    
    iw = ImpedanceWrapper( 
        types = None,
        decline_type = 'exp_decline', # 'exp_decline' or 'prop_decline'
        lambda_decay = 500,
        k_value = 500,
        config_path = 'config/config.yaml',
        config_impedance_path = 'config/config_impedance.yaml',
        verbose = True
    )

    for year in iw.years:
        print(f"Processing year: {year}")
        # 1. Process the impedance configuration (initial setup + lulc & osm stressors)
        # e.g. impedance_stressors = {'primary': '/data/data/output/roads_primary_2018.tif'}
        impedance_stressors = iw.process_impedance_config(year)

    # 2. Prompt user to update the configuration file
    print("Please check/update the configuration file for impedance dataset (config_impedance.yaml):")

    # 2.1. Or validate after manual update 
    is_valid = iw.validate_impedance_config(impedance_stressors)
    if not is_valid:
        raise ValueError("The configuration file is not valid. Please update the configuration file.")
    
    for year in iw.years:
        # 3.  Get the maximum value of the impedance raster dataset
        impedance_ds, impedance_max = iw.get_impedance_max_value(year)

        #3.0 Calculate impedance
        max_result_tif = iw.calculate_impedance(impedance_stressors,impedance_ds,impedance_max)

    # # delete temporary impedance stressors.yaml
    # os.remove(stressor_yaml_path)
    # print("Temporary file with OSM stressors has been deleted")
